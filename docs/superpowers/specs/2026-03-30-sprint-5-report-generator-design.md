# Sprint 5 — P10 Report Generator Design Spec

## Goal

Add multi-format report rendering (JSON, CSV, PDF) with immutable versioning and a methodology appendix to the P10 regulatory data product. Extends Sprint 4b's `SystemicRiskReport` computation and Sprint 4c's REST API.

## Architecture

Three-layer design matching existing patterns:

```
SystemicRiskReport (Sprint 4b — computation output)
        │
        ▼
VersionedReport (Sprint 5 — adds version metadata + content hash)
        │
        ▼
ReportRenderer (Sprint 5 — JSON / CSV / PDF output)
        │
        ▼
/reports/{report_id}?format=json|csv|pdf (Sprint 4c endpoint, enhanced)
```

**Principle:** Computation stays in Sprint 4b. Sprint 5 adds packaging and presentation — no new financial math.

---

## Part 1 — VersionedReport Dataclass

### File: `lip/p10_regulatory_data/report_metadata.py`

**Naming note:** The blueprint (§7.7) uses `SystemicRiskReport` as the name for the versioned report wrapper. This spec uses `VersionedReport` for that role to avoid collision with the existing `SystemicRiskReport` computation dataclass in `systemic_risk.py`, which is a pure analytics output with no version tracking.

```python
class ReportIntegrityError(Exception):
    """Raised when a report's content hash does not match its stored hash."""

@dataclass(frozen=True)
class VersionedReport:
    """Immutable versioned regulatory report.

    Wraps SystemicRiskReport with version tracking, content integrity,
    and regulatory traceability metadata. Once generated, a report
    version is never modified — corrections produce a new version with
    a `supersedes` pointer.
    """
    report_id: str              # "RPT-{hex12}" — consistent with existing codebase
    version: str                # "1.0", "1.1" etc.
    supersedes: Optional[str]   # report_id of the version this corrects, or None
    generated_at: float         # time.time() — Unix timestamp (ISO-8601 in renderers)
    period_start: str           # ISO-8601 label for the reporting period start
    period_end: str             # ISO-8601 label for the reporting period end
    methodology_version: str    # "P10-METH-v1.0"
    content_hash: str           # SHA-256 hex digest of serialized report content
    hmac_signature: Optional[str] = None  # Sprint 6: HMAC using RegulatorSubscriptionToken key
    report: SystemicRiskReport  # the underlying computation output
```

**Note on field ordering:** `hmac_signature` (with default `None`) must appear before `report` (no default) in the actual implementation, or use `field()` to handle it. The implementer should resolve the frozen dataclass ordering constraint — placing all defaulted fields after non-defaulted ones, or using `__post_init__` with a factory function.

**Immutability contract:**
- `frozen=True` prevents attribute mutation after construction
- `content_hash` = SHA-256 over deterministic JSON serialization of the `report` field
- Hash is verified on retrieval — any corruption raises `ReportIntegrityError`

**`generated_at` type rationale:** `float` (Unix timestamp) matches the existing `SystemicRiskReport.timestamp` field. Renderers serialize this as ISO-8601 strings in JSON/CSV output. The "round floats to 6 decimal places" rule in the JSON renderer applies only to statistical floats (failure_rate, HHI, etc.), not to timestamps.

**Versioning rules:**
- First generation of a report gets version "1.0"
- If underlying data is corrected and re-generated, new version "1.1" is created with `supersedes` pointing to "1.0"
- The original version 1.0 is never deleted or modified
- Version chain is traversable: given any report_id, you can trace its full correction history

---

## Part 2 — Report Renderers

### File: `lip/p10_regulatory_data/report_renderer.py`

Three format renderers behind a unified interface:

```python
class ReportRenderer:
    """Renders VersionedReport into JSON, CSV, or PDF format."""

    def render_json(self, report: VersionedReport) -> str:
        """Structured JSON — machine-readable, schema-consistent."""

    def render_csv(self, report: VersionedReport) -> str:
        """Flat CSV — one row per corridor snapshot, metadata header."""

    def render_pdf(self, report: VersionedReport) -> bytes:
        """Formatted PDF — title page, data tables, methodology appendix."""
```

### JSON Renderer
- Deterministic key ordering (for hash stability)
- Includes full report metadata (version, content_hash, methodology_version)
- Includes methodology appendix as a nested object
- Statistical floats rounded to 6 decimal places; timestamps serialized as ISO-8601 strings

### CSV Renderer
- Comment header block (`#`) with report metadata (report_id, version, generated_at, methodology_version, content_hash)
- Column headers: corridor, period_label, failure_rate, total_payments, failed_payments, bank_count, trend_direction, trend_magnitude, contains_stale_data
- One row per `CorridorRiskSnapshot`
- Summary footer row with overall_failure_rate, concentration_hhi, systemic_risk_score
- UTF-8 BOM prefix for Excel compatibility

