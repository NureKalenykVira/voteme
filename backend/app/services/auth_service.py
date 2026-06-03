import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.voter_list_repository import VoterListRepository
from app.schemas.auth import LoginRequest, RegisterRequest, UpdateProfileRequest
from app.services.email_service import EmailService


logger = logging.getLogger(__name__)

_email_service = EmailService()


class AuthService:
    def __init__(self) -> None:
        self._users = UserRepository()
        self._audit = AuditRepository()
        self._voter_lists = VoterListRepository()
        self._settings = SystemSettingsRepository()

    async def _resolve_session_timeout(self, session: AsyncSession) -> int | None:
        raw = await self._settings.get_one(session, "session_timeout_minutes")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    async def register(
        self, session: AsyncSession, data: RegisterRequest
    ) -> User:
        existing = await self._users.get_by_email(session, data.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        hashed = hash_password(data.password)
        confirmation_token = secrets.token_urlsafe(32)

        user = await self._users.create(
            session,
            email=data.email,
            hashed_password=hashed,
            confirmation_token=confirmation_token,
            full_name=data.full_name,
        )
        await self._audit.create_entry(session, "USER_REGISTERED", actor_id=user.id, data={"email": user.email})
        await self._voter_lists.link_user_by_email(session, user.email, user.id)
        await session.commit()
        await session.refresh(user)

        try:
            await _email_service.send_confirmation_email(user.email, confirmation_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send confirmation email",
            )
        return user

    async def login(
        self, session: AsyncSession, data: LoginRequest
    ) -> str:
        user = await self._users.get_by_email(session, data.email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not user.is_confirmed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not confirmed",
            )

        expire_minutes = await self._resolve_session_timeout(session)
        token = create_access_token(
            sub=str(user.id), role=user.role, expire_minutes=expire_minutes
        )
        await self._audit.create_entry(session, "USER_LOGIN", actor_id=user.id)
        await self._voter_lists.link_user_by_email(session, user.email, user.id)
        await session.commit()
        return token

    async def confirm_email(
        self, session: AsyncSession, token: str
    ) -> User:
        user = await self._users.get_by_confirmation_token(session, token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid confirmation token",
            )

        await self._users.mark_confirmed(session, user)
        await self._audit.create_entry(session, "USER_CONFIRMED", actor_id=user.id)
        await self._voter_lists.link_user_by_email(session, user.email.lower(), user.id)
        await session.commit()
        await session.refresh(user)
        return user

    async def update_profile(
        self, session: AsyncSession, user: User, data: UpdateProfileRequest
    ) -> User:
        updated_fields: list[str] = []
        if data.full_name is not None and data.full_name != user.full_name:
            user = await self._users.update(session, user, full_name=data.full_name)
            updated_fields.append("full_name")
        if updated_fields:
            await self._audit.create_entry(
                session,
                "USER_PROFILE_UPDATED",
                actor_id=user.id,
                data={"updated_fields": updated_fields},
            )
        await session.commit()
        await session.refresh(user)
        return user

    async def delete_account(
        self, session: AsyncSession, user: User
    ) -> None:
        now = datetime.now(timezone.utc)
        # Write audit BEFORE soft delete so actor_id FK is still resolvable
        await self._audit.create_entry(
            session,
            "USER_DELETED",
            actor_id=user.id,
            data={"email": user.email},
        )
        # Soft delete + anonymize PII — format preserves user_id and timestamp for traceability
        ts = int(now.timestamp())
        anon_email = f"deleted_{user.id}_{ts}@deleted.local"
        await self._users.update(
            session,
            user,
            is_deleted=True,
            deleted_at=datetime.now(timezone.utc),
            email=anon_email,
            full_name=None,
            confirmation_token=None,
        )
        await session.commit()

    async def request_password_reset(
        self, session: AsyncSession, email: str
    ) -> None:
        """Always returns without error regardless of whether email exists (prevents user enumeration)."""
        user = await self._users.get_by_email(session, email)
        if user is None or not user.is_confirmed:
            return

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await self._users.update(
            session,
            user,
            password_reset_token=token,
            password_reset_token_expires_at=expires_at,
        )
        await session.commit()

        try:
            await _email_service.send_password_reset_email(user.email, token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reset email",
            )

    async def reset_password(
        self, session: AsyncSession, token: str, new_password: str
    ) -> None:
        user = await self._users.get_by_reset_token(session, token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )
        if (
            user.password_reset_token_expires_at is None
            or datetime.now(timezone.utc) > user.password_reset_token_expires_at
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )

        hashed = hash_password(new_password)
        await self._users.update(
            session,
            user,
            hashed_password=hashed,
            password_reset_token=None,
            password_reset_token_expires_at=None,
        )
        await self._audit.create_entry(session, "USER_PASSWORD_RESET", actor_id=user.id)
        await session.commit()

    async def become_organizer(
        self, session: AsyncSession, user: User
    ) -> tuple[str, User]:
        if not user.is_confirmed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email confirmation required to become an organizer",
            )
        if user.role != Role.voter:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role is already organizer or higher",
            )

        previous_role = user.role.value
        await self._users.update(session, user, role=Role.organizer)
        await self._audit.create_entry(
            session,
            "USER_BECAME_ORGANIZER",
            actor_id=user.id,
            data={"previous_role": previous_role},
        )
        await session.commit()
        await session.refresh(user)

        expire_minutes = await self._resolve_session_timeout(session)
        new_token = create_access_token(
            sub=str(user.id), role=user.role, expire_minutes=expire_minutes
        )
        return new_token, user
