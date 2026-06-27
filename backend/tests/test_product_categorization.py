"""Tests for Item 19 — AI product categorisation service.

These are pure unit tests; they stub out ``openai.AsyncOpenAI`` so we
exercise the prompt-building, JSON parsing, confidence gating, and
graceful-degradation paths without touching the real OpenAI API.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import product_categorization as pc


class _FakeChoice:
    def __init__(self, content: str):
        self.message = SimpleNamespace(content=content)


class _FakeResp:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeChat:
    def __init__(self, content: str, capture: dict | None = None):
        self._content = content
        self._capture = capture
        self.completions = self
        self.create_calls = 0

    async def create(self, **kwargs):
        self.create_calls += 1
        if self._capture is not None:
            self._capture.update(kwargs)
        return _FakeResp(self._content)


class _FakeClient:
    def __init__(self, content: str, capture: dict | None = None):
        self._chat = _FakeChat(content, capture)

    @property
    def chat(self):
        return self._chat


def _patch_openai(monkeypatch, content: str, capture: dict | None = None):
    """Install a fake openai.AsyncOpenAI that returns ``content``."""
    client = _FakeClient(content, capture)

    def _factory(**kwargs):
        return client

    fake_module = SimpleNamespace(AsyncOpenAI=_factory)
    monkeypatch.setattr(pc, "openai", fake_module, raising=False)
    # ``import openai`` happens inside the function, so also put it on
    # sys.modules for that path.
    import sys
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    return client


@pytest.mark.asyncio
async def test_empty_batch_is_noop():
    result = await pc.categorize_products_batch([])
    assert result.suggestions == {}
    assert result.ai_disabled is False  # empty input, not "disabled"
    assert result.errors == []


@pytest.mark.asyncio
async def test_missing_api_key_returns_disabled(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "")
    result = await pc.categorize_products_batch(
        [pc.ProductToCategorize(sku="S1", name="Hammer")]
    )
    assert result.ai_disabled is True
    assert result.suggestions == {}


@pytest.mark.asyncio
async def test_successful_batch_parses_suggestions(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    payload = json.dumps([
        {"sku": "S1", "category": "Tools", "confidence": 0.9},
        {"sku": "S2", "category": "Electronics", "confidence": 0.6},
    ])
    _patch_openai(monkeypatch, payload)

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku="S1", name="Hammer"),
        pc.ProductToCategorize(sku="S2", name="Gadget"),
    ])

    assert set(result.suggestions) == {"S1", "S2"}
    assert result.suggestions["S1"].category == "Tools"
    assert result.suggestions["S1"].confidence == pytest.approx(0.9)
    # threshold 0.75 → S1 auto-assigns, S2 flagged
    auto = result.auto_assign_skus()
    review = result.needs_review_skus()
    assert auto == {"S1": "Tools"}
    assert review == ["S2"]


@pytest.mark.asyncio
async def test_wrapped_dict_response_is_unwrapped(monkeypatch):
    # Model sometimes returns {"results": [...]} instead of a bare array.
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    payload = json.dumps({
        "results": [{"sku": "S1", "category": "Office", "confidence": 0.8}]
    })
    _patch_openai(monkeypatch, payload)

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku="S1", name="Stapler"),
    ])
    assert "S1" in result.suggestions


@pytest.mark.asyncio
async def test_markdown_fence_is_stripped(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    payload = (
        "```json\n"
        + json.dumps([{"sku": "S1", "category": "Food", "confidence": 0.95}])
        + "\n```"
    )
    _patch_openai(monkeypatch, payload)

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku="S1", name="Apple"),
    ])
    assert result.suggestions["S1"].category == "Food"


@pytest.mark.asyncio
async def test_malformed_json_surfaces_error(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    _patch_openai(monkeypatch, "not json at all {{{")

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku="S1", name="X"),
    ])
    assert result.suggestions == {}
    assert any("invalid_json" in e for e in result.errors)


@pytest.mark.asyncio
async def test_unknown_sku_from_model_is_discarded(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    payload = json.dumps([
        {"sku": "S1", "category": "Tools", "confidence": 0.9},
        {"sku": "HALLUCINATED", "category": "Bogus", "confidence": 0.99},
    ])
    _patch_openai(monkeypatch, payload)

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku="S1", name="Hammer"),
    ])
    assert list(result.suggestions) == ["S1"]
    assert any("unknown_sku_from_model" in e for e in result.errors)


@pytest.mark.asyncio
async def test_upstream_exception_is_soft_failed(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")

    class _Boom:
        def __init__(self, **_): pass
        @property
        def chat(self): raise RuntimeError("network exploded")

    import sys
    fake_module = SimpleNamespace(AsyncOpenAI=_Boom)
    monkeypatch.setattr(pc, "openai", fake_module, raising=False)
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku="S1", name="X"),
    ])
    assert result.suggestions == {}
    assert "ai_unavailable" in result.errors
    # Crucially NOT ai_disabled — that's reserved for "key missing"
    assert result.ai_disabled is False


@pytest.mark.asyncio
async def test_batch_cap_truncates_and_warns(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(pc, "MAX_BATCH_SIZE", 3)
    capture: dict = {}
    _patch_openai(
        monkeypatch,
        json.dumps([{"sku": f"S{i}", "category": "X", "confidence": 0.9}
                   for i in range(3)]),
        capture=capture,
    )

    products = [pc.ProductToCategorize(sku=f"S{i}", name=f"n{i}") for i in range(10)]
    result = await pc.categorize_products_batch(products)

    assert len(result.suggestions) == 3
    assert any("batch_capped" in e for e in result.errors)
    # Prompt must only contain the first 3 SKUs we sent.
    user_msg = capture["messages"][1]["content"]
    assert "S0" in user_msg and "S2" in user_msg
    assert "S9" not in user_msg


@pytest.mark.asyncio
async def test_prompt_seeds_existing_categories(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    capture: dict = {}
    _patch_openai(
        monkeypatch,
        json.dumps([{"sku": "S1", "category": "Tools", "confidence": 0.9}]),
        capture=capture,
    )
    await pc.categorize_products_batch(
        [pc.ProductToCategorize(sku="S1", name="Drill")],
        existing_categories=["Tools", "Office"],
    )
    user_msg = capture["messages"][1]["content"]
    # Pick-list is surfaced to the model so it reuses existing labels.
    assert "Tools" in user_msg and "Office" in user_msg


@pytest.mark.asyncio
async def test_confidence_is_clamped_to_unit_interval(monkeypatch):
    monkeypatch.setattr(pc.settings, "OPENAI_API_KEY", "sk-test")
    payload = json.dumps([
        {"sku": "S1", "category": "X", "confidence": 1.7},
        {"sku": "S2", "category": "Y", "confidence": -0.5},
        {"sku": "S3", "category": "Z", "confidence": "not a number"},
    ])
    _patch_openai(monkeypatch, payload)

    result = await pc.categorize_products_batch([
        pc.ProductToCategorize(sku=s, name=s) for s in ("S1", "S2", "S3")
    ])
    assert result.suggestions["S1"].confidence == 1.0
    assert result.suggestions["S2"].confidence == 0.0
    assert result.suggestions["S3"].confidence == 0.0
