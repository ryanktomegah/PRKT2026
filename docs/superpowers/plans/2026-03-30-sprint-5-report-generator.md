# Sprint 5 — P10 Report Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-format report rendering (JSON, CSV, PDF) with immutable versioning, content-hash integrity, and a methodology appendix to the P10 regulatory data product.

**Architecture:** Three new modules in `lip/p10_regulatory_data/` (report_metadata, report_renderer, methodology) produce versioned reports with SHA-256 integrity hashes. The service layer (`regulatory_service.py`) migrates from `CachedReport` to `VersionedReport`, and the router adds content negotiation (JSON/CSV/PDF) plus a `/reports/generate` endpoint.

**Tech Stack:** Python 3.14, dataclasses (frozen), hashlib (SHA-256), csv (stdlib), fpdf2 (optional), FastAPI, Pydantic, pytest, ruff

---

## Context

Session 13 of 23. Sprint 4b built the systemic risk engine. Sprint 4c exposed it via 7 REST endpoints. Sprint 5 adds report packaging — multi-format rendering with versioning and methodology documentation.

**Existing code consumed:**
- `lip/p10_regulatory_data/systemic_risk.py` — `SystemicRiskReport` (frozen dataclass, the computation output)
- `lip/p10_regulatory_data/systemic_risk.py` — `CorridorRiskSnapshot` (frozen dataclass)
- `lip/api/regulatory_service.py` — `CachedReport` (to be replaced), `RegulatoryService` class
- `lip/api/regulatory_router.py` — existing `GET /reports/{report_id}` endpoint
- `lip/api/regulatory_models.py` — `ReportResponse` Pydantic model
- `lip/p10_regulatory_data/constants.py` — P10 privacy/risk constants
- `lip/p10_regulatory_data/__init__.py` — package exports

**Spec:** `docs/superpowers/specs/2026-03-30-sprint-5-report-generator-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/p10_regulatory_data/report_metadata.py` | `VersionedReport` frozen dataclass, `ReportIntegrityError`, factory + hash verification |
| Create | `lip/p10_regulatory_data/methodology.py` | `MethodologyAppendix` — static template with 7 sections |
| Create | `lip/p10_regulatory_data/report_renderer.py` | `ReportRenderer` — JSON, CSV, PDF output |
| Modify | `lip/api/regulatory_service.py` | Migrate `CachedReport` → `VersionedReport`, add `generate_report()`, `render_report()`, `get_version_chain()` |
| Modify | `lip/api/regulatory_router.py` | Content negotiation via `format` param, new `POST /reports/generate` |
| Modify | `lip/api/regulatory_models.py` | Add `GenerateReportRequest`, update `ReportResponse` |
| Modify | `lip/p10_regulatory_data/__init__.py` | Export new classes |
| Create | `lip/tests/test_p10_report_generator.py` | ~28 TDD tests |
| Modify | `lip/tests/test_regulatory_api.py` | Update existing tests for VersionedReport migration |

---

## Task 1: Implement VersionedReport + ReportIntegrityError (TDD)

**Files:** `lip/tests/test_p10_report_generator.py` (create), `lip/p10_regulatory_data/report_metadata.py` (create)

- [ ] **Step 1: Write `TestVersionedReport` tests** (5 tests):

```python
"""
test_p10_report_generator.py — TDD tests for P10 Report Generator.

Sprint 5: Multi-format report rendering, versioning, methodology.
"""
from __future__ import annotations

import pytest


class TestVersionedReport:
    """VersionedReport immutability, hashing, and versioning."""

    @staticmethod
    def _make_report():
        """Create a SystemicRiskReport for testing."""
        from lip.p10_regulatory_data.systemic_risk import (
            CorridorRiskSnapshot,
            SystemicRiskReport,
        )

        return SystemicRiskReport(
            timestamp=1700000000.0,
            corridor_snapshots=[
                CorridorRiskSnapshot(
                    corridor="EUR-USD",
                    period_label="2029-08-01T14:00Z",
                    failure_rate=0.10,
                    total_payments=1000,
                    failed_payments=100,
                    bank_count=10,
                    trend_direction="STABLE",
                    trend_magnitude=0.0,
                    contains_stale_data=False,
                ),
            ],
            overall_failure_rate=0.10,
            highest_risk_corridor="EUR-USD",
            concentration_hhi=1.0,
            systemic_risk_score=0.10,
            stale_corridor_count=0,
            total_corridors_analyzed=1,
        )

    def test_frozen_immutability(self):
        """VersionedReport cannot be mutated after construction."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        vr = create_versioned_report(report=report)
        with pytest.raises(AttributeError):
            vr.version = "2.0"

    def test_content_hash_is_sha256(self):
        """Content hash is a 64-char hex SHA-256 digest."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        vr = create_versioned_report(report=report)
        assert len(vr.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in vr.content_hash)

    def test_deterministic_hash(self):
        """Same report produces same content hash."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        vr1 = create_versioned_report(report=report)
        vr2 = create_versioned_report(report=report)
        assert vr1.content_hash == vr2.content_hash

    def test_supersedes_chain(self):
        """Corrected report has supersedes pointing to original."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        original = create_versioned_report(report=report)
        corrected = create_versioned_report(
            report=report,
            version="1.1",
            supersedes=original.report_id,
        )
        assert corrected.supersedes == original.report_id
        assert corrected.version == "1.1"
        assert original.supersedes is None

    def test_integrity_verification_passes(self):
        """verify_integrity returns True when hash matches."""
        from lip.p10_regulatory_data.report_metadata import (
            create_versioned_report,
            verify_report_integrity,
        )

        report = self._make_report()
        vr = create_versioned_report(report=report)
        assert verify_report_integrity(vr) is True

    def test_integrity_verification_fails(self):
        """Tampered hash raises ReportIntegrityError."""
        import dataclasses

        from lip.p10_regulatory_data.report_metadata import (
            ReportIntegrityError,
            create_versioned_report,
            verify_report_integrity,
        )

        report = self._make_report()
        vr = create_versioned_report(report=report)
        # Tamper with the hash by creating a new instance with wrong hash
        tampered = dataclasses.replace(vr, content_hash="0" * 64)
        with pytest.raises(ReportIntegrityError):
            verify_report_integrity(tampered)
```

