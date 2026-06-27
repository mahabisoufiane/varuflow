#!/usr/bin/env python3
"""One-shot script: add require_module plan enforcement to the 148 routers missing it.

Run from repo root:
    python agents/add_plan_enforcement.py
"""
import re
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parent.parent / "backend/app/routers"

MODULE_MAP: dict[str, str] = {
    # ── invoicing (FREE+) ──────────────────────────────────────────
    "contract_signing":         "invoicing",
    "credit_notes":             "invoicing",
    "customer_activity":        "invoicing",
    "customer_addresses":       "invoicing",
    "customer_contacts":        "invoicing",
    "customer_history":         "invoicing",
    "customer_notes":           "invoicing",
    "customer_org_members":     "invoicing",
    "customer_preferences":     "invoicing",
    "customer_statements":      "invoicing",
    "customer_tags":            "invoicing",
    "disputes":                 "invoicing",
    "email_templates":          "invoicing",
    "invoice_activity":         "invoicing",
    "invoice_notes":            "invoicing",
    "invoice_tags":             "invoicing",
    "invoice_templates":        "invoicing",
    "online_orders":            "invoicing",
    "payment_options":          "invoicing",
    "receipt_exports":          "invoicing",
    "referrals":                "invoicing",
    "referrals_sprint9":        "invoicing",
    "return_pickups":           "invoicing",
    "saved_payment_methods":    "invoicing",
    "statement_requests":       "invoicing",

    # ── inventory (FREE+) ─────────────────────────────────────────
    "auto_reorder":             "inventory",
    "custom_fields":            "inventory",
    "data_import":              "inventory",
    "documents":                "inventory",
    "kitting":                  "inventory",
    "labels":                   "inventory",
    "landed_costs":             "inventory",
    "product_activity":         "inventory",
    "product_import":           "inventory",
    "product_notes":            "inventory",
    "purchase_order_activity":  "inventory",
    "purchase_order_notes":     "inventory",
    "purchase_order_tags":      "inventory",
    "purchase_requests":        "inventory",
    "qc":                       "inventory",
    "stock_counts":             "inventory",
    "stock_transfers":          "inventory",
    "supplier_activity":        "inventory",
    "supplier_contacts":        "inventory",
    "supplier_notes":           "inventory",
    "supplier_sustainability":  "inventory",
    "supplier_tags":            "inventory",
    "tags":                     "inventory",
    "uploads":                  "inventory",
    "vendor_ratings":           "inventory",
    "warehouse_activity":       "inventory",
    "warehouse_notes":          "inventory",
    "warehouse_tags":           "inventory",

    # ── settings (FREE+) ─────────────────────────────────────────
    "audit":                    "settings",
    "currencies":               "settings",
    "customer_api_keys":        "settings",
    "customer_app_config":      "settings",
    "customer_webhooks_config": "settings",
    "gdpr_consent":             "settings",
    "location_timezones":       "settings",
    "notification_bundles":     "settings",
    "notification_channels":    "settings",
    "notification_prefs":       "settings",
    "notifications":            "settings",
    "policy_docs":              "settings",
    "saved_filters":            "settings",
    "search":                   "settings",
    "zapier_connect":           "settings",
    "zapier_connector":         "settings",

    # ── analytics (PRO+) ─────────────────────────────────────────
    "activity":                 "analytics",
    "after_sales":              "analytics",
    "carbon":                   "analytics",
    "decision_log":             "analytics",
    "esg":                      "analytics",
    "franchise":                "analytics",
    "market_expansion":         "analytics",
    "marketing_attribution":    "analytics",
    "merchant_reviews":         "analytics",
    "mobile_kpi":               "analytics",
    "nps":                      "analytics",
    "pricing_experiments":      "analytics",
    "regulatory_calendar":      "analytics",
    "service_reviews":          "analytics",
    "voice_reports":            "analytics",
    "watch_sessions":           "analytics",

    # ── crm (PRO+) ───────────────────────────────────────────────
    "announcements":            "crm",
    "birthday_vouchers":        "crm",
    "customer_chat":            "crm",
    "family_accounts":          "crm",
    "landing_pages":            "crm",
    "live_chat":                "crm",
    "membership_tiers":         "crm",
    "merchant_subscriptions":   "crm",
    "message_translation":      "crm",
    "messaging":                "crm",
    "operator_referrals":       "crm",
    "partner_program":          "crm",
    "photo_updates":            "crm",
    "portfolio_photos":         "crm",
    "reviews":                  "crm",
    "sms_outbox":               "crm",
    "unified_inbox":            "crm",
    "video_consultations":      "crm",

    # ── hr (PRO+) ────────────────────────────────────────────────
    "achievements":             "hr",
    "background_checks":        "hr",
    "calendar_sync":            "hr",
    "checklists":               "hr",
    "conflict_of_interest":     "hr",
    "identity_verification":    "hr",
    "important_dates":          "hr",
    "knowledge_base":           "hr",
    "mileage_logs":             "hr",
    "mobile_routes":            "hr",
    "mobile_signatures":        "hr",
    "mobile_voice_notes":       "hr",
    "okr":                      "hr",
    "sop_library":              "hr",
    "staff_credentials":        "hr",
    "staff_notes":              "hr",
    "tasks":                    "hr",
    "work_management":          "hr",

    # ── finance (PRO+) ───────────────────────────────────────────
    "accountant_forwarding":    "finance",
    "data_room":                "finance",
    "expense_tags":             "finance",
    "insurance":                "finance",
    "insurance_addons":         "finance",
    "petty_cash":               "finance",
    "quote_comparisons":        "finance",

    # ── manufacturing (PRO+) ─────────────────────────────────────
    "bom_extras":               "manufacturing",
    "job_cards":                "manufacturing",

    # ── pos (PRO+) ───────────────────────────────────────────────
    "booking_capacity":         "pos",
    "booking_subscriptions":    "pos",
    "group_bookings":           "pos",
    "live_tracking":            "pos",
    "lock_screen_alerts":       "pos",
    "mobile_terminal":          "pos",
    "service_status":           "pos",
    "service_timeline":         "pos",
    "shop_config":              "pos",
    "wallet_passes":            "pos",
    "wallet_payments":          "pos",

    # ── ai (PRO+) ────────────────────────────────────────────────
    "chatbot":                  "ai",
    "sentiment_analysis":       "ai",
    "smart_replies":            "ai",
    "voice_notes":              "ai",
    "voice_shortcuts":          "ai",
}

