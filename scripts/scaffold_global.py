#!/usr/bin/env python3
"""
scaffold_global.py — idempotent generator that scaffolds multi-environment
and multi-country structure for the Varuflow monorepo.

Creates (never overwrites existing non-empty files):
  config/countries/<code>.json            Tax / VAT / currency per country
  config/countries/index.json             Machine-readable master list
  docs/legal/<code>/README.md             Compliance placeholder per country
  deploy/<env>/                           Deployment manifests per env
  deploy/<env>/<region>/<code>/           Per-country per-env deploy stubs
  backend/.env.development|preproduction|production      Env-tier templates
  frontend/.env.development|preproduction|production     Env-tier templates
  frontend/messages/<locale>.json         Copies of en.json for new locales

Safe to re-run. Run from repo root:  python3 scripts/scaffold_global.py
"""
from __future__ import annotations
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Country master data — ISO 3166-1 alpha-2, ISO 4217 currency, primary VAT rate
# Sources: national tax authority websites (rates current as of 2025). Review
# before trusting in billing code — rates change. Values are *standard* rates.
# ─────────────────────────────────────────────────────────────────────────────
COUNTRIES: list[dict] = [
    # EU-27
    {"code": "AT", "name": "Austria",        "region": "europe", "currency": "EUR", "vat": 20.0,  "locale": "de-AT"},
    {"code": "BE", "name": "Belgium",        "region": "europe", "currency": "EUR", "vat": 21.0,  "locale": "nl-BE"},
    {"code": "BG", "name": "Bulgaria",       "region": "europe", "currency": "BGN", "vat": 20.0,  "locale": "bg-BG"},
    {"code": "HR", "name": "Croatia",        "region": "europe", "currency": "EUR", "vat": 25.0,  "locale": "hr-HR"},
    {"code": "CY", "name": "Cyprus",         "region": "europe", "currency": "EUR", "vat": 19.0,  "locale": "el-CY"},
    {"code": "CZ", "name": "Czechia",        "region": "europe", "currency": "CZK", "vat": 21.0,  "locale": "cs-CZ"},
    {"code": "DK", "name": "Denmark",        "region": "europe", "currency": "DKK", "vat": 25.0,  "locale": "da-DK"},
    {"code": "EE", "name": "Estonia",        "region": "europe", "currency": "EUR", "vat": 22.0,  "locale": "et-EE"},
    {"code": "FI", "name": "Finland",        "region": "europe", "currency": "EUR", "vat": 25.5,  "locale": "fi-FI"},
    {"code": "FR", "name": "France",         "region": "europe", "currency": "EUR", "vat": 20.0,  "locale": "fr-FR"},
    {"code": "DE", "name": "Germany",        "region": "europe", "currency": "EUR", "vat": 19.0,  "locale": "de-DE"},
    {"code": "GR", "name": "Greece",         "region": "europe", "currency": "EUR", "vat": 24.0,  "locale": "el-GR"},
    {"code": "HU", "name": "Hungary",        "region": "europe", "currency": "HUF", "vat": 27.0,  "locale": "hu-HU"},
    {"code": "IE", "name": "Ireland",        "region": "europe", "currency": "EUR", "vat": 23.0,  "locale": "en-IE"},
    {"code": "IT", "name": "Italy",          "region": "europe", "currency": "EUR", "vat": 22.0,  "locale": "it-IT"},
    {"code": "LV", "name": "Latvia",         "region": "europe", "currency": "EUR", "vat": 21.0,  "locale": "lv-LV"},
    {"code": "LT", "name": "Lithuania",      "region": "europe", "currency": "EUR", "vat": 21.0,  "locale": "lt-LT"},
    {"code": "LU", "name": "Luxembourg",     "region": "europe", "currency": "EUR", "vat": 17.0,  "locale": "fr-LU"},
    {"code": "MT", "name": "Malta",          "region": "europe", "currency": "EUR", "vat": 18.0,  "locale": "en-MT"},
    {"code": "NL", "name": "Netherlands",    "region": "europe", "currency": "EUR", "vat": 21.0,  "locale": "nl-NL"},
    {"code": "PL", "name": "Poland",         "region": "europe", "currency": "PLN", "vat": 23.0,  "locale": "pl-PL"},
    {"code": "PT", "name": "Portugal",       "region": "europe", "currency": "EUR", "vat": 23.0,  "locale": "pt-PT"},
    {"code": "RO", "name": "Romania",        "region": "europe", "currency": "RON", "vat": 19.0,  "locale": "ro-RO"},
    {"code": "SK", "name": "Slovakia",       "region": "europe", "currency": "EUR", "vat": 23.0,  "locale": "sk-SK"},
    {"code": "SI", "name": "Slovenia",       "region": "europe", "currency": "EUR", "vat": 22.0,  "locale": "sl-SI"},
    {"code": "ES", "name": "Spain",          "region": "europe", "currency": "EUR", "vat": 21.0,  "locale": "es-ES"},
    {"code": "SE", "name": "Sweden",         "region": "europe", "currency": "SEK", "vat": 25.0,  "locale": "sv-SE"},
    # Non-EU Europe
    {"code": "GB", "name": "United Kingdom", "region": "europe", "currency": "GBP", "vat": 20.0,  "locale": "en-GB"},
    {"code": "NO", "name": "Norway",         "region": "europe", "currency": "NOK", "vat": 25.0,  "locale": "nb-NO"},
    {"code": "IS", "name": "Iceland",        "region": "europe", "currency": "ISK", "vat": 24.0,  "locale": "is-IS"},
    {"code": "CH", "name": "Switzerland",    "region": "europe", "currency": "CHF", "vat": 8.1,   "locale": "de-CH"},
    {"code": "AL", "name": "Albania",        "region": "europe", "currency": "ALL", "vat": 20.0,  "locale": "sq-AL"},
    {"code": "BA", "name": "Bosnia",         "region": "europe", "currency": "BAM", "vat": 17.0,  "locale": "bs-BA"},
    {"code": "ME", "name": "Montenegro",     "region": "europe", "currency": "EUR", "vat": 21.0,  "locale": "sr-ME"},
    {"code": "MK", "name": "North Macedonia","region": "europe", "currency": "MKD", "vat": 18.0,  "locale": "mk-MK"},
    {"code": "RS", "name": "Serbia",         "region": "europe", "currency": "RSD", "vat": 20.0,  "locale": "sr-RS"},
    {"code": "UA", "name": "Ukraine",        "region": "europe", "currency": "UAH", "vat": 20.0,  "locale": "uk-UA"},
    {"code": "MD", "name": "Moldova",        "region": "europe", "currency": "MDL", "vat": 20.0,  "locale": "ro-MD"},

    # Middle East
    {"code": "AE", "name": "United Arab Emirates", "region": "middle-east", "currency": "AED", "vat": 5.0,  "locale": "ar-AE"},
    {"code": "SA", "name": "Saudi Arabia",         "region": "middle-east", "currency": "SAR", "vat": 15.0, "locale": "ar-SA"},
    {"code": "QA", "name": "Qatar",                "region": "middle-east", "currency": "QAR", "vat": 0.0,  "locale": "ar-QA"},
    {"code": "KW", "name": "Kuwait",               "region": "middle-east", "currency": "KWD", "vat": 0.0,  "locale": "ar-KW"},
    {"code": "BH", "name": "Bahrain",              "region": "middle-east", "currency": "BHD", "vat": 10.0, "locale": "ar-BH"},
    {"code": "OM", "name": "Oman",                 "region": "middle-east", "currency": "OMR", "vat": 5.0,  "locale": "ar-OM"},
    {"code": "IL", "name": "Israel",               "region": "middle-east", "currency": "ILS", "vat": 18.0, "locale": "he-IL"},
    {"code": "TR", "name": "Türkiye",              "region": "middle-east", "currency": "TRY", "vat": 20.0, "locale": "tr-TR"},
    {"code": "JO", "name": "Jordan",               "region": "middle-east", "currency": "JOD", "vat": 16.0, "locale": "ar-JO"},
    {"code": "LB", "name": "Lebanon",              "region": "middle-east", "currency": "LBP", "vat": 11.0, "locale": "ar-LB"},
    {"code": "EG", "name": "Egypt",                "region": "middle-east", "currency": "EGP", "vat": 14.0, "locale": "ar-EG"},
    {"code": "IQ", "name": "Iraq",                 "region": "middle-east", "currency": "IQD", "vat": 0.0,  "locale": "ar-IQ"},
    {"code": "YE", "name": "Yemen",                "region": "middle-east", "currency": "YER", "vat": 5.0,  "locale": "ar-YE"},

    # Americas
    {"code": "US", "name": "United States", "region": "americas", "currency": "USD", "vat": 0.0,  "locale": "en-US"},
    {"code": "CA", "name": "Canada",        "region": "americas", "currency": "CAD", "vat": 5.0,  "locale": "en-CA"},
    {"code": "MX", "name": "Mexico",        "region": "americas", "currency": "MXN", "vat": 16.0, "locale": "es-MX"},
    {"code": "BR", "name": "Brazil",        "region": "americas", "currency": "BRL", "vat": 17.0, "locale": "pt-BR"},
    {"code": "AR", "name": "Argentina",     "region": "americas", "currency": "ARS", "vat": 21.0, "locale": "es-AR"},
    {"code": "CL", "name": "Chile",         "region": "americas", "currency": "CLP", "vat": 19.0, "locale": "es-CL"},
    {"code": "CO", "name": "Colombia",      "region": "americas", "currency": "COP", "vat": 19.0, "locale": "es-CO"},
    {"code": "PE", "name": "Peru",          "region": "americas", "currency": "PEN", "vat": 18.0, "locale": "es-PE"},
    {"code": "UY", "name": "Uruguay",       "region": "americas", "currency": "UYU", "vat": 22.0, "locale": "es-UY"},
    {"code": "PY", "name": "Paraguay",      "region": "americas", "currency": "PYG", "vat": 10.0, "locale": "es-PY"},
    {"code": "BO", "name": "Bolivia",       "region": "americas", "currency": "BOB", "vat": 13.0, "locale": "es-BO"},
    {"code": "EC", "name": "Ecuador",       "region": "americas", "currency": "USD", "vat": 15.0, "locale": "es-EC"},
    {"code": "VE", "name": "Venezuela",     "region": "americas", "currency": "VES", "vat": 16.0, "locale": "es-VE"},
    {"code": "GT", "name": "Guatemala",     "region": "americas", "currency": "GTQ", "vat": 12.0, "locale": "es-GT"},
    {"code": "CR", "name": "Costa Rica",    "region": "americas", "currency": "CRC", "vat": 13.0, "locale": "es-CR"},
    {"code": "PA", "name": "Panama",        "region": "americas", "currency": "PAB", "vat": 7.0,  "locale": "es-PA"},
    {"code": "DO", "name": "Dominican Rep.","region": "americas", "currency": "DOP", "vat": 18.0, "locale": "es-DO"},
    {"code": "JM", "name": "Jamaica",       "region": "americas", "currency": "JMD", "vat": 15.0, "locale": "en-JM"},
]

