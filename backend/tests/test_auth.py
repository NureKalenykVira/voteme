import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _register(
    client: AsyncClient, email: str, password: str = "Password123"
):
    return await client.post(
        "/auth/register", json={"email": email, "password": password}
    )


async def _confirm_user(db_session: AsyncSession, email: str) -> User:
    result = await db_session.execute(
        select(User).where(User.email == email.lower())
    )
    user = result.scalar_one()
    user.is_confirmed = True
    user.confirmation_token = None
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestRegister:
    async def test_register_success_returns_201_and_user(
        self, client: AsyncClient
    ):
        response = await _register(client, "alice@example.com")
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "alice@example.com"
        assert body["role"] == "voter"
        assert body["is_confirmed"] is False
        assert "id" in body
        assert "created_at" in body
        assert "hashed_password" not in body
        assert "confirmation_token" not in body

    async def test_register_duplicate_email_returns_409(
        self, client: AsyncClient
    ):
        await _register(client, "bob@example.com")
        response = await _register(client, "bob@example.com")
        assert response.status_code == 409
        assert response.json()["detail"] == "Email already registered"

    async def test_register_short_password_returns_422(
        self, client: AsyncClient
    ):
        response = await _register(client, "short@example.com", "Ab1")
        assert response.status_code == 422

    async def test_register_password_without_digit_returns_422(
        self, client: AsyncClient
    ):
        response = await _register(client, "nodigit@example.com", "Password")
        assert response.status_code == 422

    async def test_register_password_without_letter_returns_422(
        self, client: AsyncClient
    ):
        response = await _register(client, "noletter@example.com", "12345678")
        assert response.status_code == 422

    async def test_register_invalid_email_returns_422(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "Password123"},
        )
        assert response.status_code == 422

    async def test_register_persists_user_with_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _register(client, "carol@example.com")
        result = await db_session.execute(
            select(User).where(User.email == "carol@example.com")
        )
        user = result.scalar_one()
        assert user.hashed_password != "Password123"
        assert user.confirmation_token is not None
        assert len(user.confirmation_token) >= 32
        assert user.is_confirmed is False


class TestLogin:
    async def test_login_unconfirmed_user_returns_403(
        self, client: AsyncClient
    ):
        await _register(client, "dan@example.com")
        response = await client.post(
            "/auth/login",
            json={"email": "dan@example.com", "password": "Password123"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Email not confirmed"

    async def test_login_confirmed_user_returns_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _register(client, "eve@example.com")
        await _confirm_user(db_session, "eve@example.com")
        response = await client.post(
            "/auth/login",
            json={"email": "eve@example.com", "password": "Password123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 0

    async def test_login_wrong_password_returns_401(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _register(client, "frank@example.com")
        await _confirm_user(db_session, "frank@example.com")
        response = await client.post(
            "/auth/login",
            json={"email": "frank@example.com", "password": "WrongPass123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    async def test_login_unknown_email_returns_401(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "Password123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"


class TestConfirmEmail:
    async def test_confirm_email_success_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _register(client, "grace@example.com")
        result = await db_session.execute(
            select(User).where(User.email == "grace@example.com")
        )
        user = result.scalar_one()
        token = user.confirmation_token

        response = await client.get(
            "/auth/confirm-email", params={"token": token}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Email confirmed successfully"

        db_session.expire_all()
        result = await db_session.execute(
            select(User).where(User.email == "grace@example.com")
        )
        refreshed = result.scalar_one()
        assert refreshed.is_confirmed is True
        assert refreshed.confirmation_token is None

    async def test_confirm_email_invalid_token_returns_404(
        self, client: AsyncClient
    ):
        response = await client.get(
            "/auth/confirm-email", params={"token": "nope-not-a-real-token"}
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Invalid confirmation token"

    async def test_confirm_email_missing_token_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/auth/confirm-email")
        assert response.status_code == 422


class TestMe:
    async def test_me_with_valid_token_returns_current_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _register(client, "henry@example.com")
        await _confirm_user(db_session, "henry@example.com")
        login = await client.post(
            "/auth/login",
            json={"email": "henry@example.com", "password": "Password123"},
        )
        token = login.json()["access_token"]

        response = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "henry@example.com"
        assert body["is_confirmed"] is True
        assert body["role"] == "voter"

    async def test_me_without_token_returns_401(self, client: AsyncClient):
        response = await client.get("/auth/me")
        assert response.status_code == 401

    async def test_me_with_invalid_token_returns_401(
        self, client: AsyncClient
    ):
        response = await client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"
