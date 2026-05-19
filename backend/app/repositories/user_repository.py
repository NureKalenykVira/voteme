from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    async def get_by_email(
        self, session: AsyncSession, email: str
    ) -> Optional[User]:
        normalized = email.lower()
        result = await session.execute(
            select(User).where(User.email == normalized)
        )
        return result.scalar_one_or_none()

    async def get_by_confirmation_token(
        self, session: AsyncSession, token: str
    ) -> Optional[User]:
        result = await session.execute(
            select(User).where(User.confirmation_token == token)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        email: str,
        hashed_password: str,
        confirmation_token: str,
        full_name: Optional[str] = None,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            confirmation_token=confirmation_token,
            full_name=full_name,
        )
        session.add(user)
        await session.flush()
        return user

    async def mark_confirmed(
        self, session: AsyncSession, user: User
    ) -> User:
        user.is_confirmed = True
        user.confirmation_token = None
        await session.flush()
        return user
