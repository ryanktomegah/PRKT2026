"""
test_c2_model.py — Spec-mandated C2 test suite (8 required tests)

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

Tests validate the Unified LightGBM PD Model against spec requirements:
  - PD score range [0, 1]
  - Fee floor enforcement (300 bps canonical, Architecture Spec v1.2 Appendix A)
  - LGD range [0, 1]
  - SHAP key alignment with feature vector
  - AUC > 0.80 on separable data
  - Log-loss improvement over three-model baseline
  - fee_bps Decimal type contract
  - Model save/load round-trip determinism
"""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal

import numpy as np
import pytest

from lip.c2_pd_model.baseline import financial_ratio_pd
from lip.c2_pd_model.features import FeatureMasker
from lip.c2_pd_model.fee import compute_fee_bps_from_el
from lip.c2_pd_model.lgd import LGD_BY_JURISDICTION, estimate_lgd
from lip.c2_pd_model.model import PDModel
from lip.c2_pd_model.training import PDTrainingPipeline, TrainingConfig

# ---------------------------------------------------------------------------
# Private data helpers
# ---------------------------------------------------------------------------


def _minimal_payment(i: int = 0, amount_usd: float = 250_000.0) -> dict:
    """Minimal payment dict compatible with UnifiedFeatureEngineer."""
    return {
        "amount_usd": amount_usd,
        "currency_pair": "USD/EUR",
        "sending_bic": "DEUTDEDB",
        "receiving_bic": "BNPAFRPP",
        "timestamp": 1_700_000_000.0 + i,
        "days_since_last_payment": 5.0,
        "corridor_failure_rate": 0.03,
        "corridor_volume_7d": 5_000_000.0,
        "n_payments_30d": 15,
        "n_failures_30d": 1,
        "amount_zscore": 0.0,
        "amount_percentile": 0.5,
        "payment_velocity_24h": 3.0,
        "large_amount_threshold": 1_000_000.0,
        "currency_risk_score": 0.3,
    }


def _minimal_tier3_borrower() -> dict:
    """Minimal Tier-3 (thin-file) borrower dict."""
    return {
        "has_financial_statements": False,
        "has_transaction_history": False,
        "has_credit_bureau": False,
        "months_history": 2,
        "transaction_count": 3,
        "counterparty_age_days": 60.0,
        "jurisdiction_risk_score": 0.4,
        "entity_age_days": 90.0,
    }


def _make_separable_records(n: int = 200, seed: int = 42) -> list:
    """Records where amount_usd perfectly separates labels.

    label=1 → amount_usd = $5 M (maps to features[0] + features[9])
    label=0 → amount_usd = $50 K

    This guarantees clear decision boundaries for even a minimal LightGBM model.
    """
    records = []
    for i in range(n):
        label = i % 2  # balanced alternating labels
        amount = 5_000_000.0 if label == 1 else 50_000.0
        borrower = _minimal_tier3_borrower()
        borrower["jurisdiction_risk_score"] = 0.8 if label == 1 else 0.2
        records.append({
            "label": label,
            "payment": {
                **_minimal_payment(i, amount),
                "amount_zscore": 2.0 if label == 1 else -2.0,
                "amount_percentile": 0.95 if label == 1 else 0.05,
            },
            "borrower": borrower,
        })
    return records


