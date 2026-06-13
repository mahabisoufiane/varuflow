"""Pure helpers for the inline email campaign block editor (Item 63).

Operators compose campaign bodies from typed blocks; we validate
the structure and render it to safe HTML + a plain-text fallback.

Supported block types
---------------------
* ``heading``   — { text, level: 1|2|3 }
* ``paragraph`` — { text }
* ``button``    — { text, url }
* ``image``     — { url, alt?, width? }
* ``divider``   — {}
* ``spacer``    — { height: 8..80 }

All user-supplied strings are HTML-escaped before being inserted
into the rendered markup. URLs must start with ``http://`` or
``https://`` (or ``mailto:`` for buttons) — no ``javascript:``
vectors.
"""
from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

ALLOWED_TYPES: frozenset[str] = frozenset({
    "heading", "paragraph", "button", "image", "divider", "spacer",
})
ALLOWED_HEADING_LEVELS: frozenset[int] = frozenset({1, 2, 3})
ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https"})
ALLOWED_BUTTON_SCHEMES: frozenset[str] = frozenset({"http", "https", "mailto"})

MAX_BLOCKS: int = 50
MAX_TEXT_LENGTH: int = 2_000
MAX_URL_LENGTH: int = 500
MAX_ALT_LENGTH: int = 160
MIN_SPACER: int = 8
MAX_SPACER: int = 80
MIN_IMAGE_WIDTH: int = 16
MAX_IMAGE_WIDTH: int = 1_200


def _require_keys(block: dict, required: set[str], optional: set[str]) -> None:
    got = set(block.keys()) - {"type"}
    unknown = got - (required | optional)
    if unknown:
        raise ValueError(f"unknown keys for block: {sorted(unknown)}")
    missing = required - got
    if missing:
        raise ValueError(f"missing keys for block: {sorted(missing)}")


