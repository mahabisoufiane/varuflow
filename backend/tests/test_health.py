from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
    # 200 when DB is reachable, 503 when not — both are valid shapes
    assert response.status_code in (200, 503)
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["version"] == "0.1.0"
    assert "database" in data