- [ ] **Step 2: Run tests (expect ImportError)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_report_generator.py::TestVersionedReport -v`

- [ ] **Step 3: Implement `report_metadata.py`**

```python
"""
report_metadata.py — Versioned regulatory report dataclass.

Sprint 5: Immutable report with content hash integrity.
Wraps SystemicRiskReport (Sprint 4b) with version tracking.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from lip.p10_regulatory_data.systemic_risk import SystemicRiskReport


class ReportIntegrityError(Exception):
    """Raised when a report's content hash does not match its stored hash."""


@dataclass(frozen=True)
class VersionedReport:
    """Immutable versioned regulatory report."""

    report_id: str
    version: str
    generated_at: float
    period_start: str
    period_end: str
    methodology_version: str
    content_hash: str
    report: SystemicRiskReport
    supersedes: Optional[str] = None       # previous version, or None
    hmac_signature: Optional[str] = None   # Sprint 6


def _compute_content_hash(report: SystemicRiskReport) -> str:
    """SHA-256 over deterministic JSON serialization of the report."""
    data = {
        "timestamp": report.timestamp,
        "overall_failure_rate": report.overall_failure_rate,
        "highest_risk_corridor": report.highest_risk_corridor,
        "concentration_hhi": report.concentration_hhi,
        "systemic_risk_score": report.systemic_risk_score,
        "stale_corridor_count": report.stale_corridor_count,
        "total_corridors_analyzed": report.total_corridors_analyzed,
        "corridor_snapshots": [
            {
                "corridor": s.corridor,
                "period_label": s.period_label,
                "failure_rate": s.failure_rate,
                "total_payments": s.total_payments,
                "failed_payments": s.failed_payments,
                "bank_count": s.bank_count,
                "trend_direction": s.trend_direction,
                "trend_magnitude": s.trend_magnitude,
                "contains_stale_data": s.contains_stale_data,
            }
            for s in report.corridor_snapshots
        ],
    }
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def create_versioned_report(
    report: SystemicRiskReport,
    version: str = "1.0",
    supersedes: Optional[str] = None,
    period_start: str = "",
    period_end: str = "",
) -> VersionedReport:
    """Factory that builds a VersionedReport with computed content hash."""
    from lip.p10_regulatory_data.methodology import MethodologyAppendix

    return VersionedReport(
        report_id=f"RPT-{uuid.uuid4().hex[:12].upper()}",
        version=version,
        generated_at=time.time(),
        period_start=period_start,
        period_end=period_end,
        methodology_version=MethodologyAppendix.VERSION,
        content_hash=_compute_content_hash(report),
        report=report,
        supersedes=supersedes,
    )


def verify_report_integrity(vr: VersionedReport) -> bool:
    """Verify content hash matches. Raises ReportIntegrityError on mismatch."""
    expected = _compute_content_hash(vr.report)
    if vr.content_hash != expected:
        raise ReportIntegrityError(
            f"Report {vr.report_id} integrity check failed: "
            f"expected {expected}, got {vr.content_hash}"
        )
    return True
