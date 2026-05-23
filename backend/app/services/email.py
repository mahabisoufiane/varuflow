"""Email sending via Resend API using httpx."""
import html
import httpx

from app.config import settings


RESEND_URL = "https://api.resend.com/emails"


def _h(value) -> str:
    """HTML-escape any interpolated string before dropping it into a template.

    Product names, SKUs, customer names, and org names all come from user
    input — an unescaped '<' breaks rendering and at the limit could be
    used to smuggle script tags into an email client that executes them.
    """
    return html.escape(str(value) if value is not None else "", quote=True)


def _from_header(display_name: str | None, addr: str) -> str:
    """Build a safe RFC 5322 "From" header.

    Do NOT HTML-escape the display name here — email headers aren't HTML,
    and running it through `_h()` renders a customer-facing From as e.g.
    "A &amp; B AB <invoices@varuflow.app>" in every inbox that receives
    an invoice from a Swedish org whose name contains "&", "<", ">" or
    quote characters (common: "A & B AB", "Söder <Stockholm> AB").

    Must also:
      • Strip CR / LF / NUL — the three control characters that can be
        used to inject additional MIME headers (Bcc, Reply-To, etc.) via
        header-injection. The org name is owner-controlled but a typo or
        paste could still break delivery; proper sanitation costs nothing.
      • Quote the display name if it contains any RFC 5322 "specials"
        (()<>@,;:\\"[]). Inside the quoted-string, backslash-escape `"`
        and `\\`.
    """
    name = (display_name or "").strip()
    # Drop every control character the RFC disallows in unstructured text,
    # plus CR/LF/NUL which are the header-injection vectors.
    name = "".join(ch for ch in name if ord(ch) >= 0x20 and ch != "\x7f")
    if not name:
        return addr
    # RFC 5322 "specials" that force quoting of the display name.
    _SPECIALS = set('()<>@,;:\\"[]')
    if any(ch in _SPECIALS for ch in name):
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}" <{addr}>'
    return f"{name} <{addr}>"


async def send_invoice_email(
    to_email: str,
    customer_name: str,
    invoice_number: str,
    total_sek: str,
    due_date: str,
    pdf_bytes: bytes,
    org_name: str,
) -> bool:
    """Send an invoice PDF by email. Returns True on success, False if not configured."""
    if not settings.RESEND_API_KEY:
        return False  # Silently skip — Resend not configured

    import base64

    payload = {
        "from": _from_header(org_name, "invoices@varuflow.app"),
        "to": [to_email],
        "subject": f"Invoice {invoice_number} from {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Invoice {_h(invoice_number)}</h2>
          <p>Dear {_h(customer_name)},</p>
          <p>Please find attached your invoice for <strong>{_h(total_sek)} SEK</strong>, due by <strong>{_h(due_date)}</strong>.</p>
          <p style="margin-top:32px;color:#888;font-size:12px">
            Sent via Varuflow · If you have questions, please reply to this email.
          </p>
        </div>
        """,
        "attachments": [
            {
                "filename": f"{invoice_number}.pdf",
                "content": base64.b64encode(pdf_bytes).decode(),
            }
        ],
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

    return res.status_code in (200, 201)


async def send_magic_link_email(
    to_email: str,
    customer_name: str,
    magic_url: str,
    org_name: str,
) -> bool:
    """Send a portal magic-link email. Returns True on success, False if not configured."""
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "portal@varuflow.app"),
        "to": [to_email],
        "subject": f"Your secure login link — {org_name} portal",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Sign in to your portal</h2>
          <p>Hi {_h(customer_name)},</p>
          <p>Click below to securely access your invoices. This link expires in 15 minutes.</p>
          <p style="margin:24px 0">
            <a href="{_h(magic_url)}" style="background:#1a2332;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
              Open portal
            </a>
          </p>
          <p style="color:#888;font-size:12px">
            If you didn't request this link, you can safely ignore this email.<br>
            Sent via Varuflow
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

    return res.status_code in (200, 201)


async def send_supplier_portal_email(
    to_email: str,
    supplier_name: str,
    magic_url: str,
    org_name: str,
    expires_in_days: int,
) -> bool:
    """Send a supplier-portal magic-link email.

    Returns True on success, False if Resend is not configured (dev).
    Same contract as :func:`send_magic_link_email` — callers that need
    to surface a dev link to the operator check the return value and
    stash the URL in ``dev_magic_url`` on the response.
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "portal@varuflow.app"),
        "to": [to_email],
        "subject": f"Access your purchase orders — {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Supplier portal access</h2>
          <p>Hi {_h(supplier_name)},</p>
          <p>
            {_h(org_name)} has shared a secure link so you can review
            their open purchase orders and confirm acceptance.
          </p>
          <p style="margin:24px 0">
            <a href="{_h(magic_url)}" style="background:#1a2332;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
              Open supplier portal
            </a>
          </p>
          <p style="color:#888;font-size:12px">
            This link is valid for {_h(expires_in_days)} days. If you
            didn't expect it, you can safely ignore this email.<br>
            Sent via Varuflow
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

    return res.status_code in (200, 201)


