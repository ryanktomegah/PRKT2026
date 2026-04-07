# EPG-16 / EPG-17 / EPG-18 — AML Caps + Boot Enforcement + Human Review Routing

**Status:** ✅ Implemented
**Decided:** 2026-03-18
**Decision authority:** CIPHER (EPG-16/17), REX (EPG-18)
**Source rationale:** [`/CLAUDE.md`](../../CLAUDE.md) § EPG-09/10/16/17/18
**Implementation:** commit `0ec874c`

---

## EPG-16 — AML caps default 0 (unlimited); per-licensee via C8 token

The default AML dollar cap and count cap are **0**, which is interpreted as **unlimited** by an explicit guard in `lip/c6_aml_velocity/velocity.py`. Per-licensee caps are loaded from the C8 license token at boot.

### Why "0 = unlimited" instead of `None` or `-1`

Correspondent banking volumes are unbounded by design. Any non-zero default cap risks shutting down a real bank's payment stream during normal operations. Picking a "safe" default (e.g. $1B/day) creates a silent failure mode where an enterprise customer hits the cap once a quarter and nobody knows why payments stopped. The only honest default is "no cap unless the license token says otherwise."

`0` is chosen over `None` because it serializes cleanly through JSON, Pydantic, and Redis without special-casing, and the explicit `0 → unlimited` guard is a single line that is impossible to misread.

### Per-licensee caps are mandatory in production

Although the default is unlimited, no production deployment runs uncapped. The C8 license token issued to each licensee bank specifies the agreed dollar/count caps for that licensee. EPG-17 enforces this at boot.

---

## EPG-17 — Explicit cap enforcement at boot

`license_token.from_dict` requires `aml_dollar_cap_usd` and `aml_count_cap` as **mandatory JSON fields**. A token missing either field raises `KeyError`, which is caught by `boot_validator` and engages the kill switch.

### Why mandatory at boot, not optional with default

Defaults are the enemy of compliance discipline. If the fields are optional with a default of unlimited, an operator who forgets to set them gets an unlimited deployment that behaves identically to a correctly-configured one — until an audit asks "what cap is this licensee under?" and the answer is "nobody set one." Mandatory fields make this failure mode impossible: the system simply does not boot without an explicit cap value (which may be 0/unlimited, but must be explicit).

### Pairing with the kill switch

The boot_validator → kill switch chain is the C7 standard pattern. Any compliance-relevant field that must be present at boot follows this pattern: missing field → exception → kill switch engaged → no payment processing until corrected. There is no "degraded mode" for missing AML caps.

---

## EPG-18 — C6 anomaly flag → PENDING_HUMAN_REVIEW (EU AI Act Art. 14)

When C6 raises an anomaly flag on a payment (`aml_anomaly_flagged=True`), the payment is routed to `PENDING_HUMAN_REVIEW` **before** any autonomous FUNDED decision can be reached.

### Why this is required by law, not policy

EU AI Act Article 14 ("Human oversight") requires that high-risk AI systems include "human-in-the-loop" capability for outcomes that could materially affect natural persons. LIP qualifies as a high-risk system under Annex III. C6's anomaly detection is the explicit hook that satisfies Art. 14 — the model can flag, but it cannot fund without human sign-off when it has flagged.

### What "anomaly flag" means in C6

C6 carries multiple checks (sanctions, velocity caps, anomaly detection). A sanctions hit or velocity cap breach is a hard block. An *anomaly* flag is the softer signal: the payment looks unusual relative to the licensee's pattern but does not clearly violate a rule. Without EPG-18, an anomaly flag would have been advisory only. With EPG-18, it forces human review.

### Test coverage caveat

Mock C6 results in older tests carried `MagicMock` truthy bleed-through on `anomaly_flagged`, which made the EPG-18 gate fire spuriously. All test mock C6 results were updated to `anomaly_flagged=False` explicitly. New tests must follow this pattern.

---

## Why these three were decided together

EPG-16/17/18 all touch C6 and the C7 routing logic, and all three are EU AI Act / DORA gating requirements. Splitting them across separate decisions would have made the implementation order ambiguous. The single commit `0ec874c` lands them together, and the test suite enforces all three invariants in one block.