```

- [ ] **Step 4: Run tests (expect PASS)**
- [ ] **Step 5: Ruff check + commit**

---

## Task 2: Implement MethodologyAppendix (TDD)

**Files:** `lip/tests/test_p10_report_generator.py` (add class), `lip/p10_regulatory_data/methodology.py` (create)

- [ ] **Step 1: Write `TestMethodologyAppendix` tests** (3 tests):

```python
class TestMethodologyAppendix:
    """Methodology appendix template tests."""

    def test_version_string(self):
        """VERSION matches expected format."""
        from lip.p10_regulatory_data.methodology import MethodologyAppendix

        assert MethodologyAppendix.VERSION == "P10-METH-v1.0"

    def test_all_seven_sections_present(self):
        """get_sections() returns all 7 methodology sections."""
        from lip.p10_regulatory_data.methodology import MethodologyAppendix

        sections = MethodologyAppendix.get_sections()
        assert len(sections) == 7
        expected_keys = [
            "data_collection",
            "corridor_failure_rate",
            "concentration_analysis",
            "contagion_simulation",
            "systemic_risk_score",
            "data_quality",
            "limitations",
        ]
        for key in expected_keys:
            assert key in sections, f"Missing section: {key}"
            assert len(sections[key]) > 50, f"Section {key} too short"

    def test_text_references_constants(self):
        """Full text references actual P10 constant values."""
        from lip.p10_regulatory_data.methodology import MethodologyAppendix

        text = MethodologyAppendix.get_text()
        # Must reference key constant values
        assert "k >= 5" in text or "k=5" in text or "k ≥ 5" in text
        assert "epsilon" in text.lower() or "ε" in text
        assert "0.25" in text  # HHI threshold
        assert "0.7" in text or "0.70" in text  # decay
```

- [ ] **Step 2: Run tests (expect ImportError)**
- [ ] **Step 3: Implement `methodology.py`**

```python
"""
methodology.py — P10 analytical methodology appendix.

Static template attached to every regulatory report. Version-tracked
independently — methodology version bumps when any analytical method changes.
"""
from __future__ import annotations

from typing import Dict


class MethodologyAppendix:
    """P10 methodology documentation template.

    Version-tracked independently from reports. When methodology changes,
    version bumps and all subsequent reports reference the new version.
    """

    VERSION = "P10-METH-v1.0"

    _SECTIONS: Dict[str, str] = {
        "data_collection": (
            "Data is collected from anonymized telemetry feeds across enrolled "
            "banks. Entity identifiers are hashed using SHA-256 with a rotating "
            "salt (365-day rotation, 30-day overlap). Corridor-level statistics "
            "are subject to k-anonymity suppression (k >= 5): corridors with "
            "fewer than 5 contributing banks are excluded from published results. "
            "Differential privacy noise (Laplace mechanism, epsilon = 0.5) is "
            "applied to failure rate statistics to prevent inference attacks."
        ),
        "corridor_failure_rate": (
            "Failure rates are computed as volume-weighted ratios of failed "
            "payments to total payments per corridor per period. Periods are "
            "1-hour windows. Trend detection compares the average failure rate "
            "over the most recent 3 periods against the prior 3 periods. A "
            "relative change exceeding +10% is classified as RISING, below "
            "-10% as FALLING, and within +/-10% as STABLE."
        ),
        "concentration_analysis": (
            "Concentration is measured using the Herfindahl-Hirschman Index "
            "(HHI) on a 0.0 to 1.0 scale, where 1.0 indicates a single "
            "corridor or jurisdiction captures all volume. The effective count "
            "equals 1/HHI. A corridor or jurisdiction is flagged as concentrated "
            "when HHI >= 0.25 (equivalent to fewer than 4 equally-sized "
            "entities). Both corridor-level and jurisdiction-level HHI are "
            "computed; jurisdictions are derived by splitting corridor pairs "
            "(e.g., EUR-USD assigns half volume to EUR, half to USD)."
        ),
        "contagion_simulation": (
            "Contagion is modeled via breadth-first search (BFS) propagation on "
            "a corridor dependency graph. Edge weights are Jaccard similarity "
            "coefficients between the bank sets of connected corridors. Stress "
            "propagates with a per-hop decay factor of 0.7 and is pruned when "
            "the propagated stress level falls below 0.05. Maximum propagation "
            "depth is 5 hops. The systemic risk score from contagion equals "
            "the volume-weighted sum of stress levels across all affected "
            "corridors, clamped to [0, 1]."
        ),
        "systemic_risk_score": (
            "The overall systemic risk score combines the volume-weighted "
            "failure rate with a concentration penalty: "
            "score = weighted_failure_rate * (1 + max(0, HHI - 0.25)), "
            "clamped to the range [0.0, 1.0]. This penalizes systems where "
            "high failure rates coincide with concentrated corridor volumes."
        ),
        "data_quality": (
            "Each corridor snapshot is flagged if it contains stale data "
            "(telemetry older than the current aggregation window). The total "
            "count of stale corridors is reported alongside the corridor count. "
            "Suppressed corridors (below k-anonymity threshold) are counted "
            "but not published. Privacy budget consumption (cumulative epsilon) "
            "is tracked per reporting cycle."
        ),
        "limitations": (
            "In the current version (v0), corridor dependency graphs use "
            "synthetic bank sets derived from shared currency zones. Real bank "
            "hash sets require live telemetry ingestion across 5+ enrolled "
            "banks. Minimum 5 banks per corridor are required for k-anonymity "
            "compliance. Correlation structure between corridors is approximated "
            "via Jaccard similarity of bank sets, which may underestimate true "
            "dependencies in corridors sharing non-bank intermediaries."
        ),
    }

    @classmethod
    def get_text(cls) -> str:
        """Full methodology text for report appendix."""
        parts = []
        for title, body in cls._SECTIONS.items():
            heading = title.replace("_", " ").title()
            parts.append(f"{heading}\n{body}")
        return "\n\n".join(parts)

    @classmethod
    def get_sections(cls) -> Dict[str, str]:
        """Methodology as named sections for JSON embedding."""
        return dict(cls._SECTIONS)
