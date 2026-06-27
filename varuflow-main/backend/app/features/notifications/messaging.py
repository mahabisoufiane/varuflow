"""Internal staff messaging router.

GET  /api/work/messages/conversations     — list DM threads + channels with unread counts
GET  /api/work/messages/dm/{staff_id}     — fetch conversation with a specific staff member
POST /api/work/messages/dm               — send a direct message
GET  /api/work/messages/channels         — list available channels
GET  /api/work/messages/channel/{slug}   — fetch channel messages
POST /api/work/messages/channel          — post to a channel
POST /api/work/messages/{id}/read        — mark a DM message read
POST /api/work/messages/channel/{slug}/read — mark all channel messages read
GET  /api/work/messages/unread           — unread counts (DM + per channel)
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.notifications.model_messaging import StaffMessage, StaffMessageRead
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/work/messages", tags=["messaging"], dependencies=[Depends(require_module("crm"))])

# Default channels every org has. In the future these could be stored in DB.
DEFAULT_CHANNELS = ["general", "ops", "sales"]


# ── Schemas ───────────────────────────────────────────────────────────────────

class DmIn(BaseModel):
    recipient_id: str
    body: str


class ChannelPostIn(BaseModel):
    slug: str
    body: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msg_out(m: StaffMessage, my_staff_id: str) -> dict:
    return {
        "id": str(m.id),
        "sender_id": str(m.sender_id) if m.sender_id else None,
        "recipient_id": str(m.recipient_id) if m.recipient_id else None,
        "channel": m.channel,
        "body": m.body,
        "read_at": m.read_at.isoformat() if m.read_at else None,
        "created_at": m.created_at.isoformat(),
        "is_mine": str(m.sender_id) == my_staff_id if m.sender_id else False,
    }


async def _require_staff_id(member: dict) -> str:
    staff_id = member.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=403, detail="No staff profile linked to this account")
    return str(staff_id)


# ── Unread counts ─────────────────────────────────────────────────────────────

@router.get("/unread")
async def get_unread_counts(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return unread DM count + per-channel unread counts."""
    try:
        org_id = member["org_id"]
        staff_id = await _require_staff_id(member)

        # Unread DMs — messages sent TO me without read_at
        dm_unread = await db.scalar(
            select(func.count()).where(
                StaffMessage.org_id == org_id,
                StaffMessage.recipient_id == uuid.UUID(staff_id),
                StaffMessage.channel.is_(None),
                StaffMessage.read_at.is_(None),
            )
        )

        # Channel unread — messages not in staff_message_reads for me
        channel_unread: dict[str, int] = {}
        for slug in DEFAULT_CHANNELS:
            read_subq = select(StaffMessageRead.message_id).where(
                StaffMessageRead.staff_id == uuid.UUID(staff_id)
            ).scalar_subquery()
            count = await db.scalar(
                select(func.count()).where(
                    StaffMessage.org_id == org_id,
                    StaffMessage.channel == slug,
                    StaffMessage.sender_id != uuid.UUID(staff_id),
                    StaffMessage.id.not_in(read_subq),
                )
            )
            channel_unread[slug] = count or 0

        return {
            "dm": dm_unread or 0,
            "channels": channel_unread,
            "total": (dm_unread or 0) + sum(channel_unread.values()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_unread_counts failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Conversations list ────────────────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns one entry per DM thread (the other party's staff_id + last message
    preview + unread count) plus one entry per channel.
    """
    try:
        org_id = member["org_id"]
        staff_id = await _require_staff_id(member)
        sid = uuid.UUID(staff_id)

        # All DM messages involving me
        rows = (await db.execute(
            select(StaffMessage)
            .where(
                StaffMessage.org_id == org_id,
                StaffMessage.channel.is_(None),
                or_(
                    StaffMessage.sender_id == sid,
                    StaffMessage.recipient_id == sid,
                ),
            )
            .order_by(StaffMessage.created_at.desc())
        )).scalars().all()

        # Group by the "other party" in the conversation
        threads: dict[str, dict] = {}
        for m in rows:
            other = str(m.recipient_id) if str(m.sender_id) == staff_id else str(m.sender_id) if m.sender_id else None
            if not other:
                continue
            if other not in threads:
                threads[other] = {
                    "type": "dm",
                    "staff_id": other,
                    "last_message": m.body[:100],
                    "last_at": m.created_at.isoformat(),
                    "unread": 0,
                }
            # Count unread (sent TO me, not yet read)
            if str(m.recipient_id) == staff_id and not m.read_at:
                threads[other]["unread"] += 1

        dm_list = sorted(threads.values(), key=lambda x: x["last_at"], reverse=True)

        # Channels — just return defaults with unread counts
        channel_list = [
            {"type": "channel", "slug": slug, "name": f"#{slug}"}
            for slug in DEFAULT_CHANNELS
        ]

        return {"dms": dm_list, "channels": channel_list}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_conversations failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Direct messages ───────────────────────────────────────────────────────────

@router.get("/dm/{other_staff_id}")
async def get_dm_thread(
    other_staff_id: str,
    limit: int = 50,
    before: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the conversation between me and another staff member."""
    try:
        org_id = member["org_id"]
        staff_id = await _require_staff_id(member)
        sid = uuid.UUID(staff_id)
        oid = uuid.UUID(other_staff_id)

        q = (
            select(StaffMessage)
            .where(
                StaffMessage.org_id == org_id,
                StaffMessage.channel.is_(None),
                or_(
                    and_(StaffMessage.sender_id == sid, StaffMessage.recipient_id == oid),
                    and_(StaffMessage.sender_id == oid, StaffMessage.recipient_id == sid),
                ),
            )
            .order_by(StaffMessage.created_at.desc())
            .limit(limit)
        )
        if before:
            q = q.where(StaffMessage.created_at < datetime.fromisoformat(before))

        messages = (await db.execute(q)).scalars().all()

        # Mark unread messages sent to me as read
        unread = [m for m in messages if str(m.recipient_id) == staff_id and not m.read_at]
        if unread:
            now = datetime.now(timezone.utc)
            for m in unread:
                m.read_at = now
            await db.commit()

        return [_msg_out(m, staff_id) for m in reversed(messages)]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_dm_thread failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/dm", status_code=201)
async def send_dm(
    body: DmIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        staff_id = await _require_staff_id(member)
        if not body.body.strip():
            raise HTTPException(status_code=422, detail="Message body cannot be empty")
        m = StaffMessage(
            org_id=org_id,
            sender_id=uuid.UUID(staff_id),
            recipient_id=uuid.UUID(body.recipient_id),
            body=body.body.strip(),
        )
        db.add(m)
        await db.commit()
        return _msg_out(m, staff_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_dm failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Channels ──────────────────────────────────────────────────────────────────

@router.get("/channels")
async def list_channels(member=Depends(get_current_member)):
    """Return available channel slugs."""
    return [{"slug": s, "name": f"#{s}"} for s in DEFAULT_CHANNELS]


@router.get("/channel/{slug}")
async def get_channel(
    slug: str,
    limit: int = 50,
    before: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        staff_id = await _require_staff_id(member)

        if slug not in DEFAULT_CHANNELS:
            raise HTTPException(status_code=404, detail="Channel not found")

        q = (
            select(StaffMessage)
            .where(StaffMessage.org_id == org_id, StaffMessage.channel == slug)
            .order_by(StaffMessage.created_at.desc())
            .limit(limit)
        )
        if before:
            q = q.where(StaffMessage.created_at < datetime.fromisoformat(before))

        messages = (await db.execute(q)).scalars().all()

        # Mark all fetched messages as read for this staff member
        sid = uuid.UUID(staff_id)
        now = datetime.now(timezone.utc)
        already_read_q = select(StaffMessageRead.message_id).where(
            StaffMessageRead.staff_id == sid,
            StaffMessageRead.message_id.in_([m.id for m in messages]),
        )
        already_read = {r for r in (await db.execute(already_read_q)).scalars().all()}
        for m in messages:
            if m.id not in already_read and str(m.sender_id) != staff_id:
                db.add(StaffMessageRead(message_id=m.id, staff_id=sid, read_at=now))
        if messages:
            await db.commit()

        return [_msg_out(m, staff_id) for m in reversed(messages)]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_channel failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/channel", status_code=201)
async def post_to_channel(
    body: ChannelPostIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        staff_id = await _require_staff_id(member)
        if body.slug not in DEFAULT_CHANNELS:
            raise HTTPException(status_code=404, detail="Channel not found")
        if not body.body.strip():
            raise HTTPException(status_code=422, detail="Message body cannot be empty")
        m = StaffMessage(
            org_id=org_id,
            sender_id=uuid.UUID(staff_id),
            channel=body.slug,
            body=body.body.strip(),
        )
        db.add(m)
        await db.commit()
        return _msg_out(m, staff_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("post_to_channel failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")
