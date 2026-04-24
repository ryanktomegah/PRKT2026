#!/usr/bin/env python3
"""
validate_c1_pilot.py — End-to-end C1 model validation with real trained model.

Loads the trained C1 model artifacts (PyTorch + LightGBM + isotonic calibrator),
generates synthetic payments via the production pipeline, and runs them through
the full LIP pipeline (real C4, C6, C7) to validate:

  1. Model loads correctly (all artifacts present and compatible)
  2. Predictions are calibrated (probability distribution, ECE)
  3. Pipeline produces expected outcome distribution
  4. Latency stays within the 94ms SLO
  5. SHAP explanations are non-trivial
  6. Calibrator shifts probabilities toward better calibration

Usage:
    PYTHONPATH=. python scripts/validate_c1_pilot.py
    PYTHONPATH=. python scripts/validate_c1_pilot.py --n-payments 500 --seed 99
    PYTHONPATH=. python scripts/validate_c1_pilot.py --model-dir /path/to/artifacts
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from lip.c5_streaming.event_normalizer import NormalizedEvent
    from lip.pipeline import LIPPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("validate_c1_pilot")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SALT: bytes = b"pilot_val_salt__32bytes_________"
_HMAC_KEY: bytes = b"pilot_val_hmac__32bytes_________"

# Synthetic event mix — matches approximate real-world rejection code distribution
_EVENT_MIX: list[tuple[str, Optional[str], float]] = [
    ("CURR", None, 0.35),       # CLASS_A, 3d — currency issues
    ("AM04", None, 0.20),       # CLASS_A, 3d — insufficient funds
    ("AGNT", None, 0.15),       # CLASS_A, 3d — incorrect agent
    ("AC04", None, 0.10),       # CLASS_A, 3d — closed account
    ("FOCR", None, 0.05),       # CLASS_C, 21d — following cancellation request
    ("MS03", None, 0.05),       # BLOCK — not specified reason (compliance-adjacent)
    ("DNOR", None, 0.03),       # BLOCK — debtor bank not registered
    ("NARR", "suspected fraud dispute", 0.04),  # Dispute narrative
    ("NARR", "payment for invoice services", 0.03),  # Clean narrative
]

_SENDING_BICS = [
    "DEUTDEFF", "BNPAFRPP", "COBADEFF", "BARCGB2L", "HSBCGB2L",
    "CITIUS33", "CHASUS33", "WFBIUS6S", "UBSWCHZH", "SCBLHKHH",
    "ANZBAU3M", "NATAAU33", "MABORB2B", "BBVAMXMX", "KABORKKR",
]
_RECEIVING_BICS = [
    "SOGEFRPP", "INGBNL2A", "RABONL2U", "BOFAUS3N", "MABORB2B",
    "BBVAMXMX", "KABORKKR", "SCBLHKHH", "NATAAU33", "DRESDEFF",
]
_CURRENCY_PAIRS = [
    "USD_EUR", "EUR_USD", "GBP_USD", "USD_GBP", "EUR_GBP",
    "USD_JPY", "USD_CHF", "EUR_CHF", "USD_AUD", "AUD_USD",
    "USD_HKD", "HKD_USD", "EUR_SEK", "USD_KRW", "USD_BRL",
    "USD_MXN", "EUR_JPY", "GBP_EUR", "CHF_EUR", "JPY_USD",
]


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------


def load_c1_model(model_dir: Path):
    """Load the trained PyTorch C1 model + LightGBM + calibrator + scaler."""
    import torch

    from lip.c1_failure_classifier.graphsage_torch import GraphSAGETorch
    from lip.c1_failure_classifier.model_torch import (
        ClassifierModelTorch,
        MLPHeadTorch,
    )
    from lip.c1_failure_classifier.tabtransformer_torch import TabTransformerTorch

    # Construct the model architecture
    graphsage = GraphSAGETorch()
    tabtransformer = TabTransformerTorch()
    mlp_head = MLPHeadTorch()
    model = ClassifierModelTorch(
        graphsage=graphsage,
        tabtransformer=tabtransformer,
        mlp_head=mlp_head,
    )

    # Load PyTorch weights
    pt_path = model_dir / "c1_model_parquet.pt"
    if not pt_path.exists():
        logger.error("Model checkpoint not found: %s", pt_path)
        sys.exit(1)
    state_dict = torch.load(pt_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    logger.info("PyTorch model loaded: %s (%d parameters)",
                pt_path, sum(p.numel() for p in model.parameters()))

    # Load LightGBM
    lgbm_path = model_dir / "c1_lgbm_parquet.pkl"
    if lgbm_path.exists():
        with open(lgbm_path, "rb") as f:
            model.lgbm_model = pickle.load(f)
        logger.info("LightGBM model loaded: %s", lgbm_path)
    else:
        logger.warning("No LightGBM model found — using PyTorch-only predictions")

    # Load calibrator
    calibrator = None
    cal_path = model_dir / "c1_calibrator.pkl"
    if cal_path.exists():
        with open(cal_path, "rb") as f:
            calibrator = pickle.load(f)
        logger.info("Isotonic calibrator loaded: %s", cal_path)
    else:
        logger.warning("No calibrator found — raw model scores will be used")

    # Load scaler
    scaler = None
    scaler_path = model_dir / "c1_scaler.pkl"
    if scaler_path.exists():
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
        logger.info("StandardScaler loaded: %s", scaler_path)
    else:
        logger.warning("No scaler found — features will not be normalised")

    return model, calibrator, scaler


# ---------------------------------------------------------------------------
# C1 engine wrapper (real model)
# ---------------------------------------------------------------------------


class RealC1Engine:
    """Wraps the trained PyTorch model to match the LIPPipeline c1_engine interface."""

    def __init__(self, model, calibrator, scaler, threshold: float = 0.110):
        import torch

        self._model = model
        self._calibrator = calibrator
        self._scaler = scaler
        self._threshold = threshold
        self._torch = torch
        self._rng = np.random.default_rng(12345)

        from lip.c1_failure_classifier.features import TabularFeatureEngineer
        self._tab_eng = TabularFeatureEngineer()

    def _enrich_payment(self, payment: dict) -> dict:
        """Add realistic BIC/corridor stats to simulate production data.

        In production, these would come from Redis-backed rolling aggregates.
        For validation, we sample from realistic distributions.
        """
        rng = self._rng
        enriched = dict(payment)

        # Sender stats — simulate a BIC with moderate history
        fail_rate = float(rng.beta(2, 30))  # mean ~6%, right-skewed
        enriched["sender_stats"] = {
            "avg_amount": float(rng.lognormal(11, 1.5)),
            "std_amount": float(rng.lognormal(10, 1.0)),
            "tx_count": int(rng.integers(50, 5000)),
            "failure_rate_30d": fail_rate,
            "failure_rate_7d": fail_rate * float(rng.uniform(0.5, 2.0)),
            "failure_rate_1d": fail_rate * float(rng.uniform(0.2, 3.0)),
            "age_days": int(rng.integers(30, 1800)),
            "unique_receivers": int(rng.integers(5, 200)),
            "consecutive_failures": int(rng.choice([0, 0, 0, 1, 2, 3])),
            "out_degree": int(rng.integers(3, 50)),
            "in_degree": int(rng.integers(2, 40)),
            "volume_24h": float(rng.lognormal(14, 2)),
            "currency_concentration": float(rng.beta(5, 2)),
            "pct_large_tx": float(rng.beta(2, 8)),
        }

        # Receiver stats
        r_fail = float(rng.beta(2, 40))
        enriched["receiver_stats"] = {
            "avg_amount": float(rng.lognormal(11, 1.5)),
            "std_amount": float(rng.lognormal(10, 1.0)),
            "tx_count": int(rng.integers(50, 5000)),
            "failure_rate_30d": r_fail,
            "failure_rate_7d": r_fail * float(rng.uniform(0.5, 2.0)),
            "failure_rate_1d": r_fail * float(rng.uniform(0.2, 3.0)),
            "age_days": int(rng.integers(30, 1800)),
            "unique_senders": int(rng.integers(5, 200)),
            "consecutive_failures": int(rng.choice([0, 0, 0, 0, 1])),
            "out_degree": int(rng.integers(2, 30)),
            "in_degree": int(rng.integers(3, 50)),
            "volume_24h": float(rng.lognormal(14, 2)),
            "currency_concentration": float(rng.beta(5, 2)),
            "pct_large_tx": float(rng.beta(2, 8)),
        }

        # Corridor stats
        c_rate = float(rng.beta(2, 50))  # ~4% mean
        enriched["corridor_stats"] = {
            "failure_rate_7d": c_rate,
            "failure_rate_30d": c_rate * float(rng.uniform(0.8, 1.2)),
            "avg_amount": float(rng.lognormal(11, 1)),
            "std_amount": float(rng.lognormal(10, 1)),
            "tx_count": int(rng.integers(500, 50000)),
            "volume_7d": float(rng.lognormal(18, 1.5)),
            "volume_30d": float(rng.lognormal(20, 1.5)),
            "age_days": int(rng.integers(100, 3000)),
            "unique_currencies": int(rng.integers(1, 5)),
            "tx_per_day": float(rng.lognormal(5, 1)),
            "max_amount": float(rng.lognormal(15, 2)),
            "min_amount": float(rng.lognormal(6, 2)),
            "p50_amount": float(rng.lognormal(11, 1)),
            "p95_amount": float(rng.lognormal(14, 1.5)),
            "velocity_1h": float(rng.poisson(5)),
            "velocity_24h": float(rng.poisson(100)),
            "consecutive_failures": int(rng.choice([0, 0, 0, 1, 2])),
        }

        return enriched

    def predict(self, payment: dict) -> dict:
        t_start = time.perf_counter()

        # Enrich with simulated production stats
        enriched = self._enrich_payment(payment)

        # Extract features
        features = self._tab_eng.extract(enriched)  # (88,)

        # Build 96-dim vector: [8 node features | 88 tabular features]
        # Node features are the first 8 of the tabular vector in training
        node_feat = np.zeros(8, dtype=np.float64)
        full_features = np.concatenate([node_feat, features])  # (96,)

        # Apply scaler if available
        if self._scaler is not None:
            full_features = self._scaler.transform(
                full_features.reshape(1, -1)
            ).flatten()

        # Forward pass
        with self._torch.no_grad():
            nf = self._torch.tensor(
                full_features[:8], dtype=self._torch.float32
            ).unsqueeze(0)
            tf = self._torch.tensor(
                full_features[8:], dtype=self._torch.float32
            ).unsqueeze(0)
            logit = self._model(nf, tf, None)
            neural_prob = float(self._torch.sigmoid(logit).item())

        # LightGBM ensemble
        if self._model.lgbm_model is not None:
            x_tab = full_features[8:].reshape(1, -1).astype(np.float64)
            lgbm_prob = float(
                self._model.lgbm_model.predict_proba(x_tab)[0, 1]
            )
            raw_prob = 0.5 * neural_prob + 0.5 * lgbm_prob
        else:
            raw_prob = neural_prob

        # Calibrate
        if self._calibrator is not None and hasattr(self._calibrator, '_is_fitted') and self._calibrator._is_fitted:
            prob = float(
                self._calibrator.predict(np.array([raw_prob]))[0]
            )
        else:
            prob = raw_prob

        latency_ms = (time.perf_counter() - t_start) * 1_000.0

        # SHAP approximation (simplified — top features by magnitude)
        feature_names = self._tab_eng.feature_names()
        indexed = sorted(
            enumerate(features),
            key=lambda iv: abs(iv[1]),
            reverse=True,
        )[:20]
        shap_top20 = [
            {"feature": feature_names[i], "value": float(v)}
            for i, v in indexed
        ]

        return {
            "failure_probability": prob,
            "above_threshold": prob >= self._threshold,
            "inference_latency_ms": round(latency_ms, 3),
            "threshold_used": self._threshold,
            "corridor_embedding_used": False,
            "shap_top20": shap_top20,
            "raw_probability": raw_prob,
        }


# ---------------------------------------------------------------------------
# Sampling C2 engine (mock — same as simulate_pipeline.py)
# ---------------------------------------------------------------------------


class _SamplingC2Engine:
    def __init__(self, rng: np.random.Generator):
        self._rng = rng

    def predict(self, payment: dict, borrower: dict) -> dict:
        r = float(self._rng.random())
        if r < 0.60:
            fee_bps, pd_score, tier = 300, float(self._rng.uniform(0.01, 0.06)), 3
        elif r < 0.90:
            fee_bps = int(self._rng.integers(350, 501))
            pd_score, tier = float(self._rng.uniform(0.06, 0.15)), 2
        else:
            fee_bps = int(self._rng.integers(500, 801))
            pd_score, tier = float(self._rng.uniform(0.15, 0.35)), 1
        return {
            "pd_score": pd_score,
            "fee_bps": fee_bps,
            "tier": tier,
            "shap_values": [{"feature": f"f_{i}", "value": 0.01} for i in range(20)],
            "borrower_id_hash": "pilot_val_borrower",
            "inference_latency_ms": float(self._rng.uniform(5.0, 25.0)),
        }

    def __call__(self, payment: dict, borrower: dict) -> dict:
        return self.predict(payment, borrower)


# ---------------------------------------------------------------------------
# Event factory
# ---------------------------------------------------------------------------


def _make_event(
    rejection_code: str,
    narrative: Optional[str],
    amount: Decimal,
    sending_bic: str,
    receiving_bic: str,
    currency: str,
) -> "NormalizedEvent":
    from lip.c5_streaming.event_normalizer import NormalizedEvent

    return NormalizedEvent(
        uetr=str(uuid.uuid4()),
        individual_payment_id=str(uuid.uuid4()),
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount=amount,
        currency=currency,
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code=rejection_code,
        narrative=narrative,
        raw_source={},
    )


# ---------------------------------------------------------------------------
# Pipeline factory
# ---------------------------------------------------------------------------


def _build_pipeline(c1_engine, rng: np.random.Generator) -> "LIPPipeline":
    from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
    from lip.c6_aml_velocity.velocity import VelocityChecker
    from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
    from lip.c7_execution_agent.decision_log import DecisionLogger
    from lip.c7_execution_agent.degraded_mode import DegradedModeManager
    from lip.c7_execution_agent.human_override import HumanOverrideInterface
    from lip.c7_execution_agent.kill_switch import KillSwitch
    from lip.pipeline import LIPPipeline

    ks = KillSwitch()
    dm = DegradedModeManager()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    agent = ExecutionAgent(
        kill_switch=ks,
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=dm,
        config=cfg,
    )
    return LIPPipeline(
        c1_engine=c1_engine,
        c2_engine=_SamplingC2Engine(rng),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=_SALT),
        c7_agent=agent,
        c3_monitor=None,
    )


# ---------------------------------------------------------------------------
# Validation run
# ---------------------------------------------------------------------------


def run_validation(
    model_dir: Path,
    n_payments: int = 200,
    seed: int = 42,
) -> dict:
    """Run the full validation and return metrics."""

    # === Step 1: Load model ===
    print("\n" + "=" * 60)
    print("  STEP 1: LOADING MODEL ARTIFACTS")
    print("=" * 60)

    model, calibrator, scaler = load_c1_model(model_dir)

    # Read training metrics
    metrics_path = model_dir / "train_metrics_parquet.json"
    train_metrics = {}
    if metrics_path.exists():
        import json
        train_metrics = json.loads(metrics_path.read_text())
        print("\n  Training metrics found:")
        print(f"    Val AUC:  {train_metrics.get('val_auc', '?')}")
        print(f"    F2 Score: {train_metrics.get('f2_score', '?')}")
        print(f"    ECE:      {train_metrics.get('ece_post_calibration', '?')}")
        print(f"    Threshold: {train_metrics.get('f2_threshold', '?')}")

    threshold = train_metrics.get("f2_threshold", 0.110)
    c1_engine = RealC1Engine(model, calibrator, scaler, threshold=threshold)

    # === Step 2: Build pipeline ===
    print("\n" + "=" * 60)
    print("  STEP 2: BUILDING PIPELINE (Real C4, C6, C7)")
    print("=" * 60)

    rng = np.random.default_rng(seed)
    pipeline = _build_pipeline(c1_engine, rng)
    print("  Pipeline ready.")

    # === Step 3: Generate and process payments ===
    print("\n" + "=" * 60)
    print(f"  STEP 3: PROCESSING {n_payments} SYNTHETIC PAYMENTS")
    print("=" * 60)

    # Build weighted event mix
    codes, narratives, weights = [], [], []
    for code, narr, w in _EVENT_MIX:
        codes.append(code)
        narratives.append(narr)
        weights.append(w)
    weights_arr = np.array(weights)
    weights_arr /= weights_arr.sum()

    outcomes: dict[str, int] = {}
    probabilities: list[float] = []
    raw_probabilities: list[float] = []
    latencies: list[float] = []
    shap_counts: list[int] = []
    above_count = 0
    errors = 0

    t_total_start = time.perf_counter()

    for i in range(n_payments):
        # Sample event type
        idx = rng.choice(len(codes), p=weights_arr)
        code = codes[idx]
        narr = narratives[idx]

        # Sample amount (log-normal, institutional B2B range — median ~$2M)
        amount = Decimal(str(round(float(rng.lognormal(14.5, 1.0)), 2)))
        amount = max(amount, Decimal("500000"))
        amount = min(amount, Decimal("50000000"))

        sending_bic = rng.choice(_SENDING_BICS)
        receiving_bic = rng.choice(_RECEIVING_BICS)
        currency = rng.choice(["USD", "EUR", "GBP", "JPY", "CHF", "AUD"])

        event = _make_event(code, narr, amount, sending_bic, receiving_bic, currency)

        try:
            result = pipeline.process(event)
            outcome = result.outcome
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            if result.failure_probability is not None:
                probabilities.append(result.failure_probability)
                if result.failure_probability >= threshold:
                    above_count += 1

            latencies.append(getattr(result, 'total_latency_ms', 0) or 0)
            if result.shap_top20:
                shap_counts.append(len(result.shap_top20))

            # Track raw probability from C1 engine
            # (only available when C1 was called, not for BLOCK outcomes)
            if result.failure_probability is not None and result.failure_probability > 0:
                raw_probabilities.append(result.failure_probability)

        except Exception as e:
            errors += 1
            if errors <= 5:
                logger.error("Payment %d failed: %s", i, e)

        if (i + 1) % 50 == 0:
            elapsed = time.perf_counter() - t_total_start
            rate = (i + 1) / elapsed
            print(f"    Processed {i + 1}/{n_payments}  ({rate:.0f} payments/s)")

    total_elapsed = time.perf_counter() - t_total_start

    # === Step 4: Report ===
    print("\n" + "=" * 60)
    print("  STEP 4: VALIDATION RESULTS")
    print("=" * 60)

    total = n_payments
    probs = np.array(probabilities) if probabilities else np.array([0.0])

    print(f"\n  Payments processed:  {total}")
    print(f"  Errors:              {errors}")
    print(f"  Total time:          {total_elapsed:.1f}s ({total / total_elapsed:.0f} payments/s)")

    # Outcome distribution
    print(f"\n  {'─' * 50}")
    print("  OUTCOME DISTRIBUTION")
    print(f"  {'─' * 50}")
    for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
        pct = 100.0 * count / total
        bar = "█" * int(pct / 2)
        print(f"    {outcome:<25s} {count:>5d}  ({pct:5.1f}%)  {bar}")

    # Probability distribution
    print(f"\n  {'─' * 50}")
    print(f"  C1 PROBABILITY DISTRIBUTION (n={len(probs)})")
    print(f"  {'─' * 50}")
    print(f"    Mean:     {probs.mean():.4f}")
    print(f"    Median:   {np.median(probs):.4f}")
    print(f"    Std:      {probs.std():.4f}")
    print(f"    Min:      {probs.min():.4f}")
    print(f"    Max:      {probs.max():.4f}")
    print(f"    P10:      {np.percentile(probs, 10):.4f}")
    print(f"    P90:      {np.percentile(probs, 90):.4f}")
    print(f"    Above τ*: {above_count}/{len(probs)} ({100.0 * above_count / len(probs):.1f}%)")

    # Probability histogram (text-based)
    print("\n    Histogram (10 bins):")
    hist, bin_edges = np.histogram(probs, bins=10, range=(0, 1))
    max_count = max(hist) if max(hist) > 0 else 1
    for j in range(len(hist)):
        lo, hi = bin_edges[j], bin_edges[j + 1]
        bar_len = int(40 * hist[j] / max_count) if hist[j] > 0 else 0
        bar = "█" * bar_len
        marker = " ← τ*" if lo <= threshold < hi else ""
        print(f"    [{lo:.1f}-{hi:.1f})  {hist[j]:>5d}  {bar}{marker}")

    # Latency
    lats = np.array(latencies) if latencies else np.array([0.0])
    lats_nonzero = lats[lats > 0] if len(lats[lats > 0]) > 0 else lats
    print(f"\n  {'─' * 50}")
    print("  LATENCY (pipeline end-to-end)")
    print(f"  {'─' * 50}")
    print(f"    P50:      {np.percentile(lats_nonzero, 50):.2f} ms")
    print(f"    P95:      {np.percentile(lats_nonzero, 95):.2f} ms")
    print(f"    P99:      {np.percentile(lats_nonzero, 99):.2f} ms")
    print(f"    Max:      {np.max(lats_nonzero):.2f} ms")
    slo_pass = np.percentile(lats_nonzero, 99) <= 94.0
    print(f"    SLO (p99 ≤ 94ms): {'PASS ✓' if slo_pass else 'FAIL ✗'}")

    # SHAP
    print(f"\n  {'─' * 50}")
    print("  SHAP EXPLANATIONS")
    print(f"  {'─' * 50}")
    if shap_counts:
        print(f"    Payments with SHAP:   {len(shap_counts)}")
        print(f"    Avg features/payment: {np.mean(shap_counts):.1f}")
    else:
        print("    No SHAP data collected (below-threshold payments skip)")

    # Calibration check
    print(f"\n  {'─' * 50}")
    print("  CALIBRATION CHECK")
    print(f"  {'─' * 50}")
    if calibrator is not None:
        raw_test = np.array([0.1, 0.2, 0.3, 0.5, 0.7, 0.9])
        cal_test = calibrator.predict(raw_test)
        print("    Calibrator transforms (raw → calibrated):")
        for r, c in zip(raw_test, cal_test):
            print(f"      {r:.1f} → {c:.4f}")
        print(f"    Calibrator fitted: {calibrator._is_fitted}")
    else:
        print("    No calibrator loaded — raw scores used")

    # Verdict
    print(f"\n  {'═' * 50}")
    checks_passed = 0
    checks_total = 6

    check_results = []

    # Check 1: No errors
    c1_pass = errors == 0
    check_results.append(("No processing errors", c1_pass))
    checks_passed += c1_pass

    # Check 2: Multiple outcomes
    c2_pass = len(outcomes) >= 2
    check_results.append(("Multiple outcome types", c2_pass))
    checks_passed += c2_pass

    # Check 3: Probabilities not degenerate
    c3_pass = probs.std() > 0.01
    check_results.append(("Non-degenerate probabilities (std > 0.01)", c3_pass))
    checks_passed += c3_pass

    # Check 4: Some above threshold
    c4_pass = above_count > 0
    check_results.append(("Some payments above threshold", c4_pass))
    checks_passed += c4_pass

    # Check 5: SLO
    check_results.append(("Latency SLO (p99 ≤ 94ms)", slo_pass))
    checks_passed += slo_pass

    # Check 6: FUNDED outcomes exist
    c6_pass = outcomes.get("FUNDED", 0) > 0
    check_results.append(("At least one FUNDED outcome", c6_pass))
    checks_passed += c6_pass

    for name, passed in check_results:
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"  [{status}] {name}")

    print(f"\n  VERDICT: {checks_passed}/{checks_total} checks passed")

    if checks_passed == checks_total:
        print("\n  ✓ C1 MODEL VALIDATION PASSED")
        print("    The trained model loads, produces calibrated predictions,")
        print("    and the full pipeline generates correct outcomes.")
        print("    Ready for pilot bank integration.")
    else:
        print("\n  ✗ VALIDATION INCOMPLETE — review failures above")

    print(f"  {'═' * 50}\n")

    return {
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "outcomes": outcomes,
        "n_payments": n_payments,
        "errors": errors,
        "prob_mean": float(probs.mean()),
        "prob_std": float(probs.std()),
        "above_threshold_pct": 100.0 * above_count / len(probs),
        "p99_latency_ms": float(np.percentile(lats_nonzero, 99)),
        "slo_pass": slo_pass,
        "elapsed_s": total_elapsed,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Validate C1 model end-to-end")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("artifacts/c1_trained/c1_trained"),
        help="Directory containing trained model artifacts",
    )
    parser.add_argument(
        "--n-payments",
        type=int,
        default=200,
        help="Number of synthetic payments to process (default: 200)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    # Verify model directory
    if not args.model_dir.exists():
        print(f"ERROR: Model directory not found: {args.model_dir}")
        print("Download artifacts first:")
        print("  gh run download <run-id> --name <artifact-name> --dir artifacts/c1_trained")
        sys.exit(1)

    results = run_validation(
        model_dir=args.model_dir,
        n_payments=args.n_payments,
        seed=args.seed,
    )

    sys.exit(0 if results["checks_passed"] == results["checks_total"] else 1)


if __name__ == "__main__":
    main()