```

- [ ] **Step 4: Run tests (expect PASS)**
- [ ] **Step 5: Ruff check + commit**

---

## Task 3: Implement ReportRenderer — JSON + CSV (TDD)

**Files:** `lip/tests/test_p10_report_generator.py` (add classes), `lip/p10_regulatory_data/report_renderer.py` (create)

- [ ] **Step 1: Write `TestReportRendererJSON` tests** (4 tests):

```python
class TestReportRendererJSON:
    """JSON report rendering tests."""

    @staticmethod
    def _make_versioned_report():
        """Create a VersionedReport for testing."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        return create_versioned_report(
            report=TestVersionedReport._make_report(),
            period_start="2029-08-01T00:00Z",
            period_end="2029-08-01T23:59Z",
        )

    def test_valid_json_with_required_fields(self):
        """JSON output is valid and contains all metadata fields."""
        import json

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_json(vr)
        data = json.loads(output)
        assert data["report_id"] == vr.report_id
        assert data["version"] == vr.version
        assert data["content_hash"] == vr.content_hash
        assert data["methodology_version"] == vr.methodology_version
        assert "corridor_snapshots" in data

    def test_deterministic_ordering(self):
        """Same report produces identical JSON output."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        report = TestVersionedReport._make_report()
        # Use fixed inputs to get same hash
        vr1 = create_versioned_report(report=report)
        vr2 = create_versioned_report(report=report)
        renderer = ReportRenderer()
        # report_id and generated_at differ, but key ordering should be deterministic
        j1 = renderer.render_json(vr1)
        j2 = renderer.render_json(vr2)
        import json

        d1 = json.loads(j1)
        d2 = json.loads(j2)
        # Same keys in same order (sorted)
        assert list(d1.keys()) == list(d2.keys())

    def test_methodology_appendix_included(self):
        """JSON output includes methodology sections."""
        import json

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        data = json.loads(renderer.render_json(vr))
        assert "methodology" in data
        assert "data_collection" in data["methodology"]
        assert len(data["methodology"]) == 7

    def test_statistical_floats_rounded(self):
        """Statistical floats are rounded to 6 decimal places."""
        import json

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        data = json.loads(renderer.render_json(vr))
        # failure_rate 0.10 should round cleanly
        snapshot = data["corridor_snapshots"][0]
        fr_str = str(snapshot["failure_rate"])
        # Should have at most 6 decimal places
        if "." in fr_str:
            assert len(fr_str.split(".")[1]) <= 6
```

- [ ] **Step 2: Write `TestReportRendererCSV` tests** (4 tests):

```python
class TestReportRendererCSV:
    """CSV report rendering tests."""

    @staticmethod
    def _make_versioned_report():
        return TestReportRendererJSON._make_versioned_report()

    def test_metadata_header_comments(self):
        """CSV starts with # comment header containing metadata."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        lines = output.split("\n")
        comment_lines = [l for l in lines if l.startswith("#")]
        assert len(comment_lines) >= 3
        header_text = "\n".join(comment_lines)
        assert vr.report_id in header_text
        assert vr.content_hash in header_text

    def test_one_row_per_corridor(self):
        """Data section has one row per corridor snapshot."""
        import csv
        import io

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        # Strip comment lines and BOM
        data_lines = [l for l in output.split("\n") if l and not l.startswith("#")]
        # Remove BOM if present
        if data_lines and data_lines[0].startswith("\ufeff"):
            data_lines[0] = data_lines[0][1:]
        reader = csv.reader(io.StringIO("\n".join(data_lines)))
        rows = list(reader)
        # Header + 1 data row + 1 summary row = 3
        assert len(rows) >= 3  # header + data + summary

    def test_summary_footer_present(self):
        """CSV ends with a summary row."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        assert "SUMMARY" in output or "overall_failure_rate" in output.lower()

    def test_utf8_bom_prefix(self):
        """CSV output starts with UTF-8 BOM for Excel compatibility."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        assert output.startswith("\ufeff")
```

- [ ] **Step 3: Run tests (expect ImportError)**
- [ ] **Step 4: Implement `report_renderer.py`** — JSON and CSV only (PDF in Task 4)

```python
"""
report_renderer.py — Multi-format report rendering.

