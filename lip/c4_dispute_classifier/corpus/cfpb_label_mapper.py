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
"""

from __future__ import annotations

import csv
import io
import logging
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
        if lang and lang.lower() not in ("", "older american", "servicemember"):
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
