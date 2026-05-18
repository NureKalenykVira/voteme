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
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self) -> None:
        self._users = UserRepository()

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
        )
        await session.commit()
        await session.refresh(user)

        logger.info(
            "Confirmation token for %s: %s",
            data.email,
            confirmation_token,
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

        return create_access_token(sub=str(user.id), role=user.role)

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
        await session.commit()
        await session.refresh(user)
        return user
