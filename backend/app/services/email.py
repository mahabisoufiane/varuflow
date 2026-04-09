"""Email sending via Resend API using httpx."""
import httpx

from app.config import settings


RESEND_URL = "https://api.resend.com/emails"


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
        "from": f"{org_name} <invoices@varuflow.app>",
        "to": [to_email],
        "subject": f"Invoice {invoice_number} from {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Invoice {invoice_number}</h2>
          <p>Dear {customer_name},</p>
          <p>Please find attached your invoice for <strong>{total_sek} SEK</strong>, due by <strong>{due_date}</strong>.</p>
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
        "from": f"{org_name} <portal@varuflow.app>",
        "to": [to_email],
        "subject": f"Your secure login link — {org_name} portal",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Sign in to your portal</h2>
          <p>Hi {customer_name},</p>
          <p>Click below to securely access your invoices. This link expires in 15 minutes.</p>
          <p style="margin:24px 0">
            <a href="{magic_url}" style="background:#1a2332;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
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
            <a href="{payment_url}" style="background:#dc2626;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
              Pay now — {total_sek} SEK
            </a>
          </p>"""

    urgency = "2nd reminder" if days_overdue >= 14 else "Payment reminder"
    payload = {
        "from": f"{org_name} <invoices@varuflow.app>",
        "to": [to_email],
        "subject": f"[{urgency}] Invoice {invoice_number} — {days_overdue} days overdue",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin-bottom:20px">
            <strong style="color:#dc2626">&#9888;&#65039; Payment overdue by {days_overdue} days</strong>
          </div>
          <h2 style="color:#1a2332">Invoice {invoice_number}</h2>
          <p>Dear {customer_name},</p>
          <p>
            This is a reminder that invoice <strong>{invoice_number}</strong> for
            <strong>{total_sek} SEK</strong> was due on <strong>{due_date}</strong>
            and is now <strong>{days_overdue} days overdue</strong>.
          </p>
          {pay_button}
          <p>If you have already arranged payment, please disregard this message.</p>
          <p style="margin-top:24px;color:#888;font-size:12px">
            Sent by {org_name} via Varuflow · Reply to this email with any questions.
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
        f"<tr><td style='padding:6px 8px;border-bottom:1px solid #eee'>{i['name']}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee;color:#888'>{i['sku']}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee;color:#dc2626;font-weight:600'>{i['stock']}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{i['reorder_level']}</td></tr>"
        for i in low_stock_items
    )

    payload = {
        "from": f"{org_name} <alerts@varuflow.app>",
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


async def send_weekly_digest_email(
    to_email: str,
    org_name: str,
    stats: dict,
) -> bool:
    """Send a weekly digest email. stats: {revenue, sales_count, top_products, low_stock_count}."""
    if not settings.RESEND_API_KEY:
        return False

    top_rows = "".join(
        f"<li style='margin:4px 0'>{p['name']} — <strong>{p['quantity']} units</strong></li>"
        for p in stats.get("top_products", [])[:5]
    )

    payload = {
        "from": f"Varuflow <digest@varuflow.app>",
        "to": [to_email],
        "subject": f"Weekly digest — {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#1a2332">Your weekly summary</h2>
          <p style="color:#888">Week ending {stats.get('week_ending', '')}</p>
          <div style="display:flex;gap:16px;margin:24px 0">
            <div style="flex:1;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:28px;font-weight:700;color:#16a34a">{stats.get('revenue', '0')} kr</div>
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
        "from": f"{org_name} <invoices@varuflow.app>",
        "to": [to_email],
        "subject": f"Pay invoice {invoice_number} online — {org_name}",
        "html": f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1a2332">Invoice {invoice_number}</h2>
          <p>Dear {customer_name},</p>
          <p>Your invoice for <strong>{total_sek} SEK</strong> is due by <strong>{due_date}</strong>.</p>
          <p style="margin:24px 0">
            <a href="{payment_url}" style="background:#1a2332;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
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

