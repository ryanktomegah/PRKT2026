"""
tier_assignment.py — Deterministic tier assignment
C2 Spec Section 4: Three-tier framework (internalized as feature)

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

import hashlib
from dataclasses import dataclass
from enum import IntEnum


class Tier(IntEnum):
    """Credit-data richness tier controlling which feature groups are populated."""

    TIER_1 = 1  # Full financial statements + credit bureau
    TIER_2 = 2  # Transaction history only
    TIER_3 = 3  # Thin-file (minimal data available)


@dataclass
class TierFeatures:
    """Availability flags and counters used by the deterministic tier assignment rule.

    All fields are mandatory; callers must explicitly set False / 0 for missing data
    rather than passing None so the assignment rule remains purely deterministic.
    """

    has_financial_statements: bool
    has_transaction_history: bool
    has_credit_bureau: bool
    months_history: int
    transaction_count: int


def assign_tier(features: TierFeatures) -> Tier:
    """Return the deterministic tier for a borrower given their data availability.

    Assignment rules (evaluated top-down, first match wins):

    * **Tier 1** – full financial statements AND credit-bureau data present,
      with at least 24 months of history and ≥ 100 transactions recorded.
    * **Tier 2** – transaction history present, with at least 6 months of history
      and ≥ 12 transactions.
    * **Tier 3** – thin-file; all other cases.

    The function is *strictly deterministic*: identical ``TierFeatures`` values
    always produce the same ``Tier``.

    Parameters
    ----------
    features:
        ``TierFeatures`` instance populated from the borrower data availability
        check performed upstream (e.g. during data ingestion).

    Returns
    -------
    Tier
        The assigned tier for downstream feature engineering and model routing.
    """
    if (
        features.has_financial_statements
        and features.has_credit_bureau
        and features.months_history >= 24
        and features.transaction_count >= 100
    ):
        return Tier.TIER_1

    if (
        features.has_transaction_history
        and features.months_history >= 6
        and features.transaction_count >= 12
    ):
        return Tier.TIER_2

    return Tier.TIER_3


def tier_one_hot(tier: Tier) -> list:
    """Convert a ``Tier`` to a one-hot encoded list of length 3.

    Encoding:
        Tier 1 → [1, 0, 0]
        Tier 2 → [0, 1, 0]
        Tier 3 → [0, 0, 1]

    Parameters
    ----------
    tier:
        A ``Tier`` enum value.

    Returns
    -------
    list of int
        Length-3 binary list with exactly one active position.
    """
    mapping = {
        Tier.TIER_1: [1, 0, 0],
        Tier.TIER_2: [0, 1, 0],
        Tier.TIER_3: [0, 0, 1],
    }
    return mapping[tier]


def hash_borrower_id(tax_id: str, salt: bytes) -> str:
    """Return a SHA-256 hex digest of the borrower's tax identifier.

    **Privacy requirement**: raw ``tax_id`` values MUST NEVER be stored or
    logged anywhere in the pipeline.  All downstream references to a borrower
    must use the returned hash.  The ``salt`` parameter prevents rainbow-table
    attacks; use a per-deployment secret stored in a secrets manager.

    Parameters
    ----------
    tax_id:
        The raw tax / national-ID string to be hashed.
    salt:
        Cryptographic salt bytes.  Must be at least 16 bytes; sourced from a
        secrets manager and never hard-coded.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest (64 characters).
    """
    h = hashlib.sha256()
    h.update(salt)
    h.update(tax_id.encode("utf-8"))
    return h.hexdigest()
