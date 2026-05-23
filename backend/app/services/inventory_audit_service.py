"""Inventory audit trail service (Item 47).

Pure helpers classify stock movements as "unusual" so the UI can
highlight them in red, and build the CSV payload. The DB query
work lives in the router because it's a single filter-and-join.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════


# Above this quantity, an OUT or ADJUSTMENT movement is flagged as
# "unusual" in the UI. 50 picked as a sensible default for retail —
# a single SKU rarely ships 50+ units in one line outside of wholesale.
LARGE_MOVEMENT_THRESHOLD = 50

# Export-page row cap. Keeps a single CSV generation from OOM'ing the
# worker on very noisy orgs. Matches the bokföringslagen-export style.
EXPORT_ROW_CAP = 10_000


# ═══════════════════════════════════════════════════════════════════
# Pure classifier
# ═══════════════════════════════════════════════════════════════════


@dataclass
class MovementFlag:
    """Explains why a movement is unusual. ``reasons`` is empty for
    routine movements."""
    reasons: tuple[str, ...]

    @property
    def unusual(self) -> bool:
        return bool(self.reasons)

    def to_dict(self) -> dict:
        return {"unusual": self.unusual, "reasons": list(self.reasons)}


def classify_movement(
    *,
    movement_type: str,
    quantity: int,
    note: str | None = None,
) -> MovementFlag:
    """Flag a stock movement for manual review.

    Currently flags:

    * Large OUT movements (above :data:`LARGE_MOVEMENT_THRESHOLD`).
      These are the canonical "did someone fat-finger the count?"
      case operators ask about.
    * Any ADJUSTMENT — manual stock adjustments are rare and
      worth surfacing in the audit trail so shrinkage can be
      triangulated.
    * Large ADJUSTMENTs (same threshold) — doubly flagged so the
      UI can render them with a distinct priority.
    """
    reasons: list[str] = []
    t = (movement_type or "").upper()
    q = int(quantity)
    if t == "OUT" and q > LARGE_MOVEMENT_THRESHOLD:
        reasons.append("large_out")
    if t == "ADJUSTMENT":
        reasons.append("manual_adjustment")
        if q > LARGE_MOVEMENT_THRESHOLD:
            reasons.append("large_adjustment")
    return MovementFlag(reasons=tuple(reasons))


# ═══════════════════════════════════════════════════════════════════
# CSV export (pure)
# ═══════════════════════════════════════════════════════════════════


CSV_HEADERS = (
    "timestamp",
    "type",
    "quantity",
    "product_sku",
    "product_name",
    "warehouse",
    "reference",
    "reason",
    "actor_user_id",
    "ip_address",
    "unusual",
)


@dataclass
class ExportRow:
    timestamp: datetime
    type: str
    quantity: int
    product_sku: str
    product_name: str
    warehouse: str
    reference: str | None
    reason: str | None
    actor_user_id: str | None
    ip_address: str | None
    unusual: bool

    def as_tuple(self) -> tuple:
        return (
            self.timestamp.isoformat(),
            self.type,
            self.quantity,
            self.product_sku,
            self.product_name,
            self.warehouse,
            self.reference or "",
            self.reason or "",
            self.actor_user_id or "",
            self.ip_address or "",
            "yes" if self.unusual else "",
        )


def render_csv(rows: list[ExportRow]) -> str:
    """Render rows to RFC 4180 CSV text.

    Uses csv.writer so quoting / escaping is correct even when
    product names contain commas or quotes (the exported file
    has to open cleanly in Excel, Google Sheets, Numbers, and
    Swedish-locale variants).
    """
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    w.writerow(CSV_HEADERS)
    for r in rows[:EXPORT_ROW_CAP]:
        w.writerow(r.as_tuple())
    return buf.getvalue()