ENVS = ["development", "preproduction", "production"]


def write_if_missing(path: Path, content: str) -> bool:
    """Write file only if it doesn't exist or is empty. Returns True on write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def scaffold_country_config() -> int:
    """config/countries/<code>.json + index.json"""
    base = ROOT / "config" / "countries"
    written = 0
    for c in COUNTRIES:
        body = {
            "iso_alpha2":      c["code"],
            "display_name":    c["name"],
            "region":          c["region"],
            "default_locale":  c["locale"],
            "currency":        c["currency"],
            "vat": {
                "standard_rate_pct": c["vat"],
                "reduced_rates_pct": [],
                "registration_required": True,
                "reverse_charge_b2b":    c["region"] == "europe",
            },
            "invoice": {
                "sequence_format": "INV-{YYYY}-{NNNN}",
                "due_days_default": 30,
                "late_fee_pct":    0.0,
            },
            "legal_doc_path": f"docs/legal/{c['code']}/README.md",
        }
        p = base / f"{c['code']}.json"
        if write_if_missing(p, json.dumps(body, indent=2, ensure_ascii=False) + "\n"):
            written += 1

    index = {
        "generated_by": "scripts/scaffold_global.py",
        "regions": sorted({c["region"] for c in COUNTRIES}),
        "countries": [
            {"code": c["code"], "name": c["name"], "region": c["region"], "currency": c["currency"]}
            for c in sorted(COUNTRIES, key=lambda x: x["code"])
        ],
    }
    idx_path = base / "index.json"
    # index.json is always rewritten (it's a derived file)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return written


def scaffold_legal_docs() -> int:
    """docs/legal/<code>/README.md"""
    base = ROOT / "docs" / "legal"
    written = 0
    for c in COUNTRIES:
        body = f"""# Legal & Compliance — {c['name']} ({c['code']})

