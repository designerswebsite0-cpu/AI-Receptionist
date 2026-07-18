"""Pure HTTP-layer tests for the public webchat auth boundary — no database
needed (same convention as test_auth_required.py): the missing/garbage
token check in app.webchat.deps.get_webchat_session raises before any query
runs. Confirms the opposite property from test_auth_required.py: webchat
endpoints must NOT require a Supabase Authorization header (they're
intentionally anonymous), but must still reject an absent/garbage session
token.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

_DUMMY_UUID = "00000000-0000-0000-0000-000000000000"

SESSION_SCOPED_ENDPOINTS = [
    ("GET", f"/api/v1/webchat/sessions/{_DUMMY_UUID}"),
    ("DELETE", f"/api/v1/webchat/sessions/{_DUMMY_UUID}"),
    ("POST", f"/api/v1/webchat/sessions/{_DUMMY_UUID}/messages"),
    ("GET", f"/api/v1/webchat/sessions/{_DUMMY_UUID}/messages"),
    ("POST", f"/api/v1/webchat/sessions/{_DUMMY_UUID}/handoff"),
    ("POST", f"/api/v1/webchat/sessions/{_DUMMY_UUID}/feedback"),
    ("POST", f"/api/v1/webchat/sessions/{_DUMMY_UUID}/contact"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", SESSION_SCOPED_ENDPOINTS)
async def test_session_scoped_endpoint_rejects_missing_token(method: str, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", SESSION_SCOPED_ENDPOINTS)
async def test_session_scoped_endpoint_rejects_garbage_token(method: str, path: str, db_engine):
    # db_engine is unused directly — it exists purely so this test skips
    # cleanly (like every other DB-dependent test in this suite) when no
    # database is reachable, instead of the garbage-token lookup query
    # itself raising a raw connection error.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, headers={"x-webchat-session-token": "not-a-real-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", SESSION_SCOPED_ENDPOINTS)
async def test_session_scoped_endpoint_does_not_accept_a_supabase_bearer_token_instead(
    method: str, path: str, db_engine
):
    """Confirms these endpoints use a distinct auth mechanism from the
    staff-facing API — a Supabase JWT (even a well-formed one) is not a
    substitute for a webchat session token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401
