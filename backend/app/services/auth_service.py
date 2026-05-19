import logging
import secrets

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.email_service import EmailService


logger = logging.getLogger(__name__)

_email_service = EmailService()


class AuthService:
    def __init__(self) -> None:
        self._users = UserRepository()
        self._audit = AuditRepository()

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

        token = create_access_token(sub=str(user.id), role=user.role)
        await self._audit.create_entry(session, "USER_LOGIN", actor_id=user.id)
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
        await session.commit()
        await session.refresh(user)
        return user