> ⚠️ PLACEHOLDER — review with local legal counsel before production use.

## Tax
- Standard VAT / sales tax: **{c['vat']}%**
- Currency: **{c['currency']}**
- Region: `{c['region']}`

## Required compliance artifacts
- [ ] Privacy policy (GDPR / local equivalent)
- [ ] Terms of service
- [ ] Cookie policy
- [ ] Data processing agreement (B2B)
- [ ] Invoicing format compliance (mandatory fields per local law)
- [ ] Data residency requirements
- [ ] E-invoicing mandates (if applicable)

## Invoice mandatory fields (verify with local authority)
- Seller legal name, address, tax ID
- Buyer legal name, address, tax ID (B2B)
- Unique sequential invoice number
- Issue date and supply date
- Description, quantity, unit price, VAT rate, VAT amount, total

## Data residency
Document here where personal data of `{c['code']}` users is stored and
which sub-processors have access.
"""
        p = base / c["code"] / "README.md"
        if write_if_missing(p, body):
            written += 1
    return written


def scaffold_deploy_templates() -> int:
    """deploy/<env>/ and deploy/<env>/<region>/<code>/ stubs."""
    written = 0
    for env in ENVS:
        env_readme = ROOT / "deploy" / env / "README.md"
        if write_if_missing(env_readme, f"""# {env.title()} deployments

