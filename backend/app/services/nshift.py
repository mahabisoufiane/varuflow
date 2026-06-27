"""nShift / Unifaun shipping gateway.

Covers PostNord, DHL, and UPS via a single nShift account.
Set NSHIFT_API_KEY + NSHIFT_API_SECRET + NSHIFT_SENDER_ID in env to enable.
Returns None on any failure so callers can fall back to manual tracking entry.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_NSHIFT_BASE = "https://api.nshift.com/shipping/v3"

# Map Varuflow carrier codes to nShift service codes
_CARRIER_SERVICE = {
    "POSTNORD": "SE_PPR",   # PostNord Parcel
    "DHL": "DHL_EXPRESS",
    "UPS": "UPS_EXPRESS",
}


async def create_shipment(
    order_number: str,
    customer_name: str,
    shipping_address: dict,
    items_description: str,
    weight_kg: float = 1.0,
    carrier: str = "POSTNORD",
) -> Optional[dict]:
    """Create a shipment label via nShift.

    Returns dict with keys: shipment_id, tracking_number, tracking_url, label_pdf_base64
    Returns None if nShift is not configured or the call fails.
    """
    if not settings.NSHIFT_API_KEY or not settings.NSHIFT_API_SECRET:
        log.warning("nShift credentials not configured — skipping label generation")
        return None

    service_code = _CARRIER_SERVICE.get(carrier.upper(), "SE_PPR")
    credentials = base64.b64encode(
        f"{settings.NSHIFT_API_KEY}:{settings.NSHIFT_API_SECRET}".encode()
    ).decode()

    payload = {
        "shipment": {
            "senderQuickId": settings.NSHIFT_SENDER_ID,
            "service": {"id": service_code},
            "parcels": [{"copies": 1, "weight": weight_kg}],
            "receiver": {
                "quickId": order_number,
                "name": customer_name,
                "address1": shipping_address.get("line1", ""),
                "city": shipping_address.get("city", ""),
                "zipCode": shipping_address.get("postal_code", ""),
                "countryCode": shipping_address.get("country", "SE"),
            },
            "orderNo": order_number,
            "reference": items_description[:50],
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{_NSHIFT_BASE}/shipments",
                json=payload,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                },
            )
            res.raise_for_status()
            data = res.json()

        shipment_id = data.get("id") or data.get("shipmentId") or ""
        tracking_number = (
            data.get("parcels", [{}])[0].get("trackingNumber")
            or data.get("trackingNumber", "")
        )
        tracking_url = (
            data.get("parcels", [{}])[0].get("trackingUrl")
            or data.get("trackingUrl", "")
        )
        label_b64 = data.get("pdf") or data.get("label", "")

        return {
            "shipment_id": shipment_id,
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
            "label_pdf_base64": label_b64,
        }
    except httpx.HTTPStatusError as e:
        log.error("nShift API error %s: %s", e.response.status_code, e.response.text[:300])
        return None
    except Exception as e:
        log.error("nShift create_shipment failed: %s", e)
        return None


async def get_tracking(shipment_id: str) -> Optional[dict]:
    """Poll nShift for tracking events on a previously created shipment."""
    if not settings.NSHIFT_API_KEY or not settings.NSHIFT_API_SECRET:
        return None

    credentials = base64.b64encode(
        f"{settings.NSHIFT_API_KEY}:{settings.NSHIFT_API_SECRET}".encode()
    ).decode()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                f"{_NSHIFT_BASE}/shipments/{shipment_id}",
                headers={"Authorization": f"Basic {credentials}"},
            )
            res.raise_for_status()
            return res.json()
    except Exception as e:
        log.error("nShift get_tracking failed for %s: %s", shipment_id, e)
        return None
