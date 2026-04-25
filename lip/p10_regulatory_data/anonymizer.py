"""
anonymizer.py — RegulatoryAnonymizer: 3-layer privacy pipeline.

Layer 1: Entity hashing (delegates to lip.common.encryption.hash_identifier)
Layer 2: k-Anonymity enforcement (suppression only, k >= 5)
Layer 3: Differential privacy (Laplace mechanism, epsilon = 0.5)

Architecture: P10 Blueprint Section 5 (Privacy Architecture).
QUANT authority: Laplace math, sensitivity calibration, budget arithmetic.
CIPHER authority: k-anonymity threshold, entity hashing, salt rotation.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set

import numpy as np

from .constants import (
    P10_DIFFERENTIAL_PRIVACY_EPSILON,
    P10_K_ANONYMITY_THRESHOLD,
    P10_PRIVACY_BUDGET_PER_CYCLE,
)
from .privacy_budget import PrivacyBudgetTracker
from .telemetry_schema import (
    AnonymizedCorridorResult,
    CorridorStatistic,
    PrivacyBudgetStatus,
    TelemetryBatch,
)

logger = logging.getLogger(__name__)


class PrivacyBudgetExhaustedError(RuntimeError):
    """Raised when a corridor's DP budget is exhausted and no cached result exists.

    B8-02: the anonymizer must never return raw un-noised data. If the budget
    is exhausted and no stale cached result is available, this exception is
    raised instead.
    """


class RegulatoryAnonymizer:
    """Three-layer privacy pipeline for P10 regulatory data.

    Usage::

        anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"))
        results = anon.anonymize_batch(batches)

    Thread-safety: NOT thread-safe. Callers must synchronise externally.
    """

    def __init__(
        self,
        k: int = P10_K_ANONYMITY_THRESHOLD,
        epsilon: Decimal = P10_DIFFERENTIAL_PRIVACY_EPSILON,
        budget_per_cycle: Decimal = P10_PRIVACY_BUDGET_PER_CYCLE,
        rng_seed: Optional[int] = None,
    ):
        self._k = k
        self._epsilon = epsilon
        self._budget = PrivacyBudgetTracker(budget_per_cycle=budget_per_cycle)
        self._rng = np.random.default_rng(seed=rng_seed)
        self._cache: Dict[str, AnonymizedCorridorResult] = {}
        self._suppression_count = 0
        self._total_corridors_evaluated = 0

    # -- Public Accessors ------------------------------------------------------

    @property
    def epsilon(self) -> Decimal:
        """The differential privacy epsilon parameter (public accessor)."""
        return self._epsilon

    # -- Layer 2: k-Anonymity --------------------------------------------------

    def _enforce_k_anonymity(self, corridor: str, bank_hashes: Set[str]) -> bool:
        """Return True if corridor has >= k distinct banks."""
        return len(bank_hashes) >= self._k

    # -- Layer 3: Differential Privacy -----------------------------------------

    def _apply_laplace_noise(
        self,
        value: float,
        sensitivity: float,
        rng: Optional[np.random.Generator] = None,
    ) -> float:
        """Add calibrated Laplace noise to a value.

        Noise scale b = sensitivity / epsilon.
        Result is clamped to >= 0.0 (failure rates cannot be negative).

        This method does NOT deduct from the privacy budget. The caller
        (or _apply_laplace_noise_for_corridor) handles budget accounting.
        """
        gen = rng if rng is not None else self._rng
        b = sensitivity / float(self._epsilon)
        noise = gen.laplace(loc=0.0, scale=b)
        return max(0.0, value + noise)

    def _apply_laplace_noise_for_corridor(
        self,
        corridor: str,
        value: float,
        sensitivity: float,
        rng: Optional[np.random.Generator] = None,
    ) -> float:
        """Apply Laplace noise AND deduct epsilon from corridor budget."""
        self._budget.deduct(corridor, self._epsilon)
        return self._apply_laplace_noise(value, sensitivity, rng=rng)

    # -- Full Pipeline ---------------------------------------------------------

    def anonymize_batch(
        self, batches: List[TelemetryBatch],
    ) -> List[AnonymizedCorridorResult]:
        """Full 3-layer pipeline: hash -> k-anonymity -> differential privacy.

        Steps:
          1. Group corridor statistics across all batches by corridor
          2. For each corridor, collect distinct bank_hashes
          3. Enforce k-anonymity: suppress corridors with < k banks
          4. Aggregate statistics across banks for passing corridors
          5. Apply Laplace noise to aggregate failure rate, counts
          6. If budget exhausted, return cached stale result

        Returns:
            List of AnonymizedCorridorResult, one per corridor that
            passed k-anonymity (or stale cached result if budget exhausted).
        """
        if not batches:
            return []

        # Step 1-2: Group by corridor, collect bank sets and stats
        corridor_banks: Dict[str, Set[str]] = defaultdict(set)
        corridor_stats: Dict[str, List[CorridorStatistic]] = defaultdict(list)
        period_label = self._compute_period_label(batches[0].period_start)

        for batch in batches:
            for cs in batch.corridor_statistics:
                corridor_banks[cs.corridor].add(batch.bank_hash)
                corridor_stats[cs.corridor].append(cs)

        results: List[AnonymizedCorridorResult] = []

        for corridor, bank_set in corridor_banks.items():
            self._total_corridors_evaluated += 1

            # Step 3: k-anonymity check
            if not self._enforce_k_anonymity(corridor, bank_set):
                self._suppression_count += 1
                logger.debug(
                    "k-anonymity suppression: corridor=%s bank_count=%d k=%d",
                    corridor, len(bank_set), self._k,
                )
                continue

            # Step 4: Aggregate across banks
            stats_list = corridor_stats[corridor]
            total_payments = sum(s.total_payments for s in stats_list)
            failed_payments = sum(s.failed_payments for s in stats_list)
            raw_failure_rate = (
                failed_payments / total_payments if total_payments > 0 else 0.0
            )

            # Step 5-6: Apply differential privacy (or serve stale)
            cache_key = f"{corridor}:{period_label}"

            # B8-01: sequential composition — releasing 3 noised statistics
            # costs 3*epsilon, not 1*epsilon. Check budget for the true cost.
            epsilon_per_batch = self._epsilon * 3

            if not self._budget.has_budget(corridor, epsilon_per_batch):
                # Budget exhausted: serve cached stale result
                if cache_key in self._cache:
                    stale_result = self._cache[cache_key]
                    results.append(AnonymizedCorridorResult(
                        corridor=stale_result.corridor,
                        period_label=stale_result.period_label,
                        total_payments=stale_result.total_payments,
                        failed_payments=stale_result.failed_payments,
                        failure_rate=stale_result.failure_rate,
                        bank_count=len(bank_set),
                        k_anonymity_satisfied=True,
                        privacy_budget_remaining=(
                            self._budget.get_status(corridor).budget_remaining
                        ),
                        noise_applied=stale_result.noise_applied,
                        stale=True,
                    ))
                else:
                    # B8-02: NEVER return raw un-noised data. A corridor
                    # seen for the first time after budget exhaustion has
                    # no cached noised result to serve — raising is the
                    # only privacy-safe option.
                    raise PrivacyBudgetExhaustedError(
                        f"Privacy budget exhausted for corridor {corridor} "
                        f"and no cached result available. Cannot release "
                        f"un-noised data."
                    )
                continue

            # B8-01: Apply Laplace noise to all 3 statistics, each deducting
            # epsilon via _apply_laplace_noise_for_corridor (sequential
            # composition: total cost = 3 * epsilon per batch).
            sensitivity = 1.0 / total_payments if total_payments > 0 else 1.0
            noised_rate = self._apply_laplace_noise_for_corridor(
                corridor, raw_failure_rate, sensitivity,
            )
            noised_total = max(0, round(
                self._apply_laplace_noise_for_corridor(
                    corridor, float(total_payments), 1.0,
                ),
            ))
            noised_failed = max(0, round(
                self._apply_laplace_noise_for_corridor(
                    corridor, float(failed_payments), 1.0,
                ),
            ))
            # Ensure failed <= total
            noised_failed = min(noised_failed, noised_total)

            budget_status = self._budget.get_status(corridor)
            result = AnonymizedCorridorResult(
                corridor=corridor,
                period_label=period_label,
                total_payments=noised_total,
                failed_payments=noised_failed,
                failure_rate=noised_rate,
                bank_count=len(bank_set),
                k_anonymity_satisfied=True,
                privacy_budget_remaining=budget_status.budget_remaining,
                noise_applied=True,
                stale=False,
            )
            self._cache[cache_key] = result
            results.append(result)

        return results

    # -- Budget Accessors ------------------------------------------------------

    def get_privacy_budget_status(self, corridor: str) -> PrivacyBudgetStatus:
        """Check remaining budget for a corridor."""
        return self._budget.get_status(corridor)

    def reset_budget_cycle(self) -> None:
        """Reset all corridor budgets (called every 30 days)."""
        self._budget.reset_all()
        self._cache.clear()

    # -- Suppression Metrics ---------------------------------------------------

    @property
    def suppression_rate(self) -> float:
        """Fraction of corridor/time-bucket evaluations that were suppressed."""
        if self._total_corridors_evaluated == 0:
            return 0.0
        return self._suppression_count / self._total_corridors_evaluated

    # -- Helpers ---------------------------------------------------------------

    @staticmethod
    def _compute_period_label(dt: datetime) -> str:
        """Round datetime to hourly bucket and return ISO label."""
        rounded = dt.replace(minute=0, second=0, microsecond=0)
        return rounded.strftime("%Y-%m-%dT%H:00Z")