Sprint 5: JSON, CSV, PDF output from VersionedReport.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from lip.p10_regulatory_data.methodology import MethodologyAppendix
from lip.p10_regulatory_data.report_metadata import VersionedReport


class ReportRenderer:
    """Renders VersionedReport into JSON, CSV, or PDF format."""

    def render_json(self, report: VersionedReport) -> str:
        """Structured JSON — machine-readable, schema-consistent."""
        data = self._build_json_dict(report)
        return json.dumps(data, sort_keys=True, indent=2)

    def render_csv(self, report: VersionedReport) -> str:
        """Flat CSV — one row per corridor snapshot, metadata header."""
        output = io.StringIO()

        # UTF-8 BOM for Excel
        output.write("\ufeff")

        # Metadata header as comments
        output.write(f"# report_id: {report.report_id}\n")
        output.write(f"# version: {report.version}\n")
        output.write(f"# generated_at: {self._format_timestamp(report.generated_at)}\n")
        output.write(f"# methodology_version: {report.methodology_version}\n")
        output.write(f"# content_hash: {report.content_hash}\n")

        # Data rows
        writer = csv.writer(output)
        headers = [
            "corridor", "period_label", "failure_rate", "total_payments",
            "failed_payments", "bank_count", "trend_direction",
            "trend_magnitude", "contains_stale_data",
        ]
        writer.writerow(headers)

        for s in report.report.corridor_snapshots:
            writer.writerow([
                s.corridor, s.period_label,
                round(s.failure_rate, 6), s.total_payments,
                s.failed_payments, s.bank_count,
                s.trend_direction, round(s.trend_magnitude, 6),
                s.contains_stale_data,
            ])

        # Summary footer
        r = report.report
        writer.writerow([
            "SUMMARY", "", round(r.overall_failure_rate, 6), "",
            "", r.total_corridors_analyzed, r.highest_risk_corridor,
            round(r.concentration_hhi, 6), round(r.systemic_risk_score, 6),
        ])

        return output.getvalue()

    def render_pdf(self, report: VersionedReport) -> bytes:
        """Formatted PDF — title page, data tables, methodology appendix."""
        try:
            from fpdf import FPDF
        except ImportError:
            raise ImportError(
                "fpdf2 is required for PDF report generation. "
                "Install with: pip install fpdf2"
            ) from None

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title page
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 20, "Systemic Risk Report", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, f"Report ID: {report.report_id}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"Version: {report.version}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"Generated: {self._format_timestamp(report.generated_at)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"Period: {report.period_start} to {report.period_end}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

        # Executive summary
        r = report.report
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, f"Overall Failure Rate: {r.overall_failure_rate:.4f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Highest Risk Corridor: {r.highest_risk_corridor}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Systemic Risk Score: {r.systemic_risk_score:.4f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Concentration HHI: {r.concentration_hhi:.4f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Corridors Analyzed: {r.total_corridors_analyzed}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Stale Corridors: {r.stale_corridor_count}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

        # Corridor data table
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Corridor Data", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        col_widths = [30, 22, 22, 22, 22, 22, 22, 22]
        table_headers = ["Corridor", "Fail Rate", "Total", "Failed", "Banks", "Trend", "Magnitude", "Stale"]
        for i, h in enumerate(table_headers):
            pdf.cell(col_widths[i], 8, h, border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for s in r.corridor_snapshots:
            vals = [
                s.corridor, f"{s.failure_rate:.4f}", str(s.total_payments),
                str(s.failed_payments), str(s.bank_count), s.trend_direction,
                f"{s.trend_magnitude:.4f}", str(s.contains_stale_data),
            ]
            for i, v in enumerate(vals):
                pdf.cell(col_widths[i], 7, v, border=1)
            pdf.ln()
        pdf.ln(10)

        # Methodology appendix
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Methodology Appendix", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for title, body in MethodologyAppendix.get_sections().items():
            heading = title.replace("_", " ").title()
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, body)
            pdf.ln(4)

        # Integrity footer
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 6, f"Content Hash: {report.content_hash}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Methodology Version: {report.methodology_version}", new_x="LMARGIN", new_y="NEXT")

        return pdf.output()

    def _build_json_dict(self, report: VersionedReport) -> Dict[str, Any]:
        """Build the JSON-serializable dictionary."""
        r = report.report
        return {
            "report_id": report.report_id,
            "version": report.version,
            "supersedes": report.supersedes,
            "generated_at": self._format_timestamp(report.generated_at),
            "period_start": report.period_start,
            "period_end": report.period_end,
            "methodology_version": report.methodology_version,
            "content_hash": report.content_hash,
            "overall_failure_rate": round(r.overall_failure_rate, 6),
            "highest_risk_corridor": r.highest_risk_corridor,
            "concentration_hhi": round(r.concentration_hhi, 6),
            "systemic_risk_score": round(r.systemic_risk_score, 6),
            "stale_corridor_count": r.stale_corridor_count,
            "total_corridors_analyzed": r.total_corridors_analyzed,
            "corridor_snapshots": [
                {
                    "corridor": s.corridor,
                    "period_label": s.period_label,
                    "failure_rate": round(s.failure_rate, 6),
                    "total_payments": s.total_payments,
                    "failed_payments": s.failed_payments,
                    "bank_count": s.bank_count,
                    "trend_direction": s.trend_direction,
                    "trend_magnitude": round(s.trend_magnitude, 6),
                    "contains_stale_data": s.contains_stale_data,
                }
                for s in r.corridor_snapshots
            ],
            "methodology": MethodologyAppendix.get_sections(),
        }

    @staticmethod
    def _format_timestamp(ts: float) -> str:
        """Convert Unix timestamp to ISO-8601 string."""
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
```

- [ ] **Step 5: Run tests (expect PASS)**
- [ ] **Step 6: Ruff check + commit**

---

## Task 4: PDF Tests + fpdf2 Install

**Note:** The full `render_pdf` method is included in Task 3's `report_renderer.py` implementation. Task 4 adds the PDF-specific tests and installs `fpdf2`.

**Files:** `lip/tests/test_p10_report_generator.py` (add class)

- [ ] **Step 1: Install fpdf2**

Run: `pip install fpdf2`

- [ ] **Step 2: Write `TestReportRendererPDF` tests** (3 tests):

```python
class TestReportRendererPDF:
    """PDF report rendering tests."""

    @staticmethod
    def _make_versioned_report():
        return TestReportRendererJSON._make_versioned_report()

    def test_pdf_magic_bytes(self):
        """PDF output starts with %PDF magic bytes."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_pdf(vr)
        assert isinstance(output, bytes)
        assert output[:5] == b"%PDF-"

    def test_pdf_contains_metadata(self):
        """PDF contains report ID and title."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_pdf(vr)
        # PDF text is embedded in the binary — search for key strings
        text = output.decode("latin-1")
        assert "Systemic Risk Report" in text
        assert vr.report_id in text

    def test_pdf_import_error_without_fpdf2(self):
        """render_pdf raises ImportError if fpdf2 not installed."""
        from unittest.mock import patch

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        with patch.dict("sys.modules", {"fpdf": None}):
            with pytest.raises(ImportError, match="fpdf2"):
                renderer.render_pdf(vr)
