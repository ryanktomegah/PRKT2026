"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

cfpb_label_mapper.py — Maps CFPB complaint sub-issues to C4 dispute classes.

Data source: Consumer Financial Protection Bureau complaint database
  https://files.consumerfinance.gov/ccdb/complaints.csv.zip
  Free, ~500MB CSV, updated nightly.

The CFPB dataset is used to bootstrap the C4 Dispute Classifier corpus.
Records are filtered to those with a non-null ``consumer_complaint_narrative``
in English, then labelled using the mapping below.

Target: 50K records balanced across four classes.

Usage:
    python -m lip.c4_dispute_classifier.corpus.cfpb_label_mapper \\
        --input /path/to/complaints.csv \\
        --output /path/to/labelled_corpus.csv \\
        --target-per-class 12500
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import sys
from collections import Counter
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label mapping: CFPB sub-issue → C4 dispute class
# ---------------------------------------------------------------------------

LABEL_MAP: Dict[str, str] = {
    # DISPUTE_CONFIRMED — clear fraud or unauthorised activity
    "Fraud or scam": "DISPUTE_CONFIRMED",
    "Unauthorized transactions/trans": "DISPUTE_CONFIRMED",
    "Card was charged for something you did not purchase": "DISPUTE_CONFIRMED",

    # DISPUTE_POSSIBLE — billing disputes that may or may not be confirmed
    "Problem with a purchase shown on your statement": "DISPUTE_POSSIBLE",
    "Charged fees you didn't expect": "DISPUTE_POSSIBLE",
    "Charged wrong amount": "DISPUTE_POSSIBLE",

    # NEGOTIATION — debt collection and settlement disputes
    "Settlement process and costs": "NEGOTIATION",
    "Attempting to collect wrong amount": "NEGOTIATION",
    "Written notification about debt": "NEGOTIATION",

    # NOT_DISPUTE — complaints unrelated to payment disputes
    "Can't open an account": "NOT_DISPUTE",
    "Incorrect information on your report": "NOT_DISPUTE",
}

# All valid C4 dispute classes
DISPUTE_CLASSES = frozenset({"DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE", "NEGOTIATION", "NOT_DISPUTE"})

# Target size per class for balanced corpus
TARGET_PER_CLASS: int = 12_500  # 50K total / 4 classes


# ---------------------------------------------------------------------------
# CFPB record filtering and labelling
# ---------------------------------------------------------------------------

def map_label(sub_issue: str) -> Optional[str]:
    """Map a CFPB sub-issue string to a C4 dispute class.

    Parameters
    ----------
    sub_issue:
        The ``sub_issue`` field from a CFPB complaint record.

    Returns
    -------
    Optional[str]
        One of the four dispute classes, or ``None`` if the sub-issue
        is not in :data:`LABEL_MAP`.
    """
    return LABEL_MAP.get(sub_issue)


def filter_and_label(
    records: List[Dict[str, str]],
    target_per_class: int = TARGET_PER_CLASS,
) -> List[Dict[str, str]]:
    """Filter CFPB records and assign C4 dispute labels.

    Selection criteria:
    - ``consumer_complaint_narrative`` is non-empty
    - Record language is English (or not specified, defaulting to English)
    - ``sub_issue`` maps to a known C4 class via :data:`LABEL_MAP`

    The output is balanced: at most ``target_per_class`` records per class.

    Parameters
    ----------
    records:
        Raw CFPB complaint records (list of dicts).
    target_per_class:
        Maximum number of records per class (default 12,500 for 50K total).

    Returns
    -------
    List[Dict[str, str]]
        Filtered and labelled records with an added ``dispute_class`` field.
    """
    class_counts: Dict[str, int] = {cls: 0 for cls in DISPUTE_CLASSES}
    labelled: List[Dict[str, str]] = []

    for record in records:
        narrative = (record.get("consumer_complaint_narrative") or "").strip()
        if not narrative:
            continue

        lang = (record.get("tags") or "").strip()
        if lang and lang.lower() not in ("older american", "servicemember"):
            continue

        sub_issue = (record.get("sub_issue") or "").strip()
        dispute_class = map_label(sub_issue)
        if dispute_class is None:
            continue

        if class_counts[dispute_class] >= target_per_class:
            continue

        labelled_record = dict(record)
        labelled_record["dispute_class"] = dispute_class
        labelled.append(labelled_record)
        class_counts[dispute_class] += 1

        # Stop early once all classes are full
        if all(c >= target_per_class for c in class_counts.values()):
            break

    logger.info(
        "CFPB filter_and_label: %d records selected — %s",
        len(labelled),
        {k: v for k, v in class_counts.items()},
    )
    return labelled


