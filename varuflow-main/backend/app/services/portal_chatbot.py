"""Portal chat bot — automated first-line replies to portal customers.

Pipeline (run as a FastAPI background task after each customer message):
  1. Bot is OFF unless a ChatbotConfig row exists with is_enabled=True.
     (The GET /api/chatbot/config endpoint defaults to enabled-looking
     values when no row exists — the bot must NOT inherit that default:
     replying to customers is an explicit opt-in.)
  2. Staff takeover: if a staff message exists in the thread within the
     last HUMAN_ACTIVE_WINDOW, the bot stays silent — a human owns it.
  3. KB match: keyword-scored lookup over the org's published KbArticles.
  4. LLM fallback: only when OPENAI_API_KEY is set; grounded strictly on
     the top KB articles + org display name. Customers must never see
     business internals, so this deliberately does NOT use
     services/ai_context.build_ai_context (revenue, stock, invoices).
  5. Fallback + escalation: polite handoff message, escalated_at stamped
     on the ChatbotConversation (dedupe), handoff email sent best-effort.

Replies are inserted as PortalChatMessage(sender_type="bot") so they show
up in the existing customer /portal/chat stream and the staff
/portal-admin/chat view without any new read path. Bot messages never set
read_at, so the customer's own messages still count as unread for staff.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.database import async_session, scoped_select
from app.features.ai.model_chatbot import ChatbotConfig, ChatbotConversation
from app.features.ai.model_knowledge_base import KbArticle
from app.features.portal.models import PortalChatMessage
from app.services.email import send_chat_handoff_email

logger = logging.getLogger(__name__)

# A staff reply younger than this means a human owns the thread.
HUMAN_ACTIVE_WINDOW = timedelta(minutes=30)

# The LLM is instructed to output exactly this when the KB can't answer.
_ESCALATE_SENTINEL = "ESCALATE"

FALLBACK_REPLY = (
    "I couldn't find an answer to that in our help articles. "
    "I've notified the team — a real person will follow up here shortly."
)

# Tiny bilingual stopword set — enough to stop "how do I ..." / "hur gör
# jag ..." from matching every article. Not linguistics, just noise control.
_STOPWORDS = frozenset(
    "the and for with that this from your our you can how what when where "
    "will would could does have has are was were not but all any out get "
    "och att det som för med den min mitt mina vad hur när var kan ska "
    "inte jag har hej hello tack thanks please".split()
)


def _tokenize(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-zåäöA-ZÅÄÖ0-9]{3,}", text.lower())
        if t not in _STOPWORDS
    }


@dataclass
class ScoredArticle:
    article_id: uuid.UUID
    title: str
    body: str
    title_hits: int
    body_hits: int

    @property
    def score(self) -> int:
        return 3 * self.title_hits + self.body_hits

    @property
    def confident(self) -> bool:
        # Confident = the customer's words clearly point at this article:
        # two distinct tokens in the title, or one title hit backed by
        # at least two body hits.
        return self.title_hits >= 2 or (self.title_hits >= 1 and self.body_hits >= 2)


def score_kb_articles(
    message: str, articles: list[tuple[uuid.UUID, str, str]]
) -> list[ScoredArticle]:
    """Rank KB articles by distinct-token overlap with the message.

    Pure function (unit-testable). Beats the naive ``ILIKE '%message%'``
    (which only matches when the whole sentence appears verbatim) without
    any new infrastructure.
    """
    tokens = _tokenize(message)
    if not tokens:
        return []
    scored: list[ScoredArticle] = []
    for article_id, title, body in articles:
        title_tokens = _tokenize(title or "")
        body_tokens = _tokenize(body or "")
        s = ScoredArticle(
            article_id=article_id,
            title=title or "",
            body=body or "",
            title_hits=len(tokens & title_tokens),
            body_hits=len(tokens & body_tokens),
        )
        if s.score > 0:
            scored.append(s)
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


async def generate_llm_reply(
    org_name: str, message: str, top_articles: list[ScoredArticle]
) -> str | None:
    """Grounded LLM answer, or None (no key / timeout / error / ESCALATE).

    gpt-4o-mini on purpose: this is a grounded FAQ answerer, not analysis —
    a deliberate, documented deviation from the "GPT-4 only in the
    integrations router" rule (this is the second sanctioned call site).
    """
    if not settings.OPENAI_API_KEY or not top_articles:
        return None

    kb_context = "\n\n".join(
        f"## {a.title}\n{a.body[:1500]}" for a in top_articles[:3]
    )
    system = (
        f"You are the customer support assistant for {org_name}. "
        "Answer ONLY using the knowledge base articles below. Be brief and "
        "friendly, and reply in the customer's language. If the articles do "
        f"not answer the question, reply with exactly {_ESCALATE_SENTINEL}.\n\n"
        f"{kb_context}"
    )
    try:
        import openai

        client_ai = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY, timeout=10.0, max_retries=0
        )
        resp = await client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": message[:2000]},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:  # timeout, quota, network — all mean "no answer"
        logger.warning("portal_chatbot llm fallback failed: %s", str(e)[:300])
        return None
    if not reply or _ESCALATE_SENTINEL in reply[:40]:
        return None
    return reply


async def run_bot_turn(
    org_id: uuid.UUID,
    customer_id: uuid.UUID,
    message_id: uuid.UUID,
    message_body: str,
) -> None:
    """Background task: maybe answer one customer portal message.

    Opens its own session — the request session is closed by the time
    BackgroundTasks run. Must never raise: an exception here would only
    pollute logs after the response has already been sent.
    """
    try:
        async with async_session() as db:
            await _run_bot_turn_inner(db, org_id, customer_id, message_id, message_body)
    except Exception:
        logger.exception(
            "portal_chatbot turn failed | org=%s customer=%s", org_id, customer_id
        )


async def _run_bot_turn_inner(
    db, org_id, customer_id, message_id, message_body
) -> None:
    now = datetime.now(UTC)

    # 1. Explicit opt-in only.
    config = (
        await db.execute(select(ChatbotConfig).where(ChatbotConfig.org_id == org_id))
    ).scalars().first()
    if config is None or not config.is_enabled:
        return

    # 2. Human owns the thread? Stay silent.
    last_staff_at = (
        await db.execute(
            select(PortalChatMessage.created_at)
            .where(
                PortalChatMessage.org_id == org_id,
                PortalChatMessage.customer_id == customer_id,
                PortalChatMessage.sender_type == "staff",
            )
            .order_by(PortalChatMessage.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_staff_at is not None and (now - last_staff_at) < HUMAN_ACTIVE_WINDOW:
        return

    # 3. Stale-turn guard: if the customer already sent a newer message,
    #    skip this turn — the newer task will answer once with fresh context.
    newer = (
        await db.execute(
            select(PortalChatMessage.id)
            .where(
                PortalChatMessage.org_id == org_id,
                PortalChatMessage.customer_id == customer_id,
                PortalChatMessage.sender_type == "customer",
                PortalChatMessage.id != message_id,
                PortalChatMessage.created_at
                > select(PortalChatMessage.created_at)
                .where(PortalChatMessage.id == message_id)
                .scalar_subquery(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if newer is not None:
        return

    # 4. Per-thread bot state (also makes transcripts visible on the
    #    existing /customer-service/chatbot staff screen). Take the LATEST
    #    conversation even if escalated — spawning a fresh one after each
    #    escalation would re-escalate (and re-email) on every message.
    conv = (
        await db.execute(
            select(ChatbotConversation)
            .where(
                ChatbotConversation.org_id == org_id,
                ChatbotConversation.visitor_id == customer_id,
            )
            .order_by(ChatbotConversation.created_at.desc())
        )
    ).scalars().first()
    if conv is not None and conv.escalated_at is not None and last_staff_at is not None:
        # Staff handled the escalated thread (and >HUMAN_ACTIVE_WINDOW ago,
        # or we'd have returned above) — start a fresh conversation.
        if last_staff_at.replace(tzinfo=None) > conv.escalated_at.replace(tzinfo=None):
            conv = None
    if conv is None:
        conv = ChatbotConversation(org_id=org_id, visitor_id=customer_id, messages=[])
        db.add(conv)
        await db.flush()

    # While escalated and still waiting for a human, don't repeat the
    # fallback or re-notify — only speak again if we actually have an
    # answer this time.
    escalation_pending = conv.escalated_at is not None

    transcript = list(conv.messages or [])
    replies: list[str] = []

    # 5. Welcome message on the bot's first appearance in this conversation.
    if config.welcome_message and not any(m.get("role") == "bot" for m in transcript):
        replies.append(config.welcome_message)

    # 6. Answer: KB → LLM → fallback.
    escalation_turn = False
    answer: str | None = None
    scored: list[ScoredArticle] = []
    if config.knowledge_base_enabled:
        rows = (
            await db.execute(
                scoped_select(KbArticle, org_id)
                .where(KbArticle.is_published.is_(True))
                .with_only_columns(KbArticle.id, KbArticle.title, KbArticle.body)
                .limit(200)
            )
        ).all()
        scored = score_kb_articles(
            message_body, [(r.id, r.title, r.body) for r in rows]
        )
    if scored and scored[0].confident:
        answer = scored[0].body[:1000]
    else:
        answer = await generate_llm_reply(
            await _org_name(db, org_id), message_body, scored
        )
    if answer is None and not escalation_pending:
        answer = FALLBACK_REPLY
        escalation_turn = True
    if answer is not None:
        replies.append(answer)

    # 7. Persist bot replies into the shared portal stream + transcript.
    for body in replies:
        db.add(
            PortalChatMessage(
                org_id=org_id, customer_id=customer_id, sender_type="bot", body=body
            )
        )
    transcript.append(
        {"role": "visitor", "content": message_body[:2000], "ts": now.isoformat()}
    )
    for body in replies:
        transcript.append({"role": "bot", "content": body, "ts": now.isoformat()})
    conv.messages = transcript
    # updated_at/created_at on ChatbotConversation are timestamp WITHOUT
    # time zone (unlike escalated_at) — asyncpg rejects aware datetimes.
    conv.updated_at = now.replace(tzinfo=None)

    # 8. Escalation: fallback turn, or the customer has gone threshold
    #    bot-answered turns without a human stepping in.
    visitor_turns = sum(1 for m in transcript if m.get("role") == "visitor")
    threshold = max(config.escalation_threshold or 3, 1)
    if conv.escalated_at is None and (escalation_turn or visitor_turns >= threshold):
        conv.escalated_at = now
        if config.handoff_email:
            try:
                await send_chat_handoff_email(
                    to_email=config.handoff_email,
                    org_name=await _org_name(db, org_id),
                    customer_name=await _customer_name(db, org_id, customer_id),
                    recent_messages=transcript[-6:],
                )
            except Exception:
                logger.exception("portal_chatbot handoff email failed | org=%s", org_id)

    await db.commit()


async def _org_name(db, org_id: uuid.UUID) -> str:
    from app.features.auth.organization import Organization

    org = await db.get(Organization, org_id)
    return org.name if org else "Varuflow"


async def _customer_name(db, org_id: uuid.UUID, customer_id: uuid.UUID) -> str:
    from app.features.invoicing.models import Customer

    row = (
        await db.execute(
            scoped_select(Customer, org_id).where(Customer.id == customer_id)
        )
    ).scalars().first()
    return row.company_name if row else "Customer"