This directory contains per-country deployment manifests for the **{env}** tier.

- `backend.env.example` — Railway env template for this tier
- `frontend.env.example` — Vercel env template for this tier
- `<region>/<country>/` — per-country overrides (domain, Stripe keys, DB URL)

Never commit real secrets. Use Railway / Vercel environment variables.
"""):
            written += 1

        tier_backend = ROOT / "deploy" / env / "backend.env.example"
        if write_if_missing(tier_backend, _backend_env_template(env)):
            written += 1
        tier_frontend = ROOT / "deploy" / env / "frontend.env.example"
        if write_if_missing(tier_frontend, _frontend_env_template(env)):
            written += 1

        for c in COUNTRIES:
            country_dir = ROOT / "deploy" / env / c["region"] / c["code"]
            readme = country_dir / "README.md"
            if write_if_missing(readme, f"""# {c['name']} — {env}

| Field | Value |
|-------|-------|
| ISO   | {c['code']} |
| Region | {c['region']} |
| Currency | {c['currency']} |
| VAT | {c['vat']}% |
| Locale | {c['locale']} |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-{env}-{c['code'].lower()})
ENV={env if env == 'production' else 'production'}   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://{c['code'].lower()}.varuflow.app
FRONTEND_URL=https://{c['code'].lower()}.varuflow.app
PORTAL_BASE_URL=https://{c['code'].lower()}.varuflow.app
DATABASE_URL=<tier-specific Postgres for {c['code']}>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-{env}-{c['code'].lower()})
NEXT_PUBLIC_API_URL=https://api-{c['code'].lower()}-{env}.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY={c['code']}
NEXT_PUBLIC_DEFAULT_LOCALE={c['locale']}
NEXT_PUBLIC_DEFAULT_CURRENCY={c['currency']}
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
"""):
                written += 1
    return written


def _backend_env_template(env: str) -> str:
    prod_like = env in ("preproduction", "production")
    debug = "false" if prod_like else "true"
    env_name = "production" if prod_like else "development"
    return f"""# Backend env template — {env} tier
