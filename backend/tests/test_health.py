import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestHealth:
    async def test_health_returns_200_and_ok(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_health_requires_no_auth(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
