"""Push notification integration tests (v25).

Covers:
  * POST /api/notifications/register is an UPSERT.
  * POST /api/notifications/unregister removes the row.
  * GET/PUT /api/notifications/preferences round-trips.
  * ``send_expo_push`` posts the correct Expo payload shape and
    cleans up tokens flagged ``DeviceNotRegistered``.

Requires a live PostgreSQL — skipped automatically via the shared
``db_session`` fixture when Postgres is unreachable.
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.features.notifications.models import DeviceToken
from app.services import push as push_service



async def test_register_upserts_device_token(db_session, two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        r1 = await client.post(
            "/api/notifications/register",
            json={"device_token": "ExponentPushToken[test-abc]", "platform": "ios"},
        )
        assert r1.status_code == 201
        # Re-registering the same token must NOT create a duplicate row.
        r2 = await client.post(
            "/api/notifications/register",
            json={"device_token": "ExponentPushToken[test-abc]", "platform": "android"},
        )
        assert r2.status_code == 201

    rows = (
        await db_session.execute(
            select(DeviceToken).where(DeviceToken.token == "ExponentPushToken[test-abc]")
        )
    ).scalars().all()
    assert len(rows) == 1
    # Platform must reflect the most recent registration.
    assert rows[0].platform == "android"
    assert rows[0].org_id == member.org_id


async def test_unregister_deletes_row(db_session, two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    db_session.add(DeviceToken(
        id=uuid.uuid4(),
        org_id=member.org_id,
        user_id=member.user_id,
        token="ExponentPushToken[del-me]",
        platform="ios",
    ))
    await db_session.commit()

    async with client_factory(member) as client:
        r = await client.post(
            "/api/notifications/unregister",
            json={"device_token": "ExponentPushToken[del-me]"},
        )
        assert r.status_code == 204

    rows = (
        await db_session.execute(
            select(DeviceToken).where(DeviceToken.token == "ExponentPushToken[del-me]")
        )
    ).scalars().all()
    assert rows == []


async def test_preferences_roundtrip(two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        r1 = await client.get("/api/notifications/preferences")
        assert r1.status_code == 200
        # Defaults from migration v25 are all TRUE.
        assert r1.json() == {
            "push_stockout_enabled": True,
            "push_overdue_enabled": True,
            "push_portal_order_enabled": True,
        }

        r2 = await client.put(
            "/api/notifications/preferences",
            json={"push_stockout_enabled": False},
        )
        assert r2.status_code == 200
        assert r2.json()["push_stockout_enabled"] is False
        # Untouched preferences remain TRUE.
        assert r2.json()["push_overdue_enabled"] is True


async def test_send_expo_push_payload_shape(monkeypatch, db_session):
    """send_expo_push posts exactly what Expo expects and swallows
    errors. We intercept via httpx.MockTransport."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"status": "ok", "id": f"ticket-{i}"} for i in range(len(captured["body"]))]},
        )

    transport = httpx.MockTransport(handler)

    # Swap httpx.AsyncClient so the service uses our transport.
    real_client = httpx.AsyncClient

    class _PatchedClient(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(push_service.httpx, "AsyncClient", _PatchedClient)

    result = await push_service.send_expo_push(
        ["ExponentPushToken[a]", "ExponentPushToken[b]"],
        title="Hello",
        body="World",
        data={"type": "stockout", "product_id": "abc"},
        db=db_session,
    )

    assert captured["url"].startswith("https://exp.host/--/api/v2/push/send") or "exp.host" in captured["url"]
    assert isinstance(captured["body"], list)
    assert len(captured["body"]) == 2
    first = captured["body"][0]
    assert first["to"] == "ExponentPushToken[a]"
    assert first["title"] == "Hello"
    assert first["body"] == "World"
    assert first["data"]["type"] == "stockout"
    assert first["sound"] == "default"
    assert first["priority"] == "high"
    assert result["sent"] == 2
    assert result["errors"] == []


async def test_send_expo_push_cleans_up_dead_tokens(monkeypatch, db_session, two_orgs):
    """When Expo reports DeviceNotRegistered, the DeviceToken row is deleted."""
    member = two_orgs["a"]["member"]
    db_session.add(DeviceToken(
        id=uuid.uuid4(),
        org_id=member.org_id,
        user_id=member.user_id,
        token="ExponentPushToken[dead]",
        platform="ios",
    ))
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {
                "status": "error",
                "message": "gone",
                "details": {"error": "DeviceNotRegistered"},
            }
        ]})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    class _PatchedClient(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(push_service.httpx, "AsyncClient", _PatchedClient)

    result = await push_service.send_expo_push(
        ["ExponentPushToken[dead]"],
        title="x", body="y",
        db=db_session,
    )
    assert result["errors"] == ["ExponentPushToken[dead]"]

    remaining = (
        await db_session.execute(
            select(DeviceToken).where(DeviceToken.token == "ExponentPushToken[dead]")
        )
    ).scalars().all()
    assert remaining == []