```

- [ ] **Step 3: Run tests (expect PASS — fpdf2 installed in step 1)**
- [ ] **Step 4: Ruff check + commit**

---

## Task 5: Migrate Service Layer to VersionedReport (TDD)

**Files:** `lip/tests/test_p10_report_generator.py` (add class), `lip/api/regulatory_service.py` (modify), `lip/tests/test_regulatory_api.py` (update)

- [ ] **Step 1: Write `TestServiceIntegration` tests** (5 tests):

```python
class TestServiceIntegration:
    """Service layer integration with VersionedReport."""

    @staticmethod
    def _make_engine_with_data():
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        engine.ingest_results([
            AnonymizedCorridorResult(
                corridor="EUR-USD",
                period_label="2029-08-01T14:00Z",
                total_payments=1000,
                failed_payments=100,
                failure_rate=0.10,
                bank_count=10,
                k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5,
                noise_applied=True,
                stale=False,
            ),
        ])
        return engine

    def test_generate_report_produces_versioned_report(self):
        """generate_report() returns a VersionedReport."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.report_metadata import VersionedReport

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        assert isinstance(vr, VersionedReport)
        assert vr.report_id.startswith("RPT-")
        assert vr.version == "1.0"

    def test_render_report_json(self):
        """render_report with fmt='json' returns JSON string."""
        import json

        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        content, content_type = service.render_report(vr.report_id, fmt="json")
        assert content_type == "application/json"
        data = json.loads(content)
        assert data["report_id"] == vr.report_id

    def test_render_report_csv(self):
        """render_report with fmt='csv' returns CSV string."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        content, content_type = service.render_report(vr.report_id, fmt="csv")
        assert content_type == "text/csv"
        assert vr.report_id in content

    def test_stress_test_produces_versioned_report(self):
        """run_stress_test() returns VersionedReport."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.report_metadata import VersionedReport

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        report_id, vr = service.run_stress_test(
            scenario_name="test-scenario",
            shocks=[("EUR-USD", 0.9)],
        )
        assert isinstance(vr, VersionedReport)
        assert vr.report_id == report_id

    def test_version_chain_single_report(self):
        """get_version_chain returns a list containing the single report."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        chain = service.get_version_chain(vr.report_id)
        assert len(chain) == 1
        assert chain[0].report_id == vr.report_id
