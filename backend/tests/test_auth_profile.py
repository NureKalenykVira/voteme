import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(
    db_session: AsyncSession,
    email: str,
    role: Role = Role.voter,
    *,
    is_confirmed: bool = True,
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password("Password123"),
        full_name="Test User",
        role=role,
        is_confirmed=is_confirmed,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(sub=str(user.id), role=user.role)
    return {"Authorization": f"Bearer {token}"}


_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f1f0000000049454e44ae42"
    "6082"
)


class TestUpdateProfile:
    async def test_update_full_name_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "prof_upd1@example.com")
        response = await client.patch(
            "/auth/me",
            headers=_auth(user),
            json={"full_name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "New Name"

    async def test_update_persists_in_db(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "prof_upd2@example.com")
        uid = user.id
        await client.patch(
            "/auth/me",
            headers=_auth(user),
            json={"full_name": "Persisted"},
        )
        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.id == uid))
        refreshed = result.scalar_one()
        assert refreshed.full_name == "Persisted"

    async def test_update_without_token_returns_401(self, client: AsyncClient):
        response = await client.patch("/auth/me", json={"full_name": "X"})
        assert response.status_code == 401


class TestDeleteAccount:
    async def test_delete_returns_204(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "del_acc1@example.com")
        response = await client.delete("/auth/me", headers=_auth(user))
        assert response.status_code == 204

    async def test_delete_soft_deletes_and_anonymizes(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "del_acc2@example.com")
        uid = user.id
        await client.delete("/auth/me", headers=_auth(user))

        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.id == uid))
        refreshed = result.scalar_one()
        assert refreshed.is_deleted is True
        assert refreshed.email != "del_acc2@example.com"
        assert refreshed.email.endswith("@deleted.local")
        assert refreshed.full_name is None

    async def test_delete_without_token_returns_401(self, client: AsyncClient):
        response = await client.delete("/auth/me")
        assert response.status_code == 401


class TestForgotPassword:
    async def test_forgot_password_unknown_email_returns_200(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/forgot-password",
            json={"email": "ghost@example.com"},
        )
        assert response.status_code == 200

    async def test_forgot_password_known_email_sets_token(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.auth_service._email_service.send_password_reset_email",
            AsyncMock(),
        )
        user = await _make_user(db_session, "forgot1@example.com")
        uid = user.id
        response = await client.post(
            "/auth/forgot-password",
            json={"email": "forgot1@example.com"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.id == uid))
        refreshed = result.scalar_one()
        assert refreshed.password_reset_token is not None
        assert refreshed.password_reset_token_expires_at is not None

    async def test_forgot_password_unconfirmed_user_no_token(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.auth_service._email_service.send_password_reset_email",
            AsyncMock(),
        )
        user = await _make_user(
            db_session, "forgot_unconf@example.com", is_confirmed=False
        )
        uid = user.id
        response = await client.post(
            "/auth/forgot-password",
            json={"email": "forgot_unconf@example.com"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.id == uid))
        refreshed = result.scalar_one()
        assert refreshed.password_reset_token is None


class TestResetPassword:
    async def _set_reset_token(
        self,
        db_session: AsyncSession,
        user: User,
        token: str,
        *,
        expires_in: timedelta = timedelta(hours=1),
    ) -> None:
        user.password_reset_token = token
        user.password_reset_token_expires_at = (
            datetime.now(timezone.utc) + expires_in
        )
        await db_session.commit()

    async def test_reset_password_success_updates_hash(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "reset1@example.com")
        await self._set_reset_token(db_session, user, "valid-reset-token-1")
        uid = user.id

        response = await client.post(
            "/auth/reset-password",
            json={"token": "valid-reset-token-1", "new_password": "NewPass123"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.id == uid))
        refreshed = result.scalar_one()
        assert verify_password("NewPass123", refreshed.hashed_password)
        assert refreshed.password_reset_token is None

    async def test_reset_password_invalid_token_returns_400(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/reset-password",
            json={"token": "nope", "new_password": "NewPass123"},
        )
        assert response.status_code == 400

    async def test_reset_password_expired_token_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "reset_exp@example.com")
        await self._set_reset_token(
            db_session, user, "expired-token-1", expires_in=timedelta(hours=-1)
        )
        response = await client.post(
            "/auth/reset-password",
            json={"token": "expired-token-1", "new_password": "NewPass123"},
        )
        assert response.status_code == 400

    async def test_reset_password_weak_password_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "reset_weak@example.com")
        await self._set_reset_token(db_session, user, "weak-pass-token")
        response = await client.post(
            "/auth/reset-password",
            json={"token": "weak-pass-token", "new_password": "short"},
        )
        assert response.status_code == 422


class TestUploadAvatar:
    async def test_upload_png_returns_200_and_avatar_url(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "avatar1@example.com")
        response = await client.post(
            "/auth/me/avatar",
            headers=_auth(user),
            files={"file": ("a.png", BytesIO(_PNG_BYTES), "image/png")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["avatar_url"] is not None
        assert str(user.id) in body["avatar_url"]

    async def test_upload_invalid_type_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await _make_user(db_session, "avatar2@example.com")
        response = await client.post(
            "/auth/me/avatar",
            headers=_auth(user),
            files={"file": ("a.txt", BytesIO(b"not an image"), "text/plain")},
        )
        assert response.status_code == 400

    async def test_upload_without_token_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/auth/me/avatar",
            files={"file": ("a.png", BytesIO(_PNG_BYTES), "image/png")},
        )
        assert response.status_code == 401
