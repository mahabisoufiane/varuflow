"""Feature 20 — AI chat live-business-context tests.

Covers the standalone context builder (`build_ai_context`) and the
/api/integrations/ai/chat endpoint end-to-end with OpenAI mocked so
no network call fires and no API key is required.

Scope:
    - Context dataclass reports correct low-stock / overdue / revenue
      numbers seeded into the DB.
    - The system prompt the endpoint hands to OpenAI starts with the
      exact verbatim prefix from the spec and embeds the seeded product
      and customer names.
    - The 20/day rate limit on PRO plans returns HTTP 429 once the
      daily quota is exhausted — regression guard for the atomic UPSERT
      in `routers.integrations.ai_chat`.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ai.ai_usage import DailyAiUsage
from app.features.inventory.models import Product, StockLevel, Warehouse
from app.features.invoicing.models import (
    Customer,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from app.features.auth.organization import OrgPlan
from app.services.ai_context import build_ai_context


TODAY = date(2025, 6, 15)


async def _seed_org(db: AsyncSession, org):
    """Populate ``org`` with deterministic inventory + invoicing data.

    Returns a dict of the seeded objects so tests can assert against
    the exact strings that should appear in the prompt / response.
    """
    # Warehouse — needed because StockLevel FK points at warehouses.
    wh = Warehouse(id=uuid.uuid4(), org_id=org.id, name="Main")
    db.add(wh)

    # Low-stock products: Kaffe and Mjölk are below their reorder level;
    # Socker is healthy so must NOT appear in the prompt.
    kaffe = Product(
        id=uuid.uuid4(), org_id=org.id, name="Kaffe Mellanrost",
        sku="SKU-KAFFE", purchase_price=Decimal("40"),
        sell_price=Decimal("100"), reorder_level=20, is_active=True,
    )
    mjolk = Product(
        id=uuid.uuid4(), org_id=org.id, name="Mjölk 1L",
        sku="SKU-MJOLK", purchase_price=Decimal("10"),
        sell_price=Decimal("20"), reorder_level=50, is_active=True,
    )
    socker = Product(
        id=uuid.uuid4(), org_id=org.id, name="Socker 1kg",
        sku="SKU-SOCKER", purchase_price=Decimal("15"),
        sell_price=Decimal("25"), reorder_level=10, is_active=True,
    )
    db.add_all([kaffe, mjolk, socker])

    db.add_all([
        StockLevel(org_id=org.id, product_id=kaffe.id, warehouse_id=wh.id, quantity=4),
        StockLevel(org_id=org.id, product_id=mjolk.id, warehouse_id=wh.id, quantity=10),
        StockLevel(org_id=org.id, product_id=socker.id, warehouse_id=wh.id, quantity=500),
    ])

    # Two customers with overdue invoices and one PAID invoice for the
    # 30-day revenue aggregate + month-over-month delta.
    cust1 = Customer(id=uuid.uuid4(), org_id=org.id, company_name="Alpha Kund AB")
    cust2 = Customer(id=uuid.uuid4(), org_id=org.id, company_name="Beta Butik AB")
    db.add_all([cust1, cust2])

    overdue_old = Invoice(
        id=uuid.uuid4(), org_id=org.id, customer_id=cust1.id,
        invoice_number="INV-2025-0001",
        issue_date=TODAY - timedelta(days=60),
        due_date=TODAY - timedelta(days=30),
        status=InvoiceStatus.SENT,
        subtotal=Decimal("8000"), vat_amount=Decimal("2000"),
        total_sek=Decimal("10000"),
    )
    overdue_mid = Invoice(
        id=uuid.uuid4(), org_id=org.id, customer_id=cust2.id,
        invoice_number="INV-2025-0002",
        issue_date=TODAY - timedelta(days=40),
        due_date=TODAY - timedelta(days=10),
        status=InvoiceStatus.SENT,
        subtotal=Decimal("4000"), vat_amount=Decimal("1000"),
        total_sek=Decimal("5000"),
    )
    # PAID this month — feeds revenue_30d_sek and current_month_sek.
    paid_this_month = Invoice(
        id=uuid.uuid4(), org_id=org.id, customer_id=cust1.id,
        invoice_number="INV-2025-0003",
        issue_date=TODAY - timedelta(days=5),
        due_date=TODAY + timedelta(days=25),
        status=InvoiceStatus.PAID,
        subtotal=Decimal("2400"), vat_amount=Decimal("600"),
        total_sek=Decimal("3000"),
    )
    # PAID last month — feeds prev_month_sek only (older than 30 days
    # from TODAY so excluded from revenue_30d_sek).
    paid_last_month = Invoice(
        id=uuid.uuid4(), org_id=org.id, customer_id=cust2.id,
        invoice_number="INV-2025-0004",
        issue_date=date(2025, 5, 10),
        due_date=date(2025, 6, 10),
        status=InvoiceStatus.PAID,
        subtotal=Decimal("1600"), vat_amount=Decimal("400"),
        total_sek=Decimal("2000"),
    )
    db.add_all([overdue_old, overdue_mid, paid_this_month, paid_last_month])

    # Partial payment on overdue_old — remaining balance should be 6000.
    db.add(Payment(
        org_id=org.id, invoice_id=overdue_old.id,
        amount=Decimal("4000"), payment_date=TODAY - timedelta(days=20),
        method=PaymentMethod.BANK_TRANSFER,
    ))

    await db.commit()

    return {
        "kaffe": kaffe, "mjolk": mjolk, "socker": socker,
        "cust1": cust1, "cust2": cust2,
        "overdue_old": overdue_old, "overdue_mid": overdue_mid,
    }


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession, two_orgs):
    seeded = await _seed_org(db_session, two_orgs["a"]["org"])
    yield {"seeded": seeded, "org": two_orgs["a"]["org"], "member": two_orgs["a"]["member"]}


@pytest.mark.asyncio
async def test_build_ai_context_contains_low_stock_and_overdue(
    db_session: AsyncSession, seeded,
):
    ctx = await build_ai_context(db_session, org_id=seeded["org"].id, today=TODAY)

    low_stock_names = [it.name for it in ctx.low_stock]
    assert "Kaffe Mellanrost" in low_stock_names
    assert "Mjölk 1L" in low_stock_names
    # Healthy product must not appear.
    assert "Socker 1kg" not in low_stock_names

    # 30-day revenue = only the PAID invoice issued 5 days ago.
    assert ctx.revenue_30d_sek == pytest.approx(3000.0)

    # Overdue list: both SENT+past-due invoices with remaining balance.
    overdue_names = {it.customer_name for it in ctx.overdue}
    assert overdue_names == {"Alpha Kund AB", "Beta Butik AB"}
    alpha = next(it for it in ctx.overdue if it.customer_name == "Alpha Kund AB")
    # 10 000 total − 4 000 paid = 6 000 remaining.
    assert alpha.remaining_sek == pytest.approx(6000.0)
    assert alpha.days_overdue == 30

    # Month delta: current (3000) vs prev (2000) = +50%.
    assert ctx.month_delta_pct == pytest.approx(50.0)

    # Prompt string surfaces the seeded names verbatim.
    prompt = ctx.to_prompt_string()
    assert "Kaffe Mellanrost" in prompt
    assert "Mjölk 1L" in prompt
    assert "Alpha Kund AB" in prompt


@pytest.mark.asyncio
async def test_ai_chat_injects_context_into_system_prompt(
    db_session: AsyncSession, seeded, client_factory, monkeypatch,
):
    # Force the PRO plan gate and the API key presence check to pass.
    org = seeded["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    from app.routers import integrations as integrations_router
    monkeypatch.setattr(integrations_router.settings, "OPENAI_API_KEY", "sk-test")

    captured: dict = {}

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.chat = SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(side_effect=self._create),
            ))

        async def _create(self, *, model, messages, max_tokens, temperature):
            captured["messages"] = messages
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="ok"),
            )])

    # Patch the AsyncOpenAI symbol on the `openai` module that the
    # endpoint imports lazily inside the try block.
    import openai as _openai  # noqa: WPS433
    monkeypatch.setattr(_openai, "AsyncOpenAI", _FakeClient)

    async with client_factory(seeded["member"]) as client:
        res = await client.post(
            "/api/integrations/ai/chat",
            json={"message": "Vad ska jag göra idag?"},
        )

    assert res.status_code == 200, res.text
    assert res.json() == {"reply": "ok"}

    system = next(m for m in captured["messages"] if m["role"] == "system")["content"]
    assert system.startswith(
        "You are Varuflow AI, a business advisor for a Swedish wholesale company."
    )
    assert "Kaffe Mellanrost" in system
    assert "Alpha Kund AB" in system


@pytest.mark.asyncio
async def test_ai_chat_rate_limit_returns_429(
    db_session: AsyncSession, seeded, client_factory, monkeypatch,
):
    org = seeded["org"]
    org.plan = OrgPlan.PRO
    # Pre-fill today's counter to the cap so the next request trips the
    # limit immediately without looping 20 times in the test.
    db_session.add(DailyAiUsage(
        org_id=org.id, usage_date=date.today(), count=20,
    ))
    await db_session.commit()

    from app.routers import integrations as integrations_router
    monkeypatch.setattr(integrations_router.settings, "OPENAI_API_KEY", "sk-test")

    # Even though OpenAI should not be reached, patch it defensively so
    # a bug that falls through to the call doesn't make a real request.
    import openai as _openai  # noqa: WPS433

    class _Boom:
        def __init__(self, *a, **kw): raise AssertionError("OpenAI must not be called when rate-limited")
    monkeypatch.setattr(_openai, "AsyncOpenAI", _Boom)

    async with client_factory(seeded["member"]) as client:
        res = await client.post(
            "/api/integrations/ai/chat",
            json={"message": "hej"},
        )
    assert res.status_code == 429
    assert "limit" in res.json()["detail"].lower()
