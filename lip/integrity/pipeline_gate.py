"""pipeline_gate.py — Pipeline-level integrity gate.

Runs at LIPPipeline construction time (NOT per inference — the 94ms SLO is
sacred). Aggregates the integrity sub-systems into a single ``check()``
method that returns an ``IntegrityGateResult``. v1 is warn-only: failures
log a warning but do not block pipeline startup. Future work: convert to
hard-block once all components have been migrated.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from lip.integrity.claims_registry import ClaimsRegistry
from lip.integrity.oss_tracker import OSSAttributionRegistry

logger = logging.getLogger(__name__)


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
        """Run all integrity checks. Always returns a result; never raises."""
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

        # Claims/evidence check
        claims_count = 0
        evidence_count = 0
        if self._claims is not None:
            claims_count = self._claims.claim_count()
            evidence_count = self._claims.evidence_count()

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
            logger.warning("Integrity gate failed: %s", issues)
        else:
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
