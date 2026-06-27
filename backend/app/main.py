import asyncio
import logging
import logging.config
import os
from contextlib import asynccontextmanager

import alembic.command
import alembic.config
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Structured JSON-style logging
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

from app.config import settings, validate_production_config
from app.database import engine
from app.middleware.country import CountryMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.readonly import ReadOnlyMiddleware
from app.middleware.pause_guard import PauseWriteGuardMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.routers import accounting, activity, ai_automation, ai_engine, analytics, approval_chains, audit, auth, auto_reorder, bank_feed, bi, billing, bookings, budget, campaigns, balance_sheet, cashflow, ceo_dashboard, churn_dashboard, commissions, compliance_audit_chain, compliance_data_residency, compliance_field_masking, compliance_pentest, contract_signing, contracts, countries, credit_notes, crm, crm_sync, currencies, custom_fields, customer_activity, customer_contacts, customer_notes, customer_statements, customer_tags, data_import, developer, documents, einvoice, email_sequences, expense_activity, expense_budgets, expense_notes, expense_reports, expense_tags, expenses, financial_reports, fixed_assets, forecasting, franchise, gcc_payments, gdpr, gdpr_consent, gift_cards, health, hr_employee_onboarding, hr_employees, hr_leave, hr_org_chart, hr_reviews, hr_time, hr_timesheets, hr_training, integrations, inventory, inventory_audit, invoice_activity, invoice_notes, invoice_tags, invoice_templates, invoicing, kpi_goals, labels, lead_forms, leads, ledger, local_auth, loyalty, manufacturing, market_expansion, meeting_links, mileage_logs, mobile_routes, mobile_signatures, mobile_terminal, mobile_voice_notes, multi_entity, notification_channels, notifications, okr, onboarding, online_orders, open_banking, partner_program, payroll, payment_options, after_sales, messaging, petty_cash, pnl, policy_docs, portal, portal_admin, pos, pos_quick_buttons, pricing_experiments, product_activity, product_import, product_notes, product_tags, projects, purchase_order_notes, purchase_order_tags, purchase_order_activity, purchase_requests, qc, quotes, recurring, recurring_expenses, referrals, reports, reviews, sandbox, saved_filters, scenario_planning, scheduling, search, segments, settings_security, shifts, shop_config, shopify_sync, stock_counts, stock_transfers, storefront, supplier_activity, supplier_contacts, supplier_credit_notes, supplier_notes, supplier_portal, supplier_statements, supplier_tags, tags, team, uploads, vat_return, visma_sync, waitlist, warehouse_activity, warehouse_notes, warehouse_tags, webhooks, widget, work_management, zapier_connect, zatca, zakat, tasks, announcements, job_cards, email_templates, sms_outbox, local_payments, merchant_subscriptions, reconciliation, bom_extras, landed_costs, vendor_ratings, kitting, dashboard_builder, report_builder, cashflow_prediction, anomaly_detection, cohort_analysis, esign, risk_register, insurance, regulatory_calendar, whistleblower, conflict_of_interest, carbon, esg, supplier_sustainability, investor_updates, cap_table, board_packs, data_room, marketing_attribution, ab_testing, landing_pages, marketing_broadcasts, nps, sop_library, checklists, recurring_reminders, decision_log, family_accounts, booking_subscriptions, group_bookings, booking_waitlist, wallet_passes, customer_app_config, customer_chat, video_consultations, voice_notes, notification_prefs, service_status, service_timeline, live_tracking, photo_updates, customer_history
from app.routers import accounting_partners, operator_referrals
# Sprint 9: Personalization + Loyalty & Rewards
from app.routers import (
    achievements,
    ai_recommendations,
    birthday_vouchers,
    customer_preferences,
    important_dates,
    loyalty_streaks,
    membership_tiers,
    referrals_sprint9,
    saved_payment_methods,
    staff_notes,
)
# Sprint 10: Convenience + B2B Buyer Features
from app.routers import (
    accountant_forwarding,
    buyer_pos,
    calendar_sync,
    customer_addresses,
    customer_org_members,
    negotiated_pricing,
    quote_comparisons,
    receipt_exports,
    wallet_payments,
)
# Sprint 11: Trust & Verification + Customer Service Layer
from app.routers import (
    service_reviews,
    staff_credentials,
    booking_capacity,
    portfolio_photos,
    live_chat,
    chatbot,
    knowledge_base,
    return_pickups,
)
# Sprint 12: Trust & Safety + Communication Layer
from app.routers import (
    identity_verification,
    background_checks,
    insurance_addons,
    disputes,
    merchant_reviews,
    unified_inbox,
    message_translation,
    smart_replies,
    sentiment_analysis,
)
# Sprint 13: Reporting + AI Across the Stack
from app.routers import (
    statement_requests,
    mobile_kpi,
    voice_reports,
    anomaly_notifications,
    ai_product_desc,
    ai_email_draft,
    ai_photo_tags,
    ai_pricing,
    ai_personas,
)
# Sprint 14: Integrations QoL
from app.routers import (
    merchant_calendar_sync,
    zapier_connector,
    customer_webhooks_config,
    customer_api_keys,
    notification_bundles,
    location_timezones,
)
# Sprint 15: Mobile First
from app.routers import (
    home_screen_widgets,
    watch_sessions,
    voice_shortcuts,
    lock_screen_alerts,
)
# Trial system
from app.routers import trial
# Upsell trigger engine
from app.routers import upsells
from app.services.scheduler import create_scheduler

