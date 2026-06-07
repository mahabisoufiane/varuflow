"""Data room — folders, documents, and shareable access links.

Endpoints
─────────
GET    /api/data-room/folders                       → list top-level folders
POST   /api/data-room/folders                       → create folder
DELETE /api/data-room/folders/{id}                  → delete folder
GET    /api/data-room/folders/{id}/documents        → list documents in folder
POST   /api/data-room/folders/{id}/documents        → upload document
DELETE /api/data-room/documents/{id}                → delete document
GET    /api/data-room/shares                        → list share links
POST   /api/data-room/shares                        → create share link
DELETE /api/data-room/shares/{id}                   → revoke share
GET    /api/data-room/access/{token}                → PUBLIC access via share token
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.data_room import DataRoomDocument, DataRoomFolder, DataRoomShare
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/data-room", tags=["data-room"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _folder_out(f: DataRoomFolder, doc_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "org_id": str(f.org_id),
        "name": f.name,
        "parent_folder_id": str(f.parent_folder_id) if f.parent_folder_id else None,
        "description": f.description,
        "document_count": doc_count,
        "created_at": f.created_at.isoformat(),
    }


def _document_out(d: DataRoomDocument) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "org_id": str(d.org_id),
        "folder_id": str(d.folder_id),
        "name": d.name,
        "file_url": d.file_url,
        "file_size": d.file_size,
        "mime_type": d.mime_type,
        "uploaded_by": str(d.uploaded_by) if d.uploaded_by else None,
        "created_at": d.created_at.isoformat(),
    }


def _share_out(s: DataRoomShare) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "label": s.label,
        "token": s.token,
        "folder_ids": s.folder_ids,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "view_count": s.view_count,
        "created_by": str(s.created_by) if s.created_by else None,
        "created_at": s.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_folder_id: Optional[uuid.UUID] = None
    description: Optional[str] = None


class DocumentIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    file_url: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = Field(default=None, max_length=100)


class ShareIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    folder_ids: list[uuid.UUID]
    expires_at: Optional[datetime] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/folders")
async def list_folders(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        folders = (await db.execute(
            select(DataRoomFolder)
            .where(
                DataRoomFolder.org_id == org_id,
                DataRoomFolder.parent_folder_id.is_(None),
            )
            .order_by(DataRoomFolder.name)
        )).scalars().all()

        results = []
        for f in folders:
            count_row = await db.execute(
                select(func.count(DataRoomDocument.id)).where(DataRoomDocument.folder_id == f.id)
            )
            doc_count = int(count_row.scalar() or 0)
            results.append(_folder_out(f, doc_count))
        return results
    except Exception as e:
        log.error("list_folders failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/folders", status_code=201)
async def create_folder(
    body: FolderIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        if body.parent_folder_id:
            parent = await db.scalar(
                select(DataRoomFolder).where(
                    DataRoomFolder.id == body.parent_folder_id,
                    DataRoomFolder.org_id == org_id,
                )
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent folder not found")

        f = DataRoomFolder(
            org_id=org_id,
            name=body.name,
            parent_folder_id=body.parent_folder_id,
            description=body.description,
        )
        db.add(f)
        await db.commit()
        await db.refresh(f)
        return _folder_out(f)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_folder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        f = await db.scalar(
            select(DataRoomFolder).where(DataRoomFolder.id == folder_id, DataRoomFolder.org_id == org_id)
        )
        if not f:
            raise HTTPException(status_code=404, detail="Folder not found")
        await db.delete(f)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_folder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/folders/{folder_id}/documents")
async def list_documents(
    folder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        folder = await db.scalar(
            select(DataRoomFolder).where(DataRoomFolder.id == folder_id, DataRoomFolder.org_id == org_id)
        )
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        docs = (await db.execute(
            select(DataRoomDocument)
            .where(DataRoomDocument.folder_id == folder_id, DataRoomDocument.org_id == org_id)
            .order_by(DataRoomDocument.name)
        )).scalars().all()
        return [_document_out(d) for d in docs]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_documents failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/folders/{folder_id}/documents", status_code=201)
async def upload_document(
    folder_id: uuid.UUID,
    body: DocumentIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        folder = await db.scalar(
            select(DataRoomFolder).where(DataRoomFolder.id == folder_id, DataRoomFolder.org_id == org_id)
        )
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        d = DataRoomDocument(
            org_id=org_id,
            folder_id=folder_id,
            name=body.name,
            file_url=body.file_url,
            file_size=body.file_size,
            mime_type=body.mime_type,
            uploaded_by=user_id,
        )
        db.add(d)
        await db.commit()
        await db.refresh(d)
        return _document_out(d)
    except HTTPException:
        raise
    except Exception as e:
        log.error("upload_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        d = await db.scalar(
            select(DataRoomDocument).where(DataRoomDocument.id == document_id, DataRoomDocument.org_id == org_id)
        )
        if not d:
            raise HTTPException(status_code=404, detail="Document not found")
        await db.delete(d)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/shares")
async def list_shares(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(DataRoomShare)
            .where(DataRoomShare.org_id == org_id)
            .order_by(DataRoomShare.created_at.desc())
        )).scalars().all()
        return [_share_out(s) for s in rows]
    except Exception as e:
        log.error("list_shares failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shares", status_code=201)
async def create_share(
    body: ShareIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        # Verify all folder_ids belong to org
        if body.folder_ids:
            folders = (await db.execute(
                select(DataRoomFolder).where(
                    DataRoomFolder.id.in_(body.folder_ids),
                    DataRoomFolder.org_id == org_id,
                )
            )).scalars().all()
            if len(folders) != len(body.folder_ids):
                raise HTTPException(status_code=404, detail="One or more folders not found")

        token = secrets.token_hex(32)
        s = DataRoomShare(
            org_id=org_id,
            label=body.label,
            token=token,
            folder_ids=[str(fid) for fid in body.folder_ids],
            expires_at=body.expires_at,
            created_by=user_id,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return _share_out(s)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_share failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/shares/{share_id}", status_code=204)
async def revoke_share(
    share_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        s = await db.scalar(
            select(DataRoomShare).where(DataRoomShare.id == share_id, DataRoomShare.org_id == org_id)
        )
        if not s:
            raise HTTPException(status_code=404, detail="Share link not found")
        await db.delete(s)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("revoke_share failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Public endpoint — no auth ─────────────────────────────────────────────────

@router.get("/access/{token}")
async def access_share(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint — no auth required. Returns shared folders and documents."""
    try:
        share = await db.scalar(
            select(DataRoomShare).where(DataRoomShare.token == token)
        )
        if not share:
            raise HTTPException(status_code=404, detail="Share link not found")

        now = datetime.now(timezone.utc)
        if share.expires_at and share.expires_at < now:
            raise HTTPException(status_code=410, detail="Share link has expired")

        # Increment view count
        share.view_count = (share.view_count or 0) + 1
        await db.flush()

        folder_ids = share.folder_ids or []
        result_folders = []
        for fid_str in folder_ids:
            try:
                fid = uuid.UUID(str(fid_str))
            except (ValueError, AttributeError):
                continue

            folder = await db.scalar(
                select(DataRoomFolder).where(DataRoomFolder.id == fid)
            )
            if not folder:
                continue

            docs = (await db.execute(
                select(DataRoomDocument)
                .where(DataRoomDocument.folder_id == fid)
                .order_by(DataRoomDocument.name)
            )).scalars().all()

            result_folders.append({
                "name": folder.name,
                "documents": [
                    {"name": d.name, "file_url": d.file_url, "created_at": d.created_at.isoformat()}
                    for d in docs
                ],
            })

        await db.commit()

        return {
            "label": share.label,
            "folders": result_folders,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("access_share failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