# Copy to Railway Variables. NEVER commit real secrets.

ENV={env_name}
DEBUG={debug}
TRUST_PROXY=true

# Per-tier URLs (override per country in deploy/{env}/<region>/<code>/)
CORS_ORIGINS=https://varuflow.vercel.app
FRONTEND_URL=https://varuflow.vercel.app
PORTAL_BASE_URL=https://varuflow.vercel.app

# Database
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_JWT_SECRET=

# Third-party
RESEND_API_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
OPENAI_API_KEY=
SENTRY_DSN=
FORTNOX_CLIENT_ID=
FORTNOX_CLIENT_SECRET=
FORTNOX_REDIRECT_URI=

# JWT secrets (generate with: python -c "import secrets; print(secrets.token_hex(32))")
PORTAL_JWT_SECRET=
AUTH_JWT_SECRET=

# SMTP
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@varuflow.se
"""


def _frontend_env_template(env: str) -> str:
    return f"""# Frontend env template — {env} tier
# Copy to Vercel Environment Variables. NEVER commit real secrets.

NEXT_PUBLIC_API_URL=https://api-{env}.varuflow.app
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=

# Country / locale defaults (override per country deployment)
NEXT_PUBLIC_DEFAULT_COUNTRY=SE
NEXT_PUBLIC_DEFAULT_LOCALE=sv-SE
NEXT_PUBLIC_DEFAULT_CURRENCY=SEK
"""


def scaffold_env_tiers() -> int:
    """backend/.env.<tier> and frontend/.env.<tier> templates."""
    written = 0
    for env in ENVS:
        be = ROOT / "backend" / f".env.{env}.example"
        fe = ROOT / "frontend" / f".env.{env}.example"
        if write_if_missing(be, _backend_env_template(env)):
            written += 1
        if write_if_missing(fe, _frontend_env_template(env)):
            written += 1
    return written


def scaffold_locales() -> int:
    """Add missing locale files, seeded from en.json."""
    msgs = ROOT / "frontend" / "messages"
    en = msgs / "en.json"
    if not en.exists():
        return 0
    seed = en.read_text(encoding="utf-8")
    # Locales required by AGENTS.md (no, da) + expansion for country coverage.
    needed = [
        "no", "da", "fi", "de", "fr", "es", "it", "nl", "pl", "pt",
        "ar", "he", "tr", "cs", "hu", "ro", "el", "bg", "hr", "sk",
        "sl", "et", "lv", "lt", "is", "uk", "sr", "mk", "sq",
    ]
    written = 0
    for loc in needed:
        p = msgs / f"{loc}.json"
        if write_if_missing(p, seed):
            written += 1
    return written


def main() -> None:
    print("Scaffolding Varuflow global structure …")
    totals = {
        "country_configs": scaffold_country_config(),
        "legal_docs":      scaffold_legal_docs(),
        "deploy_stubs":    scaffold_deploy_templates(),
        "env_tiers":       scaffold_env_tiers(),
        "locales":         scaffold_locales(),
    }
    for k, v in totals.items():
        print(f"  {k:20s} {v:5d} files written")
    total = sum(totals.values())
    print(f"Done. {total} files created / updated.")


if __name__ == "__main__":
    main()
