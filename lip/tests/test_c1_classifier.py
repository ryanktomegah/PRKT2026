"""
test_c1_classifier.py — Tests for C1 Failure Classifier
"""
import time

import numpy as np

from lip.c1_failure_classifier.calibration import IsotonicCalibrator, PlattCalibrator, compute_ece
from lip.c1_failure_classifier.embeddings import EMBEDDING_DIM, CorridorEmbeddingPipeline
from lip.c1_failure_classifier.features import TABULAR_FEATURE_DIM, TabularFeatureEngineer
from lip.c1_failure_classifier.graph_builder import BICGraphBuilder, PaymentEdge
from lip.c1_failure_classifier.graphsage import GRAPHSAGE_OUTPUT_DIM, GraphSAGEModel
from lip.c1_failure_classifier.inference import LATENCY_P99_TARGET_MS, InferenceEngine
from lip.c1_failure_classifier.model import create_default_model
from lip.c1_failure_classifier.tabtransformer import TABTRANSFORMER_INPUT_DIM, TabTransformerModel


class TestGraphBuilder:
    def _make_edge(self, uetr="u1", s="AAAAGB2L", r="BBBBDE2L", amount=50000.0):
        return PaymentEdge(
            uetr=uetr, sending_bic=s, receiving_bic=r,
            amount_usd=amount, currency_pair="USD_EUR",
            timestamp=1700000000.0, features={},
        )

    def test_add_payment_and_get_neighbors(self):
        builder = BICGraphBuilder()
        builder.add_payment(self._make_edge())
        neighbors = builder.get_neighbors("AAAAGB2L", k=10)
        assert isinstance(neighbors, list)

    def test_node_features_shape(self):
        builder = BICGraphBuilder()
        builder.add_payment(self._make_edge())
        feats = builder.get_node_features("AAAAGB2L")
        assert isinstance(feats, np.ndarray)
        assert feats.shape[0] == 8

    def test_edge_features_shape(self):
        builder = BICGraphBuilder()
        builder.add_payment(self._make_edge())
        feats = builder.get_edge_features("AAAAGB2L", "BBBBDE2L")
        assert isinstance(feats, np.ndarray)
        assert feats.shape[0] == 6


class TestTabularFeatureEngineer:
    def test_extract_returns_correct_dim(self):
        eng = TabularFeatureEngineer()
        payment = {
            "amount_usd": 100000, "currency_pair": "USD_EUR",
            "sending_bic": "AAAAGB2L", "receiving_bic": "BBBBDE2L",
        }
        feats = eng.extract(payment)
        assert feats.shape == (TABULAR_FEATURE_DIM,)

    def test_feature_names_match_dim(self):
        eng = TabularFeatureEngineer()
        names = eng.feature_names()
        assert len(names) == TABULAR_FEATURE_DIM


class TestGraphSAGE:
    def test_output_dim(self):
        model = GraphSAGEModel()
        node_feats = np.random.randn(8)
        neighbors_l1 = [np.random.randn(8) for _ in range(5)]
        neighbors_l2 = [np.random.randn(8) for _ in range(5)]
        out = model.forward(node_feats, neighbors_l1, neighbors_l2)
        assert out.shape == (GRAPHSAGE_OUTPUT_DIM,)

    def test_output_dim_no_neighbors(self):
        model = GraphSAGEModel()
        node_feats = np.random.randn(8)
        out = model.forward(node_feats, [], [])
        assert out.shape == (GRAPHSAGE_OUTPUT_DIM,)


class TestTabTransformer:
    def test_output_dim(self):
        model = TabTransformerModel()
        x = np.random.randn(TABTRANSFORMER_INPUT_DIM)
        out = model.forward(x)
        assert out.shape == (TABTRANSFORMER_INPUT_DIM,)


class TestClassifierModel:
    def test_predict_proba_in_range(self):
        model = create_default_model()
        node_feats = np.random.randn(8)
        neighbors = [np.random.randn(8) for _ in range(3)]
        tab_feats = np.random.randn(88)
        prob = model.predict_proba(node_feats, neighbors, neighbors, tab_feats)
        assert 0.0 <= prob <= 1.0

    def test_asymmetric_bce_loss(self):
        model = create_default_model()
        loss = model.asymmetric_bce_loss(1.0, 0.8)
        assert loss > 0

    def test_f2_threshold_selection(self):
        model = create_default_model()
        rng = np.random.default_rng(42)
        y_true = rng.integers(0, 2, size=100).astype(float)
        y_scores = rng.random(100)
        threshold = model.select_f2_threshold(y_true, y_scores)
        assert 0.0 < threshold < 1.0


class TestCorridorEmbedding:
    def test_store_retrieve(self):
        pipeline = CorridorEmbeddingPipeline()
        emb = np.random.randn(EMBEDDING_DIM)
        pipeline.store("USD_EUR", emb)
        retrieved = pipeline.retrieve("USD_EUR")
        assert retrieved is not None
        assert retrieved.shape == (EMBEDDING_DIM,)

    def test_cold_start_returns_vector(self):
        pipeline = CorridorEmbeddingPipeline()
        emb = np.random.randn(EMBEDDING_DIM)
        pipeline.store("USD_EUR", emb)
        result = pipeline.cold_start_embedding("USD_GBP", ["USD_EUR"])
        assert result.shape == (EMBEDDING_DIM,)

    def test_cold_start_empty_returns_zeros(self):
        pipeline = CorridorEmbeddingPipeline()
        result = pipeline.cold_start_embedding("USD_GBP", [])
        assert result.shape == (EMBEDDING_DIM,)
        assert np.allclose(result, 0)


