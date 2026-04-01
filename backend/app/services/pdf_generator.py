"""PDF generation for purchase orders using ReportLab."""
from decimal import Decimal
from io import BytesIO

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
    elements.append(Paragraph(f"Purchase Order #{po_id}", title_style))
    elements.append(Paragraph(f"Issued by {org_name} · {created}", sub_style))
    elements.append(Spacer(1, 8 * mm))

    # Supplier block
    elements.append(Paragraph("Supplier", label_style))
    elements.append(Paragraph(supplier.get("name", "—"), body_style))
    if supplier.get("address"):
        elements.append(Paragraph(supplier["address"], body_style))
    if supplier.get("email"):
        elements.append(Paragraph(supplier["email"], body_style))
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
        elements.append(Paragraph(po_data["notes"], body_style))

    doc.build(elements)
    return buffer.getvalue()