```

- [ ] **Step 2: Run tests (expect FAIL — service not yet updated)**

- [ ] **Step 3: Modify `lip/api/regulatory_service.py`**

Key changes:
1. Remove `CachedReport` dataclass
2. Import `VersionedReport`, `create_versioned_report`, `verify_report_integrity`, `ReportIntegrityError`
3. Import `ReportRenderer`
4. Import `MethodologyAppendix`
5. Change `_reports` type to `Dict[str, VersionedReport]`
6. Add `_renderer = ReportRenderer()` in `__init__`
7. Add `generate_report()` method — calls `_engine.compute_risk_report()`, wraps in `create_versioned_report()`, caches, returns
8. Add `render_report(report_id, fmt)` method — retrieves from cache, calls `_renderer.render_json/csv/pdf`, returns `(content, content_type)`
9. Add `get_version_chain(report_id)` — for v0, returns `[get_report(report_id)]` (single-element list). Full chain traversal via `supersedes` deferred to when corrections are implemented.
10. Update `run_stress_test()` to create `VersionedReport` via `create_versioned_report(report)` and cache it. Return type changes to `Tuple[str, VersionedReport]`.
11. Update `get_report()` to return `Optional[VersionedReport]` with integrity check via `verify_report_integrity()`
12. Update `get_metadata()` methodology_version to `MethodologyAppendix.VERSION`
13. TTL check uses `vr.generated_at` instead of `cached.created_at`

- [ ] **Step 4: Update existing tests in `lip/tests/test_regulatory_api.py`**

Update `test_run_stress_test_returns_report_and_does_not_pollute`:
- `report_id, vr = service.run_stress_test(...)` — `vr` is now `VersionedReport`
- Access underlying report: `vr.report.total_corridors_analyzed >= 2` (was `report.total_corridors_analyzed >= 1`; now 2 because stress test ingests 2 corridors EUR-USD + GBP-EUR)
- After stress test, verify engine not polluted: `after.total_corridors_analyzed == baseline_count`

Update `test_get_report_cached`:
- `cached = service.get_report(report_id)` returns `VersionedReport` not `CachedReport`
- Check `cached.report_id == report_id` (same assertion, different type)

Update `test_get_report_200`:
- `format=json` returns `render_json()` output which includes `report_id` at top level
- Existing assertion `resp.json()["report_id"] == report_id` still passes

- [ ] **Step 5: Run all tests (expect PASS)**
- [ ] **Step 6: Ruff check + commit**

---

## Task 6: Router Content Negotiation + Generate Endpoint (TDD)

**Files:** `lip/tests/test_p10_report_generator.py` (add class), `lip/api/regulatory_router.py` (modify), `lip/api/regulatory_models.py` (modify)

- [ ] **Step 1: Add `GenerateReportRequest` to `lip/api/regulatory_models.py`**

Inside the `try:` block, after `StressTestRequest`:
```python
class GenerateReportRequest(BaseModel):
    """Request body for POST /reports/generate."""
    period_start: str = ""
    period_end: str = ""
