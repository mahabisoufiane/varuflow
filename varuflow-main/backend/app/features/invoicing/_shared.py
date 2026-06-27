"""Shared invoicing helpers: org/number utilities, the per-invoice outbound
email cooldown, and the PDF / Peppol UBL / Norwegian EHF document generators.

Kept apart from the route modules so it imports without a router, and is
re-exported from this package's __init__ for portal / gdpr / einvoice /
recurring_send, which depend on these generators.
"""
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Invoice

log = logging.getLogger(__name__)

NAVY = colors.HexColor("#1a2332")
LIGHT_GRAY = colors.HexColor("#f3f4f6")


import time as _time_mod

_EMAIL_COOLDOWN_SECS = 60
_invoice_email_cooldown: dict[tuple[str, str, str], float] = {}


def _check_invoice_email_cooldown(org_id: uuid.UUID, invoice_id: uuid.UUID, kind: str) -> None:
    key = (str(org_id), str(invoice_id), kind)
    now = _time_mod.monotonic()
    prev = _invoice_email_cooldown.get(key, 0.0)
    if now - prev < _EMAIL_COOLDOWN_SECS:
        retry = int(_EMAIL_COOLDOWN_SECS - (now - prev)) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {retry}s before resending this invoice.",
        )
    _invoice_email_cooldown[key] = now
    # Bound memory: if the dict gets big, evict entries older than the
    # cooldown window. Happens at O(N) but only when we're over 10k keys,
    # which is already pathological.
    if len(_invoice_email_cooldown) > 10_000:
        cutoff = now - _EMAIL_COOLDOWN_SECS * 2
        for k in [k for k, t in _invoice_email_cooldown.items() if t < cutoff]:
            _invoice_email_cooldown.pop(k, None)


def _pdf_esc(v) -> str:
    """Escape a user-supplied string for safe embedding in a ReportLab
    Paragraph. ReportLab parses its input as mini-XML, so raw ``<``/``&`` in
    customer data (company name, address, invoice description, notes, …)
    either breaks rendering or lets the data alter the document's markup.
    Always wrap untrusted text with this helper before ``Paragraph(...)``.
    """
    return _xml_escape("" if v is None else str(v))

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _invoice_number(org_id: uuid.UUID, sequence: int) -> str:
    year = datetime.now(UTC).year
    return f"INV-{year}-{sequence:04d}"

def _tax_subtotals_by_rate(inv: Invoice) -> list[tuple[Decimal, Decimal, Decimal]]:
    """Group invoice lines by `tax_rate` and return one subtotal per rate.

    Returns a list of ``(rate, taxable_amount, tax_amount)`` tuples ordered
    by rate. Peppol BIS 3.0 validators enforce
    ``TaxableAmount * Percent / 100 == TaxAmount`` per ``<TaxSubtotal>`` and
    require one entry per distinct rate. Hardcoding a single 25% category
    breaks on every non-25% line item (Swedish 12% food, 6% books;
    Norwegian 15% food) and the receiver silently rejects the submission.
    """
    buckets: dict[Decimal, list[Decimal]] = {}
    for li in inv.line_items:
        rate = Decimal(li.tax_rate)
        taxable = Decimal(li.line_total)
        tax_amt = (taxable * rate / Decimal(100)).quantize(Decimal("0.01"))
        bucket = buckets.setdefault(rate, [Decimal("0.00"), Decimal("0.00")])
        bucket[0] += taxable
        bucket[1] += tax_amt
    return [(rate, vals[0], vals[1]) for rate, vals in sorted(buckets.items())]


