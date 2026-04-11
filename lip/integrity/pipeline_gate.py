"""pipeline_gate.py — Pipeline-level integrity gate.

Runs at LIPPipeline construction time (NOT per inference — the 94ms SLO is
sacred). Aggregates the integrity sub-systems into a single ``check()``
method that returns an ``IntegrityGateResult``.

The gate is blocking: when integrity checks fail, ``check()`` raises
``IntegrityGateError`` so the pipeline cannot start in a degraded state.
Call ``check()`` and handle ``IntegrityGateError`` at construction time.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lip.integrity.claims_registry import ClaimsRegistry
from lip.integrity.oss_tracker import OSSAttributionRegistry

logger = logging.getLogger(__name__)


class IntegrityGateError(Exception):
    """Raised by IntegrityGate.check() when one or more integrity checks fail.

    Contains the list of issues so callers can log a structured error.
    """

    def __init__(self, issues: list[str]) -> None:
        super().__init__(f"Integrity gate failed with {len(issues)} issue(s): {issues}")
        self.issues = issues


@dataclass(frozen=True)
class IntegrityGateResult:
    gate_passed: bool
    claims_count: int
    evidence_count: int
    oss_packages_scanned: int
    oss_unattributed: list[str] = field(default_factory=list)
    gpl_contamination: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class IntegrityGate:
    """Aggregate integrity check for pipeline startup.

    Construction takes optional registries; if a registry is None, the
    corresponding check is skipped (graceful no-op for backward
    compatibility with existing tests that do not yet wire the gate).
    """

    def __init__(
        self,
        claims_registry: ClaimsRegistry | None = None,
        oss_registry: OSSAttributionRegistry | None = None,
        model_evidence_max_age_hours: int = 720,
        enabled: bool = True,
    ) -> None:
        self._claims = claims_registry
        self._oss = oss_registry
        self._max_age = timedelta(hours=model_evidence_max_age_hours)
        self.enabled = enabled

    def check(self) -> IntegrityGateResult:
        """Run all integrity checks and raise IntegrityGateError if any fail.

        Raises
        ------
        IntegrityGateError
            If one or more integrity checks fail. The gate is blocking — a
            pipeline must not start in a degraded state.
        """
        if not self.enabled:
            return IntegrityGateResult(
                gate_passed=True,
                claims_count=0,
                evidence_count=0,
                oss_packages_scanned=0,
            )

        issues: list[str] = []
        unattributed: list[str] = []
        gpl: list[str] = []
        oss_count = 0

        # OSS check
        if self._oss is not None:
            try:
                records = self._oss.scan_installed_packages()
                oss_count = len(records)
                unattributed = self._oss.validate_all_attributed(records)
                gpl_records = self._oss.check_gpl_contamination(records)
                gpl = [r.package_name for r in gpl_records]
                if gpl:
                    issues.append(f"GPL contamination detected: {gpl}")
                if unattributed:
                    issues.append(
                        f"{len(unattributed)} packages missing attribution"
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("OSS scan failed: %s", exc)
                issues.append(f"OSS scan error: {exc}")

        # Claims/evidence check (including model evidence age gate)
        claims_count = 0
        evidence_count = 0
        if self._claims is not None:
            claims_count = self._claims.claim_count()
            evidence_count = self._claims.evidence_count()

            # B1-07: enforce model_evidence_max_age_hours against registered evidence
            now = datetime.now(timezone.utc)
            for ev in self._claims._evidence.values():
                age = now - ev.created_at
                if age > self._max_age:
                    age_hours = age.total_seconds() / 3600.0
                    max_hours = self._max_age.total_seconds() / 3600.0
                    issues.append(
                        f"Evidence {ev.evidence_id!r} is {age_hours:.1f}h old "
                        f"(max {max_hours:.0f}h) — model evidence has exceeded its "
                        "freshness window."
                    )

        gate_passed = not issues
        result = IntegrityGateResult(
            gate_passed=gate_passed,
            claims_count=claims_count,
            evidence_count=evidence_count,
            oss_packages_scanned=oss_count,
            oss_unattributed=unattributed,
            gpl_contamination=gpl,
            issues=issues,
        )

        if not gate_passed:
            logger.error("Integrity gate BLOCKED pipeline startup: %s", issues)
            raise IntegrityGateError(issues)

        logger.info(
            "Integrity gate passed: %d packages, %d claims, %d evidence records",
            oss_count,
            claims_count,
            evidence_count,
        )
        return result

    def is_healthy(self) -> bool:
        """Quick health check for monitoring endpoints."""
        return self.check().gate_passed