def _make_tier1_records(
    n: int = 400,
    default_rate: float = 0.20,
    seed: int = 0,
) -> list:
    """Synthetic Tier-1 records with a controllable default rate.

    Financial ratios are calibrated to the label so both LightGBM and
    financial_ratio_pd have a meaningful signal to exploit.  Uses 20%
    default rate (vs the real-world ~3%) so the test set has enough
    positive labels for a reliable log-loss comparison.
    """
    rng = np.random.default_rng(seed)
    records = []
    for i in range(n):
        label = int(rng.random() < default_rate)
        cr = float(np.clip(rng.normal(2.0 if label == 0 else 1.0, 0.4), 0.1, 10.0))
        dte = float(np.clip(rng.lognormal(0.5 if label == 0 else 1.5, 0.5), 0.0, 20.0))
        ic = float(np.clip(rng.normal(8.0 if label == 0 else 1.5, 2.0), -5.0, 50.0))
        records.append({
            "label": label,
            "payment": _minimal_payment(i),
            "borrower": {
                "has_financial_statements": True,
                "has_transaction_history": True,
                "has_credit_bureau": True,
                "months_history": 36,
                "transaction_count": 200,
                "counterparty_age_days": 730.0,
                "financial_statements": {
                    "current_ratio": cr,
                    "debt_to_equity": dte,
                    "interest_coverage": ic,
                    "roe": float(rng.normal(0.15 if label == 0 else -0.05, 0.08)),
                    "roa": float(rng.normal(0.08 if label == 0 else -0.02, 0.04)),
                    "ebitda_margin": float(rng.normal(0.20 if label == 0 else 0.02, 0.07)),
                    "revenue_growth": float(rng.normal(0.08 if label == 0 else -0.05, 0.10)),
                    "cash_ratio": float(np.clip(rng.normal(0.4 if label == 0 else 0.1, 0.15), 0.0, 3.0)),
                    "asset_turnover": float(np.clip(rng.normal(1.2 if label == 0 else 0.6, 0.3), 0.1, 5.0)),
                    "net_margin": float(rng.normal(0.10 if label == 0 else -0.03, 0.05)),
                },
                "altman_z_score": float(np.clip(rng.normal(3.5 if label == 0 else 1.2, 0.8), -2.0, 8.0)),
                "merton_distance_to_default": float(np.clip(rng.normal(3.0 if label == 0 else 0.8, 0.6), -2.0, 8.0)),
                "credit_bureau": {
                    "score": float(np.clip(rng.normal(720 if label == 0 else 560, 50), 300, 850)),
                    "age_months": float(rng.integers(24, 120)),
                    "payment_history_score": float(np.clip(rng.normal(0.85 if label == 0 else 0.45, 0.1), 0.0, 1.0)),
                    "avg_days_to_pay": float(np.clip(rng.normal(28 if label == 0 else 55, 10), 1.0, 120.0)),
                    "delinquency_rate": float(rng.beta(1 if label == 0 else 3, 15)),
                    "default_history_count": 0.0,
                    "bankruptcy_history": False,
                },
                "industry_risk_score": float(rng.beta(2, 5 if label == 0 else 2)),
            },
        })
    return records


def _fit_small_model(records: list, n_models: int = 2) -> tuple[PDModel, np.ndarray, np.ndarray]:
    """Return (fitted PDModel, X, y) from a list of records."""
    config = TrainingConfig(n_trials=1, n_models=n_models)
    pipeline = PDTrainingPipeline(config)
    X, y = pipeline.stage1_data_prep(records)
    model = PDModel(n_models=n_models, random_seeds=list(range(n_models)))
    model.fit(X, y)
    return model, X, y


# ---------------------------------------------------------------------------
# Required tests (8)
# ---------------------------------------------------------------------------


def test_pd_score_in_range() -> None:
    """pd_score from a fitted PDModel must be in [0.0, 1.0]."""
    records = _make_separable_records(n=100, seed=42)
    model, X, _ = _fit_small_model(records)

    # Batch prediction
    pds = model.predict_proba(X)
    assert pds.shape == (len(records),), "Shape mismatch"
    assert float(pds.min()) >= 0.0, f"min pd_score {pds.min()} < 0"
    assert float(pds.max()) <= 1.0, f"max pd_score {pds.max()} > 1"

    # Single-observation path
    single = float(model.predict_proba(X[0]))
    assert 0.0 <= single <= 1.0, f"Single pd_score {single} outside [0, 1]"


