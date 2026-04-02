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
