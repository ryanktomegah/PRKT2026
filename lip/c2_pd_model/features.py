"""
features.py — Universal + Tier 1/2/3 feature engineering with masking
C2 Spec Sections 5-6: Availability indicators for every optional feature group

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

import math
from typing import Tuple

import numpy as np

from .tier_assignment import Tier

# ---------------------------------------------------------------------------
# Feature-name registries
# ---------------------------------------------------------------------------

UNIVERSAL_FEATURE_NAMES: list = [
    "amount_usd",
    "days_since_last_payment",
    "currency_pair_encoded",
    "sending_bic_hash",
    "receiving_bic_hash",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    "amount_log",
    "amount_zscore",
    "corridor_failure_rate",
    "corridor_volume_7d",
    "n_payments_30d",
    "n_failures_30d",
    "counterparty_age_days",
    "amount_percentile",
    "is_large_amount",
    "is_round_amount",
    "payment_velocity_24h",
]

TIER1_FEATURE_NAMES: list = [
    "current_ratio",
    "debt_to_equity",
    "interest_coverage",
    "roe",
    "roa",
    "ebitda_margin",
    "revenue_growth",
    "cash_ratio",
    "asset_turnover",
    "net_margin",
    "altman_z_score",
    "merton_distance_to_default",
    "credit_bureau_score",
    "credit_bureau_age",
    "payment_history_score",
    "avg_days_to_pay",
    "delinquency_rate",
    "default_history_count",
    "bankruptcy_history",
    "industry_risk_score",
]

TIER2_FEATURE_NAMES: list = [
    "avg_payment_amount",
    "payment_amount_std",
    "payment_frequency",
    "recent_trend_slope",
    "largest_payment_30d",
    "smallest_payment_30d",
    "payment_gap_max_days",
    "payment_gap_mean_days",
    "counterparty_diversity",
    "payment_regularity_score",
]

TIER3_FEATURE_NAMES: list = [
    "thin_file_amount_proxy",
    "thin_file_corridor_risk",
    "thin_file_jurisdiction_score",
    "thin_file_entity_age_days",
    "thin_file_currency_risk",
]

# One availability flag per optional feature group (Tier 1 groups × 4 + Tier 2 groups × 2 + …).
# Defined as 20 binary indicators matching feature groups used in the masker.
AVAILABILITY_INDICATORS: list = [
    "avail_financial_statements",
    "avail_credit_bureau",
    "avail_payment_history",
    "avail_altman_inputs",
    "avail_merton_inputs",
    "avail_industry_data",
    "avail_delinquency_history",
    "avail_tax_records",
    "avail_audit_data",
    "avail_bank_statements",
    "avail_transaction_history_6m",
    "avail_transaction_history_12m",
    "avail_counterparty_network",
    "avail_payment_frequency_data",
    "avail_amount_statistics",
    "avail_corridor_statistics",
    "avail_thin_file_proxy",
    "avail_jurisdiction_data",
    "avail_entity_registry",
    "avail_currency_risk_data",
]

# Slice indices into the flat 75-dimensional feature vector
_UNIVERSAL_START = 0
_UNIVERSAL_END = 20  # exclusive
_TIER1_START = 20
_TIER1_END = 40
_TIER2_START = 40
_TIER2_END = 50
_TIER3_START = 50
_TIER3_END = 55
_AVAIL_START = 55
_AVAIL_END = 75

FEATURE_DIM = 75  # 20 + 20 + 10 + 5 + 20


# ---------------------------------------------------------------------------
# FeatureMasker
# ---------------------------------------------------------------------------


class FeatureMasker:
    """Zeros out feature slots that are unavailable for a given tier and sets
    the corresponding availability indicators accordingly.

    The masker operates on the *full* 75-dimensional feature vector so that the
    downstream model always receives a consistently shaped input regardless of
    tier.
    """

    @staticmethod
    def mask_unavailable(
        features: np.ndarray,
        tier: Tier,
        available_groups: list,
    ) -> np.ndarray:
        """Zero-out feature slots that are structurally unavailable for *tier*
        and reflect availability in the indicator slice.

        Parameters
        ----------
        features:
            Float array of shape ``(75,)`` or ``(N, 75)``.  Modified in-place
            (a copy is made internally so the original is not mutated).
        tier:
            Assigned tier that determines which optional feature groups to mask.
        available_groups:
            List of group-name strings (drawn from ``AVAILABILITY_INDICATORS``)
            that are actually populated for this observation.  Everything not
            listed is zeroed.

        Returns
        -------
        np.ndarray
            Masked feature array with the same shape as input.
        """
        out = features.copy().astype(np.float64)
        batch = out.ndim == 2

        def _zero(start: int, end: int) -> None:
            if batch:
                out[:, start:end] = 0.0
            else:
                out[start:end] = 0.0

        def _set_avail(idx: int, val: float) -> None:
            avail_idx = _AVAIL_START + idx
            if batch:
                out[:, avail_idx] = val
            else:
                out[avail_idx] = val

        # Tier 1 block — only populated when tier == TIER_1
        if tier != Tier.TIER_1:
            _zero(_TIER1_START, _TIER1_END)

        # Tier 2 block — populated for TIER_1 and TIER_2
        if tier == Tier.TIER_3:
            _zero(_TIER2_START, _TIER2_END)

        # Tier 3 (thin-file) block — only populated when tier == TIER_3
        if tier != Tier.TIER_3:
            _zero(_TIER3_START, _TIER3_END)

        # Sync availability indicators with the provided group list
        available_set = set(available_groups)
        for i, indicator_name in enumerate(AVAILABILITY_INDICATORS):
            _set_avail(i, 1.0 if indicator_name in available_set else 0.0)

        return out

    @staticmethod
    def get_full_feature_names() -> list:
        """Return the ordered list of all 75 feature names.

        Returns
        -------
        list of str
            Length-75 list covering universal features, tier-specific features,
            and availability indicators.
        """
        return (
            UNIVERSAL_FEATURE_NAMES
            + TIER1_FEATURE_NAMES
            + TIER2_FEATURE_NAMES
            + TIER3_FEATURE_NAMES
            + AVAILABILITY_INDICATORS
        )


# ---------------------------------------------------------------------------
# UnifiedFeatureEngineer
# ---------------------------------------------------------------------------

# Module-level salt placeholder — in production this is injected from a secrets
# manager at startup and never hard-coded.
_DEFAULT_SALT = b"\x00" * 32  # overridden at runtime via configure_salt()
_CONFIGURED_SALT: bytes = _DEFAULT_SALT


def configure_salt(salt: bytes) -> None:
    """Set the cryptographic salt used for borrower-ID hashing.

    Must be called once at application startup before any
    ``UnifiedFeatureEngineer`` instances are used.  The salt should be sourced
    from a secrets manager (e.g. AWS Secrets Manager, HashiCorp Vault).

    Parameters
    ----------
    salt:
        At least 16 bytes of cryptographically random data.
    """
    global _CONFIGURED_SALT  # noqa: PLW0603
    if len(salt) < 16:
        raise ValueError("Salt must be at least 16 bytes.")
    _CONFIGURED_SALT = salt


class UnifiedFeatureEngineer:
    """Extracts and assembles the full 75-dimensional feature vector from raw
    payment and borrower dictionaries.

    The vector layout is:
        [0:20]  Universal features  (all tiers)
        [20:40] Tier-1 features     (zeroed for Tier 2/3)
        [40:50] Tier-2 features     (zeroed for Tier 3)
        [50:55] Tier-3 features     (zeroed for Tier 1/2)
        [55:75] Availability flags  (per optional feature group)

    Parameters
    ----------
    tier:
        Tier assigned to the borrower being processed.
    """

    def __init__(self, tier: Tier) -> None:
        self.tier = tier
        self._masker = FeatureMasker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self, payment: dict, borrower: dict
    ) -> Tuple[np.ndarray, list]:
        """Build the 75-dimensional feature vector for a single observation.

        Borrower ID fields are hashed with SHA-256 before use; raw tax IDs are
        never stored or passed further downstream.

        Parameters
        ----------
        payment:
            Dict with keys such as ``amount_usd``, ``currency_pair``,
            ``sending_bic``, ``receiving_bic``, ``timestamp``,
            ``corridor_failure_rate``, ``corridor_volume_7d``,
            ``n_payments_30d``, ``n_failures_30d``, ``amount_zscore``,
            ``amount_percentile``, ``payment_velocity_24h``, etc.
        borrower:
            Dict with keys such as ``tax_id``, ``counterparty_age_days``,
            and optionally financial-statement / transaction-history fields.

        Returns
        -------
        Tuple[np.ndarray, list]
            * ``features`` — float64 array of shape ``(75,)``
            * ``availability_indicators`` — list of available group names drawn
              from ``AVAILABILITY_INDICATORS``
        """
        vec = np.zeros(FEATURE_DIM, dtype=np.float64)
        available_groups: list = []

        # ---- Universal features [0:20] --------------------------------
        self._fill_universal(vec, payment, borrower)

        # ---- Tier-specific features -----------------------------------
        if self.tier == Tier.TIER_1:
            available_groups = self._fill_tier1(vec, borrower)
        elif self.tier == Tier.TIER_2:
            available_groups = self._fill_tier2(vec, borrower)
        else:
            available_groups = self._fill_tier3(vec, payment, borrower)

        # ---- Mask and set availability indicators ---------------------
        masked = self._masker.mask_unavailable(vec, self.tier, available_groups)
        return masked, available_groups

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        """Coerce a value to float, returning *default* on failure."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _fill_universal(self, vec: np.ndarray, payment: dict, borrower: dict) -> None:
        """Populate the universal feature slice [0:20]."""
        sf = self._safe_float

        amount_usd = sf(payment.get("amount_usd", 0.0))
        vec[0] = amount_usd
        vec[1] = sf(payment.get("days_since_last_payment", 0.0))

        # Currency-pair encoded as a stable deterministic integer fingerprint
        cp = str(payment.get("currency_pair", ""))
        vec[2] = float(
            int.from_bytes(cp.encode()[:4].ljust(4, b"\x00"), "big") % 10_000
        )

        # BIC hashes — stable numeric fingerprints, no raw values stored
        sending_bic = str(payment.get("sending_bic", ""))
        receiving_bic = str(payment.get("receiving_bic", ""))
        vec[3] = float(
            int.from_bytes(
                sending_bic.encode()[:4].ljust(4, b"\x00"), "big"
            ) % 100_000
        )
        vec[4] = float(
            int.from_bytes(
                receiving_bic.encode()[:4].ljust(4, b"\x00"), "big"
            ) % 100_000
        )

        # Temporal features
        import datetime  # noqa: PLC0415 — intentional late import
        ts = payment.get("timestamp")
        if isinstance(ts, datetime.datetime):
            dt = ts
        elif isinstance(ts, (int, float)):
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        else:
            dt = datetime.datetime.now(tz=datetime.timezone.utc)

        vec[5] = float(dt.hour)
        vec[6] = float(dt.weekday())
        vec[7] = float(dt.month)
        vec[8] = 1.0 if dt.weekday() >= 5 else 0.0

        # Derived amount features
        vec[9] = math.log1p(max(amount_usd, 0.0))
        vec[10] = sf(payment.get("amount_zscore", 0.0))

        # Corridor statistics
        vec[11] = sf(payment.get("corridor_failure_rate", 0.0))
        vec[12] = sf(payment.get("corridor_volume_7d", 0.0))

        # Payment history counters
        vec[13] = sf(payment.get("n_payments_30d", 0.0))
        vec[14] = sf(payment.get("n_failures_30d", 0.0))

        # Counterparty age
        vec[15] = sf(borrower.get("counterparty_age_days", 0.0))

        # Amount percentile and flags
        vec[16] = sf(payment.get("amount_percentile", 0.5))
        large_threshold = sf(payment.get("large_amount_threshold", 1_000_000.0))
        vec[17] = 1.0 if amount_usd >= large_threshold else 0.0
        vec[18] = 1.0 if (amount_usd % 1000 == 0 and amount_usd > 0) else 0.0
        vec[19] = sf(payment.get("payment_velocity_24h", 0.0))

    def _fill_tier1(self, vec: np.ndarray, borrower: dict) -> list:
        """Populate Tier-1 feature slice [20:40] and return available groups."""
        sf = self._safe_float
        available: list = []

        # Financial statement ratios
        fin = borrower.get("financial_statements", {})
        if fin:
            vec[20] = sf(fin.get("current_ratio", 0.0))
            vec[21] = sf(fin.get("debt_to_equity", 0.0))
            vec[22] = sf(fin.get("interest_coverage", 0.0))
            vec[23] = sf(fin.get("roe", 0.0))
            vec[24] = sf(fin.get("roa", 0.0))
            vec[25] = sf(fin.get("ebitda_margin", 0.0))
            vec[26] = sf(fin.get("revenue_growth", 0.0))
            vec[27] = sf(fin.get("cash_ratio", 0.0))
            vec[28] = sf(fin.get("asset_turnover", 0.0))
            vec[29] = sf(fin.get("net_margin", 0.0))
            available += [
                "avail_financial_statements",
                "avail_audit_data",
                "avail_bank_statements",
            ]

        # Altman / Merton structural models
        altman = borrower.get("altman_z_score")
        if altman is not None:
            vec[30] = sf(altman)
            available.append("avail_altman_inputs")

        merton = borrower.get("merton_distance_to_default")
        if merton is not None:
            vec[31] = sf(merton)
            available.append("avail_merton_inputs")

        # Credit bureau
        bureau = borrower.get("credit_bureau", {})
        if bureau:
            vec[32] = sf(bureau.get("score", 0.0))
            vec[33] = sf(bureau.get("age_months", 0.0))
            vec[34] = sf(bureau.get("payment_history_score", 0.0))
            vec[35] = sf(bureau.get("avg_days_to_pay", 0.0))
            vec[36] = sf(bureau.get("delinquency_rate", 0.0))
            vec[37] = sf(bureau.get("default_history_count", 0.0))
            vec[38] = 1.0 if bureau.get("bankruptcy_history", False) else 0.0
            available += [
                "avail_credit_bureau",
                "avail_payment_history",
                "avail_delinquency_history",
            ]

        # Industry risk
        industry_risk = borrower.get("industry_risk_score")
        if industry_risk is not None:
            vec[39] = sf(industry_risk)
            available += ["avail_industry_data", "avail_tax_records"]

        return available

    def _fill_tier2(self, vec: np.ndarray, borrower: dict) -> list:
        """Populate Tier-2 feature slice [40:50] and return available groups."""
        sf = self._safe_float
        available: list = []

        txn = borrower.get("transaction_history", {})
        if txn:
            vec[40] = sf(txn.get("avg_payment_amount", 0.0))
            vec[41] = sf(txn.get("payment_amount_std", 0.0))
            vec[42] = sf(txn.get("payment_frequency", 0.0))
            vec[43] = sf(txn.get("recent_trend_slope", 0.0))
            vec[44] = sf(txn.get("largest_payment_30d", 0.0))
            vec[45] = sf(txn.get("smallest_payment_30d", 0.0))
            vec[46] = sf(txn.get("payment_gap_max_days", 0.0))
            vec[47] = sf(txn.get("payment_gap_mean_days", 0.0))
            vec[48] = sf(txn.get("counterparty_diversity", 0.0))
            vec[49] = sf(txn.get("payment_regularity_score", 0.0))
            available += [
                "avail_transaction_history_6m",
                "avail_transaction_history_12m",
                "avail_counterparty_network",
                "avail_payment_frequency_data",
                "avail_amount_statistics",
                "avail_corridor_statistics",
            ]

        return available

    def _fill_tier3(
        self, vec: np.ndarray, payment: dict, borrower: dict
    ) -> list:
        """Populate Tier-3 (thin-file) feature slice [50:55] and return available groups."""
        sf = self._safe_float
        available: list = []

        vec[50] = sf(payment.get("amount_usd", 0.0))
        vec[51] = sf(payment.get("corridor_failure_rate", 0.0))
        vec[52] = sf(borrower.get("jurisdiction_risk_score", 0.5))
        vec[53] = sf(borrower.get("entity_age_days", 0.0))
        vec[54] = sf(payment.get("currency_risk_score", 0.5))

        available += [
            "avail_thin_file_proxy",
            "avail_jurisdiction_data",
            "avail_entity_registry",
            "avail_currency_risk_data",
        ]

        return available

    # ------------------------------------------------------------------
    # Batch convenience
    # ------------------------------------------------------------------

    def extract_batch(
        self, payments: list, borrowers: list
    ) -> Tuple[np.ndarray, list]:
        """Extract features for a batch of observations.

        Parameters
        ----------
        payments:
            List of payment dicts.
        borrowers:
            List of borrower dicts, parallel to *payments*.

        Returns
        -------
        Tuple[np.ndarray, list]
            * Float64 array of shape ``(N, 75)``
            * List of availability-indicator lists, one per observation.
        """
        if len(payments) != len(borrowers):
            raise ValueError("payments and borrowers must have the same length.")

        rows = []
        avails = []
        for pmt, brw in zip(payments, borrowers):
            feat, avail = self.extract(pmt, brw)
            rows.append(feat)
            avails.append(avail)

        return np.vstack(rows), avails
