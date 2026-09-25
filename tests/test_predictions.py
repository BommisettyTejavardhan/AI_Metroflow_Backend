import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_predict_crowd_invalid_request(client: AsyncClient):
    response = await client.post(
        "/api/predictions/predict-crowd",
        json={"station_id": "invalid_id"}
    )
    # Because date and time are missing
    assert response.status_code == 422
