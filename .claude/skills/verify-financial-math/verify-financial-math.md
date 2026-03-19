---
description: Scan codebase for flat fee formula violations — detects any fee_bps usage missing the annualized ×(days/365) factor. Run before committing any file that touches fee_bps, settlement_amount, principal_usd, or repayment logic. QUANT authority: no fee-related code merges without this check passing.
argument-hint: "[path/to/file.py | all]"
allowed-tools: Bash, Read, Grep
---

## What this checks

The canonical fee formula (fee.py, C2 Spec Section 9):

    fee = principal × (fee_bps / 10_000) × (days_funded / 365)

A flat formula — `principal × (fee_bps / 10_000)` without `× days` — overstates fee by
`365 / days_funded`. For a 7-day loan this is a **46× overstatement**.

Run this before committing any change to:
- `lip/dgen/c3_generator.py`
- `lip/c3_repayment_engine/`
- `lip/c2_pd_model/`
- Any file importing `fee_bps` or computing `settlement_amount`

## Usage

```bash
# Check a specific file
PYTHONPATH=. python3 .claude/skills/verify-financial-math/scripts/check_fee_formulas.py lip/dgen/c3_generator.py

# Check the whole codebase
PYTHONPATH=. python3 .claude/skills/verify-financial-math/scripts/check_fee_formulas.py all
```

## Pass criteria

- Zero flat fee violations (`fee_bps / 10_000` without days factor on same line or in same expression)
- All `settlement_amount_usd` assignments that include fee include a division by 365 or a call to `compute_loan_fee`

## When a violation is found

1. Print the exact file:line
2. Show the offending expression
3. Show the correct formula as a diff suggestion
4. Do NOT proceed with any other work until the violation is fixed and re-checked

## Gotchas

- `fee_bps / 10_000` as a standalone intermediate variable is OK — only flag when the result
  is directly added to principal without a subsequent `× days/365` factor
- `compute_loan_fee(...)` from `fee.py` is always correct — no need to check its callsites
- `FEE_FLOOR_BPS = 300` constant assignments are NOT formula violations