# slowapi's `get_remote_address` reads `request.client.host`, which on
# Railway (and any reverse-proxy deployment) is the PROXY's IP — so the
# 200/min default would be shared across every real client behind the
# proxy. A single aggressive user hitting 200/min would then lock out
# everyone else. Use a key_func that honours TRUST_PROXY via
# X-Forwarded-For, matching what the custom RateLimitMiddleware does.
def _slowapi_key(request: Request) -> str:
    if settings.TRUST_PROXY:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_slowapi_key, default_limits=["200/minute"])

if settings.SENTRY_DSN:
    # Scrub PII and secrets from every event before it leaves the process.
    # Matches header/cookie/query-string keys that commonly carry sensitive
    # values. Body payloads are never attached by default when
    # send_default_pii=False, but we still redact request data that the
    # FastAPI integration may capture from exceptions raised mid-request.
    _SENSITIVE_KEYS = {
        "authorization", "cookie", "set-cookie", "x-admin-key",
        "x-confirm-delete", "stripe-signature", "password", "token",
        "access_token", "refresh_token", "totp_code", "api_key",
    }

    def _scrub(event, _hint):
        try:
            for section in ("request",):
                data = event.get(section) or {}
                for key in ("headers", "cookies", "query_string", "data"):
                    bucket = data.get(key)
                    if isinstance(bucket, dict):
                        for k in list(bucket.keys()):
                            if k.lower() in _SENSITIVE_KEYS:
                                bucket[k] = "[filtered]"
            # Strip user email/IP if somehow attached despite send_default_pii=False
            user = event.get("user") or {}
            for k in ("email", "ip_address", "username"):
                if k in user:
                    user[k] = "[filtered]"
        except Exception:
            pass
        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
        before_send=_scrub,
    )

log = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations synchronously (called from a thread executor)."""
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = alembic.config.Config(os.path.abspath(ini_path))
    alembic.command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. Security config validation (crashes on bad production config) ──────
    validate_production_config()

    # ── 2. Database migrations ────────────────────────────────────────────────
    # Executed in a thread executor because Alembic's online migration path
    # calls asyncio.run() internally, which cannot be nested inside the
    # already-running event loop.
    loop = asyncio.get_running_loop()
    try:
        log.info("Running Alembic migrations…")
        await loop.run_in_executor(None, _run_migrations)
        log.info("Alembic migrations complete.")
    except Exception:
        log.exception("Alembic migration failed — continuing startup anyway.")

    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    await engine.dispose()


# In production, disable the interactive /docs and /redoc UIs to reduce
# attack surface (they enumerate every endpoint + schema for anyone who
# finds the URL). The raw OpenAPI JSON stays available at /openapi.json
# for internal tooling and the frontend API-types codegen.
_docs_url = None if settings.ENV == "production" else "/docs"
_redoc_url = None if settings.ENV == "production" else "/redoc"

app = FastAPI(
    title="Varuflow API",
    version="0.1.0",
    description="Inventory and invoicing API for Swedish wholesalers",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Read-only maintenance mode — added BEFORE CORS so CORS still wraps the
# 503 responses it produces (preventing browser CORS errors during a
# restore). Toggle with READONLY_MODE=true in Railway Variables.
app.add_middleware(ReadOnlyMiddleware)

# Per-org subscription-pause write guard (Item 50). Blocks mutating
# requests with 423 when the caller's org has ``is_paused=True``.
# Kept after ReadOnlyMiddleware so a global freeze still trumps it.
app.add_middleware(PauseWriteGuardMiddleware)

# IP-based rate limit: 100 req/min global, tighter per-path buckets
# (login/signup/MFA/billing/AI — see RateLimitMiddleware._PATH_LIMITS).
# Must be added BEFORE CORSMiddleware so CORS headers are still injected
# on 429 responses. Set RATE_LIMIT_DISABLED=true to bypass in tests.
if settings.RATE_LIMIT_DISABLED and settings.ENV == "production":
    # Loud startup warning — a production deploy with rate limiting
    # disabled is almost certainly a config accident.
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "RATE_LIMIT_DISABLED=true in production — middleware is a no-op. "
        "Verify this is intentional."
    )
app.add_middleware(RateLimitMiddleware)

# Request-ID correlation — registered before CORS (inner layer in Starlette's
# LIFO stack) so every downstream log line and Sentry event carries the same
# id and the header is echoed on the response.
app.add_middleware(RequestIdMiddleware)

# Country resolution — registered before CORS (inner layer) so it sees real
# client headers but does not interfere with preflight short-circuiting.
app.add_middleware(CountryMiddleware)

# CORSMiddleware MUST be the outermost add_middleware layer. In Starlette's
# LIFO execution model the last-registered middleware runs first on every
# request. CountryMiddleware and RequestIdMiddleware are registered above
# (inner) so any error they produce is still wrapped by CORS headers and
# never reaches the browser without Access-Control-Allow-Origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-Country-Code", "X-Request-ID", "X-Confirm-Delete", "X-Admin-Key"],
    expose_headers=["X-Country-Code", "X-Request-ID"],
    max_age=3600,
)


@app.middleware("http")
async def _add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    # API responses are JSON only; a tight CSP blocks any script/style loads in
    # case an error path accidentally returns HTML. frame-ancestors 'none'
    # prevents clickjacking (redundant with X-Frame-Options but more modern).
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    # HSTS — only safe to emit when served over HTTPS (Railway terminates TLS).
    if settings.ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    # Do NOT catch exceptions here — this middleware is outermost (last decorator =
    # outermost in Starlette's LIFO stack). Catching and re-raising a JSONResponse
    # here would bypass CORSMiddleware (which is inner), stripping CORS headers from
    # error responses and causing browser CORS errors. Let exceptions propagate so
    # @app.exception_handler(Exception) fires inside ExceptionMiddleware (inside CORS).
    response = await call_next(request)
    # Prefer request.state (set by RequestIdMiddleware); fall back to the
    # Item 30 ContextVar so the log line stays correlated even if a
    # future middleware reshuffle removes the state attribute before this
    # handler runs. Both pointers are populated identically today; using
    # both as a defensive OR keeps this line from silently regressing.
    from app.middleware.request_id import get_current_request_id
    request_id = getattr(request.state, "request_id", None) or get_current_request_id() or "-"
    log.info(
        '"method":"%s","path":"%s","status":%d,"request_id":"%s"',
        request.method, request.url.path, response.status_code, request_id,
    )
    return response


# Catch all unhandled exceptions so they stay inside the middleware stack
# (not handled by ServerErrorMiddleware which is outside CORSMiddleware).
# Without this, 500s reach the browser without Access-Control-Allow-Origin.
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback so Railway logs surface root causes.
    # The client receives only a generic message — no internal details ever leak.
    request_id = getattr(request.state, "request_id", "-")
    log.exception(
        "Unhandled exception | method=%s path=%s request_id=%s",
        request.method, request.url.path, request_id,
    )

    origin = request.headers.get("origin")
    allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    headers = {"X-Request-ID": request_id}
    if origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers=headers,
    )

app.include_router(health.router, prefix="/api")
app.include_router(auth.router)
app.include_router(local_auth.router)
app.include_router(inventory.router)
app.include_router(stock_counts.router)
app.include_router(invoicing.router)
app.include_router(waitlist.router)
app.include_router(analytics.router)
app.include_router(team.router)
app.include_router(recurring.router)
app.include_router(recurring.public_router)
app.include_router(recurring_expenses.router)
app.include_router(mileage_logs.router)
app.include_router(expense_budgets.router)
app.include_router(expense_reports.router)
app.include_router(pos.router)
app.include_router(billing.router)
app.include_router(integrations.router)
app.include_router(portal.router)
app.include_router(portal_admin.router)
app.include_router(ai_engine.router)
app.include_router(countries.router)
app.include_router(gdpr.router)
app.include_router(audit.router)
app.include_router(einvoice.router)
app.include_router(accounting.router)
app.include_router(ledger.router)
app.include_router(financial_reports.router)
app.include_router(vat_return.router)
app.include_router(fixed_assets.router)
app.include_router(payroll.router)
app.include_router(budget.router)
app.include_router(bank_feed.router)
app.include_router(notifications.router)
app.include_router(onboarding.router)
app.include_router(webhooks.router)
app.include_router(auto_reorder.router)
app.include_router(settings_security.router)
app.include_router(bookings.router)
app.include_router(bookings.public_checkin_router)
app.include_router(commissions.router)
app.include_router(gift_cards.router)
app.include_router(currencies.router)
app.include_router(loyalty.router)
app.include_router(labels.router)
app.include_router(supplier_portal.router)
app.include_router(stock_transfers.router)
app.include_router(segments.router)
app.include_router(campaigns.router)
app.include_router(forecasting.router)
app.include_router(invoice_templates.router)
app.include_router(expenses.router)
app.include_router(expense_notes.router)
app.include_router(expense_tags.router)
app.include_router(expense_activity.router)
app.include_router(documents.router)
app.include_router(uploads.router)
app.include_router(developer.router)
app.include_router(widget.router)
app.include_router(inventory_audit.router)
app.include_router(reviews.router)
app.include_router(reviews.public_router)
app.include_router(search.router)
app.include_router(custom_fields.router)
app.include_router(tags.router)
app.include_router(saved_filters.router)
app.include_router(activity.router)
app.include_router(pos_quick_buttons.router)
app.include_router(contracts.router)
app.include_router(shifts.router)
app.include_router(referrals.router)
app.include_router(product_import.router)
app.include_router(product_notes.router)
app.include_router(product_tags.router)
app.include_router(product_activity.router)
app.include_router(warehouse_notes.router)
app.include_router(warehouse_tags.router)
app.include_router(warehouse_activity.router)
app.include_router(invoice_notes.router)
app.include_router(invoice_tags.router)
app.include_router(invoice_activity.router)
app.include_router(purchase_order_notes.router)
app.include_router(purchase_order_tags.router)
app.include_router(purchase_order_activity.router)
app.include_router(supplier_credit_notes.router)
app.include_router(supplier_statements.router)
app.include_router(credit_notes.router)
app.include_router(customer_notes.router)
app.include_router(customer_statements.router)
app.include_router(customer_tags.router)
app.include_router(customer_contacts.router)
app.include_router(customer_activity.router)
app.include_router(supplier_notes.router)
app.include_router(supplier_tags.router)
app.include_router(supplier_contacts.router)
app.include_router(supplier_activity.router)
app.include_router(storefront.router)
app.include_router(online_orders.router)
app.include_router(shop_config.router)
app.include_router(crm.router)
app.include_router(lead_forms.router)
app.include_router(leads.router)
app.include_router(email_sequences.router)
app.include_router(meeting_links.router)
app.include_router(hr_employees.router)
app.include_router(hr_leave.router)
app.include_router(hr_org_chart.router)
app.include_router(hr_reviews.router)
app.include_router(hr_time.router)
app.include_router(hr_timesheets.router)
app.include_router(hr_employee_onboarding.router)
app.include_router(hr_training.router)
app.include_router(manufacturing.router)
app.include_router(qc.router)
app.include_router(projects.router)
app.include_router(ai_automation.router)
app.include_router(zatca.router)
app.include_router(gcc_payments.router)
app.include_router(zakat.router)
app.include_router(shopify_sync.router)
app.include_router(crm_sync.router)
app.include_router(notification_channels.router)
app.include_router(visma_sync.router)
app.include_router(open_banking.router)
app.include_router(zapier_connect.router)
app.include_router(mobile_routes.router)
app.include_router(mobile_signatures.router)
app.include_router(mobile_terminal.router)
app.include_router(mobile_voice_notes.router)
app.include_router(multi_entity.router)
app.include_router(franchise.router)
app.include_router(compliance_audit_chain.router)
app.include_router(compliance_field_masking.router)
app.include_router(compliance_data_residency.router)
app.include_router(compliance_pentest.router)
app.include_router(bi.router)
app.include_router(ceo_dashboard.router)
app.include_router(kpi_goals.router)
app.include_router(okr.router)
app.include_router(risk_register.router)
app.include_router(insurance.router)
app.include_router(regulatory_calendar.router)
app.include_router(whistleblower.router)
app.include_router(conflict_of_interest.router)
app.include_router(carbon.router)
app.include_router(esg.router)
app.include_router(supplier_sustainability.router)
app.include_router(investor_updates.router)
app.include_router(cap_table.router)
app.include_router(board_packs.router)
app.include_router(data_room.router)
app.include_router(marketing_attribution.router)
app.include_router(ab_testing.router)
app.include_router(landing_pages.router)
app.include_router(marketing_broadcasts.router)
app.include_router(nps.router)
app.include_router(sop_library.router)
app.include_router(checklists.router)
app.include_router(recurring_reminders.router)
app.include_router(decision_log.router)
app.include_router(family_accounts.router)
app.include_router(booking_subscriptions.router)
app.include_router(group_bookings.router)
app.include_router(booking_waitlist.router)
app.include_router(wallet_passes.router)
app.include_router(customer_app_config.router)
app.include_router(customer_chat.router)
app.include_router(video_consultations.router)
app.include_router(voice_notes.router)
app.include_router(notification_prefs.router)
app.include_router(service_status.router)
app.include_router(service_timeline.router)
app.include_router(live_tracking.router)
app.include_router(photo_updates.router)
app.include_router(customer_history.router)
app.include_router(scenario_planning.router)
app.include_router(partner_program.router)
app.include_router(pricing_experiments.router)
app.include_router(market_expansion.router)
app.include_router(churn_dashboard.router)
app.include_router(approval_chains.router)
app.include_router(contract_signing.router)
app.include_router(policy_docs.router)
app.include_router(work_management.router)
app.include_router(scheduling.router)
app.include_router(purchase_requests.router)
app.include_router(tasks.router)
app.include_router(announcements.router)
app.include_router(job_cards.router)
app.include_router(petty_cash.router)
app.include_router(reports.router)
app.include_router(pnl.router)
app.include_router(cashflow.router)
app.include_router(balance_sheet.router)
app.include_router(quotes.public_router)
app.include_router(payment_options.router)
app.include_router(after_sales.router)
app.include_router(after_sales.public_router)
app.include_router(messaging.router)
app.include_router(email_templates.router)
app.include_router(sms_outbox.router)
app.include_router(local_payments.router)
app.include_router(merchant_subscriptions.router)
app.include_router(reconciliation.router)
app.include_router(bom_extras.router)
app.include_router(landed_costs.router)
app.include_router(vendor_ratings.router)
app.include_router(kitting.router)
app.include_router(dashboard_builder.router)
app.include_router(report_builder.router)
app.include_router(cashflow_prediction.router)
app.include_router(anomaly_detection.router)
app.include_router(cohort_analysis.router)
app.include_router(esign.router)
app.include_router(data_import.router)
app.include_router(sandbox.router)

# Sprint 9: Personalization + Loyalty & Rewards
app.include_router(customer_preferences.router)
app.include_router(ai_recommendations.router)
app.include_router(important_dates.router)
app.include_router(saved_payment_methods.router)
app.include_router(staff_notes.router)
app.include_router(membership_tiers.router)
app.include_router(achievements.router)
app.include_router(birthday_vouchers.router)
app.include_router(referrals_sprint9.router)
app.include_router(loyalty_streaks.router)
app.include_router(gdpr_consent.router)

# Sprint 10: Convenience + B2B Buyer Features
app.include_router(customer_addresses.router)
app.include_router(calendar_sync.router)
app.include_router(accountant_forwarding.router)
app.include_router(receipt_exports.router)
app.include_router(wallet_payments.router)
app.include_router(buyer_pos.router)
app.include_router(customer_org_members.router)
app.include_router(negotiated_pricing.router)
app.include_router(quote_comparisons.router)

# Sprint 11: Trust & Verification + Customer Service Layer
app.include_router(service_reviews.router)
app.include_router(staff_credentials.router)
app.include_router(booking_capacity.router)
app.include_router(portfolio_photos.router)
app.include_router(live_chat.router)
app.include_router(chatbot.router)
app.include_router(knowledge_base.router)
app.include_router(return_pickups.router)

# Sprint 12: Trust & Safety + Communication Layer
app.include_router(identity_verification.router)
app.include_router(background_checks.router)
app.include_router(insurance_addons.router)
app.include_router(disputes.router)
app.include_router(merchant_reviews.router)
app.include_router(unified_inbox.router)
app.include_router(message_translation.router)
app.include_router(smart_replies.router)
app.include_router(sentiment_analysis.router)

# Sprint 13: Reporting + AI Across the Stack
app.include_router(statement_requests.router)
app.include_router(mobile_kpi.router)
app.include_router(voice_reports.router)
app.include_router(anomaly_notifications.router)
app.include_router(ai_product_desc.router)
app.include_router(ai_email_draft.router)
app.include_router(ai_photo_tags.router)
app.include_router(ai_pricing.router)
app.include_router(ai_personas.router)

# Sprint 14: Integrations QoL
app.include_router(merchant_calendar_sync.router)
app.include_router(zapier_connector.router)
app.include_router(customer_webhooks_config.router)
app.include_router(customer_api_keys.router)
app.include_router(notification_bundles.router)
app.include_router(location_timezones.router)

# Sprint 15: Mobile First
app.include_router(home_screen_widgets.router)
app.include_router(watch_sessions.router)
app.include_router(voice_shortcuts.router)
app.include_router(lock_screen_alerts.router)

# Trial system
app.include_router(trial.router)

# Upsell trigger engine
app.include_router(upsells.router)

# Accounting firm partner programme + operator referrals
app.include_router(accounting_partners.router)
app.include_router(operator_referrals.router)

# Trial onboarding sequences admin dashboard
from app.routers import trial_admin
app.include_router(trial_admin.router)