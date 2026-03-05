"""
inference.py — C2 PD Model production inference

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np

from .fee import compute_fee_bps_from_el
from .features import UnifiedFeatureEngineer
from .lgd import estimate_lgd, lgd_for_corridor
from .model import PDModel
from .tier_assignment import hash_borrower_id, TierFeatures, assign_tier, Tier

logger = logging.getLogger(__name__)

# Module-level salt — injected at startup from secrets manager.
# Set via :func:`configure_inference_salt` before first inference call.
_INFERENCE_SALT: bytes = b"\x00" * 32  # replaced at runtime


def configure_inference_salt(salt: bytes) -> None:
    """Set the cryptographic salt used for borrower-ID hashing in inference.

    Must be called once at application startup using a salt sourced from a
    secrets manager.  Mirrors ``features.configure_salt`` but scoped to the
    inference layer so the two modules remain independently importable.

    Parameters
    ----------
    salt:
        At least 16 bytes of cryptographically random data.
    """
    global _INFERENCE_SALT  # noqa: PLW0603
    if len(salt) < 16:
        raise ValueError("Salt must be at least 16 bytes.")
    _INFERENCE_SALT = salt


class PDInferenceEngine:
    """Production inference engine for the C2 Probability of Default model.

    Wraps a trained :class:`PDModel` and a :class:`UnifiedFeatureEngineer` to
    provide a single ``predict`` entry-point.

    **Privacy contract**: raw ``tax_id`` values from the borrower dict are
    never propagated beyond this class.  All borrower identity references are
    replaced with SHA-256 hashes before being logged or returned.

    Parameters
    ----------
    model:
        Fitted :class:`PDModel` ensemble.
    feature_engineer:
        :class:`UnifiedFeatureEngineer` instance matched to the borrower's tier.
        When *auto_tier* is ``True`` (default), the engine re-derives the tier
        from the borrower dict on every call and constructs the engineer
        internally; the *feature_engineer* argument is used as a template only
        (its tier may be overridden).
    auto_tier:
        If ``True`` (default), derive tier from borrower availability flags on
        each call.  If ``False``, use the tier from the provided
        *feature_engineer* for every call.
    thin_file_pd_min:
        Lower PD bound for stress-test logging of Tier-3 predictions.
    thin_file_pd_max:
        Upper PD bound for stress-test logging of Tier-3 predictions.
    """

    def __init__(
        self,
        model: PDModel,
        feature_engineer: UnifiedFeatureEngineer,
        auto_tier: bool = True,
        thin_file_pd_min: float = 0.05,
        thin_file_pd_max: float = 0.25,
    ) -> None:
        self._model = model
        self._base_engineer = feature_engineer
        self._auto_tier = auto_tier
        self._thin_file_pd_min = thin_file_pd_min
        self._thin_file_pd_max = thin_file_pd_max

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, payment: dict, borrower: dict) -> dict:
        """Run end-to-end PD inference for a single payment / borrower pair.

        The method:
        1. Derives the tier from borrower availability flags.
        2. Engineers the 75-dimensional feature vector (with borrower IDs hashed).
        3. Runs the 5-model ensemble and obtains SHAP values.
        4. Looks up LGD from corridor jurisdictions.
        5. Derives the annualized fee in bps (≥ 300 bps floor).
        6. Returns a structured response dict.

        **Privacy**: the raw ``tax_id`` field in *borrower* is consumed only to
        produce a SHA-256 hash.  The raw value is not stored, logged, or
        returned.

        Parameters
        ----------
        payment:
            Payment-level data dict.  Expected keys include ``amount_usd``,
            ``currency_pair``, ``sending_bic``, ``receiving_bic``,
            ``timestamp``, ``corridor_failure_rate``, and optional statistics.
        borrower:
            Borrower-level data dict.  Expected to contain ``tax_id`` (hashed
            internally), data-availability flags, and optional financial /
            transaction data depending on tier.

        Returns
        -------
        dict
            PDResponse-compatible dict with the following keys:

            * ``pd_score`` (float) — PD in [0, 1].
            * ``fee_bps`` (int) — annualized fee in basis points (min 300).
            * ``lgd`` (float) — LGD as a fraction.
            * ``tier`` (int) — tier assigned to this borrower (1, 2, or 3).
            * ``shap_values`` (list of dict) — per-feature SHAP contributions.
            * ``borrower_id_hash`` (str) — SHA-256 hash of ``tax_id``.
            * ``inference_latency_ms`` (float) — wall-clock latency in ms.
        """
        t0 = time.perf_counter()

        # --- 1. Hash borrower ID immediately; never propagate raw tax_id ----
        raw_tax_id = borrower.get("tax_id", "")
        borrower_hash = hash_borrower_id(str(raw_tax_id), _INFERENCE_SALT)

        # --- 2. Tier assignment -------------------------------------------
        tier = self._resolve_tier(borrower)

        # --- 3. Feature engineering with safe borrower dict -----------------
        safe_borrower = self._sanitise_borrower(borrower, borrower_hash)
        engineer = UnifiedFeatureEngineer(tier)
        features, availability = engineer.extract(payment, safe_borrower)

        # --- 4. Model inference + SHAP -------------------------------------
        from .features import FeatureMasker  # noqa: PLC0415
        feature_names = FeatureMasker.get_full_feature_names()

        pd_score, shap_list = self._model.predict_with_shap(
            features, feature_names
        )
        pd_score_float = float(pd_score)

        # --- 5. LGD from corridor -------------------------------------------
        sending_jur = str(payment.get("sending_jurisdiction", "DEFAULT"))
        receiving_jur = str(payment.get("receiving_jurisdiction", "DEFAULT"))
        lgd_decimal = lgd_for_corridor(sending_jur, receiving_jur)
        lgd_float = float(lgd_decimal)

        # --- 6. Fee derivation ----------------------------------------------
        ead_decimal = Decimal(str(payment.get("amount_usd", 0.0)))
        fee_bps_decimal = compute_fee_bps_from_el(
            pd=Decimal(str(pd_score_float)),
            lgd=lgd_decimal,
            ead=ead_decimal,
        )
        fee_bps_int = int(fee_bps_decimal.to_integral_value())

        # --- 7. Thin-file stress-test logging --------------------------------
        if tier == Tier.TIER_3:
            self._log_thin_file_stress(pd_score_float, borrower_hash)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "pd_score": pd_score_float,
            "fee_bps": fee_bps_int,
            "lgd": lgd_float,
            "tier": int(tier),
            "shap_values": shap_list if isinstance(shap_list, list) else [shap_list],
            "borrower_id_hash": borrower_hash,
            "inference_latency_ms": round(latency_ms, 3),
        }

    def predict_batch(
        self, payments: List[dict], borrowers: List[dict]
    ) -> List[dict]:
        """Run inference on a batch of (payment, borrower) pairs.

        Iterates over pairs and calls :meth:`predict` individually.  A future
        optimisation may vectorise ensemble inference across the batch.

        Parameters
        ----------
        payments:
            List of payment dicts.
        borrowers:
            List of borrower dicts, parallel to *payments*.

        Returns
        -------
        List[dict]
            List of PDResponse-compatible dicts, one per input pair.
        """
        if len(payments) != len(borrowers):
            raise ValueError("`payments` and `borrowers` must have the same length.")

        results = []
        for pmt, brw in zip(payments, borrowers):
            results.append(self.predict(pmt, brw))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_tier(self, borrower: dict) -> Tier:
        """Derive the tier from borrower availability flags, or fall back to
        the base engineer's tier when *auto_tier* is disabled."""
        if not self._auto_tier:
            return self._base_engineer.tier

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
        return assign_tier(tf)

    @staticmethod
    def _sanitise_borrower(borrower: dict, borrower_hash: str) -> dict:
        """Return a copy of *borrower* with ``tax_id`` replaced by its hash.

        Parameters
        ----------
        borrower:
            Original borrower dict (may contain raw ``tax_id``).
        borrower_hash:
            Pre-computed SHA-256 hash of the ``tax_id``.

        Returns
        -------
        dict
            Sanitised borrower dict safe to pass to feature-engineering functions
            and include in log records.
        """
        safe = {k: v for k, v in borrower.items() if k != "tax_id"}
        safe["borrower_id_hash"] = borrower_hash
        return safe

    def _log_thin_file_stress(self, pd_score: float, borrower_hash: str) -> None:
        """Log a warning when a Tier-3 PD falls outside the spec-mandated range."""
        lo = self._thin_file_pd_min
        hi = self._thin_file_pd_max
        if not (lo <= pd_score <= hi):
            logger.warning(
                "Thin-file stress test triggered: PD %.4f outside [%.2f, %.2f] "
                "for borrower %s…",
                pd_score,
                lo,
                hi,
                borrower_hash[:8],
            )
        else:
            logger.debug(
                "Tier-3 PD %.4f in [%.2f, %.2f] — OK (borrower %s…).",
                pd_score,
                lo,
                hi,
                borrower_hash[:8],
            )
