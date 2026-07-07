"""Tests for the portal chat bot (services/portal_chatbot.py).

Covers: KB scoring (pure), explicit opt-in, the KB-answer happy path with
welcome message, staff-takeover suppression, escalation (fallback reply +
handoff email + dedupe + needs_human flag), LLM fallback failure never
blocking message persistence, and tenant isolation of KB lookups.

BackgroundTasks run inline under ASGITransport (Starlette awaits them
before the transport returns), and run_bot_turn opens its own
``async_session`` bound to the same test database — so the pipeline is
exercised end-to-end through the real POST /api/portal/chat endpoint.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.features.ai.model_chatbot import ChatbotConfig, ChatbotConversation
from app.features.ai.model_knowledge_base import KbArticle
from app.features.auth.organization import Organization
from app.features.invoicing.models import Customer, CustomerPortalToken
from app.features.portal.models import PortalChatMessage
from app.main import app
from app.services.portal_chatbot import score_kb_articles

pytestmark = pytest.mark.asyncio


async def _postgres_ok(db):
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _login(customer: Customer, org: Organization, db) -> str:
    """Issue a magic link, exchange it, return the portal JWT."""
    raw = secrets.token_urlsafe(32)
    db.add(CustomerPortalToken(
        customer_id=customer.id,
        org_id=org.id,
        token=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    ))
    await db.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(f"/api/portal/auth/verify?token={raw}")
    assert r.status_code == 200, r.text
    return r.json()["portal_token"]


async def _send_chat(token: str, body: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/portal/chat",
            json={"body": body},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 201, r.text


async def _thread(db, org_id, customer_id) -> list[PortalChatMessage]:
    return list((await db.execute(
        select(PortalChatMessage)
        .where(
            PortalChatMessage.org_id == org_id,
            PortalChatMessage.customer_id == customer_id,
        )
        .order_by(PortalChatMessage.created_at.asc())
    )).scalars().all())


@pytest_asyncio.fixture
async def bot_fixture(db_session):
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")

    org = Organization(id=uuid.uuid4(), name="Bot Seller AB", org_number="556000-0030")
    db_session.add(org)
    await db_session.commit()

    customer = Customer(
        org_id=org.id, company_name="Bot Buyer AB",
        email="buyer@botchat.test", payment_terms_days=30,
    )
    db_session.add(customer)
    db_session.add(KbArticle(
        org_id=org.id,
        title="Leverans och frakt",
        slug="leverans-frakt",
        body="Vi levererar med DHL inom 2-3 arbetsdagar. Fri frakt över 5000 kr.",
        is_published=True,
    ))
    db_session.add(ChatbotConfig(
        org_id=org.id,
        is_enabled=True,
        welcome_message="Hej! Jag är butikens assistent.",
        escalation_threshold=5,
        knowledge_base_enabled=True,
        handoff_email="support@botseller.test",
    ))
    await db_session.commit()

    yield {"org": org, "customer": customer}

    # Bot rows reference the org via FK CASCADE; conversations use a bare
    # visitor_id so clear them explicitly before dropping the org.
    for conv in (await db_session.execute(
        select(ChatbotConversation).where(ChatbotConversation.org_id == org.id)
    )).scalars().all():
        await db_session.delete(conv)
    await db_session.delete(org)
    await db_session.commit()


# ── Scoring (pure) ─────────────────────────────────────────────────────────────

def test_scoring_title_beats_body():
    aid, bid = uuid.uuid4(), uuid.uuid4()
    scored = score_kb_articles(
        "question about delivery shipping time",
        [
            (aid, "Delivery and shipping", "We ship fast."),
            (bid, "Returns", "Our delivery partner handles shipping and returns."),
        ],
    )
    assert scored[0].article_id == aid
    assert scored[0].confident


def test_scoring_keywords_match_within_sentence():
    aid = uuid.uuid4()
    scored = score_kb_articles(
        "hur fungerar leverans och frakt till Norrland?",
        [(
            aid,
            "Leverans och frakt",
            "Vi levererar med DHL. Frakt ingår över 5000 kr.",
        )],
    )
    assert scored and scored[0].confident


def test_scoring_no_overlap_is_not_confident():
    scored = score_kb_articles(
        "kan jag byta lösenord",
        [(uuid.uuid4(), "Leverans och frakt", "Vi levererar med DHL.")],
    )
    assert not scored or not scored[0].confident


# ── Endpoint-driven pipeline ───────────────────────────────────────────────────

async def test_kb_answer_with_welcome_message(bot_fixture, db_session):
    org, customer = bot_fixture["org"], bot_fixture["customer"]
    token = await _login(customer, org, db_session)

    await _send_chat(token, "Hur lång tid tar leverans och vad kostar frakt?")

    msgs = await _thread(db_session, org.id, customer.id)
    bot_msgs = [m for m in msgs if m.sender_type == "bot"]
    assert len(bot_msgs) == 2, [m.body for m in msgs]  # welcome + answer
    assert bot_msgs[0].body == "Hej! Jag är butikens assistent."
    assert "DHL" in bot_msgs[1].body
    # Bot replies must not consume staff's unread signal
    assert all(m.read_at is None for m in msgs)


async def test_bot_is_explicit_opt_in(bot_fixture, db_session):
    org, customer = bot_fixture["org"], bot_fixture["customer"]
    config = (await db_session.execute(
        select(ChatbotConfig).where(ChatbotConfig.org_id == org.id)
    )).scalars().one()
    config.is_enabled = False
    await db_session.commit()

    token = await _login(customer, org, db_session)
    await _send_chat(token, "Hur lång tid tar leverans?")

    msgs = await _thread(db_session, org.id, customer.id)
    assert all(m.sender_type == "customer" for m in msgs)


async def test_staff_takeover_silences_bot(bot_fixture, db_session):
    org, customer = bot_fixture["org"], bot_fixture["customer"]
    db_session.add(PortalChatMessage(
        org_id=org.id, customer_id=customer.id,
        sender_type="staff", body="Hej, jag hjälper dig!",
    ))
    await db_session.commit()

    token = await _login(customer, org, db_session)
    await _send_chat(token, "Hur lång tid tar leverans och frakt?")

    msgs = await _thread(db_session, org.id, customer.id)
    assert not [m for m in msgs if m.sender_type == "bot"]


async def test_escalation_fallback_email_and_dedupe(
    bot_fixture, db_session, monkeypatch
):
    org, customer = bot_fixture["org"], bot_fixture["customer"]

    calls: list[dict] = []

    async def _fake_handoff(**kwargs):
        calls.append(kwargs)
        return True

    # Patch where it's used, not where it's defined.
    monkeypatch.setattr(
        "app.services.portal_chatbot.send_chat_handoff_email", _fake_handoff
    )

    token = await _login(customer, org, db_session)
    # No KB overlap, no OPENAI_API_KEY in tests → fallback + escalate.
    await _send_chat(token, "xylophone quantum zeppelin?")

    msgs = await _thread(db_session, org.id, customer.id)
    bot_bodies = [m.body for m in msgs if m.sender_type == "bot"]
    assert any("follow up" in b for b in bot_bodies)
    assert len(calls) == 1
    assert calls[0]["to_email"] == "support@botseller.test"

    # Second unanswerable message: escalated_at already set → no new email.
    await _send_chat(token, "another impossible zeppelin question?")
    assert len(calls) == 1

    # Staff unread list flags the thread.
    conv = (await db_session.execute(
        select(ChatbotConversation).where(
            ChatbotConversation.org_id == org.id,
            ChatbotConversation.visitor_id == customer.id,
        )
    )).scalars().first()
    assert conv is not None and conv.escalated_at is not None


async def test_llm_failure_never_blocks_message_persist(
    bot_fixture, db_session, monkeypatch
):
    org, customer = bot_fixture["org"], bot_fixture["customer"]

    async def _boom(*args, **kwargs):
        raise RuntimeError("llm exploded")

    monkeypatch.setattr("app.services.portal_chatbot.generate_llm_reply", _boom)

    token = await _login(customer, org, db_session)
    # 201 asserted inside — the customer's message must persist regardless.
    await _send_chat(token, "xylophone quantum zeppelin?")

    msgs = await _thread(db_session, org.id, customer.id)
    assert [m for m in msgs if m.sender_type == "customer"]


async def test_llm_answer_path(bot_fixture, db_session, monkeypatch):
    org, customer = bot_fixture["org"], bot_fixture["customer"]

    async def _canned(org_name, message, top_articles):
        return "Canned grounded answer."

    monkeypatch.setattr("app.services.portal_chatbot.generate_llm_reply", _canned)

    token = await _login(customer, org, db_session)
    # KB has some overlap ("frakt") but not a confident match → LLM path.
    await _send_chat(token, "frakt utomlands möjligt?")

    msgs = await _thread(db_session, org.id, customer.id)
    assert any(
        m.sender_type == "bot" and m.body == "Canned grounded answer." for m in msgs
    )


async def test_kb_lookup_is_tenant_scoped(bot_fixture, db_session):
    """Org B's KB article must never answer org A's customer."""
    org_a, customer_a = bot_fixture["org"], bot_fixture["customer"]

    org_b = Organization(id=uuid.uuid4(), name="Other AB", org_number="556000-0031")
    db_session.add(org_b)
    await db_session.commit()
    db_session.add(KbArticle(
        org_id=org_b.id,
        title="Garanti och reklamation",
        slug="garanti",
        body="SECRET-ORG-B: 5 års garanti på allt.",
        is_published=True,
    ))
    await db_session.commit()

    try:
        token = await _login(customer_a, org_a, db_session)
        await _send_chat(token, "vad gäller garanti och reklamation?")

        msgs = await _thread(db_session, org_a.id, customer_a.id)
        assert all("SECRET-ORG-B" not in m.body for m in msgs)
    finally:
        await db_session.delete(org_b)
        await db_session.commit()
