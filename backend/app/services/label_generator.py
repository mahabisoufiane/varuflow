"""Barcode / QR label PDF generator (Item 36).

Pure PDF builder — takes a list of label dicts + options and returns
``bytes``. No DB access, no ORM imports: unit-testable and safe to run
from any worker.

Each label carries:
    * ``name`` — product name (truncated to fit)
    * ``sku`` — SKU code (shown as text)
    * ``price`` — optional; hidden when :data:`LabelOptions.show_price`
      is false or price is ``None``
    * ``barcode`` — payload encoded as Code128 or embedded as a QR

Supported page sizes (see :data:`LABEL_SIZES`):
    * ``38x25``  — 38×25 mm, single label per page, thermal printer
    * ``50x30``  — 50×30 mm, single label per page, thermal printer
    * ``a4``     — A4 sheet, 3×10 grid = 30 labels per page (standard
                   70×29 mm office stickers)

The generator intentionally produces the *same layout* for a single
label and a bulk list; callers pass one entry for a single PDF.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from typing import Any, Iterable, Literal

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

LabelSize = Literal["38x25", "50x30", "a4"]
BarcodeFormat = Literal["code128", "qr"]

# ``(page_width_mm, page_height_mm, cols, rows, label_w_mm, label_h_mm)``
LABEL_SIZES: dict[str, tuple[float, float, int, int, float, float]] = {
    "38x25": (38.0, 25.0, 1, 1, 38.0, 25.0),
    "50x30": (50.0, 30.0, 1, 1, 50.0, 30.0),
    # A4 sheet: 3 columns × 10 rows = 30 labels, 70×29 mm each.
    "a4": (210.0, 297.0, 3, 10, 70.0, 29.0),
}


@dataclass
class LabelOptions:
    size: LabelSize = "50x30"
    format: BarcodeFormat = "code128"
    show_price: bool = True
    show_logo: bool = False
    # ``currency`` is suffixed on the price line. Free-text so the
    # caller can pass 'kr', 'EUR', '$', etc. without the generator
    # needing to understand currency rules.
    currency: str = "kr"


# ═══════════════════════════════════════════════════════════════════
# Pure helpers
# ═══════════════════════════════════════════════════════════════════


def validate_size(size: Any) -> str:
    """Return a canonical size key or raise ``ValueError``."""
    key = str(size or "").lower().strip()
    if key not in LABEL_SIZES:
        raise ValueError(f"unsupported_label_size: {size!r}")
    return key


def validate_format(fmt: Any) -> str:
    """Return a canonical barcode-format key or raise ``ValueError``."""
    key = str(fmt or "").lower().strip()
    if key not in ("code128", "qr"):
        raise ValueError(f"unsupported_barcode_format: {fmt!r}")
    return key


def normalise_label(raw: dict) -> dict:
    """Defensive coercion — guarantees the drawing code can read fields.

    Every label passed through :func:`generate_label_pdf` is put
    through this so the generator never raises on missing keys.
    """
    name = str(raw.get("name") or "").strip()
    sku = str(raw.get("sku") or "").strip()
    barcode = str(raw.get("barcode") or raw.get("sku") or "").strip()
    price_raw = raw.get("price", None)
    price: Decimal | None
    if price_raw is None or price_raw == "":
        price = None
    else:
        try:
            price = Decimal(str(price_raw))
        except Exception:
            price = None
    return {
        "name": name[:80],
        "sku": sku[:60],
        "barcode": barcode[:120],
        "price": price,
    }


def format_price(price: Decimal | None, currency: str) -> str | None:
    if price is None:
        return None
    return f"{price:.2f} {currency}"


def truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1] + "…"


# ═══════════════════════════════════════════════════════════════════
# Drawing primitives (pure — take reportlab ``canvas`` but no DB)
# ═══════════════════════════════════════════════════════════════════


def _draw_label(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    label: dict,
    options: LabelOptions,
) -> None:
    """Draw one label at ``(x, y)`` with lower-left origin.

    Widths and heights are in points (reportlab default). The
    generator uses ``mm`` multiplier when calling this.
    """
    name = truncate(label["name"], max_chars=28)
    sku = label["sku"]
    price_text = format_price(label["price"], options.currency) if options.show_price else None

    pad = 2 * mm

    # Product name (top).
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + pad, y + height - 3 * mm, name)

    # SKU line.
    c.setFont("Helvetica", 6)
    c.drawString(x + pad, y + height - 6 * mm, f"SKU: {sku}")

    # Price (top-right) when enabled.
    if price_text:
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(x + width - pad, y + height - 4 * mm, price_text)

    # Barcode (bottom half).
    payload = label["barcode"] or sku or name or "-"
    bc_area_top = y + height - 8 * mm
    bc_area_bottom = y + pad
    bc_area_h = bc_area_top - bc_area_bottom
    if bc_area_h < 5 * mm:
        return

    if options.format == "qr":
        qr_size = min(width - 2 * pad, bc_area_h)
        qr = QrCodeWidget(payload, barLevel="M")
        bounds = qr.getBounds()
        qr_w = bounds[2] - bounds[0]
        qr_h = bounds[3] - bounds[1]
        if qr_w > 0 and qr_h > 0:
            d = Drawing(qr_size, qr_size, transform=[qr_size / qr_w, 0, 0, qr_size / qr_h, 0, 0])
            d.add(qr)
            renderPDF.draw(d, c, x + (width - qr_size) / 2, bc_area_bottom)
    else:
        # Code128 — barWidth tuned so a typical 12-char SKU fits into
        # the label width with a small margin.
        available_w = width - 2 * pad
        bar_width = max(0.3, min(0.6, available_w / (len(payload) * 11 + 35)))
        bar_height = max(5 * mm, bc_area_h - 3 * mm)
        bc = code128.Code128(
            payload, barWidth=bar_width, barHeight=bar_height, humanReadable=True
        )
        bc_w = bc.width
        bc.drawOn(c, x + (width - bc_w) / 2, bc_area_bottom)


# ═══════════════════════════════════════════════════════════════════
# Public entry points
# ═══════════════════════════════════════════════════════════════════


def generate_label_pdf(
    labels: Iterable[dict],
    options: LabelOptions | None = None,
) -> bytes:
    """Return a PDF document for ``labels`` using ``options``.

    ``labels`` can be a single-entry iterable for a one-off label, or
    many for a bulk batch. The layout (single vs. sheet) is picked
    by ``options.size``. The function never raises on missing keys
    within an individual label — they're normalised — but *does*
    raise ``ValueError`` for unsupported sizes / formats.
    """
    opts = options or LabelOptions()
    size_key = validate_size(opts.size)
    fmt_key = validate_format(opts.format)
    # Reassign so the dataclass stays in sync with validated values.
    opts = LabelOptions(
        size=size_key,  # type: ignore[arg-type]
        format=fmt_key,  # type: ignore[arg-type]
        show_price=opts.show_price,
        show_logo=opts.show_logo,
        currency=opts.currency or "kr",
    )
    page_w_mm, page_h_mm, cols, rows, label_w_mm, label_h_mm = LABEL_SIZES[size_key]
    page_size = (page_w_mm * mm, page_h_mm * mm)
    label_w = label_w_mm * mm
    label_h = label_h_mm * mm

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=page_size)
    c.setTitle("Varuflow labels")

    normalised = [normalise_label(raw) for raw in labels]
    if not normalised:
        # Blank page is fine — but emit a single empty page so the
        # PDF is still a valid download. Most printers will eject a
        # blank sheet without complaint.
        c.showPage()
        c.save()
        return buf.getvalue()

    per_page = cols * rows
    # Margin inside the A4 sheet; ignored for single-label stocks.
    sheet_margin_x = (page_size[0] - cols * label_w) / 2 if size_key == "a4" else 0
    sheet_margin_y = (page_size[1] - rows * label_h) / 2 if size_key == "a4" else 0

    for idx, lbl in enumerate(normalised):
        on_page = idx % per_page
        if on_page == 0 and idx != 0:
            c.showPage()
        col = on_page % cols
        row = on_page // cols
        # Lower-left origin: fill rows top-to-bottom.
        x = sheet_margin_x + col * label_w
        y = page_size[1] - sheet_margin_y - (row + 1) * label_h
        _draw_label(c, x=x, y=y, width=label_w, height=label_h, label=lbl, options=opts)

    c.showPage()
    c.save()
    return buf.getvalue()


def labels_per_sheet(size: str) -> int:
    """How many labels fit on one page for a given size."""
    key = validate_size(size)
    _, _, cols, rows, _, _ = LABEL_SIZES[key]
    return cols * rows
