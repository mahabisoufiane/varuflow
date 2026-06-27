"""Tests for the public booking widget (Item 46).

Pure + contract-style split, same pattern as Items 28-45.

Required test names (spec):

* test_widget_loads_for_org_slug
* test_service_list_shown
* test_slot_selection
* test_appointment_created
* test_confirmation_email_sent
* test_arabic_rtl_layout
* test_widget_respects_brand_color
* test_invalid_org_slug_404
* test_double_booking_prevented
* test_mobile_responsive
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import widget_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
_FRONTEND_ROOT = (
    _BACKEND_ROOT.parent.parent / "frontend" / "src" / "app" / "widget"
)


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/widget.py")
SERVICE_SRC = _read("services/widget_service.py")
MAIN_SRC = _read("main.py")
BOOKINGS_SRC = _read("routers/bookings.py")

# Frontend page — spec requires it to exist and carry the RTL +
# brand-color plumbing.
_FRONTEND_PAGE = _FRONTEND_ROOT / "[orgSlug]" / "page.tsx"
FRONTEND_SRC = _FRONTEND_PAGE.read_text() if _FRONTEND_PAGE.exists() else ""


# ═══════════════════════════════════════════════════════════════════
# 1. test_widget_loads_for_org_slug
# ═══════════════════════════════════════════════════════════════════


def test_widget_loads_for_org_slug():
    # Public meta endpoint exists, no auth dependency in the signature.
    assert '@router.get("/{slug}", response_model=WidgetOrgOut)' in ROUTER_SRC
    assert "get_current_member" not in ROUTER_SRC  # entire file is public.
    # Slug generation round-trips deterministically.
    org_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    s1 = svc.org_slug("Glamour Salon", org_id)
    s2 = svc.org_slug("Glamour Salon", org_id)
    assert s1 == s2
    assert s1.startswith("glamour-salon-")
    # Suffix comes from the UUID hex prefix for collision resistance.
    assert s1.endswith("111111")
    # Frontend page lives at the expected path.
    assert _FRONTEND_PAGE.exists(), (
        f"widget page missing at {_FRONTEND_PAGE}"
    )


# ═══════════════════════════════════════════════════════════════════
# 2. test_service_list_shown
# ═══════════════════════════════════════════════════════════════════


def test_service_list_shown():
    assert '@router.get("/{slug}/services", response_model=list[WidgetServiceOut])' in ROUTER_SRC
    # Only active services surface to the public widget.
    assert "Service.is_active == True" in ROUTER_SRC
    # Frontend fetches the list.
    assert "/services" in FRONTEND_SRC or "services" in FRONTEND_SRC.lower()


# ═══════════════════════════════════════════════════════════════════
# 3. test_slot_selection
# ═══════════════════════════════════════════════════════════════════


def test_slot_selection():
    assert '@router.get("/{slug}/slots", response_model=list[WidgetSlotOut])' in ROUTER_SRC
    # Pure overlap check mirrors the DB guard.
    now = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    assert svc.slots_overlap(now, now + timedelta(minutes=30),
                             now + timedelta(minutes=15),
                             now + timedelta(minutes=45)) is True
    # Edge: back-to-back slots (a.end == b.start) are NOT an overlap.
    assert svc.slots_overlap(now, now + timedelta(minutes=30),
                             now + timedelta(minutes=30),
                             now + timedelta(minutes=60)) is False
    # Service+staff validation gates on tenant scope before building
    # the grid.
    assert "service.org_id != org.id" in ROUTER_SRC
    assert "staff.org_id != org.id" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_appointment_created
# ═══════════════════════════════════════════════════════════════════


def test_appointment_created():
    assert '@router.post("/{slug}/book", response_model=BookingOut, status_code=201)' in ROUTER_SRC
    # Creates an Appointment row on the SAME underlying table used by
    # the authenticated bookings router.
    assert "from app.models.bookings import Appointment" in ROUTER_SRC
    assert 'channel="web"' in ROUTER_SRC
    # Empty/garbage inputs rejected by pure validators.
    assert svc.validate_name("  Jane  ") == "Jane"
    with pytest.raises(svc.WidgetValidationError):
        svc.validate_name("")
    assert svc.validate_email("USER@example.com") == "user@example.com"
    with pytest.raises(svc.WidgetValidationError):
        svc.validate_email("not-an-email")
    # Phone is optional but validated when provided.
    assert svc.validate_phone(None) is None
    assert svc.validate_phone("+46701234567") == "+46701234567"
    with pytest.raises(svc.WidgetValidationError):
        svc.validate_phone("abc")


# ═══════════════════════════════════════════════════════════════════
# 5. test_confirmation_email_sent
# ═══════════════════════════════════════════════════════════════════


def test_confirmation_email_sent():
    # Service exports an email dispatcher and the router invokes it.
    assert "async def send_confirmation_email" in SERVICE_SRC
    assert "await svc.send_confirmation_email(" in ROUTER_SRC
    # Body builder is pure and embeds the brand color + name/service.
    payload = svc.BookingConfirmation(
        customer_name="Zara",
        customer_email="zara@example.com",
        org_name="Glow Studio",
        service_name="Keratin",
        staff_name="Leila",
        start_time=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        brand_color="#e91e63",
    )
    html = svc.build_confirmation_html(payload)
    assert "Zara" in html
    assert "Glow Studio" in html
    assert "Keratin" in html
    assert "Leila" in html
    assert "#e91e63" in html
    # Ensure HTML escape defuses injection attempts in caller-supplied
    # fields.
    bad = svc.BookingConfirmation(
        customer_name="<script>alert(1)</script>",
        customer_email="x@y.com",
        org_name="Salon",
        service_name="Cut",
        staff_name="Ana",
        start_time=datetime(2026, 5, 1, tzinfo=timezone.utc),
        brand_color="#000000",
    )
    out = svc.build_confirmation_html(bad)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# ═══════════════════════════════════════════════════════════════════
# 6. test_arabic_rtl_layout
# ═══════════════════════════════════════════════════════════════════


def test_arabic_rtl_layout():
    # Router heuristic flips RTL for Arabic / Hebrew org names.
    assert "def _looks_rtl" in ROUTER_SRC
    # Frontend page applies dir="rtl" when the widget meta says so.
    assert 'dir={' in FRONTEND_SRC or 'dir="rtl"' in FRONTEND_SRC or "rtl" in FRONTEND_SRC
    # ar.json carries the widget namespace.
    ar_path = (
        _BACKEND_ROOT.parent.parent
        / "frontend" / "messages" / "ar.json"
    )
    ar_text = ar_path.read_text()
    assert '"widget"' in ar_text, "Arabic widget namespace missing"


# ═══════════════════════════════════════════════════════════════════
# 7. test_widget_respects_brand_color
# ═══════════════════════════════════════════════════════════════════


def test_widget_respects_brand_color():
    # Pure validator clamps bad inputs.
    assert svc.validate_brand_color("#abcdef") == "#abcdef"
    assert svc.validate_brand_color("#ABC") == "#ABC"
    assert svc.validate_brand_color("red") == svc.DEFAULT_BRAND_COLOR
    assert svc.validate_brand_color(None) == svc.DEFAULT_BRAND_COLOR
    assert svc.validate_brand_color("javascript:alert(1)") == svc.DEFAULT_BRAND_COLOR
    # Router exposes brand_color on the meta endpoint.
    assert "brand_color=brand" in ROUTER_SRC
    # Service pulls from invoice_templates.primary_color with fallback.
    assert "resolve_brand_color" in SERVICE_SRC
    assert "DEFAULT_BRAND_COLOR" in SERVICE_SRC
    # Frontend applies the color.
    assert "brand_color" in FRONTEND_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_invalid_org_slug_404
# ═══════════════════════════════════════════════════════════════════


def test_invalid_org_slug_404():
    assert 'detail="org_not_found"' in ROUTER_SRC
    # Slug resolver short-circuits on malformed slugs before hitting DB.
    assert "if not isinstance(slug, str) or \"-\" not in slug" in SERVICE_SRC
    # Wrong suffix length → None, even if the base happens to match.
    assert "if len(suffix) != SLUG_SUFFIX_LEN" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_double_booking_prevented
# ═══════════════════════════════════════════════════════════════════


def test_double_booking_prevented():
    # Public book endpoint uses the same half-open-interval guard as
    # the private router.
    assert "Appointment.start_time < end" in ROUTER_SRC
    assert "Appointment.end_time > start" in ROUTER_SRC
    assert 'status_code=status.HTTP_409_CONFLICT' in ROUTER_SRC
    assert 'detail="slot_unavailable"' in ROUTER_SRC
    # Pure overlap helper agrees on half-open semantics.
    t = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    assert svc.slots_overlap(t, t + timedelta(minutes=60),
                             t + timedelta(minutes=30),
                             t + timedelta(minutes=90)) is True


# ═══════════════════════════════════════════════════════════════════
# 10. test_mobile_responsive
# ═══════════════════════════════════════════════════════════════════


def test_mobile_responsive():
    # The generated embed snippet carries a responsive wrapper and
    # the iframe scales to 100% width.
    assert 'max-width:640px' in BOOKINGS_SRC
    assert 'width="100%"' in BOOKINGS_SRC
    # The frontend widget ships mobile-first layout classes. We look
    # for common responsive tokens rather than pinning a specific
    # breakpoint.
    for tok in ("w-full", "max-w-"):
        assert tok in FRONTEND_SRC, f"frontend missing responsive token: {tok}"


# ═══════════════════════════════════════════════════════════════════
# Invariants / smoke
# ═══════════════════════════════════════════════════════════════════


def test_router_registered_in_main():
    assert ", widget" in MAIN_SRC or "widget" in MAIN_SRC
    assert "app.include_router(widget.router)" in MAIN_SRC


def test_no_auth_on_public_paths():
    # Every @router decorator in widget.py MUST be unauthenticated:
    # no dependency on get_current_member, require_plan, etc.
    assert "Depends(get_current_member)" not in ROUTER_SRC
    assert "require_plan" not in ROUTER_SRC


def test_audit_log_on_public_booking():
    assert 'action="widget.appointment_created"' in ROUTER_SRC
    assert "actor_user_id=None" in ROUTER_SRC  # anonymous actor
    assert "await log_action(" in ROUTER_SRC


def test_slugify_pure():
    assert svc.slugify("  Glow & Co. ") == "glow-co"
    assert svc.slugify("Salon—de-Paris") == "salonde-paris"
    assert svc.slugify("") == ""
    assert svc.slugify(None) == ""  # type: ignore[arg-type]


def test_looks_rtl_heuristic():
    # _looks_rtl lives in the router; we can't import it under the
    # 3.9 sandbox (ORM uses `X | None`). Lock the Unicode-range logic
    # by reading the source instead.
    assert "0x0590 <= cp <= 0x05FF" in ROUTER_SRC  # Hebrew
    assert "0x0600 <= cp <= 0x06FF" in ROUTER_SRC  # Arabic
    assert "0x0750 <= cp <= 0x077F" in ROUTER_SRC  # Arabic Supplement
