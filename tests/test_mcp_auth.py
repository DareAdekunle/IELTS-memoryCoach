"""/mcp-server exposes tools that take any learner_id, so it must be admin-token only."""
import asyncio

import pytest

from api.main import _RequireBearerToken


def test_rejects_missing_token(api_client):
    assert api_client.post("/mcp-server/mcp/", json={}).status_code == 401


def test_rejects_wrong_token(api_client):
    response = api_client.post("/mcp-server/mcp/", json={}, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def _status(token_configured, header):
    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request"}

    headers = [(b"authorization", header)] if header is not None else []
    asyncio.run(_RequireBearerToken(inner, token_configured)({"type": "http", "headers": headers}, receive, send))
    return sent[0]["status"]


def test_correct_token_is_let_through():
    assert _status("s3cret", b"Bearer s3cret") == 200


@pytest.mark.parametrize("header", [None, b"", b"Bearer ", b"Bearer None"])
def test_unset_token_rejects_everything(header):
    assert _status(None, header) == 401
