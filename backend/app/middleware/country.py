"""Attach the resolved country code to every request.

Populates `request.state.country` early so routers and services can read a
stable, already-validated country without having to call the resolver
themselves.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.country import resolve_country


class CountryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Organization-level country is resolved later inside dependencies that
        # have a DB session; the middleware only does cheap header+host checks.
        request.state.country = resolve_country(request, org_country=None)
        response = await call_next(request)
        response.headers.setdefault("X-Country-Code", request.state.country)
        return response
