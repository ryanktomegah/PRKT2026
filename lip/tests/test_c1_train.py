"""
test_c1_train.py — Tests for C1 training entry-point (train.py).
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from lip.c1_failure_classifier.train import (
    CORPUS_TAG,
    MODEL_VERSION,
    _build_audit_checklist,
    _prepare_pipeline_data,
    generate_corpus,
    generate_model_card,
)


class TestCorpusGeneration:
    """Tests for generate_corpus()."""

    @pytest.fixture(scope="class")
    def corpus(self):
        """Small corpus for testing (1K records)."""
        return generate_corpus(n=1_000, seed=42)

    def test_returns_four_items(self, corpus) -> None:
        train, val, test, meta = corpus
        assert isinstance(train, list)
        assert isinstance(val, list)
        assert isinstance(test, list)
        assert isinstance(meta, dict)

    def test_split_sizes(self, corpus) -> None:
        train, val, test, meta = corpus
        total = len(train) + len(val) + len(test)
        assert total == 1_000
        assert abs(len(train) / total - 0.70) <= 0.02
        assert abs(len(val) / total - 0.15) <= 0.02

    def test_metadata_has_corpus_tag(self, corpus) -> None:
        _, _, _, meta = corpus
        assert meta["corpus_tag"] == CORPUS_TAG
        assert meta["split_method"].startswith("TIME_BASED")

    def test_time_based_ordering(self, corpus) -> None:
        train, val, test, _ = corpus
        assert train[-1]["timestamp_utc"] <= val[0]["timestamp_utc"]
        assert val[-1]["timestamp_utc"] <= test[0]["timestamp_utc"]


class TestPrepareData:
    """Tests for _prepare_pipeline_data()."""

    def test_adds_label_and_timestamp(self) -> None:
        records = [
            {
                "uetr": "abc-123",
                "is_failure": 1,
                "timestamp_utc": "2024-01-15T10:00:00+00:00",
            }
        ]
        prepared = _prepare_pipeline_data(records)
        assert prepared[0]["label"] == 1
        assert "timestamp" in prepared[0]
        assert isinstance(prepared[0]["timestamp"], float)


class TestModelCard:
    """Tests for generate_model_card()."""

    def test_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_model_card(
                corpus_meta={"corpus_tag": "SYNTHETIC", "total_records": 100},
                training_metrics={"model_version": MODEL_VERSION},
                output_dir=tmpdir,
            )
            assert os.path.exists(path)
            with open(path) as f:
                card = json.load(f)
            assert card["model_id"] == MODEL_VERSION
            assert card["corpus_tag"] == CORPUS_TAG

    def test_model_card_has_honest_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_model_card(
                corpus_meta={},
                training_metrics={},
                output_dir=tmpdir,
            )
            with open(path) as f:
                card = json.load(f)
            assert "honest_ceiling" in card
            assert "SYNTHETIC" in card["honest_ceiling"]["note"]


class TestAuditChecklist:
    """Tests for audit gate 1.1 checklist."""

    def test_has_pass_and_not_checkable_items(self) -> None:
        checklist = _build_audit_checklist()
        statuses = {v["status"] for v in checklist.values()}
        assert "PASS" in statuses
        assert "NOT_CHECKABLE_YET" in statuses

    def test_three_not_checkable_items(self) -> None:
        checklist = _build_audit_checklist()
        not_yet = [k for k, v in checklist.items() if v["status"] == "NOT_CHECKABLE_YET"]
        assert len(not_yet) == 3
        assert "inference_p50_lt_30ms_gpu" in not_yet
        assert "corridor_embeddings_in_redis" in not_yet
        assert "hot_swap_protocol_tested" in not_yet
