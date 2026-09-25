import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 400
    assert "Invalid email or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_invalid_data(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"email": "bademail", "password": "123"}
    )
    # Pydantic validation should fail
    assert response.status_code == 422
