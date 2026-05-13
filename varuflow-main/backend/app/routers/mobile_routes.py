"""GPS delivery/field route planning

Endpoints:
  GET  /api/mobile/routes
  POST /api/mobile/routes
  GET  /api/mobile/routes/{route_id}
  PATCH /api/mobile/routes/{route_id}
  DELETE /api/mobile/routes/{route_id}
  POST /api/mobile/routes/{route_id}/stops
  PATCH /api/mobile/routes/{route_id}/stops/{stop_id}
  POST /api/mobile/routes/{route_id}/stops/{stop_id}/arrive
  POST /api/mobile/routes/{route_id}/stops/{stop_id}/complete
  POST /api/mobile/routes/{route_id}/stops/{stop_id}/exception
  POST /api/mobile/routes/{route_id}/stops/{stop_id}/notify
  POST /api/mobile/routes/{route_id}/optimize   (reorders stops by proximity)
  GET  /api/mobile/routes/{route_id}/report     (end-of-day summary)
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.mobile_field import DeliveryRoute, RouteStop

router = APIRouter(prefix="/api/mobile/routes", tags=["mobile_routes"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ── Schemas ───────────────────────────────────────────────────────────────────

class StopIn(BaseModel):
    stop_type: str = "customer"
    ref_id: Optional[uuid.UUID] = None
    label: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None

class StopPatch(BaseModel):
    label: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    sequence: Optional[int] = None
    scheduled_at: Optional[datetime] = None

class RouteIn(BaseModel):
    name: str
    driver_name: Optional[str] = None
    route_date: date
    notes: Optional[str] = None
    notification_threshold_minutes: int = 15
    stops: list[StopIn] = []

class RoutePatch(BaseModel):
    name: Optional[str] = None
    driver_name: Optional[str] = None
    route_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    notification_threshold_minutes: Optional[int] = None

class CompleteStopIn(BaseModel):
    pod_photo_url: Optional[str] = None
    pod_signature_data: Optional[dict] = None  # {type: "drawn", data: "base64..."}
    notes: Optional[str] = None

class ExceptionIn(BaseModel):
    # no_answer / wrong_address / refused / damaged / other
    exception_type: str
    exception_reason: Optional[str] = None
    reschedule_date: Optional[date] = None

class StopOut(BaseModel):
    id: str
    stop_type: str
    ref_id: Optional[str]
    label: Optional[str]
    address: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    sequence: int
    status: str
    scheduled_at: Optional[str]
    arrived_at: Optional[str]
    completed_at: Optional[str]
    exception_type: Optional[str]
    exception_reason: Optional[str]
    reschedule_date: Optional[str]
    pod_photo_url: Optional[str]
    has_signature: bool
    notes: Optional[str]

class RouteOut(BaseModel):
    id: str
    name: str
    driver_name: Optional[str]
    route_date: str
    status: str
    notes: Optional[str]
    total_km: Optional[float]
    notification_threshold_minutes: int
    stops: list[StopOut]
    created_at: str

class RoutesOut(BaseModel):
    routes: list[RouteOut]
    total: int


def _stop_out(s: RouteStop) -> StopOut:
    return StopOut(
        id=str(s.id), stop_type=s.stop_type,
        ref_id=str(s.ref_id) if s.ref_id else None,
        label=s.label, address=s.address,
        lat=float(s.lat) if s.lat else None,
        lng=float(s.lng) if s.lng else None,
        sequence=s.sequence, status=s.status,
        scheduled_at=s.scheduled_at.isoformat() if s.scheduled_at else None,
        arrived_at=s.arrived_at.isoformat() if s.arrived_at else None,
        completed_at=s.completed_at.isoformat() if s.completed_at else None,
        exception_type=s.exception_type,
        exception_reason=s.exception_reason,
        reschedule_date=s.reschedule_date.isoformat() if s.reschedule_date else None,
        pod_photo_url=s.pod_photo_url,
        has_signature=bool(s.pod_signature_data),
        notes=s.notes,
    )


def _route_out(r: DeliveryRoute, stops: list[RouteStop]) -> RouteOut:
    return RouteOut(
        id=str(r.id), name=r.name, driver_name=r.driver_name,
        route_date=r.route_date.isoformat(),
        status=r.status, notes=r.notes,
        total_km=float(r.total_km) if r.total_km else None,
        notification_threshold_minutes=r.notification_threshold_minutes or 15,
        stops=sorted([_stop_out(s) for s in stops], key=lambda x: x.sequence),
        created_at=r.created_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=RoutesOut)
async def list_routes(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(DeliveryRoute).where(DeliveryRoute.org_id == org_id)
        if status:
            q = q.where(DeliveryRoute.status == status)
        count = await db.execute(select(func.count(DeliveryRoute.id)).where(DeliveryRoute.org_id == org_id))
        total = count.scalar_one() or 0
        rows = await db.execute(q.order_by(DeliveryRoute.route_date.desc()).limit(limit).offset((page - 1) * limit))
        routes = rows.scalars().all()

        result = []
        for route in routes:
            stops_q = await db.execute(select(RouteStop).where(RouteStop.route_id == route.id))
            result.append(_route_out(route, stops_q.scalars().all()))

        return RoutesOut(routes=result, total=total)
    except Exception as e:
        log.error("list_routes failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=RouteOut)
async def create_route(
    body: RouteIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        route = DeliveryRoute(
            org_id=org_id,
            name=body.name,
            driver_name=body.driver_name,
            route_date=body.route_date,
            notes=body.notes,
            notification_threshold_minutes=body.notification_threshold_minutes,
        )
        db.add(route)
        await db.flush()

        stops = []
        for i, s in enumerate(body.stops):
            stop = RouteStop(
                route_id=route.id, org_id=org_id,
                stop_type=s.stop_type, ref_id=s.ref_id,
                label=s.label, address=s.address,
                lat=Decimal(str(s.lat)) if s.lat else None,
                lng=Decimal(str(s.lng)) if s.lng else None,
                sequence=i, notes=s.notes,
                scheduled_at=s.scheduled_at,
            )
            db.add(stop)
            stops.append(stop)

        await db.commit()
        await db.refresh(route)
        for st in stops:
            await db.refresh(st)

        return _route_out(route, stops)
    except Exception as e:
        log.error("create_route failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{route_id}", response_model=RouteOut)
async def get_route(
    route_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        route = row.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        stops = await db.execute(select(RouteStop).where(RouteStop.route_id == route_id))
        return _route_out(route, stops.scalars().all())
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_route failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{route_id}", response_model=RouteOut)
async def update_route(
    route_id: uuid.UUID,
    body: RoutePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        route = row.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        if body.name is not None:
            route.name = body.name
        if body.driver_name is not None:
            route.driver_name = body.driver_name
        if body.route_date is not None:
            route.route_date = body.route_date
        if body.status is not None:
            route.status = body.status
        if body.notes is not None:
            route.notes = body.notes
        if body.notification_threshold_minutes is not None:
            route.notification_threshold_minutes = body.notification_threshold_minutes
        await db.commit()
        stops = await db.execute(select(RouteStop).where(RouteStop.route_id == route_id))
        return _route_out(route, stops.scalars().all())
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_route failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{route_id}")
async def delete_route(
    route_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        route = row.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        await db.delete(route)
        await db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_route failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{route_id}/stops", response_model=StopOut)
async def add_stop(
    route_id: uuid.UUID,
    body: StopIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        route_row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        if not route_row.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Route not found")

        count_row = await db.execute(select(func.count(RouteStop.id)).where(RouteStop.route_id == route_id))
        seq = count_row.scalar_one() or 0

        stop = RouteStop(
            route_id=route_id, org_id=org_id,
            stop_type=body.stop_type, ref_id=body.ref_id,
            label=body.label, address=body.address,
            lat=Decimal(str(body.lat)) if body.lat else None,
            lng=Decimal(str(body.lng)) if body.lng else None,
            sequence=seq, notes=body.notes,
            scheduled_at=body.scheduled_at,
        )
        db.add(stop)
        await db.commit()
        await db.refresh(stop)
        return _stop_out(stop)
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_stop failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{route_id}/stops/{stop_id}", response_model=StopOut)
async def update_stop(
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    body: StopPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id, RouteStop.org_id == org_id)
        )
        stop = row.scalar_one_or_none()
        if not stop:
            raise HTTPException(status_code=404, detail="Stop not found")
        if body.label is not None:
            stop.label = body.label
        if body.address is not None:
            stop.address = body.address
        if body.lat is not None:
            stop.lat = Decimal(str(body.lat))
        if body.lng is not None:
            stop.lng = Decimal(str(body.lng))
        if body.status is not None:
            stop.status = body.status
        if body.notes is not None:
            stop.notes = body.notes
        if body.sequence is not None:
            stop.sequence = body.sequence
        if body.scheduled_at is not None:
            stop.scheduled_at = body.scheduled_at
        await db.commit()
        await db.refresh(stop)
        return _stop_out(stop)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_stop failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{route_id}/stops/{stop_id}/arrive", response_model=StopOut)
async def mark_arrived(
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark a stop as visited with current arrival timestamp."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id, RouteStop.org_id == org_id)
        )
        stop = row.scalar_one_or_none()
        if not stop:
            raise HTTPException(status_code=404, detail="Stop not found")
        stop.status = "visited"
        stop.arrived_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(stop)
        return _stop_out(stop)
    except HTTPException:
        raise
    except Exception as e:
        log.error("mark_arrived failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{route_id}/optimize", response_model=RouteOut)
async def optimize_route(
    route_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Re-order unvisited stops using a nearest-neighbor heuristic."""
    org_id = _org(ctx)
    try:
        route_row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        route = route_row.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")

        stops_row = await db.execute(select(RouteStop).where(RouteStop.route_id == route_id))
        all_stops = stops_row.scalars().all()

        visited = [s for s in all_stops if s.status == "visited"]
        pending = [s for s in all_stops if s.status != "visited" and s.lat and s.lng]
        no_coords = [s for s in all_stops if s.status != "visited" and not (s.lat and s.lng)]

        # Nearest-neighbor from last visited or first pending
        if pending:
            ordered = []
            current = visited[-1] if visited else None
            remaining = list(pending)

            while remaining:
                if current and current.lat and current.lng:
                    nearest = min(remaining, key=lambda s: _haversine(
                        float(current.lat), float(current.lng),
                        float(s.lat), float(s.lng),
                    ))
                else:
                    nearest = remaining[0]
                ordered.append(nearest)
                current = nearest
                remaining.remove(nearest)

            base_seq = len(visited)
            for i, stop in enumerate(ordered):
                stop.sequence = base_seq + i
            for i, stop in enumerate(no_coords):
                stop.sequence = base_seq + len(ordered) + i

        await db.commit()
        stops_row2 = await db.execute(select(RouteStop).where(RouteStop.route_id == route_id))
        return _route_out(route, stops_row2.scalars().all())
    except HTTPException:
        raise
    except Exception as e:
        log.error("optimize_route failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{route_id}/stops/{stop_id}/complete", response_model=StopOut)
