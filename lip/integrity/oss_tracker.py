"""oss_tracker.py — Open-source attribution enforcement.

Prevents the Delve failure mode of forking an Apache 2.0 project, selling it
without attribution, and denying the OSS origin when asked. Three structural
defenses:

  1. ``scan_installed_packages`` enumerates every Python package in the
     current environment via ``importlib.metadata`` and extracts its license.

  2. ``check_gpl_contamination`` flags any GPL-family dependency that would
     contaminate BPI's commercial closed-source distribution.

  3. ``validate_all_attributed`` returns the list of packages missing an
     SPDX license identifier — CI fails on any non-empty result.

The registry is intentionally simple: it does NOT phone-home to PyPI. Every
check runs against installed metadata, so it works offline and in CI.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from typing import Iterable

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# License classification
# ---------------------------------------------------------------------------

# GPL-family licenses are incompatible with BPI's commercial closed-source
# distribution. Any dependency in this set is a contamination risk.
GPL_FAMILY: frozenset[str] = frozenset(
    {
        "GPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "LGPL-3.0-or-later",
    }
)

# Permissive licenses that REQUIRE attribution but otherwise allow commercial
# closed-source distribution. The Delve fork was Apache-2.0 — legal to
# commercialise, but the lack of attribution is what turned it into theft.
PERMISSIVE_WITH_NOTICE: frozenset[str] = frozenset(
    {
        "Apache-2.0",
        "Apache 2.0",
        "MIT",
        "MIT License",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "BSD",
    }
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DependencyRecord(BaseModel):
    """Single Python package with license + attribution metadata."""

    model_config = ConfigDict(frozen=True)

    package_name: str
    version: str
    license_spdx: str  # "UNKNOWN" if absent
    attribution_text: str  # NOTICE block; empty if missing
    source_url: str = ""
    is_approved: bool = False


@dataclass(frozen=True)
class NewDependencyDiff:
    added: list[DependencyRecord]
    removed: list[DependencyRecord]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_license(dist: importlib_metadata.Distribution) -> str:
    """Best-effort license extraction from a Distribution object.

    Tries the ``License`` and ``License-Expression`` metadata fields, then
    falls back to scanning the ``Classifier`` entries for a "License ::"
    line. Returns "UNKNOWN" if nothing is found.
    """
    md = dist.metadata
    # PEP 639: License-Expression is the preferred SPDX field
    expr = md.get("License-Expression") if md is not None else None
    if expr:
        return expr.strip()

    raw = md.get("License") if md is not None else None
    if raw and raw.strip().lower() not in {"unknown", "none", ""}:
        return raw.strip()

    # Fall back to classifier scan
    classifiers = md.get_all("Classifier") if md is not None else None
    if classifiers:
        for c in classifiers:
            if c.startswith("License ::"):
                # "License :: OSI Approved :: Apache Software License"
                return c.rsplit("::", 1)[-1].strip()
    return "UNKNOWN"


def _extract_source_url(dist: importlib_metadata.Distribution) -> str:
    md = dist.metadata
    if md is None:
        return ""
    for url in md.get_all("Project-URL") or []:
        # "Source, https://github.com/..."
        if "," in url:
            label, value = url.split(",", 1)
            if label.strip().lower() in {"source", "homepage", "repository"}:
                return value.strip()
    home = md.get("Home-page")
    return home.strip() if home else ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class OSSAttributionRegistry:
    """Scans dependencies and enforces attribution + license-compatibility."""

    def __init__(self, approved_licenses: frozenset[str] | None = None) -> None:
        self._approved = approved_licenses or PERMISSIVE_WITH_NOTICE

    # -- scanning ----------------------------------------------------------

    def scan_installed_packages(self) -> list[DependencyRecord]:
        """Return a DependencyRecord for every installed Python distribution."""
        records: list[DependencyRecord] = []
        for dist in importlib_metadata.distributions():
            md = dist.metadata
            if md is None:
                continue
            name = md.get("Name") or ""
            version = md.get("Version") or ""
            if not name:
                continue
            license_spdx = _extract_license(dist)
            records.append(
                DependencyRecord(
                    package_name=name,
                    version=version,
                    license_spdx=license_spdx,
                    attribution_text=f"{name} {version} — {license_spdx}",
                    source_url=_extract_source_url(dist),
                    is_approved=license_spdx in self._approved,
                )
            )
        # Stable ordering helps diffing in CI
        records.sort(key=lambda r: r.package_name.lower())
        return records

    # -- diffing -----------------------------------------------------------

    def check_new_dependencies(
        self,
        current: Iterable[DependencyRecord],
        previous: Iterable[DependencyRecord],
    ) -> NewDependencyDiff:
        """Return packages added or removed between two scans."""
        prev_names = {r.package_name for r in previous}
        cur_names = {r.package_name for r in current}
        added = [r for r in current if r.package_name not in prev_names]
        removed = [r for r in previous if r.package_name not in cur_names]
        return NewDependencyDiff(added=added, removed=removed)

    # -- attribution checks ------------------------------------------------

    def validate_all_attributed(
        self, records: Iterable[DependencyRecord]
    ) -> list[str]:
        """Return the list of package names missing license attribution.

        A package is "missing attribution" if its SPDX field is UNKNOWN or
        if its attribution_text is empty. Empty result = all good.
        """
        missing: list[str] = []
        for r in records:
            if (
                r.license_spdx in {"UNKNOWN", ""}
                or not r.attribution_text.strip()
            ):
                missing.append(r.package_name)
        return sorted(missing)

    # -- contamination check ----------------------------------------------

    def check_gpl_contamination(
        self, records: Iterable[DependencyRecord]
    ) -> list[DependencyRecord]:
        """Return any GPL-family dependencies that would contaminate BPI's codebase.

        BPI ships closed-source commercial software. Linking against GPL
        creates a derivative work obligation that is incompatible with the
        product's license model.
        """
        return [r for r in records if r.license_spdx in GPL_FAMILY]

    # -- attribution file generation --------------------------------------

    def generate_attribution_file(
        self, records: Iterable[DependencyRecord]
    ) -> str:
        """Generate a NOTICE/ATTRIBUTION file from the scanned records."""
        lines = [
            "# Third-Party Software Notices",
            "",
            "BPI's products incorporate the following open-source components.",
            "Each component is used under its respective license; full license",
            "text is available from the upstream source.",
            "",
        ]
        for r in sorted(records, key=lambda x: x.package_name.lower()):
            lines.append(f"## {r.package_name} {r.version}")
            lines.append(f"License: {r.license_spdx}")
            if r.source_url:
                lines.append(f"Source: {r.source_url}")
            lines.append(f"Notice: {r.attribution_text}")
            lines.append("")
        return "\n".join(lines)
