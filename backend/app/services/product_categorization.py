"""AI auto-categorisation for bulk CSV imports (Item 19).

When a merchant uploads a product CSV, the import router fills in
``category`` directly from the CSV row. Rows with no category value
are collected and sent to this module in a *single* GPT-4o call that
returns a JSON array of ``{sku, category, confidence}`` objects.

Design rules (mirrors the AI chat endpoint at
``app/routers/integrations.py::ai_chat``):

* **Hard timeout + no retries.** A hung upstream would tie up a
  worker; 25 s is generous for a ~200-row batch.
* **Never leak upstream error text.** The caller logs the original
  exception but surfaces only a generic "AI unavailable" reason so
  OpenAI account/model details cannot reach the UI.
* **Soft-fail.** If GPT-4o is not configured (``OPENAI_API_KEY``
  empty) or the call errors, we return an empty categorisation
  result — the import still succeeds, every uncategorised row lands
  in the "needs review" bucket, and the merchant can re-run once
  AI is configured.
* **Batch, never per-row.** One call for the whole import keeps the
  API cost bounded (approx. $0.01 per 200-row batch at current
  gpt-4o pricing) and avoids the per-row latency of N round-trips.

Confidence threshold: the caller decides whether to auto-assign or
flag for review based on ``CONFIDENCE_THRESHOLD`` (0.75 by default
— below that the model is guessing).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.config import settings

log = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────────────────
# Per spec: "If confidence > threshold, assign category automatically."
# 0.75 strikes a balance where the model's typed-brand-in-name matches
# (e.g. "Bosch 10mm borr" → "Tools") auto-apply, while ambiguous names
# like "Premium pack" stay in the review bucket.
CONFIDENCE_THRESHOLD: float = 0.75

# Cap per-call batch size so a pathological 50 000-row CSV doesn't hit
# GPT-4o's context ceiling. If we exceed the cap we chunk in the caller.
MAX_BATCH_SIZE: int = 200

# Category label allowed characters. The model is prompted with the
# existing category set + a short pick-list so it doesn't invent
# 50 different spellings of "Electronics".
MAX_CATEGORY_LEN: int = 100


@dataclass
class ProductToCategorize:
    """Minimal payload for one CSV row the model has to categorise."""

    sku: str
    name: str
    description: str | None = None


@dataclass
class CategorizationSuggestion:
    """One row back from the model, normalised for storage."""

    sku: str
    category: str
    confidence: float  # 0.0–1.0


@dataclass
class CategorizationBatchResult:
    """Summary returned to the import router for the audit log + UI."""

    suggestions: dict[str, CategorizationSuggestion] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    # True when AI was not configured and we no-op'd. Lets the router
    # distinguish "did nothing because disabled" from "did nothing because
    # the batch was empty" for the audit log.
    ai_disabled: bool = False

    def auto_assign_skus(
        self, *, threshold: float = CONFIDENCE_THRESHOLD,
    ) -> dict[str, str]:
        """SKUs whose confidence cleared the bar. The router writes these
        directly onto the product row."""
        return {
            sku: s.category
            for sku, s in self.suggestions.items()
            if s.confidence >= threshold
        }

    def needs_review_skus(
        self, *, threshold: float = CONFIDENCE_THRESHOLD,
    ) -> list[str]:
        """SKUs the model returned but with low confidence — surfaced
        in the import summary so the merchant can triage manually."""
        return [
            sku for sku, s in self.suggestions.items()
            if s.confidence < threshold
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def _build_prompt(
    products: list[ProductToCategorize],
    *,
    existing_categories: list[str],
) -> str:
    """Render the JSON-only prompt the model is asked to complete.

    Inlining the category pick-list matters: without it the model
    invents plausible-but-inconsistent category labels ("Electronics"
    vs "Electronic" vs "Electronic products"), fragmenting the org's
    catalogue. When the merchant has no categories yet, the model is
    told to pick broad, stable labels.
    """
    prompt_lines = [
        "You are a product taxonomist for a Swedish wholesale catalogue.",
        "Classify each product into ONE category.",
        "",
        "Rules:",
        "- Reply with a single JSON array, one object per input, keys: sku, category, confidence.",
        "- confidence is a float 0.0-1.0 reflecting how certain you are.",
        "- category must be a short noun phrase, max 100 chars, in English.",
    ]
    if existing_categories:
        picklist = ", ".join(sorted(set(existing_categories))[:50])
        prompt_lines.append(
            f"- Prefer reusing an existing category from this list when applicable: {picklist}."
        )
    else:
        prompt_lines.append(
            "- Pick broad, stable categories (e.g. Tools, Electronics, Food, Office)."
        )
    prompt_lines.append("")
    prompt_lines.append("Products:")
    for p in products:
        # Truncate long descriptions; the SKU+name is the main signal.
        desc = (p.description or "")[:200]
        prompt_lines.append(
            json.dumps(
                {"sku": p.sku, "name": p.name, "description": desc},
                ensure_ascii=False,
            )
        )
    return "\n".join(prompt_lines)


def _parse_model_reply(raw: str) -> tuple[list[CategorizationSuggestion], list[str]]:
    """Turn the raw model string into structured suggestions.

    The model sometimes wraps JSON in markdown fences; we strip them
    before parsing. Malformed entries are dropped with an error line
    so one bad row doesn't abort the whole batch.
    """
    text = (raw or "").strip()
    # Strip ```json ... ``` fences the model sometimes adds even when
    # we ask for raw JSON.
    if text.startswith("```"):
        text = text.strip("`")
        # Remove a leading "json\n" label if present.
        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [], [f"model_returned_invalid_json: {e.msg}"]

    if isinstance(data, dict):
        # Some responses wrap the array in {"results": [...]}
        for k in ("results", "products", "categories"):
            if k in data and isinstance(data[k], list):
                data = data[k]
                break
    if not isinstance(data, list):
        return [], ["model_response_not_a_list"]

    out: list[CategorizationSuggestion] = []
    errs: list[str] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            errs.append(f"row {i}: not an object")
            continue
        sku = (row.get("sku") or "").strip()
        cat = (row.get("category") or "").strip()[:MAX_CATEGORY_LEN]
        try:
            conf = float(row.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        if not sku or not cat:
            errs.append(f"row {i}: missing sku or category")
            continue
        out.append(CategorizationSuggestion(sku=sku, category=cat, confidence=conf))
    return out, errs


async def categorize_products_batch(
    products: list[ProductToCategorize],
    *,
    existing_categories: list[str] | None = None,
) -> CategorizationBatchResult:
    """Ask GPT-4o to categorise ``products`` in a single batch call.

    Returns an empty result (with ``ai_disabled=True`` when OpenAI is
    not configured) rather than raising — the CSV import must never
    fail just because AI is unavailable. Categorisation is an
    enhancement, not a gate on the underlying insert.
    """
    result = CategorizationBatchResult()
    if not products:
        return result
    if not settings.OPENAI_API_KEY:
        result.ai_disabled = True
        return result

    if len(products) > MAX_BATCH_SIZE:
        # Guard: keep a bounded context window. Chunks beyond the cap
        # are dropped from this call and reported in errors. The caller
        # is expected to chunk if it needs to categorise larger imports;
        # stopping here is safer than silently truncating.
        result.errors.append(
            f"batch_capped: received {len(products)} rows, only the first "
            f"{MAX_BATCH_SIZE} are sent to the model in one call."
        )
        products = products[:MAX_BATCH_SIZE]

    prompt = _build_prompt(products, existing_categories=list(existing_categories or []))

    try:
        import openai

        client_ai = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=25.0,
            max_retries=0,
        )
        resp = await client_ai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a product-taxonomy JSON API. Reply with a single "
                        "valid JSON array and nothing else."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            # Deterministic-ish so repeat imports produce stable categories.
            temperature=0.2,
            # Enough room for ~200 objects at ~30 tokens each.
            max_tokens=4096,
            # response_format enforces valid JSON — avoids the markdown
            # fence dance when the model is in a chatty mood.
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001 — soft-fail per module docstring
        log.error("categorize_products_batch openai call failed: %s", str(e)[:300])
        result.errors.append("ai_unavailable")
        return result

    suggestions, parse_errs = _parse_model_reply(raw)
    result.errors.extend(parse_errs)

    submitted_skus = {p.sku for p in products}
    for s in suggestions:
        if s.sku not in submitted_skus:
            # Ignore hallucinated SKUs — defence in depth; we never
            # want the model to invent a SKU that then overwrites an
            # unrelated product's category.
            result.errors.append(f"unknown_sku_from_model: {s.sku}")
            continue
        # First response wins if the model returns duplicates.
        result.suggestions.setdefault(s.sku, s)

    return result
