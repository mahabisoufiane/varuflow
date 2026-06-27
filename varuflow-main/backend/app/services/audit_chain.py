"""Tamper-evident hash chain for the audit log.

Each row stores:
  previous_hash — SHA-256 of the prior row's row_hash (genesis = "0"*64)
  row_hash      — SHA-256 of (previous_hash ‖ canonical fields)

The canonical preimage is a pipe-delimited string:
  previous_hash|org_id|actor_user_id|action|target_type|target_id|created_at_iso|extra_json

Usage — writing:
    from app.services.audit_chain import compute_row_hash, get_previous_hash
    previous = await get_previous_hash(db, org_id)
    row_hash  = compute_row_hash(previous, row)
    entry.previous_hash = previous
    entry.row_hash      = row_hash

Usage — verifying:
    from app.services.audit_chain import verify_chain
    result = await verify_chain(db, org_id)
    # result.ok == True means untampered
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.compliance.audit_models import AuditLogEntry

log = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


# ── Core hashing ──────────────────────────────────────────────────────────────

def _canonical(previous_hash: str, entry: AuditLogEntry) -> str:
    """Deterministic preimage string for a log entry."""
    created_iso = (
        entry.created_at.isoformat()
        if hasattr(entry.created_at, "isoformat")
        else str(entry.created_at)
    )
    extra_str = json.dumps(entry.extra or {}, sort_keys=True, separators=(",", ":"))
    parts = [
        previous_hash,
        str(entry.org_id or ""),
        str(entry.actor_user_id or ""),
        entry.action or "",
        entry.target_type or "",
        entry.target_id or "",
        created_iso,
        extra_str,
    ]
    return "|".join(parts)


def compute_row_hash(previous_hash: str, entry: AuditLogEntry) -> str:
    """Compute SHA-256 row_hash for an entry."""
    preimage = _canonical(previous_hash, entry)
    return hashlib.sha256(preimage.encode()).hexdigest()


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_previous_hash(db: AsyncSession, org_id: Optional[uuid.UUID]) -> str:
    """Return the row_hash of the latest entry for this org, or GENESIS_HASH."""
    q = (
        select(AuditLogEntry.row_hash)
        .where(AuditLogEntry.org_id == org_id)
        .order_by(AuditLogEntry.sequence_no.desc().nulls_last(), AuditLogEntry.created_at.desc())
        .limit(1)
    )
    row = await db.execute(q)
    result = row.scalar_one_or_none()
    # Entries written before the chain migration have the default GENESIS value
    if not result or result == GENESIS_HASH:
        return GENESIS_HASH
    return result


async def write_audit_entry(
    db: AsyncSession,
    *,
    org_id: Optional[uuid.UUID],
    actor_user_id: Optional[uuid.UUID],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    extra: Optional[dict] = None,
) -> AuditLogEntry:
    """Write a new hash-chained audit log entry. Use this instead of
    inserting AuditLogEntry directly so the chain stays intact."""
    entry = AuditLogEntry(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_address,
        extra=extra or {},
    )
    db.add(entry)
    await db.flush()  # populate entry.created_at via server_default

    previous = await get_previous_hash(db, org_id)
    entry.previous_hash = previous
    entry.row_hash = compute_row_hash(previous, entry)

    await db.flush()
    return entry


# ── Verification ──────────────────────────────────────────────────────────────

@dataclass
class ChainVerificationResult:
    ok: bool
    total_rows: int
    first_broken_id: Optional[str] = None
    first_broken_seq: Optional[int] = None
    error: Optional[str] = None


async def verify_chain(
    db: AsyncSession,
    org_id: uuid.UUID,
    limit: int = 10_000,
) -> ChainVerificationResult:
    """Walk all audit log rows for an org in insertion order and verify
    every row_hash matches its computed value. Returns on first failure."""
    q = (
        select(AuditLogEntry)
        .where(AuditLogEntry.org_id == org_id)
        .order_by(AuditLogEntry.sequence_no.asc().nulls_first(), AuditLogEntry.created_at.asc())
        .limit(limit)
    )
    rows = await db.execute(q)
    entries = rows.scalars().all()

    if not entries:
        return ChainVerificationResult(ok=True, total_rows=0)

    prev_hash = GENESIS_HASH
    for i, entry in enumerate(entries):
        # Entries pre-migration carry default hashes — skip silently
        if entry.row_hash == GENESIS_HASH and entry.previous_hash == GENESIS_HASH:
            prev_hash = entry.row_hash
            continue

        expected = compute_row_hash(entry.previous_hash, entry)
        if expected != entry.row_hash:
            return ChainVerificationResult(
                ok=False,
                total_rows=len(entries),
                first_broken_id=str(entry.id),
                first_broken_seq=i,
                error=f"Hash mismatch at row {i}: stored {entry.row_hash[:12]}… expected {expected[:12]}…",
            )
        if entry.previous_hash != prev_hash:
            return ChainVerificationResult(
                ok=False,
                total_rows=len(entries),
                first_broken_id=str(entry.id),
                first_broken_seq=i,
                error=f"Chain break at row {i}: previous_hash {entry.previous_hash[:12]}… expected {prev_hash[:12]}…",
            )
        prev_hash = entry.row_hash

    return ChainVerificationResult(ok=True, total_rows=len(entries))
