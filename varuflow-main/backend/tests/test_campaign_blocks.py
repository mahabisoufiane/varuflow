"""Item 63 — Inline email campaign block editor."""
from __future__ import annotations

import pathlib

import pytest

from app.services import email_blocks as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


MIGRATION_SRC = _read("migrations/versions/b3c5d7e9f1a4_v72_campaign_blocks.py")
MODEL_SRC = _read("app/features/marketing/campaigns.py")
SERVICE_SRC = _read("app/services/email_blocks.py")
ROUTER_SRC = _read("app/features/marketing/campaigns.py")


# ── Pure service: validate_block ──────────────────────────────────────────


def test_heading_accepts_levels_1_2_3():
    for lvl in (1, 2, 3):
        out = svc.validate_block({"type": "heading", "text": "Hi", "level": lvl})
        assert out == {"type": "heading", "text": "Hi", "level": lvl}


def test_heading_rejects_bad_level():
    for bad in (0, 4, 5, "1", None):
        with pytest.raises(ValueError):
            svc.validate_block({"type": "heading", "text": "x", "level": bad})


def test_paragraph_requires_text():
    svc.validate_block({"type": "paragraph", "text": "Hello"})
    for bad in ("", "   "):
        with pytest.raises(ValueError):
            svc.validate_block({"type": "paragraph", "text": bad})


def test_button_rejects_javascript_url():
    with pytest.raises(ValueError):
        svc.validate_block(
            {"type": "button", "text": "Buy", "url": "javascript:alert(1)"}
        )
    with pytest.raises(ValueError):
        svc.validate_block(
            {"type": "button", "text": "Buy", "url": "data:text/html,x"}
        )


def test_button_accepts_http_https_mailto():
    for url in ("http://example.com", "https://e.com/p", "mailto:hi@x.com"):
        svc.validate_block({"type": "button", "text": "Buy", "url": url})


def test_button_rejects_scheme_without_host():
    with pytest.raises(ValueError):
        svc.validate_block(
            {"type": "button", "text": "Buy", "url": "https://"}
        )


def test_mailto_requires_address():
    with pytest.raises(ValueError):
        svc.validate_block(
            {"type": "button", "text": "Buy", "url": "mailto:"}
        )


def test_image_rejects_non_http_scheme_even_for_images():
    # Image blocks only allow http/https — not mailto.
    with pytest.raises(ValueError):
        svc.validate_block({"type": "image", "url": "mailto:pic@x.com"})


def test_image_optional_alt_and_width():
    out = svc.validate_block(
        {"type": "image", "url": "https://e.com/p.png", "alt": "hi", "width": 600}
    )
    assert out == {
        "type": "image",
        "url": "https://e.com/p.png",
        "alt": "hi",
        "width": 600,
    }


def test_image_width_bounds():
    svc.validate_block(
        {"type": "image", "url": "https://e.com/p.png", "width": svc.MIN_IMAGE_WIDTH}
    )
    svc.validate_block(
        {"type": "image", "url": "https://e.com/p.png", "width": svc.MAX_IMAGE_WIDTH}
    )
    for bad in (0, 15, 1201, "600", True):
        with pytest.raises(ValueError):
            svc.validate_block(
                {"type": "image", "url": "https://e.com/p.png", "width": bad}
            )


def test_divider_takes_no_fields():
    assert svc.validate_block({"type": "divider"}) == {"type": "divider"}
    with pytest.raises(ValueError):
        svc.validate_block({"type": "divider", "extra": 1})


def test_spacer_height_bounds():
    svc.validate_block({"type": "spacer", "height": svc.MIN_SPACER})
    svc.validate_block({"type": "spacer", "height": svc.MAX_SPACER})
    for bad in (7, 81, "16", True):
        with pytest.raises(ValueError):
            svc.validate_block({"type": "spacer", "height": bad})


def test_unknown_block_type_rejected():
    with pytest.raises(ValueError):
        svc.validate_block({"type": "video", "url": "https://e.com"})


