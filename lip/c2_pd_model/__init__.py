"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

Public API for the LIP C2 PD Model component.

Exposes:
    PDModel               — 5× LightGBM ensemble for Probability of Default.
    TierAssignment        — Deterministic three-tier assignment helper.
    run_inference         — Convenience function for single-payment PD inference.
    compute_fee           — Compute the per-cycle bridge-loan fee from PD/LGD inputs.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from .features import UnifiedFeatureEngineer
from .fee import compute_fee_bps_from_el, compute_loan_fee
from .inference import PDInferenceEngine, configure_inference_salt
from .lgd import estimate_lgd, lgd_for_corridor
from .model import PDModel
from .tier_assignment import (
    Tier,
    TierFeatures,
    assign_tier,
    hash_borrower_id,
    tier_one_hot,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PDModel",
    "TierAssignment",
    "run_inference",
    "compute_fee",
    # Lower-level helpers re-exported for convenience
    "Tier",
    "TierFeatures",
    "assign_tier",
    "tier_one_hot",
    "hash_borrower_id",
    "UnifiedFeatureEngineer",
    "PDInferenceEngine",
    "estimate_lgd",
    "lgd_for_corridor",
    "compute_fee_bps_from_el",
    "compute_loan_fee",
    "configure_inference_salt",
]


# ---------------------------------------------------------------------------
# TierAssignment — convenience wrapper
# ---------------------------------------------------------------------------


class TierAssignment:
    """Stateless helper exposing the C2 Spec Section 4 tier-assignment rules.

    All methods delegate to the functions in :mod:`lip.c2_pd_model.tier_assignment`.

    Examples
    --------
    >>> ta = TierAssignment()
    >>> features = TierFeatures(
    ...     has_financial_statements=True,
    ...     has_transaction_history=True,
    ...     has_credit_bureau=True,
    ...     months_history=36,
    ...     transaction_count=250,
    ... )
    >>> ta.assign(features)
    <Tier.TIER_1: 1>
    >>> ta.one_hot(Tier.TIER_1)
    [1, 0, 0]
    """

    @staticmethod
    def assign(features: TierFeatures) -> Tier:
        """Return the deterministic tier for *features*."""
        return assign_tier(features)

    @staticmethod
    def one_hot(tier: Tier) -> list:
        """Return a length-3 one-hot list for *tier*."""
        return tier_one_hot(tier)

    @staticmethod
    def hash_id(tax_id: str, salt: bytes) -> str:
        """Return the SHA-256 hex digest of *tax_id* + *salt*."""
        return hash_borrower_id(tax_id, salt)


# ---------------------------------------------------------------------------
# run_inference — convenience function
# ---------------------------------------------------------------------------


def run_inference(
    model: PDModel,
    payment: dict,
    borrower: dict,
    salt: Optional[bytes] = None,
) -> dict:
    """Convenience wrapper: run end-to-end PD inference for one payment.

    Constructs an ephemeral :class:`PDInferenceEngine`, applies the inference
    salt (required for production; defaults to a zero-byte placeholder in
    non-production environments), and returns the full PDResponse dict.

    Parameters
    ----------
    model:
        Fitted :class:`PDModel` ensemble.
    payment:
        Payment-level data dict (see :meth:`PDInferenceEngine.predict`).
    borrower:
        Borrower-level data dict.  The ``tax_id`` field is hashed internally.
    salt:
        Cryptographic salt for borrower-ID hashing.  Should be sourced from a
        secrets manager in production.  If ``None``, a zero-byte placeholder
        is used and a warning is emitted.

    Returns
    -------
    dict
        PDResponse-compatible dict — see :meth:`PDInferenceEngine.predict`.
    """
    if salt is None:
        logger.warning(
            "run_inference called without an explicit salt. "
            "Using zero-byte placeholder — NOT suitable for production."
        )
        salt = b"\x00" * 32

    configure_inference_salt(salt)

    # Derive tier to construct the feature engineer
    tf = TierFeatures(
        has_financial_statements=bool(
            borrower.get("has_financial_statements", False)
        ),
        has_transaction_history=bool(
            borrower.get("has_transaction_history", False)
        ),
        has_credit_bureau=bool(borrower.get("has_credit_bureau", False)),
        months_history=int(borrower.get("months_history", 0)),
        transaction_count=int(borrower.get("transaction_count", 0)),
    )
    tier = assign_tier(tf)
    engineer = UnifiedFeatureEngineer(tier)

    engine = PDInferenceEngine(model, engineer, auto_tier=True)
    return engine.predict(payment, borrower)


# ---------------------------------------------------------------------------
# compute_fee — convenience function
# ---------------------------------------------------------------------------


def compute_fee(
    pd: float,
    lgd: float,
    loan_amount: float,
    days_funded: int,
    ead: Optional[float] = None,
) -> dict:
    """Derive the annualized fee bps and the actual per-cycle cash fee.

    Thin wrapper combining :func:`compute_fee_bps_from_el` and
    :func:`compute_loan_fee` into a single call for convenience.

    Parameters
    ----------
    pd:
        Probability of Default (float in ``[0, 1]``).
    lgd:
        Loss Given Default (float in ``[0, 1]``).
    loan_amount:
        Notional bridge-loan amount (in the base currency, e.g. USD).
    days_funded:
        Number of calendar days the loan is outstanding.
    ead:
        Exposure at Default; defaults to *loan_amount* when ``None``.

    Returns
    -------
    dict
        * ``fee_bps`` (Decimal) — annualized fee in basis points (≥ 300).
        * ``loan_fee`` (Decimal) — actual per-cycle cash fee rounded to cents.
        * ``floor_applied`` (bool) — ``True`` when 300 bps floor was binding.

    Examples
    --------
    >>> result = compute_fee(pd=0.01, lgd=0.35, loan_amount=1_000_000, days_funded=7)
    >>> result['fee_bps']
    Decimal('300.0')
    >>> result['floor_applied']
    True
    """
    if ead is None:
        ead = loan_amount

    pd_d = Decimal(str(pd))
    lgd_d = Decimal(str(lgd))
    ead_d = Decimal(str(ead))
    loan_d = Decimal(str(loan_amount))

    fee_bps = compute_fee_bps_from_el(pd_d, lgd_d, ead_d)
    loan_fee = compute_loan_fee(loan_d, fee_bps, days_funded)

    from .fee import verify_floor_applies  # noqa: PLC0415

    return {
        "fee_bps": fee_bps,
        "loan_fee": loan_fee,
        "floor_applied": verify_floor_applies(fee_bps),
    }