```

- [ ] **Step 2: Write `TestRouterContentNegotiation` tests** (5 tests):

```python
class TestRouterContentNegotiation:
    """Router content negotiation and generate endpoint tests."""

    @pytest.fixture()
    def client(self):
        """FastAPI test client with a seeded engine."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.rate_limiter import TokenBucketRateLimiter
        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        engine.ingest_results([
            AnonymizedCorridorResult(
                corridor="EUR-USD",
                period_label="2029-08-01T14:00Z",
                total_payments=1000,
                failed_payments=100,
                failure_rate=0.10,
                bank_count=10,
                k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5,
                noise_applied=True,
                stale=False,
            ),
        ])
        service = RegulatoryService(risk_engine=engine)
        limiter = TokenBucketRateLimiter(rate=1000, period_seconds=3600)
        app = FastAPI()
        app.include_router(
            make_regulatory_router(service, rate_limiter=limiter),
            prefix="/api/v1/regulatory",
        )
        return TestClient(app)

    def _create_report(self, client):
        """Helper: generate a report and return report_id."""
        resp = client.post(
            "/api/v1/regulatory/reports/generate",
            json={"period_start": "2029-08-01", "period_end": "2029-08-31"},
        )
        assert resp.status_code == 200
        return resp.json()["report_id"]

    def test_format_json_returns_application_json(self, client):
        """format=json returns application/json."""
        report_id = self._create_report(client)
        resp = client.get(f"/api/v1/regulatory/reports/{report_id}?format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    def test_format_csv_returns_text_csv(self, client):
        """format=csv returns text/csv."""
        report_id = self._create_report(client)
        resp = client.get(f"/api/v1/regulatory/reports/{report_id}?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert resp.text.startswith("\ufeff")

    def test_format_pdf_returns_application_pdf(self, client):
        """format=pdf returns application/pdf (if fpdf2 installed)."""
        report_id = self._create_report(client)
        resp = client.get(f"/api/v1/regulatory/reports/{report_id}?format=pdf")
        # fpdf2 may or may not be installed
        assert resp.status_code in (200, 501)
        if resp.status_code == 200:
            assert "application/pdf" in resp.headers["content-type"]
            assert resp.content[:5] == b"%PDF-"

    def test_invalid_format_returns_422(self, client):
        """Invalid format parameter returns 422."""
        report_id = self._create_report(client)
        resp = client.get(f"/api/v1/regulatory/reports/{report_id}?format=xml")
        assert resp.status_code == 422

    def test_generate_report_creates_report(self, client):
        """POST /reports/generate creates a versioned report."""
        resp = client.post(
            "/api/v1/regulatory/reports/generate",
            json={"period_start": "2029-08-01", "period_end": "2029-08-31"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_id"].startswith("RPT-")
        assert data["version"] == "1.0"
        assert "content_hash" in data
```

- [ ] **Step 3: Run tests (expect FAIL — router not updated)**

- [ ] **Step 4: Modify `lip/api/regulatory_router.py`**

Key changes:
1. Import `GenerateReportRequest` from models
2. Import `Response` from fastapi, import `json` (stdlib)
3. Import `ReportIntegrityError` from report_metadata
4. Remove `response_model=ReportResponse` from `/reports/{report_id}` route
5. Add `format` query parameter: `Query(default="json", pattern="^(json|csv|pdf)$")`
6. For `json`: call `service.render_report(report_id, "json")`, parse the JSON string, return as dict (FastAPI auto-serializes to JSONResponse). `render_json()` output includes `report_id`, `version`, `content_hash`, `corridor_snapshots`, `methodology` — a superset of the old `ReportResponse`.
7. For `csv`: return `Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={report_id}.csv"})`
8. For `pdf`: try `service.render_report(report_id, "pdf")`. Return `Response(content=pdf_bytes, media_type="application/pdf")`. If `ImportError` → HTTP 501.
9. Handle `ReportIntegrityError` → HTTP 500 with "Report integrity check failed"
10. Add `POST /reports/generate` endpoint using `GenerateReportRequest` body model. Calls `service.generate_report()`, returns report metadata dict.
11. **Update `run_stress_test` handler**: `run_stress_test()` now returns `Tuple[str, VersionedReport]`. The handler must access `vr.report.overall_failure_rate`, `vr.report.timestamp`, etc. instead of `report.overall_failure_rate`. Update the `StressTestResponse` construction accordingly.

- [ ] **Step 5: Run tests (expect PASS)**
- [ ] **Step 6: Ruff check + commit**

---

## Task 7: Exports + Full Regression + Push

- [ ] **Step 1: Update `lip/p10_regulatory_data/__init__.py`**

Add imports and `__all__` entries:
```python
from .methodology import MethodologyAppendix
from .report_metadata import ReportIntegrityError, VersionedReport, create_versioned_report, verify_report_integrity
from .report_renderer import ReportRenderer
```

- [ ] **Step 2: Update module docstring** to mention Sprint 5

- [ ] **Step 3: Run all Sprint 5 tests**

`PYTHONPATH=. python -m pytest lip/tests/test_p10_report_generator.py -v`

- [ ] **Step 4: Run Sprint 4c tests (regression)**

`PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py -v`

- [ ] **Step 5: Full regression**

`PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -k "not (test_returns_dict or test_returns_fitted or test_calibration_attaches or test_run_end_to_end)"`

- [ ] **Step 6: `ruff check lip/`** — zero errors

- [ ] **Step 7: Verify imports**

`python -c "from lip.p10_regulatory_data import VersionedReport, ReportRenderer, MethodologyAppendix; print('OK')"`

- [ ] **Step 8: Commit + push**

---

## Verification Checklist

1. [ ] `python -m pytest lip/tests/test_p10_report_generator.py -v` — all ~28 tests pass
2. [ ] `python -m pytest lip/tests/test_regulatory_api.py -v` — all 31 Sprint 4c tests still pass
3. [ ] Full regression — ~1870+ tests pass, 0 failures
4. [ ] `ruff check lip/` — zero errors
5. [ ] `python -c "from lip.p10_regulatory_data import VersionedReport, ReportRenderer; print('OK')"` — imports clean
6. [ ] QUANT: No new financial math — renderers only format existing computation output
7. [ ] CIPHER: Content hash = SHA-256 over deterministic JSON; integrity verified on retrieval
8. [ ] REX: Reports are immutable (frozen dataclass); version chain preserves full correction history
