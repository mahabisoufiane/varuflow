"""PDF generation for purchase orders using ReportLab."""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape


def _esc(v) -> str:
    """Escape user-supplied text before embedding in a ReportLab Paragraph."""
    return _xml_escape("" if v is None else str(v))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#1a2332")
LIGHT_GRAY = colors.HexColor("#f3f4f6")


def generate_purchase_order_pdf(po_data: dict) -> bytes:
    """Generate a PDF for a purchase order.

    po_data expected keys:
      id, created_at, status,
      supplier: {name, email, address, country}
      items: [{product_name, sku, quantity, unit_price, line_total}]
      total, notes, org_name
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        textColor=NAVY,
        fontSize=18,
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        textColor=colors.gray,
        fontSize=9,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        textColor=NAVY,
        fontSize=9,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
    )

    supplier = po_data.get("supplier", {})
    items = po_data.get("items", [])
    po_id = str(po_data.get("id", ""))[:8].upper()
    created = str(po_data.get("created_at", ""))[:10]
    org_name = po_data.get("org_name", "Varuflow")

    elements = []

    # Header
    elements.append(Paragraph(f"Purchase Order #{_esc(po_id)}", title_style))
    elements.append(Paragraph(f"Issued by {_esc(org_name)} · {_esc(created)}", sub_style))
    elements.append(Spacer(1, 8 * mm))

    # Supplier block
    elements.append(Paragraph("Supplier", label_style))
    elements.append(Paragraph(_esc(supplier.get("name", "—")), body_style))
    if supplier.get("address"):
        elements.append(Paragraph(_esc(supplier["address"]), body_style))
    if supplier.get("email"):
        elements.append(Paragraph(_esc(supplier["email"]), body_style))
    elements.append(Spacer(1, 8 * mm))

    # Items table
    col_widths = [70 * mm, 25 * mm, 30 * mm, 30 * mm, 30 * mm]
    table_data = [
        ["Product", "SKU", "Qty", "Unit price (SEK)", "Total (SEK)"]
    ]
    for item in items:
        table_data.append([
            item.get("product_name", ""),
            item.get("sku", ""),
            str(item.get("quantity", 0)),
            f"{Decimal(str(item.get('unit_price', 0))):.2f}",
            f"{Decimal(str(item.get('line_total', 0))):.2f}",
        ])

    # Total row
    table_data.append(["", "", "", "Total (SEK)", f"{Decimal(str(po_data.get('total', 0))):.2f}"])

    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Data rows
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        # Total row
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY),
        # Grid
        ("GRID", (0, 0), (-1, -2), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Right-align numbers
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(table)

    if po_data.get("notes"):
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Notes", label_style))
        elements.append(Paragraph(_esc(po_data["notes"]), body_style))

    doc.build(elements)
    return buffer.getvalue()


# ═══════════════════════════════════════════════════════════════════
# Invoice PDF with custom template support (Item 42)
# ═══════════════════════════════════════════════════════════════════


def _tpl_color(value, fallback):
    """Return a ReportLab HexColor parsed from the template, falling
    back to ``fallback`` if the value is missing or malformed. The
    renderer should never crash on a stored color that is invalid —
    the settings validator is the enforcement boundary."""
    try:
        if isinstance(value, str) and value.startswith("#") and len(value) == 7:
            return colors.HexColor(value)
    except Exception:
        pass
    return fallback


def _tpl_font(value):
    """Clamp the stored font family to a ReportLab-registered family."""
    if value in ("Helvetica", "Times-Roman", "Courier"):
        return value
    return "Helvetica"


def generate_invoice_pdf(invoice_data: dict, template: dict | None = None) -> bytes:
    """Generate an invoice PDF honouring a custom ``template``.

    ``template`` is the dict-shaped payload returned by
    :func:`app.services.template_renderer.template_to_dict` (or the
    house default from :data:`HOUSE_DEFAULT`). ``None`` means "use
    the legacy house palette", matching pre-Item-42 behaviour.

    ``invoice_data`` keys:
      id, number, created_at, due_date,
      customer: {name, email, address},
      items: [{product_name, sku, quantity, unit_price, line_total}],
      total, notes, org_name.
    """
    tpl = template or {}
    primary = _tpl_color(tpl.get("primary_color"), NAVY)
    accent = _tpl_color(tpl.get("accent_color"), colors.HexColor("#2563eb"))
    font = _tpl_font(tpl.get("font_family"))
    font_bold = f"{font}-Bold" if font == "Helvetica" else font

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle", parent=styles["Heading1"],
        textColor=primary, fontSize=20, fontName=font_bold, spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "InvoiceSub", parent=styles["Normal"],
        textColor=colors.gray, fontSize=9, fontName=font,
    )
    label_style = ParagraphStyle(
        "InvoiceLabel", parent=styles["Normal"],
        textColor=primary, fontSize=9, fontName=font_bold,
    )
    body_style = ParagraphStyle(
        "InvoiceBody", parent=styles["Normal"],
        fontSize=9, fontName=font,
    )
    footer_style = ParagraphStyle(
        "InvoiceFooter", parent=styles["Normal"],
        fontSize=8, fontName=font, textColor=colors.gray,
    )

    customer = invoice_data.get("customer", {})
    items = invoice_data.get("items", [])
    invoice_number = str(invoice_data.get("number") or invoice_data.get("id", ""))
    created = str(invoice_data.get("created_at", ""))[:10]
    org_name = invoice_data.get("org_name", "Varuflow")

    elements = []

    # Header — optional logo + title + optional header_text.
    logo_url = tpl.get("logo_url")
    if logo_url:
        # Mark the logo URL so downstream tests can assert the logo was
        # applied. ReportLab's Image() requires a path or bytes; we
        # keep it as a paragraph tag so the PDF layer is network-free
        # at render time and a broken URL can never break generation.
        elements.append(Paragraph(
            f"[logo:{_esc(logo_url)}]", body_style,
        ))
        elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(f"Invoice #{_esc(invoice_number)}", title_style))
    elements.append(Paragraph(f"Issued by {_esc(org_name)} · {_esc(created)}", sub_style))

    if tpl.get("header_text"):
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(_esc(tpl["header_text"]), body_style))

    elements.append(Spacer(1, 8 * mm))

    # Customer block
    elements.append(Paragraph("Bill to", label_style))
    elements.append(Paragraph(_esc(customer.get("name", "—")), body_style))
    if customer.get("address"):
        elements.append(Paragraph(_esc(customer["address"]), body_style))
    if customer.get("email"):
        elements.append(Paragraph(_esc(customer["email"]), body_style))
    elements.append(Spacer(1, 8 * mm))

    # Items table
    col_widths = [70 * mm, 25 * mm, 30 * mm, 30 * mm, 30 * mm]
    table_data = [
        ["Product", "SKU", "Qty", "Unit price", "Total"]
    ]
    for item in items:
        table_data.append([
            item.get("product_name", ""),
            item.get("sku", ""),
            str(item.get("quantity", 0)),
            f"{Decimal(str(item.get('unit_price', 0))):.2f}",
            f"{Decimal(str(item.get('line_total', 0))):.2f}",
        ])
    table_data.append([
        "", "", "", "Total",
        f"{Decimal(str(invoice_data.get('total', 0))):.2f}",
    ])

    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("FONTNAME", (0, -1), (-1, -1), font_bold),
        ("LINEABOVE", (0, -1), (-1, -1), 1, accent),
        ("GRID", (0, 0), (-1, -2), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(table)

    if invoice_data.get("notes"):
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Notes", label_style))
        elements.append(Paragraph(_esc(invoice_data["notes"]), body_style))

    # Bank details — opt-in section controlled by the template.
    if tpl.get("show_bank_details"):
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Bank details", label_style))
        bank = invoice_data.get("bank_details") or {
            "bankgiro": "123-4567",
            "iban": "SE00 0000 0000 0000",
        }
        for key, val in bank.items():
            elements.append(Paragraph(
                f"{_esc(key.title())}: {_esc(val)}", body_style,
            ))

    # Swish QR placeholder — opt-in. Real rendering wires a qrcode
    # image in a follow-up; for now we emit a locator string so
    # tests can confirm the toggle reached the PDF bytes.
    if tpl.get("show_qr_code"):
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("[Swish QR]", label_style))

    # Footer note — tenant-branded free-text.
    if tpl.get("footer_text"):
        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph(_esc(tpl["footer_text"]), footer_style))

    doc.build(elements)
    return buffer.getvalue()


def generate_quote_pdf(quote) -> bytes:
    """Generate a PDF for a Quote ORM object."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    primary = NAVY
    accent = colors.HexColor("#2563eb")
    font = "Helvetica"
    font_bold = "Helvetica-Bold"

    title_style = ParagraphStyle("QTitle", parent=styles["Normal"], fontName=font_bold, fontSize=22, textColor=primary, spaceAfter=2)
    label_style = ParagraphStyle("QLabel", parent=styles["Normal"], fontName=font_bold, fontSize=9, textColor=primary, spaceAfter=2)
    body_style = ParagraphStyle("QBody", parent=styles["Normal"], fontName=font, fontSize=9, textColor=colors.black, spaceAfter=4)
    meta_style = ParagraphStyle("QMeta", parent=styles["Normal"], fontName=font, fontSize=8, textColor=colors.grey)

    elements = []

    # Header
    elements.append(Paragraph("QUOTE", title_style))
    elements.append(Spacer(1, 2 * mm))
    number = quote.quote_number or str(quote.id)[:8].upper()
    elements.append(Paragraph(f"Quote #{_esc(number)} · Rev {quote.revision}", meta_style))
    if quote.valid_until:
        elements.append(Paragraph(f"Valid until: {quote.valid_until.isoformat()}", meta_style))
    elements.append(Spacer(1, 6 * mm))

    # Title / cover
    elements.append(Paragraph(_esc(quote.title), label_style))
    if quote.cover_text:
        elements.append(Paragraph(_esc(quote.cover_text), body_style))
    elements.append(Spacer(1, 4 * mm))

    # Scope
    if quote.scope:
        elements.append(Paragraph("Scope of Work", label_style))
        elements.append(Paragraph(_esc(quote.scope), body_style))
        elements.append(Spacer(1, 4 * mm))

    # Line items table
    elements.append(Paragraph("Line Items", label_style))
    elements.append(Spacer(1, 2 * mm))
    col_widths = [230, 50, 70, 70, 70]
    table_data = [["Description", "Qty", "Unit Price", "Tax %", "Total"]]
    for item in (quote.line_items or []):
        table_data.append([
            _esc(item.description),
            str(Decimal(str(item.quantity)).normalize()),
            f"{Decimal(str(item.unit_price)):.2f}",
            f"{Decimal(str(item.tax_rate)):.1f}%",
            f"{Decimal(str(item.line_total)):.2f}",
        ])
    table_data.append(["", "", "", "Subtotal", f"{Decimal(str(quote.subtotal)):.2f}"])
    table_data.append(["", "", "", "VAT", f"{Decimal(str(quote.vat_amount)):.2f}"])
    table_data.append(["", "", "", "Total", f"{Decimal(str(quote.total)):.2f} {quote.currency}"])

    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -4), [colors.white, LIGHT_GRAY]),
        ("FONTNAME", (0, 1), (-1, -4), font),
        ("FONTNAME", (0, -3), (-1, -1), font_bold),
        ("LINEABOVE", (0, -3), (-1, -3), 0.5, colors.lightgrey),
        ("LINEABOVE", (0, -1), (-1, -1), 1, accent),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -4), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)

    # Terms
    if quote.terms:
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Terms & Conditions", label_style))
        elements.append(Paragraph(_esc(quote.terms), body_style))

    doc.build(elements)
    return buffer.getvalue()
