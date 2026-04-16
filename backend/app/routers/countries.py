"""Read-only introspection endpoints for the multi-country configuration.

All endpoints are safe to expose publicly — they surface only the same
data that lives in the committed `config/countries/*.json` files.

- GET /api/countries             → list of all supported countries
- GET /api/countries/{code}      → full config for one country
- GET /api/countries/active      → country resolved for the current request
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.services.country import get_country_config, known_countries

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/countries", tags=["countries"])


@router.get("")
async def list_countries() -> dict:
    try:
        codes = known_countries()
        return {
            "count": len(codes),
            "countries": [
                {
                    "code": c,
                    "name": (cfg := get_country_config(c)) and cfg.get("display_name"),
                    "region": cfg and cfg.get("region"),
                    "currency": cfg and cfg.get("currency"),
                }
                for c in codes
            ],
        }
    except Exception:
        log.exception("list_countries failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/active")
async def active_country(request: Request) -> dict:
    try:
        code = getattr(request.state, "country", None)
        if not code:
            raise HTTPException(status_code=404, detail="Country not resolved")
        cfg = get_country_config(code)
        if not cfg:
            raise HTTPException(status_code=404, detail=f"Unknown country {code}")
        return {"code": code, "config": cfg}
    except HTTPException:
        raise
    except Exception:
        log.exception("active_country failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{code}")
async def get_country(code: str) -> dict:
    try:
        cfg = get_country_config(code)
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Country {code.upper()} not configured",
            )
        return cfg
    except HTTPException:
        raise
    except Exception:
        log.exception("get_country failed | code=%s", code)
        raise HTTPException(status_code=500, detail="Internal server error")