### PDF Renderer
- **Dependency:** `fpdf2` (pure Python, no system deps). Optional import — raises `ImportError` with clear message if not installed. Matches codebase pattern (`try/except ImportError`).
- **v0 scope:** Text + tables only. Charts deferred to Sprint 7/8 (require matplotlib + real data).
- **Structure:**
  1. Title page: "Systemic Risk Report", report_id, version, period, generated_at
  2. Executive summary: overall_failure_rate, highest_risk_corridor, systemic_risk_score, concentration_hhi
  3. Corridor data table: all snapshots with trend indicators
  4. Data quality section: stale_corridor_count, total_corridors_analyzed, suppression info
  5. Methodology appendix (full text from methodology module)
  6. Integrity footer: content_hash, methodology_version

---

## Part 3 — Methodology Appendix

### File: `lip/p10_regulatory_data/methodology.py`

Static template describing the analytical methodology. Attached to every report in all formats.

```python
class MethodologyAppendix:
    """P10 methodology documentation template.

    Version-tracked independently from reports. When methodology changes,
    version bumps and all subsequent reports reference the new version.
    """
    VERSION = "P10-METH-v1.0"

    @classmethod
    def get_text(cls) -> str:
        """Full methodology text for report appendix."""

    @classmethod
    def get_sections(cls) -> Dict[str, str]:
        """Methodology as named sections for JSON embedding."""
```

**Sections:**
1. **Data Collection** — Anonymized telemetry from enrolled banks; entity hashing (SHA-256 + rotating salt); k-anonymity threshold (k >= 5); differential privacy (epsilon = 0.5)
2. **Corridor Failure Rate Computation** — Volume-weighted failure rates per corridor; period aggregation; trend detection (RISING/FALLING/STABLE with 10% threshold over 3-period window)
3. **Concentration Analysis** — Herfindahl-Hirschman Index (HHI) on 0.0-1.0 scale; effective count = 1/HHI; concentration threshold = 0.25; corridor and jurisdiction dimensions
4. **Contagion Simulation** — BFS propagation on Jaccard-weighted corridor dependency graph; per-hop decay (0.7); stress threshold (0.05); max depth (5 hops)
5. **Systemic Risk Score** — Combined metric: weighted_failure_rate * (1 + concentration_penalty), clamped [0, 1]
6. **Data Quality** — Stale data flagging; suppression counting; privacy budget tracking
7. **Limitations** — Synthetic bank sets in v0 (real bank hash sets require live telemetry); minimum 5 banks per corridor for k-anonymity; correlation structure approximated via Jaccard similarity

---

## Part 4 — Service Layer Changes

### File: `lip/api/regulatory_service.py` (MODIFY)

**Changes:**
1. Replace `CachedReport` with `VersionedReport` storage — both `generate_report()` and `run_stress_test()` produce `VersionedReport` objects. The internal `_reports` dict stores `VersionedReport` exclusively. `CachedReport` is removed.
2. Add `generate_report()` method that creates a `VersionedReport` from engine output
3. Add `render_report(report_id, format)` method that delegates to `ReportRenderer`
4. Update `run_stress_test()` to produce `VersionedReport` instead of `CachedReport` — the return type changes from `Tuple[str, SystemicRiskReport]` to `Tuple[str, VersionedReport]`
5. Update `get_report()` to return `Optional[VersionedReport]` and verify content hash on retrieval
6. Align `get_metadata()` methodology_version string with `MethodologyAppendix.VERSION` (change `"P10-v1.0"` to `"P10-METH-v1.0"`)

**Impact on existing tests:** `lip/tests/test_regulatory_api.py` tests that reference `CachedReport` or access `.report` on the return value need updating. The file map includes this.

```python
def generate_report(self, period_start: str = "", period_end: str = "") -> VersionedReport:
    """Generate a new versioned report from current engine state."""

def render_report(self, report_id: str, fmt: str = "json") -> Tuple[str | bytes, str]:
    """Render a cached report in the requested format.
    Returns (content, content_type).
    """

def get_version_chain(self, report_id: str) -> List[VersionedReport]:
    """Trace the version history for a report."""
```

---

## Part 5 — Router Changes

### File: `lip/api/regulatory_router.py` (MODIFY)

**Changes to `/reports/{report_id}` endpoint:**
- Add `format` query parameter: `json` (default), `csv`, `pdf`
- For `csv` and `pdf` formats, the handler returns `fastapi.Response` directly, which bypasses `response_model` validation. The route decorator removes `response_model=ReportResponse` — instead, JSON responses are constructed manually or the model is applied conditionally.
- Set appropriate `Content-Type` and `Content-Disposition` headers
- If `format=pdf` and `fpdf2` is not installed, return HTTP 501 (Not Implemented)
- If content hash verification fails on retrieval, return HTTP 500 with "Report integrity check failed"

