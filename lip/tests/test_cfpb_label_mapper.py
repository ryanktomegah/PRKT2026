"""
test_cfpb_label_mapper.py — Tests for C4 CFPB label mapper.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile

import pytest

from lip.c4_dispute_classifier.corpus.cfpb_label_mapper import (
    DISPUTE_CLASSES,
    LABEL_MAP,
    TARGET_PER_CLASS,
    filter_and_label,
    map_label,
    save_corpus,
    summary_stats,
)


class TestLabelMap:
    """Tests for the CFPB → C4 label mapping."""

    def test_label_map_has_11_entries(self) -> None:
        assert len(LABEL_MAP) == 11

    def test_all_values_are_valid_classes(self) -> None:
        for sub_issue, cls in LABEL_MAP.items():
            assert cls in DISPUTE_CLASSES, f"{sub_issue} maps to unknown class {cls}"

    def test_all_four_classes_covered(self) -> None:
        mapped_classes = set(LABEL_MAP.values())
        assert mapped_classes == DISPUTE_CLASSES

    def test_dispute_confirmed_mappings(self) -> None:
        assert map_label("Fraud or scam") == "DISPUTE_CONFIRMED"
        assert map_label("Unauthorized transactions/trans") == "DISPUTE_CONFIRMED"

    def test_dispute_possible_mappings(self) -> None:
        assert map_label("Problem with a purchase shown on your statement") == "DISPUTE_POSSIBLE"
        assert map_label("Charged wrong amount") == "DISPUTE_POSSIBLE"

    def test_negotiation_mappings(self) -> None:
        assert map_label("Settlement process and costs") == "NEGOTIATION"
        assert map_label("Written notification about debt") == "NEGOTIATION"

    def test_not_dispute_mappings(self) -> None:
        assert map_label("Can't open an account") == "NOT_DISPUTE"
        assert map_label("Incorrect information on your report") == "NOT_DISPUTE"

    def test_unknown_returns_none(self) -> None:
        assert map_label("Some random issue") is None
        assert map_label("") is None


class TestFilterAndLabel:
    """Tests for filter_and_label()."""

    def _make_record(self, sub_issue: str, narrative: str = "complaint text") -> dict:
        return {
            "sub_issue": sub_issue,
            "consumer_complaint_narrative": narrative,
            "tags": "",
        }

    def test_filters_empty_narratives(self) -> None:
        records = [self._make_record("Fraud or scam", narrative="")]
        result = filter_and_label(records)
        assert len(result) == 0

    def test_filters_unknown_sub_issues(self) -> None:
        records = [self._make_record("Unknown issue")]
        result = filter_and_label(records)
        assert len(result) == 0

    def test_labels_known_sub_issues(self) -> None:
        records = [self._make_record("Fraud or scam")]
        result = filter_and_label(records)
        assert len(result) == 1
        assert result[0]["dispute_class"] == "DISPUTE_CONFIRMED"

    def test_respects_target_per_class(self) -> None:
        records = [self._make_record("Fraud or scam") for _ in range(20)]
        result = filter_and_label(records, target_per_class=5)
        assert len(result) == 5

    def test_balanced_output(self) -> None:
        records = []
        for sub_issue in LABEL_MAP:
            records.extend([self._make_record(sub_issue) for _ in range(10)])
        result = filter_and_label(records, target_per_class=5)
        class_counts = {}
        for r in result:
            cls = r["dispute_class"]
            class_counts[cls] = class_counts.get(cls, 0) + 1
        # Each class should have at most 5
        for cls, count in class_counts.items():
            assert count <= 5, f"{cls} has {count} records, expected ≤5"

    def test_target_per_class_default(self) -> None:
        assert TARGET_PER_CLASS == 12_500


class TestSaveCorpus:
    """Tests for save_corpus()."""

    def _make_labelled(self) -> list:
        return [
            {
                "consumer_complaint_narrative": "I was scammed",
                "sub_issue": "Fraud or scam",
                "dispute_class": "DISPUTE_CONFIRMED",
            },
            {
                "consumer_complaint_narrative": "Wrong charge",
                "sub_issue": "Charged wrong amount",
                "dispute_class": "DISPUTE_POSSIBLE",
            },
        ]

    def test_writes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "corpus.csv")
            save_corpus(self._make_labelled(), path)
            assert os.path.exists(path)
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["dispute_class"] == "DISPUTE_CONFIRMED"

    def test_empty_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.csv")
            save_corpus([], path)


class TestSummaryStats:
    """Tests for summary_stats()."""

    def test_returns_expected_keys(self) -> None:
        labelled = [
            {
                "consumer_complaint_narrative": "Some narrative text here",
                "dispute_class": "DISPUTE_CONFIRMED",
            }
        ]
        stats = summary_stats(labelled)
        assert "total_records" in stats
        assert "class_distribution" in stats
        assert "narrative_length_min" in stats
        assert "narrative_length_max" in stats
        assert "narrative_length_mean" in stats
        assert stats["total_records"] == 1

    def test_class_distribution(self) -> None:
        labelled = [
            {"consumer_complaint_narrative": "a", "dispute_class": "DISPUTE_CONFIRMED"},
            {"consumer_complaint_narrative": "b", "dispute_class": "DISPUTE_CONFIRMED"},
            {"consumer_complaint_narrative": "c", "dispute_class": "NOT_DISPUTE"},
        ]
        stats = summary_stats(labelled)
        assert stats["class_distribution"]["DISPUTE_CONFIRMED"] == 2
        assert stats["class_distribution"]["NOT_DISPUTE"] == 1