IMPORT_LINE = "from app.middleware.plan_check import require_module\n"

# Pattern: router = APIRouter(...) possibly multiline
ROUTER_RE = re.compile(
    r'^(router\s*=\s*APIRouter\()(.*)(\))',
    re.MULTILINE,
)


def patch_file(path: Path, module_key: str) -> bool:
    """Add require_module dependency to a router file. Returns True if changed."""
    src = path.read_text()

    # Skip if already has require_module
    if "require_module" in src:
        print(f"  [skip] {path.name} — already has require_module")
        return False

    # 1. Add import if missing
    if IMPORT_LINE.strip() not in src:
        # Insert after last "from app." import block
        lines = src.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from app.") or line.startswith("import app."):
                insert_at = i + 1
        if insert_at == 0:
            # fallback: after last fastapi import
            for i, line in enumerate(lines):
                if "from fastapi" in line or "import fastapi" in line:
                    insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        src = "".join(lines)

    # 2. Patch `router = APIRouter(...)` — handle both single-line and multiline
    # Find the router = APIRouter(...) block (may span multiple lines)
    router_match = re.search(r'(router\s*=\s*APIRouter\()(.*?)(\))', src, re.DOTALL)
    if not router_match:
        print(f"  [warn] {path.name} — could not find router = APIRouter(...)")
        return False

    full_match = router_match.group(0)
    inner = router_match.group(2)  # content inside APIRouter(...)

    dep = f'dependencies=[Depends(require_module("{module_key}"))]'

    if "dependencies=" in inner:
        # Append to existing dependencies list
        new_inner = re.sub(
            r'dependencies=\[([^\]]*)\]',
            lambda m: f'dependencies=[{m.group(1)}, Depends(require_module("{module_key}"))]',
            inner,
        )
    else:
        # Append as new kwarg
        stripped = inner.rstrip()
        if stripped.endswith(",") or stripped == "":
            new_inner = stripped + f"\n    {dep},\n"
        else:
            new_inner = stripped + f", {dep}"

    new_full = router_match.group(1) + new_inner + router_match.group(3)
    src = src[:router_match.start()] + new_full + src[router_match.end():]

    path.write_text(src)
    return True


def main() -> None:
    changed = 0
    skipped = 0
    errors = 0

    for stem, module_key in sorted(MODULE_MAP.items()):
        fpath = ROUTERS_DIR / f"{stem}.py"
        if not fpath.exists():
            print(f"  [missing] {stem}.py")
            errors += 1
            continue
        try:
            if patch_file(fpath, module_key):
                print(f"  [patched] {stem}.py → {module_key}")
                changed += 1
            else:
                skipped += 1
        except Exception as exc:
            print(f"  [ERROR] {stem}.py: {exc}")
            errors += 1

    print(f"\nDone: {changed} patched, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