def _require_text(value: Any, *, field: str, max_len: int = MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    if len(value) > max_len:
        raise ValueError(f"{field} too long ({max_len} chars max)")
    return value


def _require_url(value: Any, *, schemes: frozenset[str]) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("url is required")
    if len(value) > MAX_URL_LENGTH:
        raise ValueError(f"url too long ({MAX_URL_LENGTH} chars max)")
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        raise ValueError(
            f"url scheme must be one of {sorted(schemes)}"
        )
    # mailto uses `path`; http(s) requires a netloc.
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise ValueError("url must include a host")
    if parsed.scheme == "mailto" and not parsed.path:
        raise ValueError("mailto must include an address")
    return value


def validate_block(block: Any) -> dict:
    if not isinstance(block, dict):
        raise ValueError("block must be an object")
    btype = block.get("type")
    if btype not in ALLOWED_TYPES:
        raise ValueError(
            f"block.type must be one of {sorted(ALLOWED_TYPES)}"
        )

    if btype == "heading":
        _require_keys(block, {"text", "level"}, set())
        text = _require_text(block["text"], field="heading.text", max_len=240)
        level = block["level"]
        if level not in ALLOWED_HEADING_LEVELS:
            raise ValueError("heading.level must be 1, 2 or 3")
        return {"type": "heading", "text": text, "level": int(level)}

    if btype == "paragraph":
        _require_keys(block, {"text"}, set())
        return {
            "type": "paragraph",
            "text": _require_text(block["text"], field="paragraph.text"),
        }

    if btype == "button":
        _require_keys(block, {"text", "url"}, set())
        return {
            "type": "button",
            "text": _require_text(block["text"], field="button.text", max_len=80),
            "url": _require_url(block["url"], schemes=ALLOWED_BUTTON_SCHEMES),
        }

    if btype == "image":
        _require_keys(block, {"url"}, {"alt", "width"})
        url = _require_url(block["url"], schemes=ALLOWED_URL_SCHEMES)
        alt = block.get("alt")
        if alt is not None:
            if not isinstance(alt, str):
                raise ValueError("image.alt must be a string")
            if len(alt) > MAX_ALT_LENGTH:
                raise ValueError(
                    f"image.alt too long ({MAX_ALT_LENGTH} chars max)"
                )
        width = block.get("width")
        if width is not None:
            if not isinstance(width, int) or isinstance(width, bool):
                raise ValueError("image.width must be an integer")
            if width < MIN_IMAGE_WIDTH or width > MAX_IMAGE_WIDTH:
                raise ValueError(
                    f"image.width must be {MIN_IMAGE_WIDTH}..{MAX_IMAGE_WIDTH}"
                )
        out: dict = {"type": "image", "url": url}
        if alt is not None:
            out["alt"] = alt
        if width is not None:
            out["width"] = width
        return out

    if btype == "divider":
        _require_keys(block, set(), set())
        return {"type": "divider"}

    if btype == "spacer":
        _require_keys(block, {"height"}, set())
        h = block["height"]
        if not isinstance(h, int) or isinstance(h, bool):
            raise ValueError("spacer.height must be an integer")
        if h < MIN_SPACER or h > MAX_SPACER:
            raise ValueError(f"spacer.height must be {MIN_SPACER}..{MAX_SPACER}")
        return {"type": "spacer", "height": h}

    # Unreachable — ALLOWED_TYPES is exhaustive above.
    raise ValueError(f"unsupported block type: {btype}")


def validate_blocks(blocks: Any) -> list[dict]:
    if not isinstance(blocks, list):
        raise ValueError("blocks must be a list")
    if not blocks:
        raise ValueError("at least one block is required")
    if len(blocks) > MAX_BLOCKS:
        raise ValueError(f"too many blocks ({MAX_BLOCKS} max)")
    return [validate_block(b) for b in blocks]


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_html(blocks: list[dict]) -> str:
    """Render validated blocks to safe, email-client-friendly HTML."""
    parts: list[str] = []
    for b in blocks:
        t = b["type"]
        if t == "heading":
            parts.append(f"<h{b['level']}>{_esc(b['text'])}</h{b['level']}>")
        elif t == "paragraph":
            # Preserve single newlines as <br> while escaping content.
            safe = _esc(b["text"]).replace("\n", "<br>")
            parts.append(f"<p>{safe}</p>")
        elif t == "button":
            parts.append(
                '<p><a href="'
                + _esc(b["url"])
                + '" style="display:inline-block;padding:12px 20px;'
                  'background:#000;color:#fff;text-decoration:none;'
                  'border-radius:4px">'
                + _esc(b["text"])
                + "</a></p>"
            )
        elif t == "image":
            attrs = ['src="' + _esc(b["url"]) + '"']
            attrs.append('alt="' + _esc(b.get("alt", "")) + '"')
            if "width" in b:
                attrs.append(f'width="{int(b["width"])}"')
            attrs.append('style="max-width:100%;height:auto"')
            parts.append("<p><img " + " ".join(attrs) + "></p>")
        elif t == "divider":
            parts.append(
                '<hr style="border:none;border-top:1px solid #ddd;margin:24px 0">'
            )
        elif t == "spacer":
            parts.append(
                f'<div style="height:{int(b["height"])}px;line-height:'
                f'{int(b["height"])}px">&nbsp;</div>'
            )
    return "".join(parts)


def render_text(blocks: list[dict]) -> str:
    """Plain-text version for multipart/alternative."""
    lines: list[str] = []
    for b in blocks:
        t = b["type"]
        if t == "heading":
            lines.append(b["text"])
            lines.append("")
        elif t == "paragraph":
            lines.append(b["text"])
            lines.append("")
        elif t == "button":
            lines.append(f"{b['text']}: {b['url']}")
            lines.append("")
        elif t == "image":
            alt = b.get("alt")
            lines.append(f"[{alt}]" if alt else "[image]")
            lines.append(b["url"])
            lines.append("")
        elif t == "divider":
            lines.append("---")
            lines.append("")
        elif t == "spacer":
            lines.append("")
    # Trim trailing blank lines.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
