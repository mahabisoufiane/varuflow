#!/usr/bin/env python3
"""
enrich_country_data.py — upgrade config/countries/<code>.json with
reduced VAT rates, e-invoicing mandates, and tax ID formats.

All values are best-effort from public sources (EU VIES, OECD, national
tax authorities) as of 2025-2026. They must still be verified with local
counsel before being relied on for billing.

Idempotent — re-running overwrites only the enrichment fields, preserving
any manual edits to other keys.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR  = ROOT / "config" / "countries"

# iso → { reduced_rates, tax_id_format, einvoicing_mandate, tax_authority_url }
ENRICH: dict[str, dict] = {
    # EU — standard + reduced rates per https://taxation-ec.europa.eu
    "AT": {"reduced": [10.0, 13.0], "tid": "ATU\\d{8}", "einv": "B2G mandatory"},
    "BE": {"reduced": [6.0, 12.0],  "tid": "BE0\\d{9}", "einv": "B2G mandatory; B2B 2026"},
    "BG": {"reduced": [9.0],        "tid": "BG\\d{9,10}", "einv": "planned"},
    "HR": {"reduced": [5.0, 13.0],  "tid": "HR\\d{11}", "einv": "B2G mandatory"},
    "CY": {"reduced": [5.0, 9.0],   "tid": "CY\\d{8}[A-Z]", "einv": "B2G mandatory"},
    "CZ": {"reduced": [12.0],       "tid": "CZ\\d{8,10}", "einv": "B2G mandatory"},
    "DK": {"reduced": [],           "tid": "DK\\d{8}", "einv": "B2G mandatory"},
    "EE": {"reduced": [9.0, 5.0],   "tid": "EE\\d{9}", "einv": "B2G mandatory"},
    "FI": {"reduced": [14.0, 10.0], "tid": "FI\\d{8}", "einv": "B2G mandatory"},
    "FR": {"reduced": [10.0, 5.5, 2.1], "tid": "FR[A-Z0-9]{2}\\d{9}", "einv": "B2B mandatory from 2026"},
    "DE": {"reduced": [7.0],        "tid": "DE\\d{9}",  "einv": "B2B mandatory from 2025"},
    "GR": {"reduced": [13.0, 6.0],  "tid": "EL\\d{9}",  "einv": "myDATA mandatory"},
    "HU": {"reduced": [18.0, 5.0],  "tid": "HU\\d{8}",  "einv": "RTIR mandatory"},
    "IE": {"reduced": [13.5, 9.0, 4.8], "tid": "IE\\d{7}[A-Z]{1,2}", "einv": "B2G mandatory"},
    "IT": {"reduced": [10.0, 5.0, 4.0], "tid": "IT\\d{11}", "einv": "B2B+B2C mandatory (SdI)"},
    "LV": {"reduced": [12.0, 5.0],  "tid": "LV\\d{11}",  "einv": "B2G mandatory"},
    "LT": {"reduced": [9.0, 5.0],   "tid": "LT\\d{9}|LT\\d{12}", "einv": "B2G mandatory"},
    "LU": {"reduced": [14.0, 8.0, 3.0], "tid": "LU\\d{8}", "einv": "B2G mandatory"},
    "MT": {"reduced": [7.0, 5.0],   "tid": "MT\\d{8}",  "einv": "B2G mandatory"},
    "NL": {"reduced": [9.0],        "tid": "NL\\d{9}B\\d{2}", "einv": "B2G mandatory"},
    "PL": {"reduced": [8.0, 5.0],   "tid": "PL\\d{10}",  "einv": "KSeF mandatory 2026"},
    "PT": {"reduced": [13.0, 6.0],  "tid": "PT\\d{9}",   "einv": "B2G mandatory"},
    "RO": {"reduced": [9.0, 5.0],   "tid": "RO\\d{2,10}", "einv": "RO e-Factura mandatory"},
    "SK": {"reduced": [10.0, 5.0],  "tid": "SK\\d{10}",  "einv": "B2G mandatory"},
    "SI": {"reduced": [9.5, 5.0],   "tid": "SI\\d{8}",   "einv": "B2G mandatory"},
    "ES": {"reduced": [10.0, 5.0, 4.0], "tid": "ES[A-Z0-9]\\d{7}[A-Z0-9]", "einv": "B2B mandatory 2026 (Verifactu)"},
    "SE": {"reduced": [12.0, 6.0],  "tid": "SE\\d{10}01", "einv": "B2G mandatory (Peppol)"},
    # Non-EU Europe
    "GB": {"reduced": [5.0, 0.0],   "tid": "GB\\d{9}",   "einv": "voluntary"},
    "NO": {"reduced": [15.0, 12.0], "tid": "NO\\d{9}MVA", "einv": "voluntary"},
    "IS": {"reduced": [11.0],       "tid": "IS\\d{5,6}", "einv": "B2G mandatory"},
    "CH": {"reduced": [3.8, 2.6],   "tid": "CHE-\\d{3}\\.\\d{3}\\.\\d{3} (MWST|TVA|IVA)", "einv": "voluntary"},
    "AL": {"reduced": [6.0],        "tid": "AL[JKL]\\d{8}[A-Z]", "einv": "mandatory (fiskalizimi)"},
    "BA": {"reduced": [],           "tid": "\\d{12}",    "einv": "planned"},
    "ME": {"reduced": [7.0],        "tid": "ME\\d{8}",   "einv": "planned"},
    "MK": {"reduced": [5.0, 10.0],  "tid": "MK\\d{13}",  "einv": "planned"},
    "RS": {"reduced": [10.0],       "tid": "RS\\d{9}",   "einv": "SEF mandatory"},
    "UA": {"reduced": [7.0, 14.0],  "tid": "UA\\d{10,12}", "einv": "planned"},
    "MD": {"reduced": [8.0, 12.0],  "tid": "MD\\d{13}",  "einv": "planned"},
    # Middle East
    "AE": {"reduced": [],           "tid": "\\d{15}",    "einv": "FTA e-invoicing 2026"},
    "SA": {"reduced": [],           "tid": "\\d{15}",    "einv": "ZATCA mandatory (Fatoorah)"},
    "QA": {"reduced": [],           "tid": "\\d{11}",    "einv": "planned"},
    "KW": {"reduced": [],           "tid": "\\d{12}",    "einv": "planned"},
    "BH": {"reduced": [],           "tid": "\\d{15}",    "einv": "planned"},
    "OM": {"reduced": [],           "tid": "OM\\d{10}",  "einv": "planned"},
    "IL": {"reduced": [],           "tid": "\\d{9}",     "einv": "mandatory from 2024"},
    "TR": {"reduced": [10.0, 1.0],  "tid": "\\d{10,11}", "einv": "e-Fatura mandatory"},
    "JO": {"reduced": [4.0, 10.0],  "tid": "\\d{9}",     "einv": "mandatory"},
    "LB": {"reduced": [],           "tid": "\\d{9}",     "einv": "voluntary"},
    "EG": {"reduced": [5.0, 10.0],  "tid": "\\d{9}",     "einv": "ETA e-invoicing mandatory"},
    "IQ": {"reduced": [],           "tid": "\\d{9}",     "einv": "planned"},
    "YE": {"reduced": [],           "tid": "\\d{9}",     "einv": "voluntary"},
    # Americas
    "US": {"reduced": [],           "tid": "\\d{2}-\\d{7}", "einv": "voluntary (per-state sales tax)"},
    "CA": {"reduced": [],           "tid": "\\d{9}RT\\d{4}", "einv": "B2G mandatory"},
    "MX": {"reduced": [8.0, 0.0],   "tid": "[A-Z&Ñ]{3,4}\\d{6}[A-Z0-9]{3}", "einv": "CFDI mandatory"},
    "BR": {"reduced": [12.0, 7.0],  "tid": "\\d{2}\\.\\d{3}\\.\\d{3}/\\d{4}-\\d{2}", "einv": "NF-e mandatory"},
    "AR": {"reduced": [10.5, 27.0], "tid": "\\d{2}-\\d{8}-\\d{1}", "einv": "AFIP mandatory"},
    "CL": {"reduced": [],           "tid": "\\d{7,8}-[0-9K]", "einv": "SII mandatory"},
    "CO": {"reduced": [5.0],        "tid": "\\d{9}-\\d", "einv": "DIAN mandatory"},
    "PE": {"reduced": [],           "tid": "\\d{11}",    "einv": "SUNAT mandatory"},
    "UY": {"reduced": [10.0],       "tid": "\\d{12}",    "einv": "e-CFE mandatory"},
    "PY": {"reduced": [5.0],        "tid": "\\d{6,8}-\\d", "einv": "mandatory"},
    "BO": {"reduced": [],           "tid": "\\d{7,10}",  "einv": "mandatory"},
    "EC": {"reduced": [],           "tid": "\\d{13}",    "einv": "SRI mandatory"},
    "VE": {"reduced": [8.0],        "tid": "[JVEG]-\\d{9}", "einv": "planned"},
    "GT": {"reduced": [],           "tid": "\\d{7,8}-\\d", "einv": "FEL mandatory"},
    "CR": {"reduced": [4.0, 2.0, 1.0], "tid": "\\d{10,12}", "einv": "mandatory"},
    "PA": {"reduced": [10.0, 15.0], "tid": "\\d+",       "einv": "voluntary"},
    "DO": {"reduced": [16.0],       "tid": "\\d{9}|\\d{11}", "einv": "e-CF mandatory"},
    "JM": {"reduced": [10.0],       "tid": "\\d{9}",     "einv": "planned"},
}


def enrich_file(path: Path) -> bool:
    code = path.stem
    extra = ENRICH.get(code)
    if not extra:
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    vat = data.setdefault("vat", {})
    vat["reduced_rates_pct"] = extra["reduced"]
    vat["tax_id_regex"]      = extra["tid"]
    vat["einvoicing_status"] = extra["einv"]
    # Drop stale field from first pass
    vat.pop("reverse_charge_b2b_legacy", None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for f in sorted(DIR.glob("*.json")):
        if f.name == "index.json":
            continue
        if enrich_file(f):
            changed += 1
    print(f"Enriched {changed} country config files.")


if __name__ == "__main__":
    main()
