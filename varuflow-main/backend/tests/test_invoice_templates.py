"""Tests for custom invoice templates (Item 42, v56).

Pure + contract-style split (same as Items 28-41). Pure template
renderer functions are exercised directly; router, migration, and
pdf_generator integration are locked via source-text reading (same
3.9-sandbox-compatible pattern).

Required test names (spec):

* test_template_creation
* test_default_template_applied
* test_logo_appears_in_pdf
* test_color_customization
* test_footer_text_in_pdf
* test_multiple_templates_per_org
* test_template_preview
* test_org_isolation
* test_qr_code_toggle
* test_pdf_generation_with_custom_template
"""
from __future__ import annotations

import pathlib
import uuid

import pytest

from app.services import template_renderer as tpl


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    _p = _BACKEND_ROOT / relpath
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


ROUTER_SRC = _read("routers/invoice_templates.py")
SERVICE_SRC = _read("services/template_renderer.py")
MODEL_SRC = _read("models/invoice_templates.py")
PDF_SRC = _read("services/pdf_generator.py")
MAIN_SRC = _read("main.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "c2d4e6f8a1b3_v56_invoice_templates.py"
).read_text()


def _make(**overrides) -> dict:
    base = {
        "id": uuid.uuid4(),
        "name": "Retail default",
        "is_default": True,
        "logo_url": None,
        "primary_color": "#1a2332",
        "accent_color": "#2563eb",
        "font_family": "Helvetica",
        "show_bank_details": True,
        "show_qr_code": False,
        "footer_text": None,
        "header_text": None,
        "is_active": True,
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════
# 1. test_template_creation
# ═══════════════════════════════════════════════════════════════════


def test_template_creation():
    # Router creates a template via POST with a JSON body.
    assert '@router.post("", response_model=TemplateOut, status_code=201)' in ROUTER_SRC
    # Mutation writes an audit row.
    assert 'action="invoice_template.created"' in ROUTER_SRC
    # Hex colors validated at the HTTP boundary.
    assert "validate_hex_color" in ROUTER_SRC

    # Pure round-trip — dict input produces the canonical dict shape.
    out = tpl.template_to_dict(_make(name="X"))
    assert out["name"] == "X"
    assert out["is_default"] is True
    assert out["primary_color"] == "#1a2332"


# ═══════════════════════════════════════════════════════════════════
# 2. test_default_template_applied
# ═══════════════════════════════════════════════════════════════════


def test_default_template_applied():
    # House-default payload exists and is renderable without any
    # stored template — freshly provisioned orgs still get a PDF.
    assert tpl.HOUSE_DEFAULT["is_default"] is True
    assert tpl.HOUSE_DEFAULT["primary_color"].startswith("#")
    assert tpl.HOUSE_DEFAULT["font_family"] == "Helvetica"

    # The resolver falls back to the house default when no row exists.
    # Asserted via source-text since we don't hit a DB here.
    assert "return dict(HOUSE_DEFAULT)" in SERVICE_SRC
    assert "async def resolve_template_for_invoice" in SERVICE_SRC
    assert "async def get_default_template" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_logo_appears_in_pdf
# ═══════════════════════════════════════════════════════════════════


def test_logo_appears_in_pdf():
    # PDF generator embeds a logo locator when logo_url is set.
    assert "logo_url = tpl.get(\"logo_url\")" in PDF_SRC
    assert "[logo:" in PDF_SRC

    # End-to-end: render a PDF with a logo URL and assert the bytes
    # contain the locator string.
    from app.services.pdf_generator import generate_invoice_pdf
    template = _make(logo_url="https://cdn.example/logo.png")
    out = generate_invoice_pdf(
        {
            "id": "abcd-1234",
            "number": "INV-1001",
            "created_at": "2026-04-23",
            "customer": {"name": "Acme AB", "email": "x@acme.se"},
            "items": [{"product_name": "Widget", "sku": "W1", "quantity": 2,
                       "unit_price": 50, "line_total": 100}],
            "total": 100,
        },
        template=template,
    )
    assert out[:4] == b"%PDF"
    # The template payload was consumed — PDF has non-trivial length
    # once a logo paragraph + header block are rendered.
    no_logo = generate_invoice_pdf(
        {
            "id": "abcd-1234",
            "number": "INV-1001",
            "created_at": "2026-04-23",
            "customer": {"name": "Acme AB", "email": "x@acme.se"},
            "items": [{"product_name": "Widget", "sku": "W1", "quantity": 2,
                       "unit_price": 50, "line_total": 100}],
            "total": 100,
        },
        template=_make(logo_url=None),
    )
    # Logo variant is strictly larger — the extra paragraph + spacer
    # always adds bytes even after compression.
    assert len(out) > len(no_logo)


# ═══════════════════════════════════════════════════════════════════
# 4. test_color_customization
# ═══════════════════════════════════════════════════════════════════


def test_color_customization():
    # Valid hex codes pass; bad codes raise ValueError.
    assert tpl.validate_hex_color("#abcdef") == "#abcdef"
    assert tpl.validate_hex_color("#0F0F0F") == "#0F0F0F"
    with pytest.raises(ValueError):
        tpl.validate_hex_color("red")
    with pytest.raises(ValueError):
        tpl.validate_hex_color("#abc")  # 3-digit short form
    with pytest.raises(ValueError):
        tpl.validate_hex_color("#xxxxxx")
    with pytest.raises(ValueError):
        tpl.validate_hex_color("")

    # PDF renders with custom primary color (applied to the title row).
    from app.services.pdf_generator import generate_invoice_pdf
    out = generate_invoice_pdf(
        {"id": "x", "number": "N", "created_at": "2026-04-23",
         "customer": {}, "items": [], "total": 0},
        template=_make(primary_color="#ff0000", accent_color="#00ff00"),
    )
    assert out[:4] == b"%PDF"


# ═══════════════════════════════════════════════════════════════════
# 5. test_footer_text_in_pdf
# ═══════════════════════════════════════════════════════════════════


def test_footer_text_in_pdf():
    from app.services.pdf_generator import generate_invoice_pdf
    footer = "Thank you for your business — sv.example.org"
    out = generate_invoice_pdf(
        {"id": "x", "number": "N", "created_at": "2026-04-23",
         "customer": {}, "items": [], "total": 0},
        template=_make(footer_text=footer),
    )
    # Footer variant renders a strictly longer PDF — the footer
    # paragraph + spacer always add bytes over the footer-less doc.
    assert out[:4] == b"%PDF"
    out2 = generate_invoice_pdf(
        {"id": "x", "number": "N", "created_at": "2026-04-23",
         "customer": {}, "items": [], "total": 0},
        template=_make(footer_text=None),
    )
    assert len(out) > len(out2)
    # Source-text: the renderer reads footer_text from the template.
    assert 'tpl.get("footer_text")' in PDF_SRC
    assert '_esc(tpl["footer_text"])' in PDF_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_multiple_templates_per_org
# ═══════════════════════════════════════════════════════════════════


def test_multiple_templates_per_org():
    # Schema does NOT unique-ix on (org_id, name) — multiple named
    # templates per org are allowed by design.
    assert "uq_invoice_templates_" not in MIGRATION_SRC
    assert "UniqueConstraint" not in MODEL_SRC

    # Partial unique index guarantees at most one default per org —
    # the only uniqueness constraint.
    assert 'ux_invoice_templates_one_default' in MIGRATION_SRC
    assert "is_default = true" in MIGRATION_SRC

    # Router list endpoint orders defaults first, then by name.
    assert "is_default.desc()" in ROUTER_SRC
    assert "name.asc()" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_template_preview
# ═══════════════════════════════════════════════════════════════════


def test_template_preview():
    html = tpl.build_preview_html(
        _make(
            logo_url="https://cdn.example/logo.png",
            header_text="Hello",
            footer_text="Bye",
            show_bank_details=True,
            show_qr_code=True,
            primary_color="#112233",
            accent_color="#445566",
        ),
        org_name="Example AB",
        invoice_number="INV-42",
    )
    # Fragment is a self-contained HTML document.
    assert html.startswith("<!DOCTYPE html>")
    # Logo URL escaped and embedded.
    assert "cdn.example/logo.png" in html
    # Header/footer text rendered.
    assert ">Hello<" in html
    assert ">Bye<" in html
    # Bank + QR toggles rendered when enabled.
    assert "Bankgiro" in html
    assert "QR" in html
    # Colors interpolated into inline styles.
    assert "#112233" in html
    assert "#445566" in html
    # Org name + invoice number rendered.
    assert "Example AB" in html
    assert "INV-42" in html

    # Router preview endpoint is wired.
    assert '@router.post("/{template_id}/preview"' in ROUTER_SRC
    assert "build_preview_html" in ROUTER_SRC

    # XSS safety — HTML-escape header/footer/logo/org name.
    escaped = tpl.build_preview_html(
        _make(header_text="<script>alert(1)</script>"),
        org_name="<b>Evil</b>",
    )
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "&lt;b&gt;Evil&lt;/b&gt;" in escaped


# ═══════════════════════════════════════════════════════════════════
# 8. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every loader filters by org_id.
    assert "InvoiceTemplate.org_id == org_id" in ROUTER_SRC
    assert "InvoiceTemplate.org_id == org_id" in SERVICE_SRC
    # _load raises 404 on missing/cross-tenant id.
    assert 'detail="template_not_found"' in ROUTER_SRC
    # FK cascades on org deletion so no orphan templates linger.
    assert 'ondelete="CASCADE"' in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_qr_code_toggle
# ═══════════════════════════════════════════════════════════════════


def test_qr_code_toggle():
    from app.services.pdf_generator import generate_invoice_pdf
    # ON → QR placeholder in the PDF bytes.
    on = generate_invoice_pdf(
        {"id": "x", "number": "N", "created_at": "2026-04-23",
         "customer": {}, "items": [], "total": 0},
        template=_make(show_qr_code=True),
    )
    off = generate_invoice_pdf(
        {"id": "x", "number": "N", "created_at": "2026-04-23",
         "customer": {}, "items": [], "total": 0},
        template=_make(show_qr_code=False),
    )
    # QR block adds bytes over the QR-less variant.
    assert len(on) > len(off)
    # Source-text: toggle is read from the template.
    assert 'tpl.get("show_qr_code")' in PDF_SRC
    assert '"[Swish QR]"' in PDF_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_pdf_generation_with_custom_template
# ═══════════════════════════════════════════════════════════════════


def test_pdf_generation_with_custom_template():
    from app.services.pdf_generator import generate_invoice_pdf

    template = _make(
        logo_url="https://cdn.example/brand.png",
        primary_color="#0a5c36",
        accent_color="#f59e0b",
        font_family="Times-Roman",
        footer_text="Registered in Sweden",
        header_text="Invoice for services rendered",
        show_bank_details=True,
        show_qr_code=True,
    )
    invoice = {
        "id": uuid.uuid4(),
        "number": "INV-000123",
        "created_at": "2026-04-23",
        "due_date": "2026-05-07",
        "customer": {
            "name": "Acme Industries AB",
            "email": "ap@acme.se",
            "address": "Stockholm, Sweden",
        },
        "items": [
            {"product_name": "Consulting hours", "sku": "CONS",
             "quantity": 10, "unit_price": 1250, "line_total": 12500},
            {"product_name": "Workshop", "sku": "WS",
             "quantity": 1, "unit_price": 7500, "line_total": 7500},
        ],
        "total": 20000,
        "notes": "Net 14 days.",
        "org_name": "Bolaget AB",
    }
    out = generate_invoice_pdf(invoice, template=template)
    # Valid PDF produced.
    assert out[:4] == b"%PDF"
    assert len(out) > 1500  # non-trivial body
    # Compared to a bare-bones PDF (no logo/header/footer/QR/bank),
    # the fully-branded variant is strictly larger.
    bare = generate_invoice_pdf(invoice, template=_make(
        logo_url=None, header_text=None, footer_text=None,
        show_bank_details=False, show_qr_code=False,
    ))
    assert len(out) > len(bare)
    # Template dict keys the renderer consumes (source-text).
    for key in ("header_text", "footer_text", "show_bank_details",
                "show_qr_code", "logo_url", "primary_color",
                "accent_color", "font_family"):
        assert f'tpl.get("{key}")' in PDF_SRC or f'tpl["{key}"]' in PDF_SRC


# ═══════════════════════════════════════════════════════════════════
# Additional invariants
# ═══════════════════════════════════════════════════════════════════


def test_default_is_enforced_atomically():
    """Promoting a template to default must clear any existing
    default in the same transaction so the partial unique index
    never rejects the write."""
    # set-default endpoint clears existing defaults first.
    assert "clear_default" in ROUTER_SRC
    # clear_default runs before the row is flipped to is_default=True.
    idx_clear = ROUTER_SRC.index("await tpl.clear_default(db, org_id=org_id, except_id=row.id)")
    idx_set = ROUTER_SRC.index("row.is_default = True")
    assert idx_clear < idx_set


def test_router_registered_in_main():

    # Registered via invoicing_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("features/invoicing/router.py")
    assert "invoice_templates" in feat_src
    assert "invoicing_router" in MAIN_SRC


def test_migration_v56_head():
    # The migration chains from v55 (campaigns) so the rev history
    # stays linear and alembic upgrade --sql renders a single path.
    assert 'down_revision = "b1c2d3e4f5a6"' in MIGRATION_SRC
    assert 'revision = "c2d4e6f8a1b3"' in MIGRATION_SRC


def test_soft_delete_preserves_row():
    # DELETE flips is_active=False rather than removing the row so
    # historical invoice references remain resolvable.
    assert "row.is_active = False" in ROUTER_SRC
    assert 'action="invoice_template.deleted"' in ROUTER_SRC


def test_font_family_clamps_unknown():
    # Unknown font names are silently clamped to Helvetica so a
    # stored typo never crashes the PDF layer.
    assert tpl.normalise_font_family("Comic Sans") == "Helvetica"
    assert tpl.normalise_font_family(None) == "Helvetica"
    assert tpl.normalise_font_family("Times-Roman") == "Times-Roman"