def test_fee_floor_enforced() -> None:
    """fee_bps must never be below the 300 bps canonical floor.

    Architecture Spec v1.2 Appendix A — QUANT sign-off required to change.
    """
    floor = Decimal("300")

    # EL well below floor: 0.001 × 0.10 × 10000 = 1 bps
    fee = compute_fee_bps_from_el(
        pd=Decimal("0.001"),
        lgd=Decimal("0.10"),
        ead=Decimal("1_000_000"),
    )
    assert fee >= floor, f"fee_bps {fee} < 300 bps floor (EL=1 bps case)"

    # EL = 0: PD=0 or LGD=0
    fee_zero_pd = compute_fee_bps_from_el(
        pd=Decimal("0"),
        lgd=Decimal("0.45"),
        ead=Decimal("500_000"),
    )
    assert fee_zero_pd >= floor, f"fee_bps {fee_zero_pd} < floor at PD=0"

    # EL above floor: should pass through unchanged
    fee_above = compute_fee_bps_from_el(
        pd=Decimal("0.10"),
        lgd=Decimal("0.40"),
        ead=Decimal("1_000_000"),
    )
    assert fee_above >= floor, f"fee_bps {fee_above} < floor (EL=400 bps)"
    assert fee_above == Decimal("400.0"), f"Expected 400.0 bps, got {fee_above}"


def test_lgd_in_range() -> None:
    """estimate_lgd must return a value in [0.0, 1.0] for all jurisdictions."""
    all_jurisdictions = list(LGD_BY_JURISDICTION.keys()) + ["UNKNOWN_XYZ", "XX", ""]

    for jur in all_jurisdictions:
        lgd = estimate_lgd(jur)
        assert Decimal("0.0") <= lgd <= Decimal("1.0"), (
            f"LGD {lgd} out of [0, 1] for jurisdiction '{jur}'"
        )

    # Collateral reductions must also stay in range
    lgd_with_collateral = estimate_lgd("US", collateral_type="REAL_ESTATE",
                                       collateral_value_pct=Decimal("0.50"))
    assert Decimal("0.0") <= lgd_with_collateral <= Decimal("1.0"), (
        f"LGD {lgd_with_collateral} out of [0, 1] with collateral"
    )


def test_shap_keys_match_features() -> None:
    """SHAP value dict keys must exactly match the 75 canonical feature names."""
    feature_names = FeatureMasker.get_full_feature_names()
    assert len(feature_names) == 75, "Expected 75 feature names"

    records = _make_separable_records(n=80, seed=1)
    model, X, _ = _fit_small_model(records)

    # Single-observation path
    _, shap_list = model.predict_with_shap(X[0], feature_names)
    assert len(shap_list) == 1, "Single obs should return list of length 1"
    shap_dict = shap_list[0]
    assert isinstance(shap_dict, dict), "SHAP output must be a dict"
    assert set(shap_dict.keys()) == set(feature_names), (
        f"SHAP keys ({len(shap_dict)}) != feature names ({len(feature_names)})"
    )

    # Batch path
    _, shap_batch = model.predict_with_shap(X[:5], feature_names)
    assert len(shap_batch) == 5
    for sv in shap_batch:
        assert set(sv.keys()) == set(feature_names)


def test_auc_on_separable_data() -> None:
    """AUC must exceed 0.80 when trained on perfectly separable data.

    amount_usd (5 M vs 50 K) maps directly to features[0] and features[9]
    (amount_log), providing a clean decision boundary for LightGBM.
    """
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415

    records = _make_separable_records(n=200, seed=42)
    model, X, y = _fit_small_model(records)

    pds = model.predict_proba(X)
    auc = float(roc_auc_score(y, pds))
    assert auc > 0.80, (
        f"AUC {auc:.4f} <= 0.80 on separable data — model failed to learn "
        "from amount_usd signal"
    )