def _generate_invoice_pdf(inv: Invoice) -> bytes:
    """Render the invoice as a branded A4 PDF using ReportLab.

    The function header was previously lost during a refactor, leaving this
    body as unreachable dead code inside `_tax_subtotals_by_rate`. Every
    call site (/invoices/{id}/pdf, /invoices/{id}/send, the portal PDF
    download) then raised NameError → 500 to the customer.
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
    title_style = ParagraphStyle("T", parent=styles["Heading1"], textColor=NAVY, fontSize=18, spaceAfter=4)
    sub_style = ParagraphStyle("S", parent=styles["Normal"], textColor=colors.gray, fontSize=9)
    label_style = ParagraphStyle("L", parent=styles["Normal"], textColor=NAVY, fontSize=9, fontName="Helvetica-Bold")
    body_style = ParagraphStyle("B", parent=styles["Normal"], fontSize=9)

    c = inv.customer
    elements = []

    # Header
    elements.append(Paragraph(f"Invoice {_pdf_esc(inv.invoice_number)}", title_style))
    elements.append(Paragraph(
        f"Issued: {_pdf_esc(inv.issue_date)} · Due: {_pdf_esc(inv.due_date)} · Status: {_pdf_esc(inv.status)}",
        sub_style,
    ))
    elements.append(Spacer(1, 8 * mm))

    # Bill to
    elements.append(Paragraph("Bill To", label_style))
    elements.append(Paragraph(_pdf_esc(c.company_name), body_style))
    if c.org_number:
        elements.append(Paragraph(f"Org nr: {_pdf_esc(c.org_number)}", body_style))
    if c.vat_number:
        elements.append(Paragraph(f"VAT: {_pdf_esc(c.vat_number)}", body_style))
    if c.address:
        elements.append(Paragraph(_pdf_esc(c.address), body_style))
    if c.email:
        elements.append(Paragraph(_pdf_esc(c.email), body_style))
    elements.append(Spacer(1, 8 * mm))

    # Line items table
    # Table cells are rendered as literal strings (not XML-parsed) so we
    # don't escape `li.description` here; escaping would show "&amp;" etc.
    col_widths = [85 * mm, 20 * mm, 25 * mm, 20 * mm, 30 * mm]
    table_data = [["Description", "Qty", "Unit price", "VAT %", "Total (SEK)"]]
    for li in inv.line_items:
        table_data.append([
            li.description,
            str(li.quantity),
            f"{li.unit_price:.2f}",
            f"{li.tax_rate:.0f}%",
            f"{li.line_total:.2f}",
        ])

    # Subtotal / VAT / Total rows
    table_data.append(["", "", "", "Subtotal", f"{inv.subtotal:.2f}"])
    table_data.append(["", "", "", "VAT", f"{inv.vat_amount:.2f}"])
    table_data.append(["", "", "", "Total (SEK)", f"{inv.total_sek:.2f}"])

    inv_type = getattr(inv, "invoice_type", "standard")
    dep_amt = getattr(inv, "deposit_amount", None)
    has_deposit_offset = inv_type == "final" and dep_amt and Decimal(str(dep_amt)) > 0
    if has_deposit_offset:
        dep = Decimal(str(dep_amt))
        total_due = (inv.total_sek - dep).quantize(Decimal("0.01"))
        table_data.append(["", "", "", "Less deposit paid", f"-{dep:.2f}"])
        table_data.append(["", "", "", "Total due (SEK)", f"{total_due:.2f}"])

    n_summary = 5 if has_deposit_offset else 3
    bg_end = -(n_summary + 1)
    n = len(table_data)
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, bg_end), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        # Summary rows bold
        ("FONTNAME", (3, n - n_summary), (-1, n - 1), "Helvetica-Bold"),
        ("LINEABOVE", (3, n - n_summary), (-1, n - n_summary), 0.5, colors.lightgrey),
        ("LINEABOVE", (3, n - 1), (-1, n - 1), 1, NAVY),
        ("GRID", (0, 0), (-1, bg_end), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(table)

    if inv.notes:
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Notes", label_style))
        elements.append(Paragraph(_pdf_esc(inv.notes), body_style))

    doc.build(elements)
    return buffer.getvalue()


def _generate_peppol_xml(inv: Invoice, org) -> bytes:
    """Generate a Peppol BIS Billing 3.0 compliant UBL 2.1 XML invoice."""
    c = inv.customer
    org_name = org.name if org else "Varuflow"
    org_vat = org.vat_number if org and org.vat_number else "SE000000000001"

    lines_xml = ""
    for idx, li in enumerate(inv.line_items, start=1):
        lines_xml += f"""
    <cac:InvoiceLine>
      <cbc:ID>{idx}</cbc:ID>
      <cbc:InvoicedQuantity unitCode="C62">{li.quantity}</cbc:InvoicedQuantity>
      <cbc:LineExtensionAmount currencyID="SEK">{li.line_total:.2f}</cbc:LineExtensionAmount>
      <cac:Item>
        <cbc:Name>{_xml_escape(li.description)}</cbc:Name>
        <cac:ClassifiedTaxCategory>
          <cbc:ID>S</cbc:ID>
          <cbc:Percent>{li.tax_rate:.2f}</cbc:Percent>
          <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
        </cac:ClassifiedTaxCategory>
      </cac:Item>
      <cac:Price>
        <cbc:PriceAmount currencyID="SEK">{li.unit_price:.2f}</cbc:PriceAmount>
      </cac:Price>
    </cac:InvoiceLine>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ubl:Invoice xmlns:ubl="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>{_xml_escape(inv.invoice_number)}</cbc:ID>
  <cbc:IssueDate>{inv.issue_date}</cbc:IssueDate>
  <cbc:DueDate>{inv.due_date}</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SEK</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{_xml_escape(org_name)}</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{_xml_escape(org_vat)}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{_xml_escape(c.company_name)}</cbc:Name></cac:PartyName>
      {f'<cac:PartyTaxScheme><cbc:CompanyID>{_xml_escape(c.vat_number)}</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>' if c.vat_number else ''}
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="SEK">{inv.vat_amount:.2f}</cbc:TaxAmount>
    {''.join(f'''<cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="SEK">{taxable:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="SEK">{tax_amt:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>''' for rate, taxable, tax_amt in _tax_subtotals_by_rate(inv))}
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="SEK">{inv.subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="SEK">{inv.subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="SEK">{inv.total_sek:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="SEK">{inv.total_sek:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  {lines_xml}
</ubl:Invoice>"""
    return xml.encode("utf-8")


def _generate_ehf_xml(inv: Invoice, org) -> bytes:
    """Generate Norwegian EHF Billing 3.0 XML for delivery to Norwegian buyers.

    Note on currency: Varuflow stores invoice totals in SEK (see
    ``Invoice.total_sek`` / ``Invoice.subtotal`` — the data model has no
    FX / multi-currency columns today). We therefore declare the XML's
    ``DocumentCurrencyCode`` as SEK so the declared currency matches the
    numbers actually emitted. EHF 3.0 allows any ISO-4217 code in the
    supplier's currency; declaring NOK while writing SEK figures would
    silently ship the buyer an invoice for 10 000 NOK (≈9 000 SEK) when
    the seller billed 10 000 SEK — an FX error of 5-15 % that breaks the
    BFL audit trail and the buyer's accounts-payable match. When we add
    NOK billing support, emit NOK currency and the NOK amount column
    together, never one without the other.
    """
    c = inv.customer
    org_name = _xml_escape(org.name if org else "Varuflow")
    # vat_number is a free-form text column — any "&", "<" or ">" would
    # otherwise produce invalid XML that Peppol validators reject, silently
    # breaking B2B delivery. Strip the country/scheme prefix BEFORE escaping
    # so the replace() pattern still matches raw text.
    raw_vat = (org.vat_number if org and org.vat_number else "NO000000000MVA")
    org_vat = _xml_escape(raw_vat)
    endpoint_id = _xml_escape(raw_vat.replace("NO", "").replace("MVA", "").strip())
    currency = "SEK"

    lines_xml = ""
    for idx, li in enumerate(inv.line_items, start=1):
        lines_xml += f"""
  <cac:InvoiceLine>
    <cbc:ID>{idx}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">{li.quantity}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{currency}">{li.line_total:.2f}</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>{_xml_escape(li.description)}</cbc:Name>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{li.tax_rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="{currency}">{li.unit_price:.2f}</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>{_xml_escape(inv.invoice_number)}</cbc:ID>
  <cbc:IssueDate>{inv.issue_date}</cbc:IssueDate>
  <cbc:DueDate>{inv.due_date}</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cbc:EndpointID schemeID="0192">{endpoint_id}</cbc:EndpointID>
      <cac:PartyName><cbc:Name>{org_name}</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{org_vat}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{_xml_escape(c.company_name)}</cbc:Name></cac:PartyName>
      {f'<cac:PostalAddress><cbc:StreetName>{_xml_escape(c.address)}</cbc:StreetName><cac:Country><cbc:IdentificationCode>NO</cbc:IdentificationCode></cac:Country></cac:PostalAddress>' if c.address else ''}
      {f'<cac:PartyTaxScheme><cbc:CompanyID>{_xml_escape(c.vat_number)}</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>' if c.vat_number else ''}
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{currency}">{inv.vat_amount:.2f}</cbc:TaxAmount>
    {''.join(f'''<cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="{currency}">{taxable:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="{currency}">{tax_amt:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>''' for rate, taxable, tax_amt in _tax_subtotals_by_rate(inv))}
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{currency}">{inv.subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{currency}">{inv.subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{currency}">{inv.total_sek:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="{currency}">{inv.total_sek:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  {lines_xml}
</Invoice>"""
    return xml.encode("utf-8")


def _xml_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


