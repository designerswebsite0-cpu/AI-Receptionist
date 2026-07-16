"""Every protected endpoint requires a valid session — no role/permission
concept left to check (single-resort refactor, product_decisions.md), just
authentication. Pure HTTP-layer tests; no database needed.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/resort/settings"),
    ("GET", "/api/v1/customers"),
    ("GET", "/api/v1/conversations"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_protected_endpoint_rejects_missing_authorization(method: str, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_protected_endpoint_rejects_garbage_token(method: str, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_healthz_does_not_require_authentication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
