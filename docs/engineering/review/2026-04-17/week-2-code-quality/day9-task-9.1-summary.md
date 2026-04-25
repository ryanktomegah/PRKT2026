# Day 9 Task 9.1 — Python Dependency CVE + License Audit

**Date run:** 2026-04-19
**Scope:** `requirements.txt` + `requirements-ml.txt` (190 distinct packages).

## Summary

| Tool | Scope | Result |
|------|-------|--------|
| `pip-audit` | Installed versions against OSV + PyPI advisory DB | **0 vulnerabilities** |
| `safety check` | Declared requirement specifiers | 0 reported, **8 ignored** (unpinned-requirements policy) |
| `pip-licenses` | Installed licenses | 190 packages, **1 LGPL** + 2 workspace-local UNKNOWN |

Net verdict: **no critical CVE to fix.** No GPL/AGPL/SSPL/Commons-Clause
contamination. The LGPL finding is safe for our usage pattern.

## pip-audit

Command:

```
pip-audit -r requirements.txt -r requirements-ml.txt -f columns
```

Result: `No known vulnerabilities found`. Full output: `pip-audit.txt`.

pip-audit checks installed versions against OSV + PyPA advisories. A clean run
means every currently-resolved dependency in our environment has no open CVE.

## safety (ignored findings)

safety reports 0 active vulns but flags 8 *potential* vulns across 5 packages
because their requirement specifiers are unpinned. safety ignores these by
default (`ignore-unpinned-requirements=True`). The 8 ignored IDs:

| Package | Specifier | IDs | Notes |
|---------|-----------|-----|-------|
| fpdf2 | (unpinned) | 80915 (×2, one per req file) | Listed in both requirement files |
| lightgbm | (unpinned) | 78808 | |
| torch | `>=2.6.0` | 78828, 76769 | |
| cryptography | `<47.0,>=44.0.0` | 76170, 86217 | |
| scikit-learn | `<2.0,>=1.4.0` | 71596 | |

The warning says: "a lower version within your specifier range *could* have
this CVE." Because pip-audit (above) scans actually-installed versions and
found nothing, our real runtime is clean. The hardening action is to bump
each lower bound above the affected range, which is a separate hygiene PR.

**Follow-up (filed, not fixed here):** tighten requirement lower bounds for
fpdf2, lightgbm, torch, cryptography, scikit-learn to exclude ignored-CVE
ranges. Low priority — current resolution is clean.

## pip-licenses — license matrix

190 packages. Full matrix: `python-licenses.csv`.

Flagged findings (grep for `GPL|AGPL|SSPL|Commons Clause|Non-Commercial|Proprietary|Unknown`):

| Package | Version | License | Verdict |
|---------|---------|---------|---------|
| fpdf2 | 2.8.7 | LGPL-3.0-only | **Safe for our use** — LGPL permits dynamic linking / Python import without copyleft propagation. We use fpdf2 as a regular library call (PDF generation), not as part of a linked binary. No obligation to release our source under LGPL. |
| lip_c3_rust_state_machine | 0.1.0 | UNKNOWN | **Our own package** — Rust-backed C3 module. Not external. |
| lip_c6_rust_velocity | 0.1.0 | UNKNOWN | **Our own package** — Rust-backed C6 module. Not external. |

No AGPL, GPL-2.0, GPL-3.0, SSPL, Commons-Clause, or non-commercial-only
licenses present. The bank-pilot and regulatory-production path is clean
from a Python-side license perspective.

## Actions

- [x] Run pip-audit → clean.
- [x] Run safety → 0 active, 8 ignored (documented).
- [x] Extract license matrix → 190 packages, 1 LGPL (safe), 2 workspace-local.
- [x] Identify critical CVE requiring inline fix → **none found**.
- [ ] *(Follow-up, out of sprint scope)* tighten lower-bound specifiers for
      fpdf2/lightgbm/torch/cryptography/scikit-learn.

## Artefacts

- `pip-audit.txt` — full pip-audit output
- `safety-check.txt` — full safety report
- `python-licenses.csv` — complete 190-package license matrix
