"""
test_proprietary_map_drift.py — Cross-language proprietary→ISO 20022 drift guard (B6-03).

Single source of truth is ``lip/common/proprietary_iso20022_map.json``.
This test asserts every consumer (Python event_normalizer, Go normalizer)
sees the same mapping. Hand-editing a consumer to drift from the JSON will
fail this test.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ground truth: read the JSON directly, do not import the loader.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = REPO_ROOT / "lip" / "common" / "proprietary_iso20022_map.json"


def _load_ground_truth() -> dict[str, str]:
    """Return the authoritative proprietary→ISO 20022 mapping."""
    raw = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return dict(raw["mapping"])


GROUND_MAPPING = _load_ground_truth()


# ---------------------------------------------------------------------------
# JSON shape invariants
# ---------------------------------------------------------------------------


def test_json_has_fourteen_entries():
    """Proprietary map should have 14 entries (current known set)."""
    assert len(GROUND_MAPPING) == 14, sorted(GROUND_MAPPING.keys())


def test_json_values_are_iso20022():
    """All mapped values must be ISO 20022 reason codes (4-char alpha)."""
    for key, value in GROUND_MAPPING.items():
        assert re.match(r"^[A-Z]{2}[A-Z0-9]{2}$", value), (
            f"Mapped value {value!r} for key {key!r} doesn't look like "
            "an ISO 20022 reason code."
        )


def test_json_keys_are_uppercase():
    """All proprietary keys must be uppercase."""
    for key in GROUND_MAPPING:
        assert key == key.upper(), f"Key {key!r} is not uppercase"


# ---------------------------------------------------------------------------
# Python consumer — lip.c5_streaming.event_normalizer
# ---------------------------------------------------------------------------


def test_python_event_normalizer_matches_json():
    """Python event normalizer's proprietary map must equal the JSON."""
    from lip.c5_streaming.event_normalizer import _PROPRIETARY_TO_ISO20022  # noqa: PLC0415

    assert dict(_PROPRIETARY_TO_ISO20022) == GROUND_MAPPING


# ---------------------------------------------------------------------------
# Go consumer — text-parse the Go literal map. go:embed cannot cross module
# boundaries; this drift test is the guard until the JSON is vendored into
# the Go module (Phase 2 cleanup tracked in normalizer.go).
# ---------------------------------------------------------------------------

GO_NORMALIZER_PATH = (
    REPO_ROOT / "lip" / "c5_streaming" / "go_consumer" / "normalizer.go"
)


def test_go_normalizer_proprietary_map_matches_json():
    """Parse the Go literal map and verify it equals the JSON ground truth."""
    if not GO_NORMALIZER_PATH.exists():
        pytest.skip("Go consumer source not present")

    src = GO_NORMALIZER_PATH.read_text(encoding="utf-8")

    # Find: proprietaryToISO20022 = map[string]string{ "F002": "RR04", ... }
    prop_map_re = re.compile(
        r"proprietaryToISO20022\s*=\s*map\[string\]string\s*\{([^}]+)\}",
        re.DOTALL,
    )
    m = prop_map_re.search(src)
    assert m is not None, (
        "Could not find proprietaryToISO20022 literal map in normalizer.go. "
        "If the variable was renamed, update this drift test."
    )

    body = m.group(1)
    # Parse "KEY": "VALUE" pairs
    pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body)
    go_mapping = dict(pairs)

    assert go_mapping == GROUND_MAPPING, (
        f"Go normalizer proprietary map drifted from proprietary_iso20022_map.json.\n"
        f"Missing in Go: {sorted(set(GROUND_MAPPING) - set(go_mapping))}.\n"
        f"Extra in Go: {sorted(set(go_mapping) - set(GROUND_MAPPING))}.\n"
        f"Value mismatches: {[k for k in set(go_mapping) & set(GROUND_MAPPING) if go_mapping[k] != GROUND_MAPPING[k]]}."
    )