async def _send_overdue_reminder(
    to_email: str,
    customer_name: str,
    invoice_number: str,
    total_sek: str,
    due_date: str,
    days_overdue: int,
    payment_url: str | None,
    org_name: str,
) -> bool:
    """Send an overdue invoice reminder. Returns True on success, False if not configured."""
    if not settings.RESEND_API_KEY:
        return False

    pay_button = ""
    if payment_url:
        pay_button = f"""
          <p style="margin:24px 0">
            <a href="{_h(payment_url)}" style="background:#dc2626;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
              Pay now — {_h(total_sek)} SEK
            </a>
          </p>"""

    urgency = "2nd reminder" if days_overdue >= 14 else "Payment reminder"
    payload = {
        "from": _from_header(org_name, "invoices@varuflow.app"),
        "to": [to_email],
        "subject": f"[{urgency}] Invoice {invoice_number} — {days_overdue} days overdue",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin-bottom:20px">
            <strong style="color:#dc2626">&#9888;&#65039; Payment overdue by {days_overdue} days</strong>
          </div>
          <h2 style="color:#1a2332">Invoice {_h(invoice_number)}</h2>
          <p>Dear {_h(customer_name)},</p>
          <p>
            This is a reminder that invoice <strong>{_h(invoice_number)}</strong> for
            <strong>{_h(total_sek)} SEK</strong> was due on <strong>{_h(due_date)}</strong>
            and is now <strong>{days_overdue} days overdue</strong>.
          </p>
          {pay_button}
          <p>If you have already arranged payment, please disregard this message.</p>
          <p style="margin-top:24px;color:#888;font-size:12px">
            Sent by {_h(org_name)} via Varuflow · Reply to this email with any questions.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

    return res.status_code in (200, 201)


async def send_low_stock_alert_email(
    to_email: str,
    org_name: str,
    low_stock_items: list[dict],
) -> bool:
    """Send a low-stock alert email. items: [{name, sku, stock, reorder_level}]."""
    if not settings.RESEND_API_KEY:
        return False

    rows = "".join(
        f"<tr><td style='padding:6px 8px;border-bottom:1px solid #eee'>{_h(i['name'])}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee;color:#888'>{_h(i['sku'])}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee;color:#dc2626;font-weight:600'>{_h(i['stock'])}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{_h(i['reorder_level'])}</td></tr>"
        for i in low_stock_items
    )

    payload = {
        "from": _from_header(org_name, "alerts@varuflow.app"),
        "to": [to_email],
        "subject": f"[Varuflow] {len(low_stock_items)} products below reorder level — {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin-bottom:20px">
            <strong style="color:#dc2626">&#9888;&#65039; Low stock alert</strong>
          </div>
          <h2 style="color:#1a2332">Stock replenishment needed</h2>
          <p>The following products have fallen below their reorder level:</p>
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
              <tr style="background:#f9fafb">
                <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Product</th>
                <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">SKU</th>
                <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">In stock</th>
                <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Reorder at</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          <p style="margin-top:24px">
            <a href="https://varuflow.se/inventory" style="background:#1a2332;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">
              View inventory
            </a>
          </p>
          <p style="margin-top:24px;color:#888;font-size:12px">Sent by Varuflow · Unsubscribe from alerts in Settings</p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL, json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_stock_transfer_request_email(
    to_email: str,
    org_name: str,
    transfer_id: str,
    from_warehouse: str,
    to_warehouse: str,
    line_count: int,
) -> bool:
    """Notify the destination warehouse that a transfer was created (Item 38).

    Returns False without raising when RESEND is unconfigured (dev), so
    the router can still commit the DB side regardless of email status.
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "stock@varuflow.app"),
        "to": [to_email],
        "subject": f"New stock transfer — {from_warehouse} → {to_warehouse}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">New stock transfer request</h2>
          <p>A stock transfer has been created and is awaiting shipment.</p>
          <table style="border-collapse:collapse;margin:16px 0">
            <tr><td style="padding:4px 12px 4px 0;color:#666">From</td><td><strong>{_h(from_warehouse)}</strong></td></tr>
            <tr><td style="padding:4px 12px 4px 0;color:#666">To</td><td><strong>{_h(to_warehouse)}</strong></td></tr>
            <tr><td style="padding:4px 12px 4px 0;color:#666">Lines</td><td>{_h(line_count)}</td></tr>
            <tr><td style="padding:4px 12px 4px 0;color:#666">Transfer</td><td style="font-family:monospace;font-size:12px">{_h(transfer_id)}</td></tr>
          </table>
          <p style="color:#888;font-size:12px">Sent by Varuflow · {_h(org_name)}</p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL, json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_stock_transfer_received_email(
    to_email: str,
    org_name: str,
    transfer_id: str,
    from_warehouse: str,
    to_warehouse: str,
    partial: bool,
) -> bool:
    """Notify the source warehouse that a transfer has been received (Item 38)."""
    if not settings.RESEND_API_KEY:
        return False

    headline = "Transfer partially received" if partial else "Transfer received"
    body = (
        "Some units were received and accounted for. The transfer remains open until the remainder is booked."
        if partial
        else "All shipped units have been received and the transfer is now closed."
    )
    payload = {
        "from": _from_header(org_name, "stock@varuflow.app"),
        "to": [to_email],
        "subject": f"{headline} — {from_warehouse} → {to_warehouse}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">{_h(headline)}</h2>
          <p>{_h(body)}</p>
          <table style="border-collapse:collapse;margin:16px 0">
            <tr><td style="padding:4px 12px 4px 0;color:#666">From</td><td><strong>{_h(from_warehouse)}</strong></td></tr>
            <tr><td style="padding:4px 12px 4px 0;color:#666">To</td><td><strong>{_h(to_warehouse)}</strong></td></tr>
            <tr><td style="padding:4px 12px 4px 0;color:#666">Transfer</td><td style="font-family:monospace;font-size:12px">{_h(transfer_id)}</td></tr>
          </table>
          <p style="color:#888;font-size:12px">Sent by Varuflow · {_h(org_name)}</p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL, json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_weekly_digest_email(
    to_email: str,
    org_name: str,
    stats: dict,
) -> bool:
    """Send a weekly digest email. stats: {revenue, sales_count, top_products, low_stock_count}."""
    if not settings.RESEND_API_KEY:
        return False

    # Use .get() — a missing 'name' or 'quantity' key on any single row must
    # not KeyError-abort the entire digest send (e.g. analytics aggregates with
    # a null product name would otherwise drop the whole email silently).
    top_rows = "".join(
        f"<li style='margin:4px 0'>{_h(p.get('name', '—'))} — <strong>{_h(p.get('quantity', 0))} units</strong></li>"
        for p in (stats.get("top_products") or [])[:5]
    )

    payload = {
        "from": "Varuflow <digest@varuflow.app>",
        "to": [to_email],
        "subject": f"Weekly digest — {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#1a2332">Your weekly summary</h2>
          <p style="color:#888">Week ending {_h(stats.get('week_ending', ''))}</p>
          <div style="display:flex;gap:16px;margin:24px 0">
            <div style="flex:1;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:28px;font-weight:700;color:#16a34a">{_h(stats.get('revenue', '0'))} kr</div>
              <div style="font-size:13px;color:#166534">Revenue</div>
            </div>
            <div style="flex:1;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:28px;font-weight:700;color:#1d4ed8">{stats.get('sales_count', 0)}</div>
              <div style="font-size:13px;color:#1e40af">Sales</div>
            </div>
            <div style="flex:1;background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:28px;font-weight:700;color:#ca8a04">{stats.get('low_stock_count', 0)}</div>
              <div style="font-size:13px;color:#854d0e">Low stock</div>
            </div>
          </div>
          {"<h3 style='color:#1a2332'>Top sellers</h3><ul>" + top_rows + "</ul>" if top_rows else ""}
          <p style="margin-top:24px">
            <a href="https://varuflow.se/analytics" style="background:#1a2332;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">
              View full report
            </a>
          </p>
          <p style="margin-top:24px;color:#888;font-size:12px">Sent by Varuflow · Manage digest settings in your account</p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL, json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_payment_link_email(
    to_email: str,
    customer_name: str,
    invoice_number: str,
    total_sek: str,
    due_date: str,
    payment_url: str,
    org_name: str,
) -> bool:
    """Send a Stripe payment link email. Returns True on success, False if not configured."""
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "invoices@varuflow.app"),
        "to": [to_email],
        "subject": f"Pay invoice {invoice_number} online — {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Invoice {_h(invoice_number)}</h2>
          <p>Dear {_h(customer_name)},</p>
          <p>Your invoice for <strong>{_h(total_sek)} SEK</strong> is due by <strong>{_h(due_date)}</strong>.</p>
          <p style="margin:24px 0">
            <a href="{_h(payment_url)}" style="background:#1a2332;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
              Pay now
            </a>
          </p>
          <p style="color:#888;font-size:12px">
            This link expires after payment or 24 hours.<br>
            Sent via Varuflow · If you have questions, reply to this email.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

    return res.status_code in (200, 201)


async def send_bokforing_reminder_email(
    to_email: str,
    org_name: str,
    year: int,
) -> bool:
    """Annual mid-January nudge to run the bokföring compliance export.

    Returns True on success, False if Resend is not configured. Failure to
    send is logged by the scheduler and does not break subsequent sends.
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header("Varuflow", "notifications@varuflow.app"),
        "to": [to_email],
        "subject": f"Glöm inte din bokföringsexport för {year - 1}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Dags att arkivera {year - 1}</h2>
          <p>Hej {_h(org_name)},</p>
          <p>
            Bokföringslagen (BFL 7 kap. 2 §) kräver att verifikationer sparas
            i minst 7 år. Säkerställ att du har en säker kopia av
            {year - 1} års fakturor och verifikationer.
          </p>
          <p style="margin:24px 0">
            <a href="https://varuflow.vercel.app/settings/gdpr"
               style="background:#1a2332;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:600">
              Ladda ned bokföringsexport
            </a>
          </p>
          <p style="color:#888;font-size:12px">
            Sent by Varuflow · BFL compliance reminder
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

    return res.status_code in (200, 201)


# ── Dunning reminders (v20) ──────────────────────────────────────────────────

_DUNNING_SUBJECTS = {
    1: "Vänlig påminnelse: faktura {invoice_number} har förfallit",
    2: "Påminnelse: faktura {invoice_number} är {days_overdue} dagar försenad",
    3: "Slutlig betalningspåminnelse: faktura {invoice_number}",
    4: "Inkassovarning: faktura {invoice_number}",
}

_DUNNING_BODIES = {
    1: (
        "<p>Hej {customer_name},</p>"
        "<p>Faktura <strong>{invoice_number}</strong> på "
        "<strong>{amount} SEK</strong> förföll {days_overdue} dagar sedan. "
        "Vänligen betala snarast om du inte redan gjort det.</p>"
    ),
    2: (
        "<p>Hej {customer_name},</p>"
        "<p>Vi har ännu inte mottagit betalning för faktura "
        "<strong>{invoice_number}</strong> (<strong>{amount} SEK</strong>), "
        "som är <strong>{days_overdue} dagar</strong> försenad. "
        "Kontakta oss om det finns en fråga kring betalningen.</p>"
    ),
    3: (
        "<p>Hej {customer_name},</p>"
        "<p>Detta är vår <strong>slutliga påminnelse</strong> gällande "
        "faktura <strong>{invoice_number}</strong> på <strong>{amount} SEK</strong>, "
        "nu {days_overdue} dagar försenad. Om betalning inte inkommit inom "
        "7 dagar kommer ärendet att lämnas till inkasso.</p>"
    ),
    4: (
        "<p>Hej {customer_name},</p>"
        "<p>Faktura <strong>{invoice_number}</strong> på <strong>{amount} SEK</strong> "
        "är nu {days_overdue} dagar försenad och kommer att överlämnas till "
        "inkasso inom kort. Lagstadgade påminnelse- och inkassoavgifter "
        "(enligt inkassolagen) kan tillkomma.</p>"
    ),
}


async def send_dunning_email(
    *,
    to_email: str,
    customer_name: str,
    invoice_number: str,
    amount_sek: str,
    days_overdue: int,
    stage: int,
    org_name: str,
) -> bool:
    """Send a dunning reminder at ``stage`` 1-4.

    Returns False if Resend is not configured or ``stage`` is invalid.
    """
    if not settings.RESEND_API_KEY:
        return False
    if stage not in _DUNNING_SUBJECTS:
        return False

    subject = _DUNNING_SUBJECTS[stage].format(
        invoice_number=_h(invoice_number),
        days_overdue=days_overdue,
    )
    body_html = _DUNNING_BODIES[stage].format(
        customer_name=_h(customer_name),
        invoice_number=_h(invoice_number),
        amount=_h(amount_sek),
        days_overdue=days_overdue,
    )
    full_html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
      <h2 style="color:#1a2332">Betalningspåminnelse</h2>
      {body_html}
      <p style="color:#888;font-size:12px;margin-top:24px">
        Sent by {_h(org_name)} · Varuflow
      </p>
    </div>
    """

    payload = {
        "from": _from_header(org_name, "invoices@varuflow.app"),
        "to": [to_email],
        "subject": subject,
        "html": full_html,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


def _order_lines_table(lines: list[dict]) -> str:
    """Render the line-item table used by both order email templates.

    Each entry must have: ``description``, ``quantity``, ``unit_price``,
    ``line_total``. Prices are expected to already be strings/Decimals
    in SEK — the helper only formats and HTML-escapes them.
    """
    rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 10px'>{_h(ln['description'])}</td>"
        f"<td style='padding:6px 10px;text-align:right'>{_h(ln['quantity'])}</td>"
        f"<td style='padding:6px 10px;text-align:right'>{_h(ln['unit_price'])}</td>"
        f"<td style='padding:6px 10px;text-align:right'>{_h(ln['line_total'])}</td>"
        f"</tr>"
        for ln in lines
    )
    return (
        "<table style='border-collapse:collapse;width:100%;margin:16px 0'>"
        "<thead><tr style='background:#f3f4f6'>"
        "<th style='padding:6px 10px;text-align:left'>Item</th>"
        "<th style='padding:6px 10px;text-align:right'>Qty</th>"
        "<th style='padding:6px 10px;text-align:right'>Unit</th>"
        "<th style='padding:6px 10px;text-align:right'>Total</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


async def send_order_confirmation_email(
    *,
    to_email: str,
    customer_name: str,
    order_number: str,
    total_sek: str,
    lines: list[dict],
    org_name: str,
) -> bool:
    """Send an order-received confirmation to the B2B customer.

    Returns False when Resend is not configured; the caller should treat
    that as a best-effort no-op (the order itself has still been persisted).
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "orders@varuflow.app"),
        "to": [to_email],
        "subject": f"Order received — {order_number} · {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:620px;margin:0 auto">
          <h2 style="color:#1a2332">Thanks for your order</h2>
          <p>Dear {_h(customer_name)},</p>
          <p>We've received your order <strong>{_h(order_number)}</strong>
             and reserved stock against it. You will receive the final
             invoice once the order is confirmed by {_h(org_name)}.</p>
          {_order_lines_table(lines)}
          <p style="text-align:right;font-size:16px">
            <strong>Total: {_h(total_sek)} SEK</strong>
          </p>
          <p style="color:#888;font-size:12px;margin-top:24px">
            Sent via Varuflow · Reply to this email if anything is wrong.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_internal_order_notification_email(
    *,
    to_email: str,
    org_name: str,
    customer_name: str,
    order_number: str,
    total_sek: str,
    lines: list[dict],
) -> bool:
    """Notify the org's ``orders_notification_email`` that a portal
    customer has placed a new order. Returns False when Resend isn't
    configured or the destination address is blank (caller-checked)."""
    if not settings.RESEND_API_KEY or not to_email:
        return False

    payload = {
        "from": _from_header("Varuflow", "orders@varuflow.app"),
        "to": [to_email],
        "subject": f"New portal order — {order_number} from {customer_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:620px;margin:0 auto">
          <h2 style="color:#1a2332">New portal order</h2>
          <p><strong>{_h(customer_name)}</strong> just placed order
             <strong>{_h(order_number)}</strong> via the self-service
             portal. Stock has been automatically reserved and a DRAFT
             invoice created for your review in Varuflow.</p>
          {_order_lines_table(lines)}
          <p style="text-align:right;font-size:16px">
            <strong>Total: {_h(total_sek)} SEK</strong>
          </p>
          <p style="color:#888;font-size:12px;margin-top:24px">
            Organisation: {_h(org_name)} · Action: open the invoice in
            Varuflow, confirm pricing &amp; ship, then send to the customer.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_onboarding_reminder_email(
    *,
    to_email: str,
    org_name: str,
    dashboard_url: str,
) -> bool:
    """Nudge an org that signed up but hasn't completed a single
    onboarding checklist step within 48 hours. Sent at most once per
    org — the scheduler uses ``IdempotencyKey`` as the send ledger."""
    if not settings.RESEND_API_KEY or not to_email:
        return False

    payload = {
        "from": _from_header("Varuflow", "welcome@varuflow.app"),
        "to": [to_email],
        "subject": "Kom igång med Varuflow",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#1a2332">
          <h2>Välkommen till Varuflow, {_h(org_name)}!</h2>
          <p>Vi märkte att du skapade ett konto men inte hunnit börja ännu.
             Här är en kort checklista för att komma igång:</p>
          <ol style="line-height:1.9">
            <li>Lägg till din första produkt</li>
            <li>Lägg till din första kund</li>
            <li>Skapa din första faktura</li>
            <li>Bjud in en kollega</li>
            <li>Koppla Fortnox (valfritt)</li>
            <li>Skicka din första faktura</li>
          </ol>
          <p style="margin-top:24px">
            <a href="{_h(dashboard_url)}"
               style="background:#6366f1;color:#fff;padding:10px 20px;border-radius:8px;
                      text-decoration:none;font-weight:600">
              Öppna checklistan
            </a>
          </p>
          <p style="margin-top:32px;color:#888;font-size:12px">
            Du får det här mejlet en gång. Om du inte vill ha fler mejl från
            oss svarar du bara på detta så tar vi bort dig från listan.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_auto_reorder_notification_email(
    *,
    to_email: str,
    org_name: str,
    pos: list[dict],
) -> bool:
    """Notify the org owner that N draft POs need approval.

    ``pos`` items have the shape
    ``{"po_id": str, "supplier_name": str, "items_count": int, "total_sek": str}``.
    Nothing is sent to the supplier at this stage — the owner must open
    Varuflow and click SEND on each draft before anything leaves the
    org. The email body mirrors that stance ("need your approval", not
    "orders placed") to avoid creating the impression of autonomous
    ordering.
    """
    if not settings.RESEND_API_KEY or not to_email or not pos:
        return False

    count = len(pos)
    rows = "".join(
        f"<tr>"
        f"<td style='padding:8px;border-bottom:1px solid #eee'>{_h(p['supplier_name'])}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{_h(p['items_count'])}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;font-weight:600'>{_h(p['total_sek'])} SEK</td>"
        f"</tr>"
        for p in pos
    )

    payload = {
        "from": _from_header(org_name, "alerts@varuflow.app"),
        "to": [to_email],
        "subject": f"Auto-reorder: {count} purchase orders need your approval",
        "html": f"""
        <div style="font-family:sans-serif;max-width:620px;margin:0 auto;color:#1a2332">
          <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:8px;padding:12px 16px;margin-bottom:20px">
            <strong style="color:#4f46e5">Varuflow — Auto-reorder</strong>
          </div>
          <h2 style="margin:0 0 12px 0">{_h(count)} draft purchase orders need your approval</h2>
          <p>Varuflow detected products below their reorder level and
             created draft orders grouped by preferred supplier.
             <strong>Nothing has been sent to your suppliers yet</strong> —
             open each draft, review the quantities, and click SEND when
             you're happy.</p>
          <table style="width:100%;border-collapse:collapse;font-size:14px;margin-top:16px">
            <thead>
              <tr style="background:#f9fafb">
                <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Supplier</th>
                <th style="padding:8px;text-align:right;border-bottom:2px solid #e5e7eb">Products</th>
                <th style="padding:8px;text-align:right;border-bottom:2px solid #e5e7eb">Total</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          <p style="margin-top:24px">
            <a href="https://varuflow.se/inventory/purchase-orders"
               style="background:#4f46e5;color:#fff;padding:10px 20px;border-radius:8px;
                      text-decoration:none;font-weight:600">
              Review purchase orders
            </a>
          </p>
          <p style="margin-top:28px;color:#888;font-size:12px">
            To disable auto-reorder, go to Settings → Auto-reorder in Varuflow.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_giftcard_expiry_email(
    to_email: str,
    giftcard_code: str,
    remaining_value: str,
    expire_date: str,
    org_name: str,
) -> bool:
    """Notify a customer that their gift card expires within the week.

    Returns True on success, False if Resend isn't configured (in
    which case the scheduler logs the intent but doesn't retry).
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "notifications@varuflow.app"),
        "to": [to_email],
        "subject": f"Your gift card from {org_name} expires on {expire_date}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Gift card expiring soon</h2>
          <p>Your gift card code <strong>{_h(giftcard_code)}</strong> has
          <strong>{_h(remaining_value)} SEK</strong> remaining and expires
          on <strong>{_h(expire_date)}</strong>.</p>
          <p>Drop by {_h(org_name)} before then to use the balance.</p>
          <p style="margin-top:32px;color:#888;font-size:12px">
            Sent via Varuflow. If this was sent in error, please ignore.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_campaign_email(
    *,
    to_email: str,
    subject: str,
    body_html: str,
    org_name: str,
) -> bool:
    """Send a marketing-campaign email (Item 40).

    Body is pre-rendered by the campaign engine — already sanitised
    and already stamped with the GDPR unsubscribe footer. This helper
    just hands it to Resend with the campaign From header, so the
    campaign engine owns all HTML concerns and the email module stays
    a thin transport wrapper.

    Returns True on success, False on HTTP error or when Resend is not
    configured (dev boxes). The caller records FAILED in
    ``campaign_sends.status`` when this returns False so the stats
    panel surfaces the problem to the operator.
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header(org_name, "campaigns@varuflow.app"),
        "to": [to_email],
        "subject": subject,
        # Body is already rendered HTML, delivered verbatim.
        "html": body_html,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
    except Exception:  # noqa: BLE001 — transport error must not abort
        # the whole campaign send; the engine records FAILED and moves
        # on to the next recipient.
        return False
    return res.status_code in (200, 201)


async def send_subscription_pause_reminder_email(
    to_email: str,
    org_name: str,
    resume_date: str,
) -> bool:
    """Item 50 — 7-day-before-auto-resume reminder for paused orgs.

    Returns True on success, False when Resend is not configured.
    Non-fatal: the scheduler swallows exceptions so a bad inbox can
    never block the pause-reminder sweep.
    """
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": _from_header("Varuflow", "billing@varuflow.app"),
        "to": [to_email],
        "subject": f"Your Varuflow pause ends on {resume_date}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Your subscription resumes soon</h2>
          <p>Hi {_h(org_name)},</p>
          <p>Your Varuflow subscription was paused and will automatically
             resume on <strong>{_h(resume_date)}</strong> — that's 7 days
             from today.</p>
          <p>Nothing you need to do — billing resumes automatically.
             If you'd like to extend the pause or resume earlier, head
             to billing settings.</p>
          <p style="margin:24px 0">
            <a href="{settings.PORTAL_BASE_URL}/settings/billing"
               style="background:#1a2332;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:600">
              Manage subscription
            </a>
          </p>
          <p style="color:#64748b;font-size:12px">Sent once per pause
             window — no spam.</p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_portal_otp_email(
    to_email: str,
    customer_name: str,
    code: str,
    expires_in_seconds: int,
    org_name: str,
) -> bool:
    """Item 51 — Portal 2FA email with a short-lived 6-digit code."""
    if not settings.RESEND_API_KEY:
        return False

    minutes = max(1, expires_in_seconds // 60)
    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": f"Your {org_name} login code: {code}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2 style="color:#1a2332">Your verification code</h2>
          <p>Hi {_h(customer_name)},</p>
          <p>Use the code below to sign in to your {_h(org_name)} portal.
             This code expires in {minutes} minute(s).</p>
          <p style="font-size:28px;font-weight:700;letter-spacing:6px;
                    text-align:center;padding:16px;background:#f1f5f9;
                    border-radius:8px;margin:24px 0">
            {_h(code)}
          </p>
          <p style="color:#64748b;font-size:12px">
            If you didn't request this, you can safely ignore this email.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_back_in_stock_email(
    to_email: str,
    recipient_name: str | None,
    product_name: str,
    product_sku: str | None,
    org_name: str,
    shop_url: str | None = None,
) -> bool:
    """Item 56 — Back-in-stock waitlist notification."""
    if not settings.RESEND_API_KEY:
        return False

    greeting = _h(recipient_name or "there")
    sku_line = (
        f"<p style='color:#64748b;font-size:13px'>SKU: {_h(product_sku)}</p>"
        if product_sku else ""
    )
    cta = (
        f"<p style='margin:24px 0'><a href='{_h(shop_url)}' "
        f"style='background:#2d6a4f;color:#fff;padding:12px 24px;"
        f"border-radius:6px;text-decoration:none'>View product</a></p>"
        if shop_url else ""
    )
    payload = {
        "from": _from_header(org_name, settings.EMAIL_FROM),
        "to": [to_email],
        "subject": f"{product_name} is back in stock",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2 style="color:#1a2332">{_h(product_name)} is back in stock</h2>
          <p>Hi {greeting},</p>
          <p>Good news — <strong>{_h(product_name)}</strong> is available
             again at {_h(org_name)}.</p>
          {sku_line}
          {cta}
          <p style="color:#64748b;font-size:12px">
            You're receiving this because you joined the waitlist for this
            product. Reply to opt out at any time.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_order_confirmation_storefront(
    *,
    to_email: str,
    customer_name: str,
    order_number: str,
    items: list[dict],
    total: str,
    currency: str,
    shop_name: str,
    shop_url: str,
) -> bool:
    """Send an order confirmation to a storefront customer."""
    if not settings.RESEND_API_KEY:
        return False

    items_html = "".join(
        f"<tr><td style='padding:4px 8px'>{_h(it.get('description',''))}</td>"
        f"<td style='padding:4px 8px;text-align:center'>{_h(it.get('quantity',''))}</td>"
        f"<td style='padding:4px 8px;text-align:right'>{_h(it.get('unit_price',''))}</td></tr>"
        for it in items
    )
    payload = {
        "from": _from_header(shop_name, "orders@varuflow.app"),
        "to": [to_email],
        "subject": f"Order confirmed — {order_number}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Order confirmed</h2>
          <p>Hi {_h(customer_name)}, thanks for your order!</p>
          <p style="color:#64748b;font-size:13px">Order number: <strong>{_h(order_number)}</strong></p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <thead><tr style="background:#f1f5f9">
              <th style="padding:4px 8px;text-align:left">Item</th>
              <th style="padding:4px 8px">Qty</th>
              <th style="padding:4px 8px;text-align:right">Price</th>
            </tr></thead>
            <tbody>{items_html}</tbody>
            <tfoot><tr>
              <td colspan="2" style="padding:8px;font-weight:bold">Total</td>
              <td style="padding:8px;text-align:right;font-weight:bold">{_h(total)} {_h(currency)}</td>
            </tr></tfoot>
          </table>
          <p>We'll notify you when your order ships.</p>
          <p style="margin-top:32px;color:#888;font-size:12px">
            Ordered from {_h(shop_name)} · <a href="{_h(shop_url)}">{_h(shop_url)}</a>
          </p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_abandoned_cart_recovery(
    *,
    cart,
    shop_url: str,
    storefront_name: str,
) -> bool:
    """Send an abandoned-cart recovery email to a storefront shopper."""
    if not settings.RESEND_API_KEY:
        return False
    if not cart.customer_email:
        return False

    items = cart.items or []
    items_html = "".join(
        f"<li>{_h(it.get('description', 'Product'))} × {_h(it.get('qty', 1))}</li>"
        for it in items
    )
    full_url = f"{settings.FRONTEND_URL}{shop_url}"
    payload = {
        "from": _from_header(storefront_name, "shop@varuflow.app"),
        "to": [cart.customer_email],
        "subject": f"You left something behind at {storefront_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2 style="color:#1a2332">Don't forget your cart!</h2>
          <p>You left the following items behind:</p>
          <ul style="color:#334155">{items_html}</ul>
          <p style="margin:24px 0">
            <a href="{_h(full_url)}"
               style="background:#4f46e5;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none">
              Complete your order
            </a>
          </p>
          <p style="color:#64748b;font-size:12px">
            Your cart will be saved for 7 days.
            If you no longer wish to receive these reminders, simply ignore this email.
          </p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


# ── Trial emails ──────────────────────────────────────────────────────────────


async def send_trial_started_email(
    to_email: str | None,
    org_name: str,
    plan: str,
    trial_ends_at,
) -> bool:
    if not settings.RESEND_API_KEY or not to_email:
        return False
    ends = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else "14 days from now"
    payload = {
        "from": _from_header("Varuflow", "noreply@varuflow.app"),
        "to": [to_email],
        "subject": f"Your {plan} trial has started – {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2 style="color:#1a2332">Welcome to your {plan} trial!</h2>
          <p>Your 14-day free trial of Varuflow {plan} is now active for <strong>{_h(org_name)}</strong>.</p>
          <p>Your trial ends on <strong>{ends}</strong>. No credit card required until then.</p>
          <p style="margin:24px 0">
            <a href="{settings.FRONTEND_URL}"
               style="background:#4f46e5;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none">
              Open Varuflow
            </a>
          </p>
          <p style="color:#64748b;font-size:12px">
            You can upgrade to a paid plan at any time from Settings → Billing.
          </p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_trial_ending_soon_email(
    to_email: str,
    org_name: str,
    plan: str,
    trial_ends_at,
    days_remaining: int,
) -> bool:
    if not settings.RESEND_API_KEY:
        return False
    ends = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else ""
    payload = {
        "from": _from_header("Varuflow", "noreply@varuflow.app"),
        "to": [to_email],
        "subject": f"Your Varuflow {plan} trial ends in {days_remaining} day{'s' if days_remaining != 1 else ''} – {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2 style="color:#b45309">Trial ending soon</h2>
          <p>Your Varuflow <strong>{plan}</strong> trial for <strong>{_h(org_name)}</strong>
             expires on <strong>{ends}</strong>.</p>
          <p>To keep access to all Pro features, upgrade before your trial ends.</p>
          <p style="margin:24px 0">
            <a href="{settings.FRONTEND_URL}/en/settings/billing"
               style="background:#4f46e5;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none">
              Upgrade now
            </a>
          </p>
          <p style="color:#64748b;font-size:12px">
            If you choose not to upgrade, your account will revert to the Free plan.
          </p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_trial_expired_email(
    to_email: str,
    org_name: str,
    plan: str,
) -> bool:
    if not settings.RESEND_API_KEY:
        return False
    payload = {
        "from": _from_header("Varuflow", "noreply@varuflow.app"),
        "to": [to_email],
        "subject": f"Your Varuflow {plan} trial has ended – {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2 style="color:#1a2332">Your trial has ended</h2>
          <p>The 14-day {plan} trial for <strong>{_h(org_name)}</strong> has expired.
             Your account has been moved back to the Free plan.</p>
          <p>You can reactivate Pro at any time — all your data is still here.</p>
          <p style="margin:24px 0">
            <a href="{settings.FRONTEND_URL}/en/settings/billing"
               style="background:#4f46e5;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none">
              Reactivate Pro
            </a>
          </p>
        </div>
        """,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


# ── NPS & subscription health emails ─────────────────────────────────────────


async def send_nps_survey_email(
    *,
    to_email: str,
    org_name: str,
    survey_url: str,
) -> bool:
    """24-hour reminder when an NPS survey was triggered but not responded to.

    The survey_url should be the in-app URL that opens the NPS modal directly
    (e.g. https://varuflow.vercel.app/en/dashboard?nps=1).
    Returns False when Resend is not configured (dev) — callers must not raise.
    """
    if not settings.RESEND_API_KEY or not to_email:
        return False

    payload = {
        "from": _from_header("Varuflow", "feedback@varuflow.app"),
        "to": [to_email],
        "subject": "One quick question — how are things going?",
        "html": f"""
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#1a2332">
          <h2>How likely are you to recommend Varuflow?</h2>
          <p>Hi {_h(org_name)},</p>
          <p>We sent you a quick one-question survey yesterday. It takes
             10 seconds and helps us build the right things for businesses
             like yours.</p>
          <p style="margin:28px 0;text-align:center">
            <a href="{_h(survey_url)}"
               style="background:#4f46e5;color:#fff;padding:14px 32px;
                      border-radius:8px;text-decoration:none;font-weight:600;
                      font-size:15px">
              Answer the survey →
            </a>
          </p>
          <p style="color:#64748b;font-size:13px">
            This is the only reminder we'll send. Your feedback shapes
            what we build next at Varuflow.
          </p>
          <p style="color:#94a3b8;font-size:12px;margin-top:32px">
            Varuflow · Unsubscribe from feedback emails in Settings
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_nps_detractor_followup_email(
    *,
    to_email: str,
    org_name: str,
    score: int,
    comment: str | None,
    calendly_url: str,
) -> bool:
    """Follow-up email to a detractor (NPS 0-6) offering a call.

    Sent within minutes of a detractor submitting their NPS response.
    The calendly_url should be a 15-minute call booking link.
    Returns False when Resend is not configured.
    """
    if not settings.RESEND_API_KEY or not to_email:
        return False

    comment_block = ""
    if comment:
        comment_block = (
            f"<blockquote style='border-left:3px solid #e2e8f0;margin:16px 0;"
            f"padding:8px 16px;color:#64748b;font-style:italic'>"
            f"{_h(comment)}"
            f"</blockquote>"
        )

    payload = {
        "from": _from_header("Varuflow", "feedback@varuflow.app"),
        "to": [to_email],
        "subject": "Can we make this right? — your Varuflow feedback",
        "html": f"""
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#1a2332">
          <h2>Thank you for your honest feedback</h2>
          <p>Hi {_h(org_name)},</p>
          <p>You gave us a {_h(score)} out of 10 — we take that seriously.
             We'd love to understand what's not working so we can fix it.</p>
          {comment_block}
          <p>Could you spare 15 minutes for a quick call? Pick a time that
             works for you:</p>
          <p style="margin:28px 0;text-align:center">
            <a href="{_h(calendly_url)}"
               style="background:#dc2626;color:#fff;padding:14px 32px;
                      border-radius:8px;text-decoration:none;font-weight:600;
                      font-size:15px">
              Book a 15-minute call
            </a>
          </p>
          <p style="color:#64748b;font-size:13px">
            If a call doesn't work, you can also just reply to this email
            and we'll get back to you directly.
          </p>
          <p style="color:#94a3b8;font-size:12px;margin-top:32px">
            Varuflow · This email was triggered by your NPS response
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_nps_at_risk_checkin_email(
    *,
    to_email: str,
    org_name: str,
    health_score: int,
    csm_name: str,
    csm_calendly_url: str,
) -> bool:
    """Personalised check-in from a CSM for orgs with at-risk health scores (50-79).

    Sent by the weekly health sweep when intervention_triggered_at is null and
    risk_level is 'at_risk'. Sets intervention_triggered_at on the health score
    row after sending so this fires at most once per health check cycle.
    Returns False when Resend is not configured.
    """
    if not settings.RESEND_API_KEY or not to_email:
        return False

    payload = {
        "from": _from_header(csm_name, "success@varuflow.app"),
        "to": [to_email],
        "subject": f"Checking in — {org_name} on Varuflow",
        "html": f"""
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#1a2332">
          <h2>Checking in on how things are going</h2>
          <p>Hi {_h(org_name)},</p>
          <p>I'm {_h(csm_name)} from the Varuflow customer success team.
             I noticed you haven't been as active in Varuflow lately
             (your engagement score is {_h(health_score)}/100), and I
             wanted to reach out personally.</p>
          <p>Is there anything we can help with? Whether it's a feature
             question, a workflow you're trying to set up, or something
             that isn't quite clicking — I'm happy to help.</p>
          <p style="margin:28px 0">
            <a href="{_h(csm_calendly_url)}"
               style="background:#0ea5e9;color:#fff;padding:12px 28px;
                      border-radius:8px;text-decoration:none;font-weight:600">
              Book a free 20-minute session
            </a>
          </p>
          <p style="color:#64748b;font-size:13px">
            Or just reply to this email — I read every message.
          </p>
          <p style="margin-top:32px;font-size:12px;color:#94a3b8">
            {_h(csm_name)} · Customer Success, Varuflow
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


async def send_nps_critical_intervention_email(
    *,
    to_email: str,
    org_name: str,
    health_score: int,
    founder_name: str,
    founder_email: str,
    founder_calendly_url: str,
) -> bool:
    """Personal founder email for orgs with critical health scores (<50).

    Sent when risk_level is 'critical' and intervention_triggered_at is null.
    Comes from the founder's personal address so recipients know this is not
    automated — reply-to is set to founder_email for real thread continuation.
    Returns False when Resend is not configured.
    """
    if not settings.RESEND_API_KEY or not to_email:
        return False

    payload = {
        "from": _from_header(founder_name, "founders@varuflow.app"),
        "reply_to": founder_email,
        "to": [to_email],
        "subject": f"A personal note from {founder_name} at Varuflow",
        "html": f"""
        <div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;
                    color:#1a2332;line-height:1.7">
          <p>Hi {_h(org_name)},</p>
          <p>I'm {_h(founder_name)}, one of the founders of Varuflow.
             I'm writing to you personally because I pay close attention
             to how our customers are doing, and I noticed that things
             might not be going well for you on the platform.</p>
          <p>I'd love to understand what's happening. You built a
             business — you took the risk, you're doing the hard work.
             Varuflow should be making that easier, not harder. If it
             isn't, I want to know why.</p>
          <p>Would you be willing to share 20 minutes with me? I'll
             come to the call with no agenda other than to listen.</p>
          <p style="margin:32px 0">
            <a href="{_h(founder_calendly_url)}"
               style="background:#1a2332;color:#fff;padding:14px 28px;
                      border-radius:8px;text-decoration:none;font-weight:600;
                      font-family:sans-serif;font-size:14px">
              Book 20 minutes with {_h(founder_name)}
            </a>
          </p>
          <p>If a call doesn't suit you, just reply here — this goes
             straight to my personal inbox.</p>
          <p style="margin-top:40px">
            {_h(founder_name)}<br>
            <span style="color:#64748b;font-size:13px;font-family:sans-serif">Co-founder, Varuflow</span>
          </p>
          <p style="margin-top:32px;font-size:11px;color:#94a3b8;font-family:sans-serif">
            You're receiving this because our systems flagged your account
            as needing attention (health score: {_h(health_score)}/100). This
            email is sent by a real person who read your account history.
          </p>
        </div>
        """,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Trial onboarding email templates
# ---------------------------------------------------------------------------
# 11 templates × 4 locales (en, sv, ar, fr) = 44 private functions.
# All user-supplied tokens are passed through _h() before interpolation.
# Arabic (ar) variants include dir="rtl" and text-align:right on body text.
# Day 7 and Day 21 are sent From: Marcus Berg <onboarding@varuflow.app>.
# CTA colours: green #16a34a = positive upgrade, indigo #4f46e5 = neutral,
#              red #dc2626 = urgency.
# ---------------------------------------------------------------------------

def _cta_button(label: str, url: str, color: str = "#4f46e5") -> str:
    """Render a pill CTA button for inline HTML email."""
    return (
        f'<p style="margin:28px 0">'
        f'<a href="{_h(url)}" style="background:{color};color:#fff;'
        f'padding:13px 28px;border-radius:8px;text-decoration:none;'
        f'font-weight:600;font-family:sans-serif;font-size:14px">'
        f"{label}</a></p>"
    )


def _email_wrapper(body: str, rtl: bool = False) -> str:
    dir_attr = ' dir="rtl"' if rtl else ""
    align = "right" if rtl else "left"
    return (
        f'<div{dir_attr} style="font-family:Arial,sans-serif;max-width:560px;'
        f'margin:0 auto;color:#1a2332;line-height:1.65;text-align:{align}">'
        f"{body}"
        f'<p style="margin-top:48px;font-size:11px;color:#94a3b8;'
        f'font-family:sans-serif">Varuflow · Linnégatan 12, Stockholm · '
        f'<a href="{settings.FRONTEND_URL}/en/settings/notifications" '
        f'style="color:#94a3b8">Unsubscribe</a></p>'
        f"</div>"
    )


def _serif_wrapper(body: str) -> str:
    return (
        '<div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;'
        'color:#1a2332;line-height:1.7">'
        f"{body}"
        '<p style="margin-top:48px;font-size:11px;color:#94a3b8;'
        'font-family:sans-serif">Varuflow · Linnégatan 12, Stockholm · '
        f'<a href="{settings.FRONTEND_URL}/en/settings/notifications" '
        'style="color:#94a3b8">Unsubscribe</a></p>'
        "</div>"
    )


async def _send_onboarding(
    *,
    from_header: str,
    to_email: str,
    subject: str,
    html_body: str,
) -> bool:
    if not settings.RESEND_API_KEY or not to_email:
        return False
    payload = {
        "from": from_header,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    return res.status_code in (200, 201)


# ── Day 0 — Welcome ──────────────────────────────────────────────────────────

async def _trial_day_0_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    org = _h(tokens.get("org_name", "your organisation"))
    fe = settings.FRONTEND_URL
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Welcome to Varuflow! I'm Marcus, one of the founders. We built "
        "Varuflow for Nordic wholesalers who are tired of spreadsheets and "
        "clunky ERP systems — so I'm really glad you're here.</p>"
        "<p>Here are three things to get you started in the next 10 minutes:</p>"
        "<ol>"
        f'<li><a href="{fe}/en/invoices/new" style="color:#4f46e5">Create your first invoice</a> — takes about 2 minutes.</li>'
        f'<li><a href="{fe}/en/inventory" style="color:#4f46e5">Add a product</a> to your catalogue.</li>'
        f'<li><a href="{fe}/en/settings/team" style="color:#4f46e5">Invite a team member</a> — even just to see how it looks.</li>'
        "</ol>"
        + _cta_button("Open Varuflow →", fe, "#16a34a")
        + "<p>If you have any questions just reply to this email — it goes "
        "straight to me.</p>"
        "<p>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px">Co-founder, Varuflow</span></p>'
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Welcome to Varuflow, {first} 👋",
        html_body=body,
    )


async def _trial_day_0_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Välkommen till Varuflow! Jag heter Marcus och är en av grundarna. "
        "Vi byggde Varuflow för nordiska grossister som är trötta på "
        "kalkylblad och krångliga affärssystem.</p>"
        "<p>Tre saker du kan göra de nästa tio minuterna:</p>"
        "<ol>"
        f'<li><a href="{fe}/sv/invoices/new" style="color:#4f46e5">Skapa din första faktura</a> — tar ungefär 2 minuter.</li>'
        f'<li><a href="{fe}/sv/inventory" style="color:#4f46e5">Lägg till en produkt</a> i ditt sortiment.</li>'
        f'<li><a href="{fe}/sv/settings/team" style="color:#4f46e5">Bjud in en kollega</a> — bara för att se hur det känns.</li>'
        "</ol>"
        + _cta_button("Öppna Varuflow →", fe, "#16a34a")
        + "<p>Har du frågor? Svara på det här mailet — det hamnar direkt hos mig.</p>"
        "<p>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px">Medgrundare, Varuflow</span></p>'
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Välkommen till Varuflow, {first}!",
        html_body=body,
    )


async def _trial_day_0_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>أهلاً بك في Varuflow! أنا ماركوس، أحد المؤسسين. لقد بنينا "
        "Varuflow لتجار الجملة في الدول الإسكندنافية الذين يريدون التخلص "
        "من جداول البيانات وأنظمة ERP المعقدة.</p>"
        "<p>إليك ثلاثة أشياء يمكنك البدء بها خلال عشر دقائق:</p>"
        "<ol>"
        f'<li><a href="{fe}/en/invoices/new" style="color:#4f46e5">أنشئ فاتورتك الأولى</a> — تستغرق دقيقتين فقط.</li>'
        f'<li><a href="{fe}/en/inventory" style="color:#4f46e5">أضف منتجاً</a> إلى كتالوجك.</li>'
        f'<li><a href="{fe}/en/settings/team" style="color:#4f46e5">ادعُ أحد زملائك</a>.</li>'
        "</ol>"
        + _cta_button("افتح Varuflow →", fe, "#16a34a")
        + "<p>إذا كان لديك أي سؤال، فقط أجب على هذا البريد الإلكتروني — سيصلني مباشرةً.</p>"
        "<p>ماركوس بيرغ<br>"
        '<span style="color:#64748b;font-size:13px">المؤسس المشارك، Varuflow</span></p>',
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"مرحباً بك في Varuflow، {first}!",
        html_body=body,
    )


async def _trial_day_0_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Bienvenue sur Varuflow ! Je m'appelle Marcus, l'un des fondateurs. "
        "Nous avons créé Varuflow pour les grossistes nordiques qui en ont "
        "assez des tableurs et des ERP complexes.</p>"
        "<p>Trois choses à faire dans les dix prochaines minutes :</p>"
        "<ol>"
        f'<li><a href="{fe}/en/invoices/new" style="color:#4f46e5">Créez votre première facture</a> — environ 2 minutes.</li>'
        f'<li><a href="{fe}/en/inventory" style="color:#4f46e5">Ajoutez un produit</a> à votre catalogue.</li>'
        f'<li><a href="{fe}/en/settings/team" style="color:#4f46e5">Invitez un collègue</a>.</li>'
        "</ol>"
        + _cta_button("Ouvrir Varuflow →", fe, "#16a34a")
        + "<p>Si vous avez des questions, répondez simplement à cet e-mail — il m'arrive directement.</p>"
        "<p>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px">Co-fondateur, Varuflow</span></p>'
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Bienvenue sur Varuflow, {first} !",
        html_body=body,
    )


# ── Day 1 — Create first invoice ─────────────────────────────────────────────

async def _trial_day_1_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    new_url = f"{fe}/en/invoices/new"
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Creating your first invoice takes about 5 minutes. Here's exactly "
        "how to do it:</p>"
        "<ol>"
        "<li><strong>Add a customer</strong> — enter their name, email, and "
        "billing address. Varuflow saves them for next time.</li>"
        "<li><strong>Add line items</strong> — type a product name or pick "
        "from your catalogue. Quantities and prices auto-calculate.</li>"
        "<li><strong>Send or download</strong> — email a payment link "
        "directly to your customer, or download a PDF.</li>"
        "</ol>"
        + _cta_button("Create my first invoice →", new_url, "#16a34a")
        + "<p>The whole thing is under 5 minutes the first time — even faster "
        "after that.</p>"
        "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Create your first invoice in 5 minutes",
        html_body=body,
    )


async def _trial_day_1_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    new_url = f"{fe}/sv/invoices/new"
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Att skapa din första faktura tar ungefär 5 minuter. "
        "Så här gör du:</p>"
        "<ol>"
        "<li><strong>Lägg till en kund</strong> — ange namn, e-post och "
        "fakturaadress. Varuflow sparar dem till nästa gång.</li>"
        "<li><strong>Lägg till rader</strong> — skriv ett produktnamn eller "
        "välj från ditt sortiment. Antal och priser beräknas automatiskt.</li>"
        "<li><strong>Skicka eller ladda ned</strong> — mejla en betalningslänk "
        "direkt till kunden, eller ladda ned som PDF.</li>"
        "</ol>"
        + _cta_button("Skapa min första faktura →", new_url, "#16a34a")
        + "<p>Hela processen tar under 5 minuter första gången — ännu snabbare sedan.</p>"
        "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Skapa din första faktura på 5 minuter",
        html_body=body,
    )


async def _trial_day_1_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    new_url = f"{fe}/en/invoices/new"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>إنشاء فاتورتك الأولى لا يستغرق سوى 5 دقائق. إليك الخطوات:</p>"
        "<ol>"
        "<li><strong>أضف عميلاً</strong> — أدخل الاسم والبريد الإلكتروني وعنوان الفواتير. سيحفظ Varuflow بياناته للمرة القادمة.</li>"
        "<li><strong>أضف بنوداً</strong> — اكتب اسم المنتج أو اختره من الكتالوج. تُحسب الكميات والأسعار تلقائياً.</li>"
        "<li><strong>أرسل أو نزّل</strong> — أرسل رابط دفع مباشرة إلى العميل، أو نزّل ملف PDF.</li>"
        "</ol>"
        + _cta_button("إنشاء فاتورتي الأولى →", new_url, "#16a34a")
        + "<p>العملية كلها لا تستغرق أكثر من 5 دقائق في المرة الأولى.</p>"
        "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="أنشئ فاتورتك الأولى في 5 دقائق",
        html_body=body,
    )


async def _trial_day_1_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    new_url = f"{fe}/en/invoices/new"
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Créer votre première facture prend environ 5 minutes. "
        "Voici comment procéder :</p>"
        "<ol>"
        "<li><strong>Ajoutez un client</strong> — saisissez son nom, son e-mail "
        "et son adresse de facturation. Varuflow les enregistre pour la "
        "prochaine fois.</li>"
        "<li><strong>Ajoutez des lignes</strong> — tapez un nom de produit ou "
        "sélectionnez-en un dans votre catalogue. Quantités et prix se "
        "calculent automatiquement.</li>"
        "<li><strong>Envoyez ou téléchargez</strong> — envoyez un lien de "
        "paiement directement à votre client, ou téléchargez un PDF.</li>"
        "</ol>"
        + _cta_button("Créer ma première facture →", new_url, "#16a34a")
        + "<p>L'ensemble du processus prend moins de 5 minutes la première fois.</p>"
        "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Créez votre première facture en 5 minutes",
        html_body=body,
    )


# ── Day 2 — Set up your team ─────────────────────────────────────────────────

async def _trial_day_2_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    team_url = f"{fe}/en/settings/team"
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Wholesale businesses rarely run alone. Varuflow makes it easy to "
        "bring your whole team in — with the right level of access for each "
        "person.</p>"
        "<p><strong>Why it matters:</strong></p>"
        "<ul>"
        "<li>Your warehouse manager can update stock without touching invoices.</li>"
        "<li>Your accountant can view reports and export data without changing anything.</li>"
        "<li>You keep full control as the Owner.</li>"
        "</ul>"
        "<p><strong>Roles explained:</strong></p>"
        "<ul>"
        "<li><strong>Owner</strong> — full access, billing, can delete the org.</li>"
        "<li><strong>Admin</strong> — full access except billing and org deletion.</li>"
        "<li><strong>Member</strong> — can create and view, cannot delete or manage team.</li>"
        "</ul>"
        + _cta_button("Invite team members →", team_url, "#4f46e5")
        + "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Set up your team on Varuflow",
        html_body=body,
    )


async def _trial_day_2_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    team_url = f"{fe}/sv/settings/team"
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>De flesta grossistföretag drivs inte av en enda person. "
        "Varuflow gör det enkelt att ta med hela teamet — med rätt "
        "behörighetsnivå för var och en.</p>"
        "<p><strong>Därför spelar det roll:</strong></p>"
        "<ul>"
        "<li>Din lagerchef kan uppdatera lagersaldo utan att röra fakturor.</li>"
        "<li>Din ekonomiansvarige kan visa rapporter och exportera data utan att ändra något.</li>"
        "<li>Du behåller full kontroll som Ägare.</li>"
        "</ul>"
        "<p><strong>Roller förklarade:</strong></p>"
        "<ul>"
        "<li><strong>Ägare</strong> — full åtkomst, fakturering, kan ta bort organisationen.</li>"
        "<li><strong>Admin</strong> — full åtkomst utom fakturering och borttagning av organisation.</li>"
        "<li><strong>Medlem</strong> — kan skapa och visa, kan inte ta bort eller hantera team.</li>"
        "</ul>"
        + _cta_button("Bjud in teammedlemmar →", team_url, "#4f46e5")
        + "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Sätt upp ditt team i Varuflow",
        html_body=body,
    )


async def _trial_day_2_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    team_url = f"{fe}/en/settings/team"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>نادراً ما تُدار أعمال الجملة بمفردها. يُسهّل Varuflow إضافة فريقك "
        "بالكامل مع المستوى الصحيح من الصلاحيات لكل شخص.</p>"
        "<p><strong>لماذا يهم ذلك؟</strong></p>"
        "<ul>"
        "<li>يستطيع مدير المستودع تحديث المخزون دون لمس الفواتير.</li>"
        "<li>يستطيع المحاسب عرض التقارير وتصدير البيانات دون تغيير أي شيء.</li>"
        "<li>تحتفظ بالتحكم الكامل بصفتك مالكاً.</li>"
        "</ul>"
        "<p><strong>شرح الأدوار:</strong></p>"
        "<ul>"
        "<li><strong>المالك</strong> — وصول كامل، الفوترة، يمكنه حذف المؤسسة.</li>"
        "<li><strong>المشرف</strong> — وصول كامل باستثناء الفوترة وحذف المؤسسة.</li>"
        "<li><strong>العضو</strong> — يستطيع الإنشاء والعرض، لا يستطيع الحذف أو إدارة الفريق.</li>"
        "</ul>"
        + _cta_button("دعوة أعضاء الفريق →", team_url, "#4f46e5")
        + "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="أضف فريقك إلى Varuflow",
        html_body=body,
    )


async def _trial_day_2_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    team_url = f"{fe}/en/settings/team"
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Les activités de gros se gèrent rarement seul. Varuflow facilite "
        "l'intégration de toute votre équipe, avec le niveau d'accès adapté "
        "à chaque personne.</p>"
        "<p><strong>Pourquoi c'est important :</strong></p>"
        "<ul>"
        "<li>Votre responsable d'entrepôt peut mettre à jour les stocks sans toucher aux factures.</li>"
        "<li>Votre comptable peut consulter les rapports et exporter des données sans rien modifier.</li>"
        "<li>Vous gardez le plein contrôle en tant que Propriétaire.</li>"
        "</ul>"
        "<p><strong>Explication des rôles :</strong></p>"
        "<ul>"
        "<li><strong>Propriétaire</strong> — accès complet, facturation, peut supprimer l'organisation.</li>"
        "<li><strong>Administrateur</strong> — accès complet sauf facturation et suppression de l'org.</li>"
        "<li><strong>Membre</strong> — peut créer et consulter, ne peut pas supprimer ni gérer l'équipe.</li>"
        "</ul>"
        + _cta_button("Inviter des membres →", team_url, "#4f46e5")
        + "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Configurez votre équipe sur Varuflow",
        html_body=body,
    )


# ── Day 3 — Connect Stripe ────────────────────────────────────────────────────

async def _trial_day_3_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    stripe_url = f"{fe}/en/settings/payments"
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Still chasing customers for payment? Once you connect Stripe, "
        "every invoice you send includes a Pay Now button — and the money "
        "lands in your bank account automatically.</p>"
        "<p><strong>Why connect Stripe?</strong></p>"
        "<ul>"
        "<li>Customers pay online by card or bank transfer in seconds.</li>"
        "<li>Invoices are marked as paid automatically — no manual reconciliation.</li>"
        "<li>Full payment history in one place.</li>"
        "</ul>"
        "<p>It takes about 2 minutes to connect. Other payment methods "
        "(SEPA, Swish, invoice factoring) are coming soon.</p>"
        + _cta_button("Connect Stripe →", stripe_url, "#4f46e5")
        + "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Connect Stripe for online payments",
        html_body=body,
    )


async def _trial_day_3_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    stripe_url = f"{fe}/sv/settings/payments"
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Jagar du fortfarande kunder på betalning? När du kopplar Stripe "
        "innehåller varje faktura du skickar en Betala nu-knapp — och pengarna "
        "hamnar automatiskt på ditt konto.</p>"
        "<ul>"
        "<li>Kunder betalar online med kort eller banköverföring på sekunder.</li>"
        "<li>Fakturor markeras som betalda automatiskt — ingen manuell "
        "avstämning.</li>"
        "<li>Full betalningshistorik på ett ställe.</li>"
        "</ul>"
        "<p>Det tar ungefär 2 minuter att koppla. Fler betalningsmetoder "
        "(SEPA, Swish, fakturabelåning) kommer snart.</p>"
        + _cta_button("Koppla Stripe →", stripe_url, "#4f46e5")
        + "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Koppla Stripe för onlinebetalningar",
        html_body=body,
    )


async def _trial_day_3_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    stripe_url = f"{fe}/en/settings/payments"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>هل لا تزال تلاحق العملاء لتحصيل المدفوعات؟ بمجرد ربط Stripe، "
        "ستتضمن كل فاتورة ترسلها زر «ادفع الآن» — وسيصل المال إلى حسابك "
        "البنكي تلقائياً.</p>"
        "<ul>"
        "<li>يدفع العملاء عبر الإنترنت بالبطاقة أو التحويل المصرفي في ثوانٍ.</li>"
        "<li>تُحدَّد الفواتير كمدفوعة تلقائياً — لا مطابقة يدوية.</li>"
        "<li>سجل دفع كامل في مكان واحد.</li>"
        "</ul>"
        "<p>يستغرق الربط دقيقتين تقريباً. وسائل دفع أخرى (SEPA، Swish، "
        "تحصيل الفواتير) ستتوفر قريباً.</p>"
        + _cta_button("ربط Stripe →", stripe_url, "#4f46e5")
        + "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="اربط Stripe للمدفوعات الإلكترونية",
        html_body=body,
    )


async def _trial_day_3_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    stripe_url = f"{fe}/en/settings/payments"
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Vous courez encore après vos clients pour obtenir un paiement ? "
        "Une fois Stripe connecté, chaque facture que vous envoyez inclut un "
        "bouton Payer maintenant — et l'argent arrive automatiquement sur "
        "votre compte.</p>"
        "<ul>"
        "<li>Les clients paient en ligne par carte ou virement en quelques secondes.</li>"
        "<li>Les factures sont marquées comme payées automatiquement — plus de rapprochement manuel.</li>"
        "<li>Historique complet des paiements en un seul endroit.</li>"
        "</ul>"
        "<p>La connexion prend environ 2 minutes. D'autres méthodes de paiement "
        "(SEPA, Swish, affacturage) arrivent bientôt.</p>"
        + _cta_button("Connecter Stripe →", stripe_url, "#4f46e5")
        + "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Connectez Stripe pour les paiements en ligne",
        html_body=body,
    )


# ── Day 5 — AI features ───────────────────────────────────────────────────────

def _ai_badge() -> str:
    return (
        '<span style="background:#ede9fe;color:#4f46e5;font-size:11px;'
        'font-weight:700;padding:3px 8px;border-radius:20px;'
        'font-family:sans-serif">20 AI calls/day on Pro</span>'
    )


async def _trial_day_5_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    ai_url = f"{fe}/en/ai"
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Most Varuflow users discover the AI features late — we want to "
        "make sure you don't miss them.</p>"
        "<p><strong>AI demand forecasting</strong><br>"
        "Varuflow analyses your sales history and tells you which products to "
        "reorder before you run out. No more stockouts, no more over-ordering.</p>"
        "<p><strong>AI auto-categorisation</strong><br>"
        "Upload a messy product list — Varuflow will clean it up, assign "
        "categories, and suggest pricing tiers automatically.</p>"
        f"<p>{_ai_badge()}</p>"
        "<p>Both features are available on the Pro plan. You're currently on "
        "a trial that includes full Pro access.</p>"
        + _cta_button("Explore AI features →", ai_url, "#4f46e5")
        + _cta_button("Upgrade to Pro →", upgrade_url, "#16a34a")
        + "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Discover the AI features in your trial",
        html_body=body,
    )


async def _trial_day_5_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    ai_url = f"{fe}/sv/ai"
    upgrade_url = f"{fe}/sv/settings/billing"
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>De flesta Varuflow-användare hittar AI-funktionerna sent — vi vill "
        "se till att du inte missar dem.</p>"
        "<p><strong>AI-efterfrågeprognoser</strong><br>"
        "Varuflow analyserar din försäljningshistorik och berättar vilka "
        "produkter du bör beställa hem innan du tar slut. Inga fler "
        "lagerbrister, inget mer överbeställande.</p>"
        "<p><strong>AI-autokategorisering</strong><br>"
        "Ladda upp en rörig produktlista — Varuflow rensar upp den, "
        "tilldelar kategorier och föreslår prissättningsnivåer automatiskt.</p>"
        f"<p>{_ai_badge()}</p>"
        "<p>Båda funktionerna är tillgängliga i Pro-planen. Du har för "
        "närvarande ett provkonto med full Pro-åtkomst.</p>"
        + _cta_button("Utforska AI-funktioner →", ai_url, "#4f46e5")
        + _cta_button("Uppgradera till Pro →", upgrade_url, "#16a34a")
        + "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Upptäck AI-funktionerna i din provperiod",
        html_body=body,
    )


async def _trial_day_5_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    ai_url = f"{fe}/en/ai"
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>يكتشف معظم مستخدمي Varuflow ميزات الذكاء الاصطناعي متأخراً — "
        "نريد التأكد من أنك لن تفوّتها.</p>"
        "<p><strong>التنبؤ بالطلب بالذكاء الاصطناعي</strong><br>"
        "يحلّل Varuflow سجل مبيعاتك ويخبرك بالمنتجات التي تحتاج إلى إعادة "
        "طلبها قبل نفادها. لا مزيد من نقص المخزون أو الإفراط في الطلب.</p>"
        "<p><strong>التصنيف التلقائي بالذكاء الاصطناعي</strong><br>"
        "ارفع قائمة منتجات فوضوية — سيُنظّفها Varuflow، ويعيّن الفئات، "
        "ويقترح مستويات التسعير تلقائياً.</p>"
        f"<p>{_ai_badge()}</p>"
        "<p>كلتا الميزتين متاحتان في خطة Pro. أنت حالياً في فترة تجريبية "
        "تتضمن وصولاً كاملاً إلى Pro.</p>"
        + _cta_button("استكشاف ميزات الذكاء الاصطناعي →", ai_url, "#4f46e5")
        + _cta_button("الترقية إلى Pro →", upgrade_url, "#16a34a")
        + "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="اكتشف ميزات الذكاء الاصطناعي في فترتك التجريبية",
        html_body=body,
    )


async def _trial_day_5_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    ai_url = f"{fe}/en/ai"
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>La plupart des utilisateurs de Varuflow découvrent les "
        "fonctionnalités IA tardivement — nous voulons nous assurer que vous "
        "ne les manquez pas.</p>"
        "<p><strong>Prévision de la demande par IA</strong><br>"
        "Varuflow analyse votre historique des ventes et vous indique quels "
        "produits réapprovisionner avant d'être en rupture. Plus de ruptures "
        "de stock, plus de sur-commandes.</p>"
        "<p><strong>Catégorisation automatique par IA</strong><br>"
        "Importez une liste de produits désordonnée — Varuflow la nettoie, "
        "attribue des catégories et suggère des niveaux de tarification "
        "automatiquement.</p>"
        f"<p>{_ai_badge()}</p>"
        "<p>Ces deux fonctionnalités sont disponibles avec le plan Pro. "
        "Votre essai inclut un accès complet Pro.</p>"
        + _cta_button("Explorer les fonctionnalités IA →", ai_url, "#4f46e5")
        + _cta_button("Passer à Pro →", upgrade_url, "#16a34a")
        + "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Découvrez les fonctionnalités IA de votre essai",
        html_body=body,
    )


# ── Day 7 — Halfway through ───────────────────────────────────────────────────

async def _trial_day_7_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    plan = _h(tokens.get("plan_name", "Pro"))
    fe = settings.FRONTEND_URL
    body = _serif_wrapper(
        f"<p>Hi {first},</p>"
        "<p>You've been using Varuflow for 7 days now — I wanted to reach out "
        "personally.</p>"
        "<p>Building a wholesale business is genuinely hard work. I hope "
        f"Varuflow has been making at least some of it easier for you. "
        f"You've had access to the full {plan} plan this whole time.</p>"
        "<p>I'd love to know how it's going. What's been useful? What's been "
        "confusing or missing? I read every reply.</p>"
        "<p>If you have 5 minutes, just reply to this email. Or you can "
        'reach me directly at <a href="mailto:marcus@varuflow.app" '
        'style="color:#4f46e5">marcus@varuflow.app</a>.</p>'
        + _cta_button("Continue on Varuflow →", fe, "#16a34a")
        + "<p style='margin-top:40px'>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "Co-founder, Varuflow</span></p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Halfway through your trial, {first}",
        html_body=body,
    )


async def _trial_day_7_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    plan = _h(tokens.get("plan_name", "Pro"))
    fe = settings.FRONTEND_URL
    body = _serif_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Du har nu använt Varuflow i 7 dagar — jag ville höra av mig "
        "personligen.</p>"
        "<p>Att driva ett grossistföretag är genuint hårt arbete. Jag hoppas "
        f"att Varuflow har gjort åtminstone en del av det enklare för dig. "
        f"Du har haft tillgång till hela {plan}-planen hela tiden.</p>"
        "<p>Jag vill gärna veta hur det går. Vad har varit användbart? Vad "
        "har varit förvirrande eller saknats? Jag läser varje svar.</p>"
        "<p>Om du har 5 minuter, svara bara på det här mailet. Eller kontakta "
        'mig direkt på <a href="mailto:marcus@varuflow.app" '
        'style="color:#4f46e5">marcus@varuflow.app</a>.</p>'
        + _cta_button("Fortsätt med Varuflow →", fe, "#16a34a")
        + "<p style='margin-top:40px'>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "Medgrundare, Varuflow</span></p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Halvvägs genom din provperiod, {first}",
        html_body=body,
    )


async def _trial_day_7_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    plan = _h(tokens.get("plan_name", "Pro"))
    fe = settings.FRONTEND_URL
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>لقد مرّ سبعة أيام على استخدامك لـ Varuflow — أردت التواصل معك شخصياً.</p>"
        "<p>إدارة أعمال الجملة عمل شاق حقاً. آمل أن يكون Varuflow قد جعل "
        f"بعض الأمور أسهل بالنسبة لك. لقد كان بإمكانك الوصول الكامل إلى خطة "
        f"{plan} طوال هذه الفترة.</p>"
        "<p>أودّ معرفة كيف سارت الأمور. ما الذي كان مفيداً؟ ما الذي كان "
        "محيراً أو مفقوداً؟ أقرأ كل رد.</p>"
        "<p>إذا كان لديك 5 دقائق، فقط أجب على هذا البريد الإلكتروني. أو "
        'تواصل معي مباشرة على <a href="mailto:marcus@varuflow.app" '
        'style="color:#4f46e5">marcus@varuflow.app</a>.</p>'
        + _cta_button("متابعة على Varuflow →", fe, "#16a34a")
        + "<p style='margin-top:40px'>ماركوس بيرغ<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "المؤسس المشارك، Varuflow</span></p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"في منتصف فترتك التجريبية، {first}",
        html_body=body,
    )


async def _trial_day_7_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    plan = _h(tokens.get("plan_name", "Pro"))
    fe = settings.FRONTEND_URL
    body = _serif_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Cela fait 7 jours que vous utilisez Varuflow — je voulais vous "
        "contacter personnellement.</p>"
        "<p>Gérer une activité de gros est vraiment un travail difficile. "
        f"J'espère que Varuflow a rendu au moins certaines choses plus faciles "
        f"pour vous. Vous avez eu accès au plan {plan} complet tout ce temps.</p>"
        "<p>J'aimerais savoir comment ça se passe. Qu'est-ce qui a été utile ? "
        "Qu'est-ce qui a été déroutant ou manquant ? Je lis chaque réponse.</p>"
        "<p>Si vous avez 5 minutes, répondez simplement à cet e-mail. Ou "
        'contactez-moi directement à <a href="mailto:marcus@varuflow.app" '
        'style="color:#4f46e5">marcus@varuflow.app</a>.</p>'
        + _cta_button("Continuer sur Varuflow →", fe, "#16a34a")
        + "<p style='margin-top:40px'>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "Co-fondateur, Varuflow</span></p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"À mi-parcours de votre essai, {first}",
        html_body=body,
    )


# ── Day 10 — Customer success stories ────────────────────────────────────────

async def _trial_day_10_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    community_url = f"{fe}/en/community"
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Here are three Nordic wholesalers who switched to Varuflow and "
        "never looked back:</p>"
        '<div style="background:#f8fafc;border-left:3px solid #4f46e5;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Bergström Grossist, Malmö</strong><br>"
        '"Before Varuflow we had three spreadsheets, a shared email inbox, '
        "and a part-time bookkeeper reconciling everything on Fridays. Now "
        'it\'s all automatic. We saved 6 hours a week from day one."</p>'
        "</div>"
        '<div style="background:#f8fafc;border-left:3px solid #16a34a;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Nordic Parts AB, Göteborg</strong><br>"
        '"The AI reorder suggestions alone paid for the subscription in the '
        "first month. We had two major stockouts last year — we've had zero "
        'this year."</p>'
        "</div>"
        '<div style="background:#f8fafc;border-left:3px solid #f59e0b;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Hansson &amp; Co, Oslo</strong><br>"
        '"We distribute to 80 retailers. Sending 80 invoices manually was '
        "taking half a day every week. With Varuflow's recurring invoices it "
        'takes 5 minutes."</p>'
        "</div>"
        "<p>Want to share your story or connect with other Nordic wholesalers? "
        "Join our community.</p>"
        + _cta_button("Join the community →", community_url, "#4f46e5")
        + "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Tips from successful Varuflow customers",
        html_body=body,
    )


async def _trial_day_10_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    community_url = f"{fe}/sv/community"
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Här är tre nordiska grossister som bytte till Varuflow och aldrig "
        "tittade tillbaka:</p>"
        '<div style="background:#f8fafc;border-left:3px solid #4f46e5;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Bergström Grossist, Malmö</strong><br>"
        '"Innan Varuflow hade vi tre kalkylblad, en delad e-postinkorg och en '
        "deltidsbokförare som stämde av allt på fredagar. Nu är allt "
        'automatiskt. Vi sparade 6 timmar i veckan från dag ett."</p>'
        "</div>"
        '<div style="background:#f8fafc;border-left:3px solid #16a34a;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Nordic Parts AB, Göteborg</strong><br>"
        '"AI-påfyllningsförslagen ensamma betalade för prenumerationen den '
        "första månaden. Vi hade två stora lagerbrister förra året — vi har "
        'haft noll i år."</p>'
        "</div>"
        '<div style="background:#f8fafc;border-left:3px solid #f59e0b;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Hansson &amp; Co, Oslo</strong><br>"
        '"Vi distribuerar till 80 återförsäljare. Att skicka 80 fakturor '
        "manuellt tog en halv dag varje vecka. Med Varuflows återkommande "
        'fakturor tar det 5 minuter."</p>'
        "</div>"
        "<p>Vill du dela din historia eller kontakta andra nordiska grossister? "
        "Gå med i vår community.</p>"
        + _cta_button("Gå med i communityn →", community_url, "#4f46e5")
        + "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Tips från framgångsrika Varuflow-kunder",
        html_body=body,
    )


async def _trial_day_10_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    community_url = f"{fe}/en/community"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>إليك ثلاثة تجار جملة إسكندنافيين انتقلوا إلى Varuflow ولم "
        "يتراجعوا أبداً:</p>"
        '<div style="background:#f8fafc;border-right:3px solid #4f46e5;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Bergström Grossist، مالمو</strong><br>"
        '«قبل Varuflow كان لدينا ثلاثة جداول بيانات وصندوق بريد مشترك '
        "ومحاسب بدوام جزئي يُطابق كل شيء كل جمعة. الآن كل شيء تلقائي. "
        'وفّرنا 6 ساعات أسبوعياً منذ اليوم الأول.»</p>'
        "</div>"
        '<div style="background:#f8fafc;border-right:3px solid #16a34a;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Nordic Parts AB، غوتنبرغ</strong><br>"
        '«اقتراحات إعادة الطلب بالذكاء الاصطناعي وحدها غطّت تكلفة الاشتراك '
        "في الشهر الأول. كان لدينا نقصان كبيران في المخزون العام الماضي — "
        'لم يكن لدينا أي نقص هذا العام.»</p>'
        "</div>"
        '<div style="background:#f8fafc;border-right:3px solid #f59e0b;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Hansson &amp; Co، أوسلو</strong><br>"
        '«نوزّع على 80 موزعاً بالتجزئة. كان إرسال 80 فاتورة يدوياً يستغرق '
        "نصف يوم كل أسبوع. مع فواتير Varuflow المتكررة أصبح الأمر يستغرق "
        '5 دقائق.»</p>'
        "</div>"
        "<p>هل تريد مشاركة قصتك أو التواصل مع تجار جملة إسكندنافيين آخرين؟ "
        "انضم إلى مجتمعنا.</p>"
        + _cta_button("انضم إلى المجتمع →", community_url, "#4f46e5")
        + "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="نصائح من عملاء Varuflow الناجحين",
        html_body=body,
    )


async def _trial_day_10_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    community_url = f"{fe}/en/community"
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Voici trois grossistes nordiques qui sont passés à Varuflow et ne "
        "l'ont jamais regretté :</p>"
        '<div style="background:#f8fafc;border-left:3px solid #4f46e5;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Bergström Grossist, Malmö</strong><br>"
        '« Avant Varuflow, nous avions trois tableurs, une boîte e-mail '
        "partagée et un comptable à temps partiel qui rapprochait tout le "
        "vendredi. Maintenant tout est automatique. Nous avons économisé "
        '6 heures par semaine dès le premier jour. »</p>'
        "</div>"
        '<div style="background:#f8fafc;border-left:3px solid #16a34a;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Nordic Parts AB, Göteborg</strong><br>"
        '« Les suggestions de réapprovisionnement IA seules ont payé '
        "l'abonnement dès le premier mois. Nous avons eu deux ruptures "
        "majeures l'année dernière — nous en avons eu zéro cette année. »</p>"
        "</div>"
        '<div style="background:#f8fafc;border-left:3px solid #f59e0b;'
        'padding:14px 18px;margin:18px 0;border-radius:4px">'
        "<p><strong>Hansson &amp; Co, Oslo</strong><br>"
        '« Nous distribuons à 80 détaillants. Envoyer 80 factures '
        "manuellement prenait une demi-journée chaque semaine. Avec les "
        "factures récurrentes de Varuflow, ça prend 5 minutes. »</p>"
        "</div>"
        "<p>Vous souhaitez partager votre histoire ou rencontrer d'autres "
        "grossistes nordiques ? Rejoignez notre communauté.</p>"
        + _cta_button("Rejoindre la communauté →", community_url, "#4f46e5")
        + "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Conseils de clients Varuflow qui réussissent",
        html_body=body,
    )


# ── Day 12 — Trial ending soon ────────────────────────────────────────────────

def _urgency_banner(text: str) -> str:
    return (
        f'<div style="background:#dc2626;color:#fff;padding:12px 18px;'
        f'border-radius:6px;margin-bottom:20px;font-family:sans-serif;'
        f'font-weight:700;font-size:14px;text-align:center">{text}</div>'
    )


async def _trial_day_12_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "in 2 days"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ Your trial ends in 2 days")
        + f"<p>Hi {first},</p>"
        "<p>Your Varuflow trial ends soon. To keep your invoices, products, "
        "customers, and AI features, upgrade before your trial expires.</p>"
        "<p><strong>Annual plan saves you 2 months</strong> — pay for 10, "
        "get 12. That's the best deal we offer.</p>"
        "<ul>"
        "<li>Unlimited invoices &amp; customers</li>"
        "<li>Full AI demand forecasting</li>"
        "<li>Team access (up to 10 members)</li>"
        "<li>Fortnox integration</li>"
        "<li>Priority support</li>"
        "</ul>"
        + _cta_button("Upgrade now →", upgrade_url, "#16a34a")
        + f"<p>Your trial ends: <strong>{end_date}</strong></p>"
        "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Trial ending soon — upgrade now",
        html_body=body,
    )


async def _trial_day_12_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "om 2 dagar"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/sv/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ Din provperiod slutar om 2 dagar")
        + f"<p>Hej {first},</p>"
        "<p>Din Varuflow-provperiod slutar snart. För att behålla dina "
        "fakturor, produkter, kunder och AI-funktioner — uppgradera innan "
        "provperioden löper ut.</p>"
        "<p><strong>Årsplanen sparar dig 2 månader</strong> — betala för 10, "
        "få 12. Det är det bästa erbjudandet vi har.</p>"
        "<ul>"
        "<li>Obegränsade fakturor &amp; kunder</li>"
        "<li>Full AI-efterfrågeprognoser</li>"
        "<li>Teamåtkomst (upp till 10 medlemmar)</li>"
        "<li>Fortnox-integration</li>"
        "<li>Prioriterad support</li>"
        "</ul>"
        + _cta_button("Uppgradera nu →", upgrade_url, "#16a34a")
        + f"<p>Din provperiod slutar: <strong>{end_date}</strong></p>"
        "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Provperioden slutar snart — uppgradera nu",
        html_body=body,
    )


async def _trial_day_12_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "خلال يومين"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ تنتهي فترتك التجريبية خلال يومين")
        + f"<p>مرحباً {first}،</p>"
        "<p>تنتهي فترتك التجريبية في Varuflow قريباً. للحفاظ على فواتيرك "
        "ومنتجاتك وعملائك وميزات الذكاء الاصطناعي، قم بالترقية قبل انتهاء "
        "الفترة التجريبية.</p>"
        "<p><strong>الخطة السنوية توفّر لك شهرين</strong> — ادفع مقابل 10، "
        "واحصل على 12. هذا أفضل عرض نقدمه.</p>"
        "<ul>"
        "<li>فواتير وعملاء غير محدودين</li>"
        "<li>التنبؤ الكامل بالطلب بالذكاء الاصطناعي</li>"
        "<li>وصول الفريق (حتى 10 أعضاء)</li>"
        "<li>تكامل Fortnox</li>"
        "<li>دعم ذو أولوية</li>"
        "</ul>"
        + _cta_button("الترقية الآن →", upgrade_url, "#16a34a")
        + f"<p>تنتهي فترتك التجريبية: <strong>{end_date}</strong></p>"
        "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="تنتهي الفترة التجريبية قريباً — قم بالترقية الآن",
        html_body=body,
    )


async def _trial_day_12_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "dans 2 jours"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ Votre essai se termine dans 2 jours")
        + f"<p>Bonjour {first},</p>"
        "<p>Votre essai Varuflow se termine bientôt. Pour conserver vos "
        "factures, produits, clients et fonctionnalités IA, passez à la "
        "version complète avant l'expiration de votre essai.</p>"
        "<p><strong>Le plan annuel vous fait économiser 2 mois</strong> — "
        "payez 10, obtenez 12. C'est la meilleure offre que nous proposons.</p>"
        "<ul>"
        "<li>Factures et clients illimités</li>"
        "<li>Prévision de la demande IA complète</li>"
        "<li>Accès équipe (jusqu'à 10 membres)</li>"
        "<li>Intégration Fortnox</li>"
        "<li>Support prioritaire</li>"
        "</ul>"
        + _cta_button("Mettre à niveau maintenant →", upgrade_url, "#16a34a")
        + f"<p>Votre essai se termine : <strong>{end_date}</strong></p>"
        "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Essai se terminant bientôt — mettez à niveau maintenant",
        html_body=body,
    )


# ── Day 13 — Trial ends tomorrow ─────────────────────────────────────────────

async def _trial_day_13_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "tomorrow"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ Your trial ends tomorrow")
        + f"<p>Hi {first},</p>"
        "<p>This is your last chance. Your trial ends on "
        f"<strong>{end_date}</strong>.</p>"
        "<p><strong>Here's what you'll lose if you don't upgrade:</strong></p>"
        "<ul>"
        "<li>AI demand forecasting &amp; auto-categorisation</li>"
        "<li>Team member access</li>"
        "<li>Unlimited invoices (free plan is capped at 5/month)</li>"
        "<li>Fortnox sync</li>"
        "<li>Priority support</li>"
        "</ul>"
        '<div style="background:#fef9c3;border:1px solid #fde047;padding:14px 18px;'
        'border-radius:6px;margin:20px 0;font-family:sans-serif">'
        "<strong>Special offer:</strong> Upgrade today and get "
        "<strong>20% off your first 3 months</strong>. Use code "
        "<strong>TRIAL20</strong> at checkout."
        "</div>"
        + _cta_button("Upgrade before it's too late →", upgrade_url, "#dc2626")
        + "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Trial ends tomorrow, {first}",
        html_body=body,
    )


async def _trial_day_13_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "imorgon"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/sv/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ Din provperiod slutar imorgon")
        + f"<p>Hej {first},</p>"
        "<p>Det här är din sista chans. Din provperiod slutar "
        f"<strong>{end_date}</strong>.</p>"
        "<p><strong>Det här förlorar du om du inte uppgraderar:</strong></p>"
        "<ul>"
        "<li>AI-efterfrågeprognoser &amp; autokategorisering</li>"
        "<li>Teammedlemsåtkomst</li>"
        "<li>Obegränsade fakturor (gratisplanen är begränsad till 5/månad)</li>"
        "<li>Fortnox-synk</li>"
        "<li>Prioriterad support</li>"
        "</ul>"
        '<div style="background:#fef9c3;border:1px solid #fde047;padding:14px 18px;'
        'border-radius:6px;margin:20px 0;font-family:sans-serif">'
        "<strong>Specialerbjudande:</strong> Uppgradera idag och få "
        "<strong>20% rabatt de första 3 månaderna</strong>. Använd koden "
        "<strong>TRIAL20</strong> i kassan."
        "</div>"
        + _cta_button("Uppgradera innan det är för sent →", upgrade_url, "#dc2626")
        + "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Provperioden slutar imorgon, {first}",
        html_body=body,
    )


async def _trial_day_13_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "غداً"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ تنتهي فترتك التجريبية غداً")
        + f"<p>مرحباً {first}،</p>"
        "<p>هذه فرصتك الأخيرة. تنتهي فترتك التجريبية في "
        f"<strong>{end_date}</strong>.</p>"
        "<p><strong>إليك ما ستفقده إذا لم تقم بالترقية:</strong></p>"
        "<ul>"
        "<li>التنبؤ بالطلب بالذكاء الاصطناعي والتصنيف التلقائي</li>"
        "<li>وصول أعضاء الفريق</li>"
        "<li>فواتير غير محدودة (الخطة المجانية محدودة بـ 5 في الشهر)</li>"
        "<li>مزامنة Fortnox</li>"
        "<li>دعم ذو أولوية</li>"
        "</ul>"
        '<div style="background:#fef9c3;border:1px solid #fde047;padding:14px 18px;'
        'border-radius:6px;margin:20px 0;font-family:sans-serif">'
        "<strong>عرض خاص:</strong> قم بالترقية اليوم واحصل على "
        "<strong>خصم 20% على أول 3 أشهر</strong>. استخدم الرمز "
        "<strong>TRIAL20</strong> عند الدفع."
        "</div>"
        + _cta_button("قم بالترقية قبل فوات الأوان →", upgrade_url, "#dc2626")
        + "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"تنتهي الفترة التجريبية غداً، {first}",
        html_body=body,
    )


async def _trial_day_13_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    end_date = _h(tokens.get("trial_end_date", "demain"))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    body = _email_wrapper(
        _urgency_banner("⚠ Votre essai se termine demain")
        + f"<p>Bonjour {first},</p>"
        "<p>C'est votre dernière chance. Votre essai se termine le "
        f"<strong>{end_date}</strong>.</p>"
        "<p><strong>Voici ce que vous perdrez si vous ne mettez pas à niveau :</strong></p>"
        "<ul>"
        "<li>Prévision de la demande IA &amp; auto-catégorisation</li>"
        "<li>Accès des membres de l'équipe</li>"
        "<li>Factures illimitées (le plan gratuit est limité à 5/mois)</li>"
        "<li>Synchronisation Fortnox</li>"
        "<li>Support prioritaire</li>"
        "</ul>"
        '<div style="background:#fef9c3;border:1px solid #fde047;padding:14px 18px;'
        'border-radius:6px;margin:20px 0;font-family:sans-serif">'
        "<strong>Offre spéciale :</strong> Mettez à niveau aujourd'hui et "
        "obtenez <strong>20% de réduction sur vos 3 premiers mois</strong>. "
        "Utilisez le code <strong>TRIAL20</strong> à la caisse."
        "</div>"
        + _cta_button("Passer à la version complète avant qu'il soit trop tard →", upgrade_url, "#dc2626")
        + "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject=f"Votre essai se termine demain, {first}",
        html_body=body,
    )


# ── Day 14 — Trial has ended ──────────────────────────────────────────────────

async def _trial_day_14_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    survey_url = f"{fe}/en/feedback/trial-exit"
    body = _email_wrapper(
        f"<p>Hi {first},</p>"
        "<p>Your Varuflow trial has ended. You've been automatically moved "
        "to the <strong>free plan</strong>.</p>"
        "<p><strong>What you no longer have access to:</strong></p>"
        "<ul>"
        "<li>AI demand forecasting &amp; auto-categorisation</li>"
        "<li>Team member access</li>"
        "<li>Invoices beyond 5/month</li>"
        "<li>Fortnox sync</li>"
        "</ul>"
        "<p>Your data is safe. All your invoices, products, and customers "
        "are still here — you just can't create new ones beyond the free "
        "plan limits until you reactivate.</p>"
        + _cta_button("Reactivate my account →", upgrade_url, "#16a34a")
        + '<p style="margin-top:24px;font-size:13px;color:#64748b">'
        f'<a href="{_h(survey_url)}" style="color:#94a3b8">'
        "Tell us why you didn't upgrade →</a></p>"
        "<p>The Varuflow team</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Your Varuflow trial has ended",
        html_body=body,
    )


async def _trial_day_14_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/sv/settings/billing"
    survey_url = f"{fe}/sv/feedback/trial-exit"
    body = _email_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Din Varuflow-provperiod har avslutats. Du har automatiskt "
        "flyttats till <strong>gratisplanen</strong>.</p>"
        "<p><strong>Det du inte längre har tillgång till:</strong></p>"
        "<ul>"
        "<li>AI-efterfrågeprognoser &amp; autokategorisering</li>"
        "<li>Teammedlemsåtkomst</li>"
        "<li>Fakturor utöver 5/månad</li>"
        "<li>Fortnox-synk</li>"
        "</ul>"
        "<p>Din data är säker. Alla dina fakturor, produkter och kunder "
        "finns kvar — du kan bara inte skapa nya utöver gratisplanens "
        "gränser förrän du återaktiverar.</p>"
        + _cta_button("Återaktivera mitt konto →", upgrade_url, "#16a34a")
        + '<p style="margin-top:24px;font-size:13px;color:#64748b">'
        f'<a href="{_h(survey_url)}" style="color:#94a3b8">'
        "Berätta varför du inte uppgraderade →</a></p>"
        "<p>Varuflow-teamet</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Din Varuflow-provperiod har avslutats",
        html_body=body,
    )


async def _trial_day_14_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    survey_url = f"{fe}/en/feedback/trial-exit"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>انتهت فترتك التجريبية في Varuflow. تم نقلك تلقائياً إلى "
        "<strong>الخطة المجانية</strong>.</p>"
        "<p><strong>ما لم يعد بإمكانك الوصول إليه:</strong></p>"
        "<ul>"
        "<li>التنبؤ بالطلب بالذكاء الاصطناعي والتصنيف التلقائي</li>"
        "<li>وصول أعضاء الفريق</li>"
        "<li>الفواتير ما يتجاوز 5 في الشهر</li>"
        "<li>مزامنة Fortnox</li>"
        "</ul>"
        "<p>بياناتك في أمان. جميع فواتيرك ومنتجاتك وعملاؤك لا يزالون هنا "
        "— فقط لا يمكنك إنشاء جديد يتجاوز حدود الخطة المجانية حتى تعيد "
        "التفعيل.</p>"
        + _cta_button("إعادة تفعيل حسابي →", upgrade_url, "#16a34a")
        + '<p style="margin-top:24px;font-size:13px;color:#64748b">'
        f'<a href="{_h(survey_url)}" style="color:#94a3b8">'
        "أخبرنا لماذا لم تقم بالترقية →</a></p>"
        "<p>فريق Varuflow</p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="انتهت فترتك التجريبية في Varuflow",
        html_body=body,
    )


async def _trial_day_14_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    upgrade_url = f"{fe}/en/settings/billing"
    survey_url = f"{fe}/en/feedback/trial-exit"
    body = _email_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>Votre essai Varuflow s'est terminé. Vous avez été automatiquement "
        "déplacé vers le <strong>plan gratuit</strong>.</p>"
        "<p><strong>Ce à quoi vous n'avez plus accès :</strong></p>"
        "<ul>"
        "<li>Prévision de la demande IA &amp; auto-catégorisation</li>"
        "<li>Accès des membres de l'équipe</li>"
        "<li>Factures au-delà de 5/mois</li>"
        "<li>Synchronisation Fortnox</li>"
        "</ul>"
        "<p>Vos données sont en sécurité. Toutes vos factures, produits et "
        "clients sont toujours là — vous ne pouvez simplement pas en créer "
        "de nouveaux au-delà des limites du plan gratuit jusqu'à la "
        "réactivation.</p>"
        + _cta_button("Réactiver mon compte →", upgrade_url, "#16a34a")
        + '<p style="margin-top:24px;font-size:13px;color:#64748b">'
        f'<a href="{_h(survey_url)}" style="color:#94a3b8">'
        "Dites-nous pourquoi vous n'avez pas mis à niveau →</a></p>"
        "<p>L'équipe Varuflow</p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Varuflow", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Votre essai Varuflow s'est terminé",
        html_body=body,
    )


# ── Day 21 — Feedback (non-converters) ───────────────────────────────────────

async def _trial_day_21_en(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    survey_url = f"{fe}/en/feedback/trial-exit"
    body = _serif_wrapper(
        f"<p>Hi {first},</p>"
        "<p>It's Marcus. You tried Varuflow a few weeks ago and decided not "
        "to continue — and that's completely fine.</p>"
        "<p>I'm not writing to sell you anything. I genuinely want to "
        "understand what we could have done better. We build Varuflow for "
        "Nordic wholesalers, and every piece of honest feedback makes the "
        "product better for everyone.</p>"
        "<p>Two questions — takes 60 seconds:</p>"
        "<ol>"
        "<li>What was the main reason you didn't continue with Varuflow?</li>"
        "<li>Is there one feature that, if we'd had it, would have changed "
        "your mind?</li>"
        "</ol>"
        + _cta_button("Answer 2 questions →", survey_url, "#4f46e5")
        + "<p>Or just reply here — I read every email personally.</p>"
        "<p style='margin-top:40px'>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "Co-founder, Varuflow<br>"
        '<a href="mailto:marcus@varuflow.app" style="color:#64748b">'
        "marcus@varuflow.app</a></span></p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="We'd love your feedback",
        html_body=body,
    )


async def _trial_day_21_sv(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    survey_url = f"{fe}/sv/feedback/trial-exit"
    body = _serif_wrapper(
        f"<p>Hej {first},</p>"
        "<p>Det är Marcus. Du provade Varuflow för några veckor sedan och "
        "valde att inte fortsätta — och det är helt okej.</p>"
        "<p>Jag skriver inte för att sälja dig något. Jag vill genuint "
        "förstå vad vi hade kunnat göra bättre. Vi bygger Varuflow för "
        "nordiska grossister, och varje ärlig feedback gör produkten bättre "
        "för alla.</p>"
        "<p>Två frågor — tar 60 sekunder:</p>"
        "<ol>"
        "<li>Vad var det främsta skälet till att du inte fortsatte med Varuflow?</li>"
        "<li>Finns det en funktion som, om vi hade haft den, hade ändrat din "
        "åsikt?</li>"
        "</ol>"
        + _cta_button("Svara på 2 frågor →", survey_url, "#4f46e5")
        + "<p>Eller svara bara här — jag läser varje mail personligen.</p>"
        "<p style='margin-top:40px'>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "Medgrundare, Varuflow<br>"
        '<a href="mailto:marcus@varuflow.app" style="color:#64748b">'
        "marcus@varuflow.app</a></span></p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Vi vill gärna ha din feedback",
        html_body=body,
    )


async def _trial_day_21_ar(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    survey_url = f"{fe}/en/feedback/trial-exit"
    body = _email_wrapper(
        f"<p>مرحباً {first}،</p>"
        "<p>أنا ماركوس. جرّبت Varuflow قبل بضعة أسابيع وقررت عدم الاستمرار "
        "— وهذا أمر مقبول تماماً.</p>"
        "<p>لا أكتب إليك لأبيعك شيئاً. أريد حقاً أن أفهم ما كان يمكننا "
        "فعله بشكل أفضل. نبني Varuflow لتجار الجملة الإسكندنافيين، وكل "
        "ملاحظة صادقة تجعل المنتج أفضل للجميع.</p>"
        "<p>سؤالان — يستغرقان 60 ثانية:</p>"
        "<ol>"
        "<li>ما السبب الرئيسي لعدم استمرارك في استخدام Varuflow؟</li>"
        "<li>هل هناك ميزة واحدة كانت ستغير رأيك لو أتحنا؟</li>"
        "</ol>"
        + _cta_button("الإجابة على سؤالين →", survey_url, "#4f46e5")
        + "<p>أو فقط أجب على هذا البريد — أقرأ كل بريد إلكتروني شخصياً.</p>"
        "<p style='margin-top:40px'>ماركوس بيرغ<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "المؤسس المشارك، Varuflow<br>"
        '<a href="mailto:marcus@varuflow.app" style="color:#64748b">'
        "marcus@varuflow.app</a></span></p>",
        rtl=True,
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="نودّ الحصول على ملاحظاتك",
        html_body=body,
    )


async def _trial_day_21_fr(*, to_email: str, tokens: dict) -> bool:
    first = _h(tokens.get("first_name", ""))
    fe = settings.FRONTEND_URL
    survey_url = f"{fe}/en/feedback/trial-exit"
    body = _serif_wrapper(
        f"<p>Bonjour {first},</p>"
        "<p>C'est Marcus. Vous avez essayé Varuflow il y a quelques semaines "
        "et décidé de ne pas continuer — et c'est tout à fait normal.</p>"
        "<p>Je n'écris pas pour vous vendre quoi que ce soit. Je veux "
        "sincèrement comprendre ce que nous aurions pu faire mieux. Nous "
        "construisons Varuflow pour les grossistes nordiques, et chaque "
        "retour honnête améliore le produit pour tout le monde.</p>"
        "<p>Deux questions — 60 secondes :</p>"
        "<ol>"
        "<li>Quelle était la principale raison pour laquelle vous n'avez pas "
        "continué avec Varuflow ?</li>"
        "<li>Y a-t-il une fonctionnalité qui, si nous l'avions eue, aurait "
        "changé votre avis ?</li>"
        "</ol>"
        + _cta_button("Répondre à 2 questions →", survey_url, "#4f46e5")
        + "<p>Ou répondez simplement ici — je lis chaque e-mail personnellement.</p>"
        "<p style='margin-top:40px'>Marcus Berg<br>"
        '<span style="color:#64748b;font-size:13px;font-family:sans-serif">'
        "Co-fondateur, Varuflow<br>"
        '<a href="mailto:marcus@varuflow.app" style="color:#64748b">'
        "marcus@varuflow.app</a></span></p>"
    )
    return await _send_onboarding(
        from_header=_from_header("Marcus Berg", "onboarding@varuflow.app"),
        to_email=to_email,
        subject="Nous aimerions avoir votre avis",
        html_body=body,
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

_TRIAL_ONBOARDING_REGISTRY: dict = {
    # Day 0
    "trial_day_0_en": _trial_day_0_en,
    "trial_day_0_sv": _trial_day_0_sv,
    "trial_day_0_ar": _trial_day_0_ar,
    "trial_day_0_fr": _trial_day_0_fr,
    # Day 1
    "trial_day_1_en": _trial_day_1_en,
    "trial_day_1_sv": _trial_day_1_sv,
    "trial_day_1_ar": _trial_day_1_ar,
    "trial_day_1_fr": _trial_day_1_fr,
    # Day 2
    "trial_day_2_en": _trial_day_2_en,
    "trial_day_2_sv": _trial_day_2_sv,
    "trial_day_2_ar": _trial_day_2_ar,
    "trial_day_2_fr": _trial_day_2_fr,
    # Day 3
    "trial_day_3_en": _trial_day_3_en,
    "trial_day_3_sv": _trial_day_3_sv,
    "trial_day_3_ar": _trial_day_3_ar,
    "trial_day_3_fr": _trial_day_3_fr,
    # Day 5
    "trial_day_5_en": _trial_day_5_en,
    "trial_day_5_sv": _trial_day_5_sv,
    "trial_day_5_ar": _trial_day_5_ar,
    "trial_day_5_fr": _trial_day_5_fr,
    # Day 7
    "trial_day_7_en": _trial_day_7_en,
    "trial_day_7_sv": _trial_day_7_sv,
    "trial_day_7_ar": _trial_day_7_ar,
    "trial_day_7_fr": _trial_day_7_fr,
    # Day 10
    "trial_day_10_en": _trial_day_10_en,
    "trial_day_10_sv": _trial_day_10_sv,
    "trial_day_10_ar": _trial_day_10_ar,
    "trial_day_10_fr": _trial_day_10_fr,
    # Day 12
    "trial_day_12_en": _trial_day_12_en,
    "trial_day_12_sv": _trial_day_12_sv,
    "trial_day_12_ar": _trial_day_12_ar,
    "trial_day_12_fr": _trial_day_12_fr,
    # Day 13
    "trial_day_13_en": _trial_day_13_en,
    "trial_day_13_sv": _trial_day_13_sv,
    "trial_day_13_ar": _trial_day_13_ar,
    "trial_day_13_fr": _trial_day_13_fr,
    # Day 14
    "trial_day_14_en": _trial_day_14_en,
    "trial_day_14_sv": _trial_day_14_sv,
    "trial_day_14_ar": _trial_day_14_ar,
    "trial_day_14_fr": _trial_day_14_fr,
    # Day 21
    "trial_day_21_en": _trial_day_21_en,
    "trial_day_21_sv": _trial_day_21_sv,
    "trial_day_21_ar": _trial_day_21_ar,
    "trial_day_21_fr": _trial_day_21_fr,
}


async def send_trial_onboarding_email(
    *,
    template_key: str,
    to_email: str,
    tokens: dict,
    org_name: str,
) -> bool:
    """Dispatcher for all trial onboarding email templates.

    template_key format: "trial_day_{N}_{locale}"
    tokens dict: first_name, org_name, trial_end_date, plan_name, days_remaining
    Returns False if Resend not configured or template_key not found.
    """
    if not settings.RESEND_API_KEY or not to_email:
        return False

    # Merge org_name into tokens so sub-functions can access it uniformly.
    merged_tokens = {"org_name": org_name, **tokens}

    handler = _TRIAL_ONBOARDING_REGISTRY.get(template_key)
    if handler is None:
        return False

    return await handler(to_email=to_email, tokens=merged_tokens)
