---
description: Run the LIP test suite. Usage: /test [fast|full|c1|c2|c3|c4|c5|c6|c7|c8|live|<pattern>]
argument-hint: "[fast|full|c1..c8|<pattern>]"
allowed-tools: Bash
---

Run the LIP test suite using `~/.pyenv/versions/3.14.3/bin/python3` with `PYTHONPATH=.` set from `/Users/tomegah/Documents/PRKT2026`.

Interpret `$ARGUMENTS` as follows — if no argument given, default to `fast`:

| Argument | Command |
|---|---|
| `fast` (default) | `python -m pytest lip/tests/ -m "not slow" --ignore=lip/tests/test_e2e_live.py -q` |
| `full` | `python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_live.py -q` |
| `c1` | `python -m pytest lip/tests/test_c1_classifier.py lip/tests/test_c1_training.py -v` |
| `c2` | `python -m pytest lip/tests/test_c2_pd_model.py -v` |
| `c3` | `python -m pytest lip/tests/test_c3_repayment.py -v` |
| `c4` | `python -m pytest lip/tests/test_c4_dispute.py -v` |
| `c5` | `python -m pytest lip/tests/test_c5_stress_regime.py lip/tests/test_c5_streaming.py -v` |
| `c6` | `python -m pytest lip/tests/test_c6_aml.py -v` |
| `c7` | `python -m pytest lip/tests/test_c7_execution.py -v` |
| `c8` | `python -m pytest lip/tests/test_c8_license.py -v` |
| `live` | `python -m pytest lip/tests/test_e2e_live.py -m live -v` (requires Redpanda at localhost:9092) |
| anything else | treat as a pytest `-k` pattern: `python -m pytest lip/tests/ -k "$ARGUMENTS" -v --ignore=lip/tests/test_e2e_live.py` |

**Known flaky test:** `test_slo_p99_94ms` fails under CPU load — not a regression signal, ignore it.

After running, report: tests passed / failed / skipped, and highlight any failures with the relevant log excerpt. If tests fail, read the failing test file and the source it tests before diagnosing — never guess the root cause.