async def complete_stop(
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    body: CompleteStopIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark stop as completed with optional proof-of-delivery (photo + signature)."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id, RouteStop.org_id == org_id)
        )
        stop = row.scalar_one_or_none()
        if not stop:
            raise HTTPException(status_code=404, detail="Stop not found")

        now = datetime.now(timezone.utc)
        stop.status = "completed"
        stop.completed_at = now
        if stop.arrived_at is None:
            stop.arrived_at = now
        if body.pod_photo_url is not None:
            stop.pod_photo_url = body.pod_photo_url
        if body.pod_signature_data is not None:
            stop.pod_signature_data = body.pod_signature_data
        if body.notes is not None:
            stop.notes = body.notes

        await db.commit()
        await db.refresh(stop)
        return _stop_out(stop)
    except HTTPException:
        raise
    except Exception as e:
        log.error("complete_stop failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{route_id}/stops/{stop_id}/exception", response_model=StopOut)
async def record_exception(
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    body: ExceptionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record a delivery exception (could not deliver, wrong address, etc.)."""
    org_id = _org(ctx)
    VALID_TYPES = {"no_answer", "wrong_address", "refused", "damaged", "other"}
    try:
        if body.exception_type not in VALID_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid exception_type. Valid: {sorted(VALID_TYPES)}")
        row = await db.execute(
            select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id, RouteStop.org_id == org_id)
        )
        stop = row.scalar_one_or_none()
        if not stop:
            raise HTTPException(status_code=404, detail="Stop not found")

        stop.status = "exception"
        stop.exception_type = body.exception_type
        stop.exception_reason = body.exception_reason
        stop.reschedule_date = body.reschedule_date

        await db.commit()
        await db.refresh(stop)
        return _stop_out(stop)
    except HTTPException:
        raise
    except Exception as e:
        log.error("record_exception failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{route_id}/stops/{stop_id}/notify")
async def notify_customer(
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Send an 'arriving soon' email notification to the customer at this stop."""
    org_id = _org(ctx)
    try:
        # Load stop
        stop_row = await db.execute(
            select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id, RouteStop.org_id == org_id)
        )
        stop = stop_row.scalar_one_or_none()
        if not stop:
            raise HTTPException(status_code=404, detail="Stop not found")

        # Load route for driver name and ETA threshold
        route_row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        route = route_row.scalar_one_or_none()

        # Try to get customer email if ref_id points to a customer
        customer_email = None
        if stop.ref_id:
            from app.models.invoicing import Customer
            cust_row = await db.execute(
                select(Customer).where(Customer.id == stop.ref_id, Customer.org_id == org_id)
            )
            cust = cust_row.scalar_one_or_none()
            if cust and cust.email:
                customer_email = cust.email

        threshold = route.notification_threshold_minutes if route else 15
        driver_name = route.driver_name if route else "Your driver"
        label = stop.label or stop.address or "your location"

        import os
        resend_key = os.getenv("RESEND_API_KEY", "")
        from_email = os.getenv("SMTP_FROM", "noreply@varuflow.se")

        if not customer_email:
            return {"sent": False, "reason": "No customer email on this stop — set ref_id to a customer with an email address"}

        if not resend_key:
            log.info("notify_customer skipped (no RESEND_API_KEY): to=%s", customer_email)
            return {"sent": False, "reason": "RESEND_API_KEY not configured"}

        try:
            import httpx
            await httpx.AsyncClient(timeout=10).post(
                "https://api.resend.com/emails",
                json={
                    "from": from_email,
                    "to": [customer_email],
                    "subject": f"{driver_name} is arriving in ~{threshold} minutes",
                    "html": (
                        f"<p>Hi,</p><p>{driver_name} is approximately <strong>{threshold} minutes away</strong> "
                        f"and will arrive at <strong>{label}</strong>.</p>"
                        f"<p style='font-size:12px;color:#888'>Sent automatically by Varuflow delivery tracking.</p>"
                    ),
                },
                headers={"Authorization": f"Bearer {resend_key}"},
            )
        except Exception as exc:
            log.error("notify_customer email failed: %s", str(exc))
            return {"sent": False, "reason": "Email delivery failed"}

        return {"sent": True, "to": customer_email, "threshold_minutes": threshold}
    except HTTPException:
        raise
    except Exception as e:
        log.error("notify_customer failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{route_id}/report")
