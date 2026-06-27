"""Item 68 — Customer referral program."""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import referral as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


MIGRATION_SRC = _read("migrations/versions/f7a9b1c3d6e7_v76_referrals.py")
MODEL_SRC = _read("app/features/loyalty/referral.py")
SERVICE_SRC = _read("app/services/referral.py")
ROUTER_SRC = _read("app/features/loyalty/referrals.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service: code generation ─────────────────────────────────────────


def test_generate_code_avoids_confusable_glyphs():
    for _ in range(50):
        c = svc.generate_code(set())
        assert len(c) == svc.CODE_LENGTH
        for ch in c:
            assert ch in svc.CODE_ALPHABET
            assert ch not in {"O", "0", "I", "1", "L"}


def test_generate_code_skips_existing():
    existing = {svc.generate_code(set()) for _ in range(5)}
    new = svc.generate_code(existing)
    assert new not in existing


def test_normalise_code_upper_and_strip():
    c = svc.generate_code(set())
    assert svc.normalise_code(f"  {c.lower()}  ") == c


def test_normalise_code_strips_dashes_and_spaces():
    c = svc.generate_code(set())
    assert svc.normalise_code(f"{c[:4]}-{c[4:]}") == c


def test_normalise_code_rejects_wrong_length_and_charset():
    for bad in ("", "ABC", "O" * svc.CODE_LENGTH, "1" * svc.CODE_LENGTH):
        with pytest.raises(ValueError):
            svc.normalise_code(bad)


# ── Pure service: claim validation ────────────────────────────────────────


def test_validate_claim_rejects_self_referral():
    with pytest.raises(ValueError):
        svc.validate_claim(
            referrer_id="a", referee_id="a", existing_referees=[]
        )


def test_validate_claim_rejects_duplicate_referee():
    with pytest.raises(ValueError):
        svc.validate_claim(
            referrer_id="a", referee_id="b", existing_referees=["b"]
        )


def test_validate_claim_accepts_fresh_pair():
    svc.validate_claim(
        referrer_id="a", referee_id="b", existing_referees=["c", "d"]
    )


# ── Pure service: transitions ─────────────────────────────────────────────


def test_transition_pending_to_qualified_or_rejected():
    svc.assert_transition("PENDING", "QUALIFIED")
    svc.assert_transition("PENDING", "REJECTED")


def test_transition_qualified_to_rewarded_or_rejected():
    svc.assert_transition("QUALIFIED", "REWARDED")
    svc.assert_transition("QUALIFIED", "REJECTED")


def test_transition_rejects_terminal_states():
    for src in ("REWARDED", "REJECTED"):
        for tgt in ("QUALIFIED", "REWARDED", "PENDING"):
            with pytest.raises(ValueError):
                svc.assert_transition(src, tgt)


def test_transition_rejects_skip_pending_to_rewarded():
    with pytest.raises(ValueError):
        svc.assert_transition("PENDING", "REWARDED")


def test_transition_rejects_unknown_status():
    with pytest.raises(ValueError):
        svc.assert_transition("FOO", "QUALIFIED")


# ── Pure service: reward ──────────────────────────────────────────────────


def test_validate_reward_amount_bounds():
    svc.validate_reward_amount(svc.MIN_REWARD)
    svc.validate_reward_amount(svc.MAX_REWARD)
    for bad in (Decimal("0"), Decimal("-1"), True, svc.MAX_REWARD + Decimal("1")):
        with pytest.raises(ValueError):
            svc.validate_reward_amount(bad)  # type: ignore[arg-type]


def test_validate_reward_amount_rounds_to_cent():
    assert svc.validate_reward_amount("12.345") == Decimal("12.35")


def test_compute_reward_percent():
    assert svc.compute_reward(Decimal("1000"), percent=Decimal("10")) == Decimal("100.00")


def test_compute_reward_flat():
    assert svc.compute_reward(Decimal("1000"), flat=Decimal("50")) == Decimal("50.00")


def test_compute_reward_cap_is_applied():
    assert svc.compute_reward(
        Decimal("10000"), percent=Decimal("10"), cap=Decimal("500")
    ) == Decimal("500.00")


def test_compute_reward_rejects_both_or_neither():
    with pytest.raises(ValueError):
        svc.compute_reward(Decimal("100"))
    with pytest.raises(ValueError):
        svc.compute_reward(
            Decimal("100"), percent=Decimal("10"), flat=Decimal("5")
        )


def test_compute_reward_percent_bounds():
    for bad in (Decimal("0"), Decimal("-1"), Decimal("100.01")):
        with pytest.raises(ValueError):
            svc.compute_reward(Decimal("100"), percent=bad)


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v76_chains_from_v75():
    assert 'revision = "f7a9b1c3d6e7"' in MIGRATION_SRC
    assert 'down_revision = "e6f8a0b2c5d6"' in MIGRATION_SRC


def test_migration_creates_both_tables_with_uniques():
    assert 'create_table(\n        "referral_codes"' in MIGRATION_SRC
    assert 'create_table(\n        "referrals"' in MIGRATION_SRC
    assert "uq_referral_codes_customer" in MIGRATION_SRC
    assert "uq_referral_codes_org_code" in MIGRATION_SRC
    assert "uq_referrals_org_referee" in MIGRATION_SRC


def test_model_has_all_statuses():
    for s in ("PENDING", "QUALIFIED", "REWARDED", "REJECTED"):
        assert f'{s} = "{s}"' in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_referrals():
    assert 'prefix="/api/referrals"' in ROUTER_SRC
    # referrals is registered via loyalty_router (vertical-slice architecture)
    feat_src = _read("app/features/loyalty/router.py")
    assert "referrals" in feat_src
    assert "loyalty_router" in MAIN_SRC


def test_router_has_seven_endpoints():
    for sig in (
        '@router.post("/codes", response_model=CodeOut',
        '@router.get("/codes/{customer_id}"',
        '@router.post("/claims"',
        '@router.post("/{referral_id}/qualify"',
        '@router.post("/{referral_id}/reward"',
        '@router.post("/{referral_id}/reject"',
        '@router.get("", response_model=list[ReferralOut])',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_is_idempotent_on_code_mint():
    # If a code already exists the router returns it instead of minting.
    assert "Idempotent" in ROUTER_SRC or "existing is not None" in ROUTER_SRC


def test_router_scopes_customer_to_caller_org():
    assert "Customer.org_id == org_id" in ROUTER_SRC


def test_router_scopes_referral_queries_to_org():
    assert "Referral.org_id == member.org_id" in ROUTER_SRC
    assert "ReferralCode.org_id == member.org_id" in ROUTER_SRC


def test_router_logs_every_mutation():
    for action in (
        '"referral.code_minted"',
        '"referral.claim_opened"',
        '"referral.qualified"',
        '"referral.rewarded"',
        '"referral.rejected"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
