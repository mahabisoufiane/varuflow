"""Announcements router — broadcast management messages to staff.

GET  /api/announcements            — list published announcements for current user
POST /api/announcements            — create announcement (manager/admin)
PATCH /api/announcements/{id}      — update (author or admin)
DELETE /api/announcements/{id}     — delete (admin)
POST /api/announcements/{id}/read  — mark as read (by current user)
POST /api/announcements/{id}/acknowledge — mark as acknowledged
POST /api/announcements/{id}/react — add emoji reaction
GET  /api/announcements/{id}/reads — read receipt list (manager)
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.announcements import Announcement, AnnouncementRead
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["announcements"], dependencies=[Depends(require_module("crm"))])

ALLOWED_EMOJIS = {"👍", "❤️", "🎉", "👀", "✅", "🙏"}


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    category: str = "operational"
    target_role: str | None = None
    is_pinned: bool = False
    acknowledgement_required: bool = False
    published_at: str | None = None
    expires_at: str | None = None


class AnnouncementPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    category: str | None = None
    target_role: str | None = None
    is_pinned: bool | None = None
    acknowledgement_required: bool | None = None
    expires_at: str | None = None


class EmojiReact(BaseModel):
    emoji: str


def _ann_dict(a: Announcement, staff_read_map: dict | None = None) -> dict:
    staff_id_key = str(a.id)
    read_info = staff_read_map.get(str(a.id)) if staff_read_map else None
    return {
        "id": str(a.id),
        "title": a.title,
        "body": a.body,
        "author_id": str(a.author_id) if a.author_id else None,
        "category": a.category,
        "target_role": a.target_role,
        "is_pinned": a.is_pinned,
        "acknowledgement_required": a.acknowledgement_required,
        "emoji_reactions": a.emoji_reactions or {},
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "created_at": a.created_at.isoformat(),
        "read_at": read_info["read_at"] if read_info else None,
        "acknowledged_at": read_info["acknowledged_at"] if read_info else None,
        "read_count": len(a.reads) if a.reads else 0,
    }


@router.get("/api/announcements")
async def list_announcements(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        staff_id = member.get("staff_id")
        now = datetime.now(timezone.utc)

        q = select(Announcement).where(Announcement.org_id == org_id)
        # Non-admin: only see published, non-expired, matching role
        if role not in ("OWNER", "ADMIN"):
            q = q.where(
                and_(
                    Announcement.published_at.isnot(None),
                    Announcement.published_at <= now,
                    (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now),
                    (Announcement.target_role.is_(None)) | (Announcement.target_role == role),
                )
            )
        q = q.order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc().nullslast(), Announcement.created_at.desc())
        rows = (await db.execute(q)).scalars().all()

        # Build read map for current user
        read_map: dict = {}
        if staff_id:
            ann_ids = [r.id for r in rows]
            read_rows = (await db.execute(
                select(AnnouncementRead).where(
                    AnnouncementRead.announcement_id.in_(ann_ids),
                    AnnouncementRead.staff_id == uuid.UUID(str(staff_id)),
                )
            )).scalars().all()
            for rr in read_rows:
                read_map[str(rr.announcement_id)] = {
                    "read_at": rr.read_at.isoformat(),
                    "acknowledged_at": rr.acknowledged_at.isoformat() if rr.acknowledged_at else None,
                }
        for a in rows:
            await db.refresh(a, ["reads"])
        return [_ann_dict(a, read_map) for a in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_announcements failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/announcements", status_code=201)
async def create_announcement(body: AnnouncementCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can post announcements")
        a = Announcement(
            org_id=org_id,
            title=body.title,
            body=body.body,
            author_id=member.get("staff_id"),
            category=body.category,
            target_role=body.target_role,
            is_pinned=body.is_pinned,
            acknowledgement_required=body.acknowledgement_required,
            published_at=datetime.fromisoformat(body.published_at) if body.published_at else datetime.now(timezone.utc),
            expires_at=datetime.fromisoformat(body.expires_at) if body.expires_at else None,
        )
        db.add(a)
        await db.commit()
        await db.refresh(a)
        return _ann_dict(a)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_announcement failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/announcements/{ann_id}")
async def update_announcement(ann_id: str, body: AnnouncementPatch, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can edit announcements")
        a = (await db.execute(select(Announcement).where(Announcement.id == uuid.UUID(ann_id), Announcement.org_id == org_id))).scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            if field == "expires_at":
                setattr(a, field, datetime.fromisoformat(val) if val else None)
            else:
                setattr(a, field, val)
        a.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return _ann_dict(a)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_announcement failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/announcements/{ann_id}", status_code=204)
async def delete_announcement(ann_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can delete announcements")
        a = (await db.execute(select(Announcement).where(Announcement.id == uuid.UUID(ann_id), Announcement.org_id == org_id))).scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Not found")
        await db.delete(a)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_announcement failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/announcements/{ann_id}/read")
async def mark_read(ann_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        staff_id = member.get("staff_id")
        if not staff_id:
            return {"ok": True}
        a = (await db.execute(select(Announcement).where(Announcement.id == uuid.UUID(ann_id), Announcement.org_id == org_id))).scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Not found")
        existing = (await db.execute(
            select(AnnouncementRead).where(AnnouncementRead.announcement_id == a.id, AnnouncementRead.staff_id == uuid.UUID(str(staff_id)))
        )).scalar_one_or_none()
        if not existing:
            db.add(AnnouncementRead(announcement_id=a.id, staff_id=uuid.UUID(str(staff_id))))
            await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_read failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/announcements/{ann_id}/acknowledge")
async def acknowledge(ann_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        staff_id = member.get("staff_id")
        if not staff_id:
            return {"ok": True}
        a = (await db.execute(select(Announcement).where(Announcement.id == uuid.UUID(ann_id), Announcement.org_id == org_id))).scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Not found")
        now = datetime.now(timezone.utc)
        existing = (await db.execute(
            select(AnnouncementRead).where(AnnouncementRead.announcement_id == a.id, AnnouncementRead.staff_id == uuid.UUID(str(staff_id)))
        )).scalar_one_or_none()
        if existing:
            existing.acknowledged_at = now
        else:
            db.add(AnnouncementRead(announcement_id=a.id, staff_id=uuid.UUID(str(staff_id)), read_at=now, acknowledged_at=now))
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"acknowledge failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/announcements/{ann_id}/react")
async def react(ann_id: str, body: EmojiReact, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        if body.emoji not in ALLOWED_EMOJIS:
            raise HTTPException(status_code=422, detail="Emoji not allowed")
        org_id = member["org_id"]
        a = (await db.execute(select(Announcement).where(Announcement.id == uuid.UUID(ann_id), Announcement.org_id == org_id))).scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Not found")
        reactions = dict(a.emoji_reactions or {})
        reactions[body.emoji] = reactions.get(body.emoji, 0) + 1
        a.emoji_reactions = reactions
        a.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"emoji_reactions": a.emoji_reactions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"react failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/announcements/{ann_id}/reads")
async def read_receipt(ann_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Manager: see who has read/acknowledged a specific announcement."""
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Managers only")
        a = (await db.execute(select(Announcement).where(Announcement.id == uuid.UUID(ann_id), Announcement.org_id == org_id))).scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Not found")
        rows = (await db.execute(select(AnnouncementRead).where(AnnouncementRead.announcement_id == a.id))).scalars().all()
        return [{"staff_id": str(r.staff_id), "read_at": r.read_at.isoformat(), "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None} for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"read_receipt failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
