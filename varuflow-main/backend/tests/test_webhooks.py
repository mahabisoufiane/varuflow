"""Feature 22 — Outbound webhooks: HMAC signing + retry-on-500.

Two scenarios covered:

* ``test_dispatcher_signs_and_retries_on_500`` — dispatch one event to a
  mocked HTTP endpoint that returns 500; assert the delivery row is
  written with status_code=500, attempt_count=1 and ``next_retry_at``
  set 5 minutes ahead per ``RETRY_DELAYS[0]``. The X-Varuflow-Signature
  header must equal HMAC-SHA256(sha256(secret), body).

* ``test_retry_pending_promotes_attempt_count`` — second sweep against
  the same row bumps attempt_count to 2 and pushes ``next_retry_at`` to
  ``RETRY_DELAYS[1]`` (30 min).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.integrations.webhook import WebhookDelivery, WebhookEndpoint
from app.services import webhook_dispatcher as wd


def _mock_transport(status_code: int):
    """Return an httpx MockTransport that always responds with the given
    status code and captures the inbound request for inspection."""
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(status_code, text="oops")

    return httpx.MockTransport(handler), captured


@pytest_asyncio.fixture
async def endpoint(db_session: AsyncSession, two_orgs):
    org = two_orgs["a"]["org"]
    secret = "test-secret-do-not-reuse"
    ep = WebhookEndpoint(
        org_id=org.id,
        url="https://example.test/hook",
        secret_hash=wd.hash_secret(secret),
        events=["invoice.paid"],
        active=True,
    )
    db_session.add(ep)
    await db_session.commit()
    yield {"endpoint": ep, "secret": secret, "org": org}


@pytest.mark.asyncio
async def test_dispatcher_signs_and_retries_on_500(
    db_session: AsyncSession, endpoint, monkeypatch,
):
    ep = endpoint["endpoint"]
    secret = endpoint["secret"]

    transport, captured = _mock_transport(500)

    # Patch httpx.AsyncClient so the dispatcher's ``async with
    # httpx.AsyncClient()`` opens a client wired to the mock transport.
    real_client_cls = httpx.AsyncClient

    class _Patched(real_client_cls):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(wd.httpx, "AsyncClient", _Patched)

    payload = {"invoice_id": str(uuid.uuid4()), "amount_sek": 1234.56}
    ids = await wd.enqueue_event(
        db_session,
        org_id=endpoint["org"].id,
        event_type="invoice.paid",
        payload=payload,
    )
    assert len(ids) == 1

    # The mock saw one POST with the correct body and signature.
    assert captured["method"] == "POST"
    body = captured["body"]
    expected_sig = hmac.new(
        ep.secret_hash.encode("ascii"), body, hashlib.sha256,
    ).hexdigest()
    assert captured["headers"]["x-varuflow-signature"] == expected_sig
    assert captured["headers"]["x-varuflow-event"] == "invoice.paid"
    # Body is canonical JSON of the payload.
    assert json.loads(body) == payload

    # Delivery row reflects the failed attempt + 5-minute backoff.
    row = await db_session.scalar(
        select(WebhookDelivery).where(WebhookDelivery.endpoint_id == ep.id)
    )
    await db_session.refresh(row)
    assert row.status_code == 500
    assert row.delivered_at is None
    assert row.attempt_count == 1
    assert row.next_retry_at is not None
    delta = row.next_retry_at - datetime.now(timezone.utc)
    # 5 minutes ± 30 s scheduling jitter.
    assert timedelta(minutes=4, seconds=30) <= delta <= timedelta(minutes=5, seconds=30)


@pytest.mark.asyncio
async def test_retry_pending_promotes_attempt_count(
    db_session: AsyncSession, endpoint, monkeypatch,
):
    ep = endpoint["endpoint"]
    # Pre-seed a failed delivery whose next_retry_at is already due.
    delivery = WebhookDelivery(
        endpoint_id=ep.id,
        event_type="invoice.paid",
        payload={"invoice_id": str(uuid.uuid4())},
        status_code=500,
        attempt_count=1,
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db_session.add(delivery)
    await db_session.commit()

    transport, _captured = _mock_transport(500)
    real_client_cls = httpx.AsyncClient

    class _Patched(real_client_cls):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(wd.httpx, "AsyncClient", _Patched)

    n = await wd.retry_pending(db_session)
    assert n == 1

    await db_session.refresh(delivery)
    assert delivery.attempt_count == 2
    assert delivery.delivered_at is None
    delta = delivery.next_retry_at - datetime.now(timezone.utc)
    # RETRY_DELAYS[1] = 30 minutes ± 30 s jitter.
    assert timedelta(minutes=29, seconds=30) <= delta <= timedelta(minutes=30, seconds=30)
