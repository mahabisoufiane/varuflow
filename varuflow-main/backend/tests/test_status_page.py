"""Tests for the public status page rollup."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.portal.status import HealthCheck, StatusIncident
from app.services.status_page import build_status_rollup


@pytest.mark.asyncio
async def test_uptime_drops_when_database_probes_fail(db_session: AsyncSession):
    """Three failed `db_ok=False` checks within the last 30 days should
    pull the database service's 90-day uptime below 100 %, while the
    API service (every persisted row counts as up) stays at 100 %."""
    # Fresh slate so prior test runs don't pollute averages.
    await db_session.execute(delete(HealthCheck))
    await db_session.execute(delete(StatusIncident))
    await db_session.commit()

    now = datetime.now(timezone.utc)

    # 27 healthy probes spread over the last 30 days
    healthy_rows = [
        HealthCheck(
            checked_at=now - timedelta(days=i, hours=1),
            db_ok=True,
            stripe_ok=True,
            resend_ok=True,
            response_ms=42,
        )
        for i in range(27)
    ]
    # 3 failed DB probes on three distinct recent days
    failed_rows = [
        HealthCheck(
            checked_at=now - timedelta(days=d),
            db_ok=False,
            stripe_ok=True,
            resend_ok=True,
            response_ms=4000,
        )
        for d in (1, 2, 3)
    ]
    db_session.add_all(healthy_rows + failed_rows)
    await db_session.commit()

    rollup = await build_status_rollup(db_session)

    services = {s["key"]: s for s in rollup["services"]}
    assert "database" in services
    assert "api" in services

    # The database service must show degraded uptime over 90 days.
    db_uptime = services["database"]["uptime_pct_90d"]
    assert db_uptime is not None
    assert db_uptime < 100, f"expected db uptime < 100, got {db_uptime}"

    # At least one timeline bucket for the database has < 100 % uptime.
    bad_days = [
        pt for pt in services["database"]["timeline"]
        if pt["uptime_pct"] is not None and pt["uptime_pct"] < 100
    ]
    assert len(bad_days) >= 1

    # API uptime stays 100 % — every persisted probe row means the API
    # process was alive at probe time.
    api_uptime = services["api"]["uptime_pct_90d"]
    assert api_uptime == 100

    # Timeline must be densified to exactly 90 daily buckets per service.
    assert len(services["database"]["timeline"]) == 90

    # Cleanup so other tests start clean.
    await db_session.execute(delete(HealthCheck))
    await db_session.commit()
