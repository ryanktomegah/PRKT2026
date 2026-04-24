"""
runtime.py — Shared runtime helpers for C8 license enforcement.

These helpers let service entrypoints opt into boot-time license validation
without hard-wiring the validator into every test environment.
"""
from __future__ import annotations

import os
from typing import Optional

from lip.c7_execution_agent.kill_switch import KillSwitch

from .boot_validator import LicenseBootValidator
from .license_token import LicenseeContext


def license_validation_enabled() -> bool:
    """Return True when runtime component boot validation is enforced."""
    raw = os.environ.get("LIP_ENFORCE_LICENSE_VALIDATION", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def enforce_component_license(
    required_component: str,
    kill_switch: Optional[KillSwitch] = None,
) -> Optional[LicenseeContext]:
    """Validate the configured license token for *required_component*.

    Returns the derived ``LicenseeContext`` when validation is enabled and
    succeeds. Returns ``None`` when boot validation is disabled for the
    current runtime.

    Raises:
        RuntimeError: If validation is enabled and the token/key are missing,
            invalid, expired, or fail component authorization.
    """
    if not license_validation_enabled():
        return None

    runtime_kill_switch = kill_switch or KillSwitch()
    validator = LicenseBootValidator(
        runtime_kill_switch,
        required_component=required_component,
    )
    context = validator.validate()
    if context is None or runtime_kill_switch.is_active():
        raise RuntimeError(
            f"C8 license validation failed for component {required_component}"
        )
    return context