def test_log_loss_vs_baseline() -> None:
    """Unified LightGBM log-loss < three-model (financial_ratio_pd) baseline.

    Requires real LightGBM or sklearn — the LightGBMSurrogate is too simple to
    outperform the hand-tuned financial_ratio_pd baseline on 75 features.

    Uses Tier-1 records with 20% default rate so the test set has ~16 positive
    labels (80 test samples × 20%), yielding a stable log-loss estimate.
    Baseline: financial_ratio_pd evaluated with current_ratio, debt_to_equity,
    and interest_coverage — the three core financial ratios from the spec.
    """
    from sklearn.metrics import log_loss  # noqa: PLC0415

    records = _make_tier1_records(n=400, default_rate=0.20, seed=0)
    n_train = 320
    train_data, test_data = records[:n_train], records[n_train:]

    config = TrainingConfig(n_trials=1, n_models=2)
    pipeline = PDTrainingPipeline(config)
    X_train, y_train = pipeline.stage1_data_prep(train_data)
    X_test, y_test = pipeline.stage1_data_prep(test_data)

    if len(np.unique(y_test)) < 2:
        pytest.skip("Degenerate test split (single class); re-run with a different seed")

    model = PDModel(n_models=2, random_seeds=[0, 1])
    model.fit(X_train, y_train)

    lgbm_preds = np.clip(model.predict_proba(X_test), 1e-7, 1 - 1e-7)
    lgbm_loss = float(log_loss(y_test, lgbm_preds))

    # Three-model baseline: financial_ratio_pd uses only 3 financial features
    baseline_preds = []
    for record in test_data:
        fin = record["borrower"]["financial_statements"]
        pred = financial_ratio_pd(
            current_ratio=float(fin["current_ratio"]),
            debt_to_equity=float(fin["debt_to_equity"]),
            interest_coverage=float(fin["interest_coverage"]),
        )
        baseline_preds.append(max(1e-7, min(1 - 1e-7, pred)))

    baseline_loss = float(log_loss(y_test, baseline_preds))

    assert lgbm_loss < baseline_loss, (
        f"LightGBM log-loss {lgbm_loss:.4f} >= baseline log-loss {baseline_loss:.4f}. "
        "Unified 75-feature model should outperform 3-feature financial_ratio_pd."
    )


def test_fee_bps_is_decimal() -> None:
    """compute_fee_bps_from_el must return a Decimal, never a float.

    fee_bps participates in regulatory calculations — float rounding errors
    are unacceptable.  The Decimal type contract is enforced here.
    """
    result = compute_fee_bps_from_el(
        pd=Decimal("0.05"),
        lgd=Decimal("0.35"),
        ead=Decimal("500_000"),
    )
    assert isinstance(result, Decimal), (
        f"Expected Decimal, got {type(result).__name__}: {result!r}"
    )

    # Also verify for the floor case
    floor_result = compute_fee_bps_from_el(
        pd=Decimal("0"),
        lgd=Decimal("0"),
        ead=Decimal("1_000_000"),
    )
    assert isinstance(floor_result, Decimal), (
        f"Expected Decimal at floor, got {type(floor_result).__name__}"
    )


def test_model_save_load_roundtrip() -> None:
    """Saved and re-loaded PDModel must produce bit-identical predictions."""
    records = _make_separable_records(n=100, seed=7)
    model, X, _ = _fit_small_model(records)

    pds_before = model.predict_proba(X[:5])

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "pd_model.pkl")
        model.save(path)
        assert os.path.isfile(path), "Model file was not created by save()"

        loaded = PDModel(n_models=1, random_seeds=[0])  # dummy init — overwritten by load()
        loaded.load(path)

        assert loaded.n_models == model.n_models, "n_models mismatch after load"
        assert loaded.random_seeds == model.random_seeds, "random_seeds mismatch"

        pds_after = loaded.predict_proba(X[:5])
        np.testing.assert_array_equal(
            pds_before,
            pds_after,
            err_msg="Predictions differ after save/load round-trip",
        )
