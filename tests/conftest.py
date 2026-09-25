import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.fixture(scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function", autouse=True)
async def clear_db():
    # Only clear collections we test, to avoid wiping real data accidentally if connected to dev.
    # In a real scenario, use a separate test database.
    pass