async def end_of_day_report(
    route_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """End-of-day delivery report: completed, failed, distance, timing."""
    org_id = _org(ctx)
    try:
        route_row = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id, DeliveryRoute.org_id == org_id)
        )
        route = route_row.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")

        stops_row = await db.execute(
            select(RouteStop).where(RouteStop.route_id == route_id).order_by(RouteStop.sequence)
        )
        stops = stops_row.scalars().all()

        # Count by status
        completed = [s for s in stops if s.status == "completed"]
        exceptions = [s for s in stops if s.status == "exception"]
        skipped = [s for s in stops if s.status == "skipped"]
        pending = [s for s in stops if s.status == "pending"]

        # Compute total estimated distance (sum of Haversine between consecutive geo stops)
        geo_stops = [s for s in stops if s.lat and s.lng]
        total_km = 0.0
        for i in range(len(geo_stops) - 1):
            a, b = geo_stops[i], geo_stops[i + 1]
            total_km += _haversine(float(a.lat), float(a.lng), float(b.lat), float(b.lng))

        # Save computed total_km back to the route
        route.total_km = Decimal(str(round(total_km, 2)))
        await db.commit()

        # Timing analysis: scheduled vs actual
        timing_rows = []
        for s in stops:
            if s.scheduled_at and s.arrived_at:
                delta_minutes = (s.arrived_at - s.scheduled_at).total_seconds() / 60
                timing_rows.append({
                    "label": s.label or s.address or str(s.id),
                    "scheduled_at": s.scheduled_at.isoformat(),
                    "arrived_at": s.arrived_at.isoformat(),
                    "delta_minutes": round(delta_minutes, 1),
                    "on_time": delta_minutes <= 10,
                })

        stop_details = []
        for s in stops:
            stop_details.append({
                "label": s.label or s.address,
                "status": s.status,
                "arrived_at": s.arrived_at.isoformat() if s.arrived_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "exception_type": s.exception_type,
                "exception_reason": s.exception_reason,
                "reschedule_date": s.reschedule_date.isoformat() if s.reschedule_date else None,
                "has_pod_photo": bool(s.pod_photo_url),
                "has_pod_signature": bool(s.pod_signature_data),
            })

        return {
            "route_id": str(route_id),
            "route_name": route.name,
            "driver_name": route.driver_name,
            "route_date": route.route_date.isoformat(),
            "summary": {
                "total_stops": len(stops),
                "completed": len(completed),
                "exceptions": len(exceptions),
                "skipped": len(skipped),
                "pending": len(pending),
                "completion_rate": round(len(completed) / max(len(stops), 1) * 100, 1),
                "total_km": round(total_km, 2),
            },
            "timing": timing_rows,
            "stops": stop_details,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("end_of_day_report failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")

