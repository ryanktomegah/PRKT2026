# EPG Fix Gotchas
## Lessons from the Epignosis review — failure modes to avoid when implementing fixes

### Gotcha 1: Fixing C7 without fixing pipeline.py
The exact failure mode of EPG-09/10. `fe09cb6` added `_COMPLIANCE_HOLD_CODES` to `agent.py`
correctly, but `pipeline.py:418` was not updated to handle the new status code. C7 and the
pipeline are two separate places that must both be updated whenever a new status code is added.

**Rule:** Any time a new `c7_status` string is added to `agent.py`, immediately search for
`if c7_status in (` in `pipeline.py` and add it there too.

### Gotcha 2: Testing components in isolation, not end-to-end
Commit `fe09cb6` added 7 tests to `test_c7_execution.py` that correctly verified C7's
behavior in isolation. None tested the full `LIPPipeline.process()`. The pipeline fall-through
was invisible to those tests.

**Rule:** After fixing any EPG issue that touches a gate (C6, C7, taxonomy), add a
`test_e2e_pipeline.py` test that fires that specific rejection code through the full pipeline
and asserts the correct top-level outcome.

### Gotcha 3: Assuming constants.py comments match the code's intent
`SETTLEMENT_P95_CLASS_B_HOURS = 53.58  # Compliance/AML holds` labels CLASS_B as compliance
holds — but the system funds CLASS_B bridge loans. The comment reveals an unresolved
design conflict, not a description of correct behavior.

**Rule:** When reading constants.py comments to understand behavior, always cross-check
against what the pipeline actually does with that class. Comments may reflect design intent,
not code reality.

### Gotcha 4: Sign-off on one domain but not another
`_COMPLIANCE_HOLD_CODES` got REX + CIPHER sign-off (correctly). But the same set of codes
determines what ends up in the 7-year audit log (REX domain), what the pipeline returns to
the bank's treasury integration (NOVA domain), and what triggers the compliance team
notification (FORGE domain). Each agent only reviewed their slice.

**Rule:** Before fixing any EPG issue, check the authority matrix in `../sign-off/authority_matrix.md`
for ALL domains touched — not just the primary owner.

### Gotcha 5: Fail-open as a "temporary" workaround
The `else True` in `pipeline.py:291` looks like a deliberate availability decision ("if AML
is down, keep running"). It is architecturally inverted from every other safety gate.
"Availability" cannot be a reason for the AML gate to fail open.

**Rule:** Any `None` check on a safety-critical result that defaults to `True` (pass) is
wrong. Default should always be `False` (block) or raise an explicit unavailability outcome.

### Gotcha 6: Thinking the Jaccard threshold is the main sanctions problem
The 0.8 threshold is a problem, but the deeper issue is that BIC codes are passed as entity
names when no resolver is configured. Even a perfect threshold cannot match `BNPAFRPPXXX`
against `BANK OF IRAN`. Fix the resolver configuration requirement first; then revisit the
threshold.

### Gotcha 7: Using git log dates to assess whether an EPG is addressed
The review was produced on 2026-03-18. All commits are from 2026-03-17 or earlier. Do not
interpret any prior commit as addressing an EPG issue unless `state.json` records it as DONE.
