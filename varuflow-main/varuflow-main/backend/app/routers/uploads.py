"""
File upload endpoint (Item 43/44 support).

POST /api/uploads — uploads a file to Supabase Storage and returns the
public URL. Used by expenses (receipts) and documents.

The file lands in the "uploads" bucket under a path:
    {org_id}/{year}/{month}/{uuid}.{ext}

Supabase Storage is accessed via its REST API using the service key so
no additional Python SDK is needed.
"""
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.config import settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# Maximum file size: 20 MB
MAX_BYTES = 20 * 1024 * 1024

# Allowed MIME types — receipts (images + PDF) and common documents.
ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
}

SUPABASE_BUCKET = "uploads"


async def _upload_to_supabase(
    content: bytes,
    path: str,
    mime_type: str,
) -> str:
    """
    Upload *content* to Supabase Storage at *path* inside SUPABASE_BUCKET.
    Returns the public URL on success; raises HTTPException on failure.
    """
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    service_key = settings.SUPABASE_SERVICE_KEY

    upload_url = f"{supabase_url}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": mime_type,
        "x-upsert": "true",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(upload_url, content=content, headers=headers)

    if resp.status_code not in (200, 201):
        log.error("Supabase Storage upload failed: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="File storage unavailable")

    public_url = (
        f"{supabase_url}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"
    )
    return public_url


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file and return its public URL.

    Returns:
        { "url": "<public URL>", "mime_type": "...", "size": <bytes> }
    """
    try:
        # --- Validate size ---
        content = await file.read()
        size = len(content)
        if size == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        if size > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_BYTES // (1024 * 1024)} MB)",
            )

        # --- Validate MIME ---
        mime_type = file.content_type or "application/octet-stream"
        # Fallback: guess from filename if browser sends generic type.
        if mime_type == "application/octet-stream" and file.filename:
            guessed, _ = mimetypes.guess_type(file.filename)
            if guessed:
                mime_type = guessed
        if mime_type not in ALLOWED_MIME:
            raise HTTPException(
                status_code=415,
                detail=f"File type '{mime_type}' is not allowed",
            )

        # --- Build storage path ---
        org_id = user["org_id"]
        now = datetime.now(timezone.utc)
        ext = ""
        if file.filename and "." in file.filename:
            ext = "." + file.filename.rsplit(".", 1)[-1].lower()
        file_id = str(uuid.uuid4())
        path = f"{org_id}/{now.year}/{now.month:02d}/{file_id}{ext}"

        # --- Upload ---
        public_url = await _upload_to_supabase(content, path, mime_type)

        log.info(
            "File uploaded | org_id=%s user_id=%s size=%d mime=%s path=%s",
            org_id, user["user_id"], size, mime_type, path,
        )
        return {"url": public_url, "mime_type": mime_type, "size": size}

    except HTTPException:
        raise
    except Exception as e:
        log.error("upload_file failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