```python
@router.get("/reports/{report_id}", dependencies=deps)
async def get_report(
    report_id: str,
    format: str = Query(default="json", pattern="^(json|csv|pdf)$"),
):
```

**New endpoint: `POST /reports/generate`**

Uses a Pydantic request body (matching the existing `POST /stress-test` pattern):

```python
# In regulatory_models.py:
class GenerateReportRequest(BaseModel):
    period_start: str = ""
    period_end: str = ""

# In router:
@router.post("/reports/generate", dependencies=deps)
async def generate_report(request: GenerateReportRequest):
    """Generate a new versioned report from current engine state."""
```

---

## Part 6 — Constants

No new constants needed. Methodology references existing P10 constants from `lip/p10_regulatory_data/constants.py`.

---

## Part 7 — Testing Strategy

### File: `lip/tests/test_p10_report_generator.py`

~28 tests across 7 test classes:

**TestVersionedReport (5 tests)**
- Frozen dataclass immutability
- Content hash computed correctly (SHA-256)
- Supersedes chain construction
- Report integrity verification (hash match)
- Report integrity failure raises `ReportIntegrityError`

**TestReportRendererJSON (4 tests)**
- JSON output is valid JSON with all required fields
- Deterministic key ordering (same report → same JSON)
- Methodology appendix included
- Statistical floats rounded to 6 decimal places; timestamps as ISO-8601

**TestReportRendererCSV (4 tests)**
- CSV output has metadata header comments
- One row per corridor snapshot
- Summary footer row present
- UTF-8 BOM prefix for Excel

**TestReportRendererPDF (3 tests)**
- PDF output starts with `%PDF` magic bytes
- Contains report title and metadata
- Graceful ImportError if fpdf2 not installed

**TestMethodologyAppendix (3 tests)**
- Version string matches constant
- All 7 sections present
- Text references correct constant values

**TestServiceIntegration (4 tests)**
- `generate_report()` produces VersionedReport
- `render_report()` dispatches to correct renderer
- Version chain traversal
- Stress test reports are also VersionedReport

**TestRouterContentNegotiation (5 tests)**
- `format=json` returns application/json
- `format=csv` returns text/csv
- `format=pdf` returns application/pdf (or 501 if fpdf2 missing)
- Invalid format returns 422
- `POST /reports/generate` creates new report

### Existing test updates: `lip/tests/test_regulatory_api.py`

Tests referencing `CachedReport` or `.report` on service return values are updated for `VersionedReport`. Specifically:
- `test_run_stress_test_returns_report_and_does_not_pollute` — updated return type
- `test_get_report_cached` — updated to use `VersionedReport`
- `test_get_report_200` — updated response fields

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/p10_regulatory_data/report_metadata.py` | `VersionedReport`, `ReportIntegrityError` |
| Create | `lip/p10_regulatory_data/report_renderer.py` | `ReportRenderer` — JSON/CSV/PDF |
| Create | `lip/p10_regulatory_data/methodology.py` | `MethodologyAppendix` template |
| Modify | `lip/api/regulatory_service.py` | VersionedReport generation + rendering, remove CachedReport |
| Modify | `lip/api/regulatory_router.py` | Content negotiation, `/reports/generate`, remove response_model |
| Modify | `lip/api/regulatory_models.py` | Add `GenerateReportRequest` |
| Modify | `lip/p10_regulatory_data/__init__.py` | Export new classes |
| Create | `lip/tests/test_p10_report_generator.py` | ~28 TDD tests |
| Modify | `lip/tests/test_regulatory_api.py` | Update existing tests for VersionedReport |

---

## What's Explicitly Deferred

| Item | Deferred To | Reason |
|------|-------------|--------|
| PDF charts (matplotlib) | Sprint 7/8 | Requires real data for meaningful visualizations |
| Redis report persistence | Sprint 7 | In-memory sufficient for v0 |
| HMAC report signing | Sprint 6 | Requires RegulatorSubscriptionToken key management. `hmac_signature` field stubbed as `Optional[str] = None` on `VersionedReport` so Sprint 6 is not a breaking change. |
| Report scheduling/cron | Sprint 7 | Manual generation sufficient for v0 |

---

## Sprint 6 Integration Points

1. `VersionedReport.hmac_signature` is pre-stubbed — Sprint 6 fills it using RegulatorSubscriptionToken key
2. `ReportRenderer` interface supports adding new formats (e.g., XBRL for central bank submissions)
3. `MethodologyAppendix.VERSION` bump triggers automatic re-generation notice on next API call
