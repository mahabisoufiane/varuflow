"""Tests for Bolagsverket company lookup (Feature 7)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.bolagsverket import (
    _cache,
    lookup_company,
    normalise_orgnr,
)




def test_normalise_orgnr_accepts_hyphenated_and_plain():
    assert normalise_orgnr("556000-0001") == "5560000001"
    assert normalise_orgnr("5560000001") == "5560000001"
    assert normalise_orgnr(" 556000-0001 ") == "5560000001"


def test_normalise_orgnr_rejects_bad_input():
    assert normalise_orgnr("") is None
    assert normalise_orgnr("abc") is None
    assert normalise_orgnr("123") is None
    # Wrong format (11 digits)
    assert normalise_orgnr("55600000011") is None
    # Luhn mismatch: swap last two digits of a valid one
    assert normalise_orgnr("556000-0010") is None


async def test_lookup_company_rejects_invalid_orgnr():
    _cache.clear()
    result = await lookup_company("not-a-number")
    assert result["status"] == "invalid"


async def test_lookup_company_stub_when_not_configured(monkeypatch):
    _cache.clear()
    from app.services import bolagsverket

    monkeypatch.setattr(bolagsverket.settings, "BOLAGSVERKET_API_URL", "")
    result = await lookup_company("556000-0001")
    assert result["status"] == "not_configured"
    assert result["org_number"] == "5560000001"
    assert result["company_name"] is None


async def test_lookup_company_uses_cache(monkeypatch):
    _cache.clear()
    from app.services import bolagsverket

    monkeypatch.setattr(bolagsverket.settings, "BOLAGSVERKET_API_URL", "")
    await lookup_company("556000-0001")  # caches stub
    # Second call should not rebuild the stub — same object identity
    # from the cache path.
    cached_entry = _cache.get("5560000001")
    assert cached_entry is not None
    r2 = await lookup_company("5560000001")
    assert r2 is cached_entry[0]


class _FakeResponse:
    def __init__(self, status_code: int, data: dict | None = None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


async def test_lookup_company_parses_live_response(monkeypatch):
    _cache.clear()
    from app.services import bolagsverket

    monkeypatch.setattr(
        bolagsverket.settings, "BOLAGSVERKET_API_URL", "https://api.example",
    )
    monkeypatch.setattr(
        bolagsverket.settings, "BOLAGSVERKET_API_TOKEN", "fake-token",
    )

    fake_payload = {
        "name": "Alpha AB",
        "vat_number": "SE556000000101",
        "street_address": "Kungsgatan 1",
        "postal_code": "111 22",
        "city": "Stockholm",
        "registered_date": "1999-01-01",
    }
    fake_get = AsyncMock(return_value=_FakeResponse(200, fake_payload))

    class _FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            return await fake_get(url, headers=headers)

    monkeypatch.setattr(bolagsverket.httpx, "AsyncClient", _FakeClient)

    result = await lookup_company("556000-0001")
    assert result["status"] == "ok"
    assert result["company_name"] == "Alpha AB"
    assert result["vat_number"] == "SE556000000101"
    assert result["address"] == "Kungsgatan 1"
    assert result["postal_code"] == "111 22"
    assert result["city"] == "Stockholm"
    fake_get.assert_awaited_once()
    args, kwargs = fake_get.call_args
    assert "Bearer fake-token" in kwargs["headers"]["Authorization"]


async def test_lookup_company_handles_404(monkeypatch):
    _cache.clear()
    from app.services import bolagsverket

    monkeypatch.setattr(
        bolagsverket.settings, "BOLAGSVERKET_API_URL", "https://api.example",
    )

    class _FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            return _FakeResponse(404)

    monkeypatch.setattr(bolagsverket.httpx, "AsyncClient", _FakeClient)

    result = await lookup_company("556000-0001")
    assert result["status"] == "not_found"


async def test_customer_lookup_endpoint_invalid_returns_422(
    db_session, two_orgs, client_factory
):
    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/invoicing/customers/lookup/not-valid")
    assert r.status_code == 422


async def test_customer_lookup_endpoint_returns_stub(
    db_session, two_orgs, client_factory, monkeypatch,
):
    _cache.clear()
    from app.services import bolagsverket
    monkeypatch.setattr(bolagsverket.settings, "BOLAGSVERKET_API_URL", "")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/invoicing/customers/lookup/556000-0001")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_configured"
    assert body["org_number"] == "5560000001"