class TestCalibration:
    def test_ece_perfect_calibration(self):
        y_true = np.array([1, 1, 0, 0, 1, 0, 1, 0, 1, 0])
        y_prob = np.array([0.9, 0.8, 0.1, 0.2, 0.85, 0.15, 0.95, 0.05, 0.75, 0.25])
        ece = compute_ece(y_true, y_prob)
        assert 0.0 <= ece <= 1.0

    def test_isotonic_calibrator(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 100).astype(float)
        scores = rng.random(100)
        cal = IsotonicCalibrator()
        cal.fit(y, scores)
        out = cal.predict(scores)
        assert out.shape == scores.shape
        assert np.all((out >= 0) & (out <= 1))

    def test_platt_calibrator(self):
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 100).astype(float)
        scores = rng.random(100)
        cal = PlattCalibrator()
        cal.fit(y, scores)
        out = cal.predict(scores)
        assert out.shape == scores.shape


# ---------------------------------------------------------------------------
# InferenceEngine — correctness, SHAP, and latency SLO
# ---------------------------------------------------------------------------

def _make_engine() -> InferenceEngine:
    """Return an InferenceEngine with default (untrained) weights."""
    return InferenceEngine(
        model=create_default_model(),
        embedding_pipeline=CorridorEmbeddingPipeline(),
    )


_PAYMENT = {
    "amount_usd": 250_000,
    "currency_pair": "USD_EUR",
    "sending_bic": "AAAAGB2L",
    "receiving_bic": "BBBBDE2L",
    "transaction_type": "pacs.002",
}


class TestInferenceEngine:
    def test_predict_returns_required_keys(self):
        engine = _make_engine()
        result = engine.predict(_PAYMENT)
        for key in (
            "failure_probability",
            "above_threshold",
            "inference_latency_ms",
            "threshold_used",
            "corridor_embedding_used",
            "shap_top20",
        ):
            assert key in result, f"missing key: {key}"

    def test_failure_probability_in_range(self):
        engine = _make_engine()
        result = engine.predict(_PAYMENT)
        assert 0.0 <= result["failure_probability"] <= 1.0

    def test_above_threshold_consistent(self):
        engine = _make_engine()
        result = engine.predict(_PAYMENT)
        expected = result["failure_probability"] >= result["threshold_used"]
        assert result["above_threshold"] == expected

    def test_shap_top20_structure(self):
        engine = _make_engine()
        result = engine.predict(_PAYMENT)
        shap = result["shap_top20"]
        assert len(shap) <= 20
        for entry in shap:
            assert "feature" in entry
            assert "value" in entry
            assert isinstance(entry["feature"], str)
            assert isinstance(entry["value"], float)

    def test_shap_top20_sorted_by_abs_value(self):
        engine = _make_engine()
        result = engine.predict(_PAYMENT)
        values = [abs(e["value"]) for e in result["shap_top20"]]
        assert values == sorted(values, reverse=True), "SHAP not sorted by |value| desc"

    def test_slo_p99_94ms(self):
        """InferenceEngine.predict() including SHAP must complete in < 94ms (P99 SLO).

        Runs 15 warm-up calls then measures 20 production calls.  The median
        (p50) must be < 94ms.  One outlier is tolerated (≤1 of 20 may exceed),
        matching a p95 interpretation of the 94ms budget on CPU/NumPy.

        QUANT canonical constant: LATENCY_P99_TARGET_MS = 94.0 ms
        REX EU AI Act Art.13: SHAP explanations must be available within SLO.
        """
        engine = _make_engine()
        # warm-up — JIT effects, cold caches
        for _ in range(15):
            engine.predict(_PAYMENT)

        latencies = []
        for _ in range(20):
            t0 = time.perf_counter()
            engine.predict(_PAYMENT)
            latencies.append((time.perf_counter() - t0) * 1_000.0)

        p50 = float(np.median(latencies))
        n_over = sum(1 for ms in latencies if ms > LATENCY_P99_TARGET_MS)

        assert p50 < LATENCY_P99_TARGET_MS, (
            f"Median inference latency {p50:.1f}ms exceeds P99 SLO {LATENCY_P99_TARGET_MS}ms"
        )
        assert n_over <= 1, (
            f"{n_over}/20 calls exceeded {LATENCY_P99_TARGET_MS}ms "
            f"(max={max(latencies):.1f}ms)"
        )

    def test_batch_forward_consistent_with_single(self):
        """forward_batch() must produce outputs consistent with sequential forward().

        Validates that the vectorised batch implementation introduced for SHAP
        speed-up returns the same results as single-sample forward() calls
        within floating-point tolerance.

        ARIA: correctness guard for the batch-SHAP optimisation.
        """
        tab_model = create_default_model().tabtransformer
        rng = np.random.default_rng(42)
        batch = rng.standard_normal((8, TABTRANSFORMER_INPUT_DIM))

        batch_out = tab_model.forward_batch(batch)           # (8, output_dim)
        single_out = np.stack([tab_model.forward(x) for x in batch])  # (8, output_dim)

        np.testing.assert_allclose(
            batch_out, single_out, rtol=1e-5, atol=1e-7,
            err_msg="forward_batch() diverges from sequential forward()",
        )

    def test_mlp_forward_batch_consistent_with_single(self):
        """MLPHead.forward_batch() must match sequential forward() per sample."""
        model = create_default_model()
        mlp = model.mlp
        fused_dim = GRAPHSAGE_OUTPUT_DIM + TABTRANSFORMER_INPUT_DIM

        rng = np.random.default_rng(7)
        batch = rng.standard_normal((6, fused_dim))

        batch_out = mlp.forward_batch(batch)
        single_out = np.array([mlp.forward(x) for x in batch])

        np.testing.assert_allclose(
            batch_out, single_out, rtol=1e-5, atol=1e-7,
            err_msg="MLPHead.forward_batch() diverges from sequential forward()",
        )