def test_unknown_keys_rejected():
    with pytest.raises(ValueError):
        svc.validate_block(
            {"type": "paragraph", "text": "x", "extra": "nope"}
        )


# ── Pure service: validate_blocks ─────────────────────────────────────────


def test_validate_blocks_requires_non_empty_list():
    with pytest.raises(ValueError):
        svc.validate_blocks([])
    with pytest.raises(ValueError):
        svc.validate_blocks("not a list")  # type: ignore[arg-type]


def test_validate_blocks_enforces_max():
    doc = [{"type": "paragraph", "text": "x"}] * svc.MAX_BLOCKS
    svc.validate_blocks(doc)
    with pytest.raises(ValueError):
        svc.validate_blocks(doc + [{"type": "paragraph", "text": "x"}])


# ── Pure service: render_html ─────────────────────────────────────────────


def test_render_html_escapes_text_and_urls():
    doc = svc.validate_blocks(
        [
            {"type": "heading", "text": "<script>a</script>", "level": 1},
            {"type": "paragraph", "text": "Hi & bye"},
        ]
    )
    html = svc.render_html(doc)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_render_html_paragraph_preserves_newlines_as_br():
    doc = svc.validate_blocks([{"type": "paragraph", "text": "a\nb"}])
    assert "<br>" in svc.render_html(doc)


def test_render_html_button_includes_href_and_text():
    doc = svc.validate_blocks(
        [{"type": "button", "text": "Buy", "url": "https://e.com"}]
    )
    html = svc.render_html(doc)
    assert 'href="https://e.com"' in html
    assert ">Buy</a>" in html


def test_render_html_image_includes_alt_empty_when_missing():
    doc = svc.validate_blocks([{"type": "image", "url": "https://e.com/p.png"}])
    html = svc.render_html(doc)
    assert 'alt=""' in html
    assert 'src="https://e.com/p.png"' in html


def test_render_html_divider_and_spacer():
    doc = svc.validate_blocks(
        [{"type": "divider"}, {"type": "spacer", "height": 24}]
    )
    html = svc.render_html(doc)
    assert "<hr" in html
    assert "height:24px" in html


# ── Pure service: render_text ─────────────────────────────────────────────


def test_render_text_produces_plain_text_fallback():
    doc = svc.validate_blocks(
        [
            {"type": "heading", "text": "Hi", "level": 1},
            {"type": "paragraph", "text": "Body"},
            {"type": "button", "text": "Buy", "url": "https://e.com"},
        ]
    )
    out = svc.render_text(doc)
    assert "Hi" in out
    assert "Body" in out
    assert "Buy: https://e.com" in out
    # No HTML tags in the text version.
    assert "<" not in out


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v72_chains_from_v71():
    assert 'revision = "b3c5d7e9f1a4"' in MIGRATION_SRC
    assert 'down_revision = "a2b4c6d8e0f2"' in MIGRATION_SRC
    assert "add_column" in MIGRATION_SRC
    assert '"blocks"' in MIGRATION_SRC


def test_model_exposes_blocks_column():
    assert "blocks" in MODEL_SRC
    assert "JSONB" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_has_block_editor_endpoints():
    assert '@router.post("/render-blocks"' in ROUTER_SRC
    assert '@router.patch("/{campaign_id}/blocks"' in ROUTER_SRC


def test_router_render_is_stateless_no_audit():
    # The render-blocks endpoint must not call log_action.
    start = ROUTER_SRC.index('@router.post("/render-blocks"')
    end = ROUTER_SRC.index('@router.patch("/{campaign_id}/blocks"')
    segment = ROUTER_SRC[start:end]
    assert "log_action" not in segment


def test_router_patch_rejects_sent_campaigns():
    assert "cannot edit SENT campaign" in ROUTER_SRC


def test_router_patch_server_renders_body_html():
    # body_html must be set from render_html, never accepted from client.
    assert "campaign.body_html = _blk_63.render_html" in ROUTER_SRC


def test_router_logs_block_update_audit():
    assert '"campaign.blocks_updated"' in ROUTER_SRC