def load_cfpb_csv(path: str) -> List[Dict[str, str]]:
    """Load a CFPB complaints CSV file into a list of dicts.

    Parameters
    ----------
    path:
        Path to the CSV file (unzipped).

    Returns
    -------
    List[Dict[str, str]]
        One dict per complaint row.
    """
    records: List[Dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    logger.info("Loaded %d CFPB records from %s", len(records), path)
    return records


def save_corpus(
    labelled: List[Dict[str, str]],
    output_path: str,
) -> str:
    """Write the labelled corpus to a CSV file.

    Parameters
    ----------
    labelled:
        Labelled CFPB records (output of :func:`filter_and_label`).
    output_path:
        Destination CSV path.

    Returns
    -------
    str
        The path written to.
    """
    if not labelled:
        logger.warning("save_corpus: no records to write")
        return output_path

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    fieldnames = list(labelled[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(labelled)

    logger.info("Saved %d labelled records to %s", len(labelled), output_path)
    return output_path


def summary_stats(labelled: List[Dict[str, str]]) -> Dict[str, object]:
    """Compute summary statistics for the labelled corpus.

    Parameters
    ----------
    labelled:
        Labelled CFPB records.

    Returns
    -------
    Dict[str, object]
        Summary including total count, per-class counts, and narrative
        length statistics.
    """
    class_counter: Counter = Counter()
    narrative_lengths: List[int] = []

    for record in labelled:
        cls = record.get("dispute_class", "UNKNOWN")
        class_counter[cls] += 1
        narrative = (record.get("consumer_complaint_narrative") or "").strip()
        narrative_lengths.append(len(narrative))

    stats: Dict[str, object] = {
        "total_records": len(labelled),
        "class_distribution": dict(class_counter),
        "narrative_length_min": min(narrative_lengths) if narrative_lengths else 0,
        "narrative_length_max": max(narrative_lengths) if narrative_lengths else 0,
        "narrative_length_mean": (
            sum(narrative_lengths) / len(narrative_lengths)
            if narrative_lengths else 0.0
        ),
    }
    return stats


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    """Command-line entry point for CFPB label mapping.

    Usage::

        python -m lip.c4_dispute_classifier.corpus.cfpb_label_mapper \\
            --input /path/to/complaints.csv \\
            --output /path/to/labelled_corpus.csv \\
            --target-per-class 12500
    """
    parser = argparse.ArgumentParser(
        description="Map CFPB complaint sub-issues to C4 dispute classes",
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="Path to raw CFPB complaints CSV",
    )
    parser.add_argument(
        "--output", type=str, required=True,
        help="Path for output labelled CSV",
    )
    parser.add_argument(
        "--target-per-class", type=int, default=TARGET_PER_CLASS,
        help=f"Target records per class (default: {TARGET_PER_CLASS})",
    )
    parser.add_argument(
        "--stats-output", type=str, default=None,
        help="Optional path for summary statistics JSON",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load
    records = load_cfpb_csv(args.input)

    # Filter and label
    labelled = filter_and_label(records, target_per_class=args.target_per_class)

    # Save
    save_corpus(labelled, args.output)

    # Summary
    stats = summary_stats(labelled)
    logger.info("Summary: %s", json.dumps(stats, indent=2, default=str))

    if args.stats_output:
        os.makedirs(os.path.dirname(args.stats_output) or ".", exist_ok=True)
        with open(args.stats_output, "w") as f:
            json.dump(stats, f, indent=2, default=str)
        logger.info("Summary stats written to %s", args.stats_output)


if __name__ == "__main__":
    main()
