"""
aml_checker.py — Combined AML gate: sanctions → velocity → anomaly.
Architecture Spec C6: pre-offer hard-gate screening.

Execution order (all three must pass for the check to succeed):
  1. Sanctions screening (hard block on any OFAC/EU/UN hit ≥ 0.8 confidence)
  2. Velocity controls (hard block on dollar cap / count cap / concentration)
  3. Anomaly detection (soft flag only — does not block, appended to reasons)

Three-entity role mapping:
  MLO   — Machine Learning Operator
  MIPLO — Monitoring, Intelligence & Processing Lending Operator
  ELO   — Execution Lending Operator (bank-side agent, C7)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from .sanctions import SanctionsScreener
from .velocity import VelocityChecker, VelocityResult

logger = logging.getLogger(__name__)

# Path to pre-built public-domain sanctions JSON baked into the container image.
# Override via LIP_SANCTIONS_PATH env var (e.g. for local dev pointing at a
# freshly downloaded snapshot).
_DEFAULT_SANCTIONS_PATH = os.path.join(
    os.path.dirname(__file__), "data", "sanctions.json"
)

# Sentinel: distinguishes "not provided" from "explicitly None (no resolver)"
_RESOLVER_REQUIRED = object()


class ConfigurationError(Exception):
    """Raised when AMLChecker is constructed without a required configuration value.

    EPG-24: entity_name_resolver must be explicitly provided. Passing None is
    permitted only when the caller explicitly acknowledges that entity_id values
    are human-readable names (e.g. in unit tests). In production, omitting this
    argument will raise ConfigurationError at startup rather than silently passing
    BIC codes to the sanctions screener.
    """


# ---------------------------------------------------------------------------
# AMLResult
# ---------------------------------------------------------------------------

@dataclass
class AMLResult:
    """Unified outcome of the C6 AML combined gate.

    Attributes
    ----------
    passed:
        True when no hard block was triggered. False means the offer must not
        be generated.
    reason:
        Primary block reason (None when passed=True).
        One of: ``"SANCTIONS_HIT"``, ``"DOLLAR_CAP_EXCEEDED"``,
        ``"COUNT_CAP_EXCEEDED"``, ``"BENEFICIARY_CONCENTRATION_EXCEEDED"``.
    anomaly_flagged:
        True when the anomaly detector raised a soft alert.  Does not affect
        ``passed`` — the bank operator receives an advisory notification.
    triggered_rules:
        All rule identifiers that fired (hard and soft).
    sanctions_hits:
        List of sanctions hit references (empty when no hit).
    velocity_result:
        Raw VelocityResult from the velocity checker (always present).
    """

    passed: bool
    reason: Optional[str]
    anomaly_flagged: bool
    triggered_rules: List[str] = field(default_factory=list)
    sanctions_hits: List[str] = field(default_factory=list)
    velocity_result: Optional[VelocityResult] = None


# ---------------------------------------------------------------------------
# AMLChecker
# ---------------------------------------------------------------------------

class AMLChecker:
    """Combined C6 AML gate used by the LIP pipeline.

    Replaces raw ``VelocityChecker`` as the pipeline's C6 component.
    The ``check()`` method signature is intentionally compatible with the
    ``VelocityChecker.check()`` call in ``pipeline.py``:

        result = aml_checker.check(entity_id, amount, beneficiary_id)
        aml_passed = result.passed

    Parameters
    ----------
    velocity_checker:
        ``VelocityChecker`` instance (required).
    sanctions_screener:
        ``SanctionsScreener`` instance.  When ``None`` a default screener
        (mock lists) is created automatically.
    anomaly_detector:
        Optional ``AnomalyDetector`` instance.  When ``None`` anomaly
        detection is skipped.
    entity_name_resolver:
        Callable ``(entity_id: str) -> str`` that returns a human-readable entity
        name for sanctions matching (e.g. resolves BIC ``"BNPAFRPPXXX"`` to
        ``"BNP PARIBAS"``).

        **This argument is required.** Omitting it raises ``ConfigurationError``
        at construction time — passing BIC codes directly to the sanctions screener
        produces Jaccard scores of 0.0 against every sanctioned entity name and
        silently disables sanctions enforcement (EPG-24).

        Pass ``entity_name_resolver=None`` explicitly only in unit tests where
        ``entity_id`` values are already human-readable names.
    """

    def __init__(
        self,
        velocity_checker: VelocityChecker,
        sanctions_screener: Optional[SanctionsScreener] = None,
        anomaly_detector=None,
        entity_name_resolver=_RESOLVER_REQUIRED,
    ) -> None:
        # EPG-24: require explicit configuration of the name resolver.
        # Callers must either provide a resolver or pass entity_name_resolver=None
        # to explicitly acknowledge they are running without one (tests only).
        if entity_name_resolver is _RESOLVER_REQUIRED:
            raise ConfigurationError(
                "AMLChecker requires entity_name_resolver to be explicitly provided. "
                "In production, supply a callable that resolves entity_id (e.g. a BIC) "
                "to a human-readable name for sanctions screening. "
                "In unit tests where entity_id values are already human-readable, "
                "pass entity_name_resolver=None to acknowledge no resolver is needed."
            )
        if entity_name_resolver is None:
            logger.warning(
                "AMLChecker: entity_name_resolver=None — sanctions screening will use "
                "raw entity_id strings. Acceptable in tests; not acceptable in production "
                "where entity_id is a BIC code."
            )
        self._velocity = velocity_checker
        if sanctions_screener is not None:
            self._sanctions = sanctions_screener
        else:
            # Load from LIP_SANCTIONS_PATH if explicitly set (production / staging).
            # Falls back to mock data (MOCK_SANCTIONS_ENTRIES) when env var is absent
            # so unit tests continue to work without a real sanctions snapshot.
            lists_path = os.environ.get("LIP_SANCTIONS_PATH")
            if lists_path and os.path.exists(lists_path):
                self._sanctions = SanctionsScreener(lists_path=lists_path)
                logger.info("AMLChecker: loaded sanctions from %s", lists_path)
            else:
                self._sanctions = SanctionsScreener()  # mock data
        self._anomaly = anomaly_detector
        self._resolve_name = entity_name_resolver

    # ── Public API ──────────────────────────────────────────────────────────

    def check(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        entity_name: Optional[str] = None,
        beneficiary_name: Optional[str] = None,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> AMLResult:
        """Run the full C6 AML gate for a single transaction.

        Steps (in order):
          1. Sanctions — any OFAC/EU/UN hit → hard block, no further checks.
          2. Velocity  — dollar/count/concentration cap exceeded → hard block.
          3. Anomaly   — soft flag only (does not block offer generation).

        Parameters
        ----------
        entity_id:
            Sending entity identifier (used for hashing in velocity check).
        amount:
            Transaction amount in USD.
        beneficiary_id:
            Beneficiary entity identifier.
        entity_name:
            Optional plaintext entity name for sanctions fuzzy matching.
            Falls back to ``entity_id`` string when ``None``.
        beneficiary_name:
            Optional plaintext beneficiary name for sanctions screening.
        dollar_cap_override:
            Optional USD cap to use instead of the default $1M limit.
        count_cap_override:
            Optional count cap to use instead of the default 100 limit.

        Returns
        -------
        AMLResult
            Combined gate outcome.
        """
        triggered_rules: List[str] = []
        sanctions_hits: List[str] = []

        # ── Step 1: Sanctions screening ──────────────────────────────────────
        sender_name = entity_name or (
            self._resolve_name(entity_id) if self._resolve_name else entity_id
        )
        bene_name = beneficiary_name or (
            self._resolve_name(beneficiary_id) if self._resolve_name else beneficiary_id
        )

        for name in (sender_name, bene_name):
            try:
                hits = self._sanctions.screen(name)
                for hit in hits:
                    rule = f"SANCTIONS_{hit.list_name.value}_HIT"
                    triggered_rules.append(rule)
                    sanctions_hits.append(f"{hit.list_name.value}:{hit.reference}")
                    logger.warning(
                        "Sanctions hit: entity=%s list=%s ref=%s confidence=%.2f",
                        hit.entity_name_hash[:8],
                        hit.list_name.value,
                        hit.reference,
                        hit.confidence,
                    )
            except Exception as exc:
                logger.error("Sanctions screening error for entity '%s': %s", name[:16], exc)

        if sanctions_hits:
            return AMLResult(
                passed=False,
                reason="SANCTIONS_HIT",
                anomaly_flagged=False,
                triggered_rules=triggered_rules,
                sanctions_hits=sanctions_hits,
                velocity_result=None,
            )

        # ── Step 2: Velocity controls ─────────────────────────────────────────
        vel_result: VelocityResult = self._velocity.check(
            entity_id, amount, beneficiary_id,
            dollar_cap_override=dollar_cap_override,
            count_cap_override=count_cap_override,
        )

        if not vel_result.passed:
            triggered_rules.append(vel_result.reason or "VELOCITY_BLOCKED")
            logger.warning(
                "Velocity hard block: reason=%s entity_hash=%s",
                vel_result.reason,
                vel_result.entity_id_hash[:8],
            )
            return AMLResult(
                passed=False,
                reason=vel_result.reason,
                anomaly_flagged=False,
                triggered_rules=triggered_rules,
                sanctions_hits=[],
                velocity_result=vel_result,
            )

        # ── Step 3: Anomaly detection (soft flag) ─────────────────────────────
        anomaly_flagged = False
        if self._anomaly is not None:
            try:
                txn = {
                    "amount": float(amount),
                    "hour": 0,
                    "day_of_week": 0,
                    "dollar_volume_24h": float(vel_result.dollar_volume_24h),
                    "count_24h": vel_result.count_24h,
                    "beneficiary_concentration": float(
                        vel_result.beneficiary_concentration or Decimal("0")
                    ),
                }
                anomaly_result = self._anomaly.predict(txn)
                if anomaly_result.is_anomaly:
                    anomaly_flagged = True
                    triggered_rules.append("ANOMALY_SOFT_ALERT")
                    logger.info(
                        "Anomaly soft alert: entity_hash=%s score=%.4f",
                        vel_result.entity_id_hash[:8],
                        anomaly_result.anomaly_score,
                    )
            except Exception as exc:
                logger.debug("Anomaly detection skipped: %s", exc)

        # Record the transaction in the velocity window (only after passing all gates)
        try:
            self._velocity.record(entity_id, amount, beneficiary_id)
        except Exception as exc:
            logger.error("Failed to record velocity event: %s", exc)

        return AMLResult(
            passed=True,
            reason=None,
            anomaly_flagged=anomaly_flagged,
            triggered_rules=triggered_rules,
            sanctions_hits=[],
            velocity_result=vel_result,
        )
