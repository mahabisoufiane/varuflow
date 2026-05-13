"""WhatsApp + SMS transport for dunning reminders (Item 18 — v40).

Provider-agnostic HTTP bridge. Both channels POST the same
``{"to": "+E164", "from": "...", "body": "..."}`` JSON to a configured
endpoint with a Bearer token. Any gateway matching that contract
works — Twilio Content API behind a shim, Meta Cloud API behind a
shim, 46elks, Sinch, whatever the operator has.

Keeping this provider-shape-agnostic at the service layer means
swapping providers is a config change, not a code change.

The module also exports ``normalise_e164`` which accepts the
loose strings merchants paste into the UI (``"+46 70 123 45 67"``,
``"070-1234567"``, ``"0046701234567"``) and returns a well-formed
``+46…`` or ``None``. If normalisation fails the caller skips the
channel — per spec, a WhatsApp failure must never block the email
reminder.
"""
from __future__ import annotations

import logging
import re

import httpx

from app.config import settings

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Phone normalisation
# ─────────────────────────────────────────────────────────────────────────────

# Strip every character that is not a digit or a leading '+'. Swedish
# UIs routinely include spaces, hyphens, and parentheses in copy-paste.
_NON_DIGIT = re.compile(r"[^\d+]")


def normalise_e164(raw: str | None, *, default_country_code: str = "46") -> str | None:
    """Return ``"+<digits>"`` or ``None``.

    Accepts:
      * ``"+46701234567"`` → ``"+46701234567"``
      * ``"0046701234567"`` → ``"+46701234567"``
      * ``"0701234567"`` → ``"+46701234567"`` (default country prefix applied)
      * ``"+46 70-123 45 67"`` → ``"+46701234567"``
      * Anything under 8 digits or over 15 → ``None`` (ITU-T E.164 limit).

    The default country code matters only for purely-local numbers
    starting with ``0``. For a multi-country deploy the caller should
    pass the customer's country prefix explicitly; the dunning sweep
    today only serves Swedish orgs so +46 is a safe fallback.
    """
    if not raw:
        return None
    cleaned = _NON_DIGIT.sub("", raw.strip())
    if not cleaned:
        return None

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("00"):
        digits = cleaned[2:]
    elif cleaned.startswith("0"):
        # Local format — strip the trunk zero and prefix the default CC.
        digits = default_country_code + cleaned[1:]
    else:
        # No country prefix at all — accept only if already long enough
        # to plausibly be E.164 without a trunk zero (e.g. "46701234567").
        digits = cleaned

    # E.164: country code + subscriber number ≤ 15 digits, ≥ 8 practical
    # minimum (an 8-digit subscriber + at least 1-digit CC).
    if not digits.isdigit() or not (8 <= len(digits) <= 15):
        return None
    return "+" + digits


# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

# Kept short and polite per spec. No PII beyond invoice number and
# amount; no payment link (the customer already has that from the
# invoice email and including it on WhatsApp makes the message look
# like a smishing attempt). Formatted with a stable keyword set so a
# translator swap is a drop-in.
_WHATSAPP_TEMPLATES: dict[int, str] = {
    1: (
        "Hej {customer_name}, en vänlig påminnelse om faktura "
        "{invoice_number} på {amount} SEK som förfallit. "
        "Tack! – {org_name}"
    ),
    2: (
        "Hej {customer_name}, faktura {invoice_number} på {amount} SEK "
        "är {days_overdue} dagar försenad. Vänligen betala snarast. – {org_name}"
    ),
    3: (
        "Hej {customer_name}, detta är en sista påminnelse på faktura "
        "{invoice_number} ({amount} SEK, {days_overdue} dagar försenad) "
        "innan ärendet skickas vidare. – {org_name}"
    ),
    4: (
        "Hej {customer_name}, faktura {invoice_number} ({amount} SEK) är "
        "nu {days_overdue} dagar försenad och kommer lämnas över till inkasso. "
        "– {org_name}"
    ),
}

# SMS is the same text — carriers will auto-split >160 chars into
# multi-part messages; the templates are short enough that stage 1-2
# fit in one segment.
_SMS_TEMPLATES = _WHATSAPP_TEMPLATES


def render_whatsapp_body(
    *,
    stage: int,
    customer_name: str,
    invoice_number: str,
    amount_sek: str,
    days_overdue: int,
    org_name: str,
) -> str | None:
    """Render the WhatsApp/SMS body for the given stage, or None if the
    stage is outside the 1-4 ladder."""
    tpl = _WHATSAPP_TEMPLATES.get(stage)
    if tpl is None:
        return None
    return tpl.format(
        customer_name=customer_name,
        invoice_number=invoice_number,
        amount=amount_sek,
        days_overdue=days_overdue,
        org_name=org_name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Transport
# ─────────────────────────────────────────────────────────────────────────────


async def _post(
    *, url: str, token: str, to: str, sender: str, body: str,
) -> tuple[bool, str | None]:
    """Generic HTTP POST. Returns (ok, error_detail)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                url,
                json={"to": to, "from": sender, "body": body},
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as e:  # noqa: BLE001 — surface error, never break caller
        log.warning("transport_post_failed url=%s err=%r", url, e)
        return False, f"transport_error: {e!r}"
    if res.status_code in (200, 201, 202):
        return True, None
    return False, f"http_{res.status_code}"


async def send_whatsapp(*, to: str, body: str) -> tuple[bool, str | None]:
    """Send a WhatsApp message. Returns ``(ok, error_detail)``.

    * ``(False, "not_configured")`` when env vars are missing — the
      caller treats this the same as a transport failure (skip channel,
      leave invoice behind for manual nudge) so CI and local runs stay
      green without provider secrets.
    * ``(False, "invalid_number")`` for unparseable numbers — defence
      in depth; callers should already have normalised.
    """
    if not (
        settings.WHATSAPP_API_URL
        and settings.WHATSAPP_API_TOKEN
        and settings.WHATSAPP_FROM_NUMBER
    ):
        return False, "not_configured"
    normalised = normalise_e164(to)
    if normalised is None:
        return False, "invalid_number"
    return await _post(
        url=settings.WHATSAPP_API_URL,
        token=settings.WHATSAPP_API_TOKEN,
        to=normalised,
        sender=settings.WHATSAPP_FROM_NUMBER,
        body=body,
    )


async def send_sms(*, to: str, body: str) -> tuple[bool, str | None]:
    """Send an SMS. Same contract and error codes as :func:`send_whatsapp`."""
    if not (
        settings.SMS_API_URL
        and settings.SMS_API_TOKEN
        and settings.SMS_FROM_NUMBER
    ):
        return False, "not_configured"
    normalised = normalise_e164(to)
    if normalised is None:
        return False, "invalid_number"
    return await _post(
        url=settings.SMS_API_URL,
        token=settings.SMS_API_TOKEN,
        to=normalised,
        sender=settings.SMS_FROM_NUMBER,
        body=body,
    )
