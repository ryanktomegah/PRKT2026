"""Tests for lip.integrity.oss_tracker."""
from __future__ import annotations

from lip.integrity.oss_tracker import (
    DependencyRecord,
    OSSAttributionRegistry,
)


def _rec(
    name: str,
    license_spdx: str = "Apache-2.0",
    attribution: str | None = None,
) -> DependencyRecord:
    return DependencyRecord(
        package_name=name,
        version="1.0.0",
        license_spdx=license_spdx,
        attribution_text=attribution if attribution is not None else f"{name} notice",
        source_url=f"https://example.com/{name}",
        is_approved=license_spdx == "Apache-2.0",
    )


# ---------------------------------------------------------------------------


def test_scan_installed_packages_returns_non_empty():
    reg = OSSAttributionRegistry()
    records = reg.scan_installed_packages()
    assert len(records) > 0
    # pydantic should always be present (it's a project dependency)
    names = {r.package_name.lower() for r in records}
    assert "pydantic" in names


def test_detect_new_dependency_flagged():
    reg = OSSAttributionRegistry()
    previous = [_rec("requests"), _rec("pydantic")]
    current = [_rec("requests"), _rec("pydantic"), _rec("brand-new-pkg")]
    diff = reg.check_new_dependencies(current, previous)

    assert [r.package_name for r in diff.added] == ["brand-new-pkg"]
    assert diff.removed == []


def test_gpl_contamination_detected():
    reg = OSSAttributionRegistry()
    records = [
        _rec("safe-pkg", "Apache-2.0"),
        _rec("contaminated", "GPL-3.0"),
        _rec("also-bad", "AGPL-3.0"),
    ]
    contaminated = reg.check_gpl_contamination(records)
    assert {r.package_name for r in contaminated} == {"contaminated", "also-bad"}


def test_all_attributed_passes_when_complete():
    reg = OSSAttributionRegistry()
    records = [_rec("a"), _rec("b"), _rec("c")]
    assert reg.validate_all_attributed(records) == []


def test_missing_attribution_flagged():
    reg = OSSAttributionRegistry()
    records = [
        _rec("good"),
        _rec("unknown-license", license_spdx="UNKNOWN"),
        _rec("empty-attribution", attribution=""),
    ]
    missing = reg.validate_all_attributed(records)
    assert sorted(missing) == ["empty-attribution", "unknown-license"]


def test_generate_attribution_file_contains_required_sections():
    reg = OSSAttributionRegistry()
    records = [
        _rec("alpha", "MIT"),
        _rec("beta", "Apache-2.0"),
    ]
    text = reg.generate_attribution_file(records)
    assert "Third-Party" in text
    assert "alpha" in text
    assert "beta" in text
    assert "MIT" in text
    assert "Apache-2.0" in text
