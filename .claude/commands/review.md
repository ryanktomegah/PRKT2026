---
description: Review code or a file against LIP standards — canonical constants, data contracts, security, test coverage. Usage: /review <file-or-component>
argument-hint: "<file-path or component name>"
allowed-tools: Read, Grep, Glob, Bash
---

Perform a rigorous code review of `$ARGUMENTS` (a file path or component name like `c1`, `c2`, `dgen`) against LIP-specific standards.

**Before reviewing, always read the source first.** Never infer from filenames alone.

**Review checklist:**

### 1. Canonical Constants (QUANT sign-off required to change)
- Fee floor: 300 bps — never hardcoded as a raw number elsewhere
- Maturity: CLASS_A=3d, CLASS_B=7d, CLASS_C=21d, BLOCK=0d
- Latency SLO: ≤ 94ms — no test should assert a different bound
- UETR TTL: 45 days
- Stress multiplier: 3.0
- Threshold τ*: 0.152
- Flag any deviation from these values.

### 2. Data contracts
- All required fields present in record dicts before passing to pipeline stages
- No field semantics inferred from names — verify against docstrings and source
- `is_permanent_failure` means Class A vs B/C among RJCT events — NOT overall failure rate

### 3. Security
- No real BICs, PII, or credentials in committed code or test fixtures
- AML patterns only in `c6_corpus_*.json` (gitignored)
- UETR salt rotation logic not bypassed
- No `--no-verify` in any script

### 4. Test coverage
- Every new public function has at least one test
- Edge cases covered: empty input, single record, all-failure, all-success
- No mocked database/filesystem where real behaviour is testable

### 5. ML-specific (C1/C2/C4)
- No label leakage between train/val splits
- Calibration applied after threshold selection, not before
- Feature scaling fitted on train only, applied to val

Report findings as: ✅ Clean / ⚠️ Warning / 🔴 Violation — with file path and line number for each issue. Suggest fixes for violations.
