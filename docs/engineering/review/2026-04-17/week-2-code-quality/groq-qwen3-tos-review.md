# Day 9 Task 9.3 — Groq / Qwen3 ToS Review + Repo Hygiene Scans

**Date run:** 2026-04-19
**LLM backend under review:** Groq-hosted `qwen/qwen3-32b` (see C4 CLAUDE.md notes).
**Headline verdict:** **NO Trigger-#3 escalation.** Groq AUP permits finance
use with human-supervision conditions that LIP's architecture already satisfies.
Qwen3-32B is Apache 2.0 — fully cleared for commercial use. Repo history and
gitignore posture are clean — no secrets, no AML typology leakage.

## 1. Groq — cloud API terms

Groq distinguishes between **website terms** (groq.com/terms-of-use, governs
marketing site only) and the **Services Agreement** (governs API use,
GroqCloud, GroqChat, Groq Playground). LIP consumes the API, so the Services
Agreement + AUP apply. Website terms are not the relevant document.

### Primary documents consulted (effective 2025-10-15)

- Services Agreement: https://console.groq.com/docs/legal/services-agreement
- Acceptable Use & Responsible AI Policy: https://console.groq.com/docs/legal/ai-policy
- Privacy Policy: https://groq.com/privacy-policy
- DPA: https://console.groq.com/docs/legal/customer-data-processing-addendum
- BAA: https://console.groq.com/docs/legal/customer-business-associate-addendum

### Key Services Agreement clauses

**No training on customer data:**
> "Groq is not permitted to use Inputs or Outputs for training or fine-tuning
> any AI Model Services or other models, unless explicitly granted permission
> or instructed by Customer."

**Limited access / retention:**
> "Groq does not access, use, store, or retain Inputs or Outputs except as
> necessary to provide the Cloud Services…or ensure the reliable operation of
> the Cloud Services."

**30-day deletion on termination:**
> "Groq will delete any Customer Data…within 30 days, unless otherwise
> described…or if Groq is required to retain any such information under
> applicable law."

**"High Risk Activities" definition is narrow (not finance):**
> "activities where the use or failure of the Cloud Services…could reasonably
> be expected to lead to death, personal injury, or environmental or property
> damage (such as the creation or operation of nuclear facilities, air traffic
> control, life support systems, or weaponry)."

**No default SLA:**
> "Customer may purchase…service level commitments from Groq, each of which
> will be governed by a separate agreement or supplemental terms published by
> Groq."

**Warranties disclaimed:**
> "the AI Model Services are provided without any express or implied warranty
> regarding the quality or the accuracy of the AI Model Services (including
> Outputs)."

### Acceptable Use Policy — the relevant finance clause

> "make automated decisions that have a material detrimental impact on
> individual rights without human supervision in high-risk domains, such as
> in employment, healthcare, finance, legal, housing, insurance, or social
> welfare."

Translation: finance is **allowed**, but **automated finance decisions that
materially affect individual rights require human supervision.**

Human-oversight requirement:

> "appropriate human oversight, testing, and other use case-specific
> safeguards"

EU AI Act compliance is explicitly required of the Customer.

### Does LIP's use of Groq-hosted Qwen3 violate the AUP?

**No — provided the following hold, which they do:**

| AUP requirement | LIP status |
|-----------------|------------|
| Human supervision in high-risk finance decisions | ✅ EPG-18 routes C6 anomaly to `PENDING_HUMAN_REVIEW`; C8 license-manager governs deployment scope; decision log (7-year retention) exists for SR 11-7 / EU AI Act Art.17 audit |
| Output accuracy evaluation before consequential use | ✅ QUANT canonical constants; ARIA model validation gates (data quality caveats in metrics per CLAUDE.md rules); C2 model card required for ML deployment |
| EU AI Act compliance | ✅ REX lens is the final authority on DORA / EU AI Act; data cards mandatory; per CLAUDE.md "REX will refuse to mark a model deployment-ready without a data card and out-of-time validation record" |
| No training on Groq side | Structural — guaranteed by contract |
| Customer data used for Groq model training | ❌ Not used — per Services Agreement § (no-training clause above) |

**Additional LIP consideration:** LIP's dispute-classification path (C4) is
not *consumer-facing*. Classifications route to internal risk-adjustment logic
(rejection taxonomy + compliance-hold gate), not to an end consumer or loan
approval decision. The "material detrimental impact on individual rights"
threshold in the AUP is aimed at consumer-credit decisioning; LIP's B2B
interbank structure (EPG-14: originating bank BIC is the borrower, not the
end customer) puts LIP well short of that threshold.

### Gaps / things counsel should still verify

1. **DPA acceptance.** Services Agreement references a DPA at
   `/customer-data-processing-addendum`. Whether BPI has *executed* this DPA
   (or needs to, for GDPR-adjacent EU bank data flowing through Groq) is a
   procurement step, not a code change.
2. **No contractual SLA by default.** For pilot banks that demand uptime
   commitments, BPI will need to negotiate a supplemental SLA with Groq or
   move to a private-hosted Qwen3 deployment (AWS Bedrock / GCP Vertex /
   self-hosted vLLM). Not blocking for pre-lawyer review; will be blocking for
   bank-pilot contract.
3. **Input-log retention ambiguity.** Services Agreement says Groq may retain
   inputs "as necessary to provide the Cloud Services" — the specific
   retention window is not quantified beyond the 30-day-on-termination rule.
   If EU bank data flows through Groq, counsel should ask Groq for a
   retention SLA in writing.
4. **No explicit BAA coverage of financial PII.** The BAA is HIPAA-scoped. The
   DPA is the GDPR/CCPA-scoped instrument. Neither specifically addresses
   GLBA / FCRA / Canadian PIPEDA for financial data — standard operating
   posture for most cloud-LLM vendors, not a Groq-specific gap. Counsel
   should flag this in the LIP → bank license agreement rather than
   renegotiating Groq's boilerplate.

### Verdict — Trigger #3?

**No escalation.** Groq ToS does not forbid regulated-finance use; the
conditions it imposes (human supervision, EU AI Act compliance, accuracy
evaluation) are already structurally enforced by LIP's compliance
architecture (REX lens, EPG-18, C8 licensing, decision log). The pending
follow-ups above are procurement-side negotiation items for pilot bank
onboarding, not ToS blockers.

## 2. Qwen3-32B model license

**License: Apache 2.0** (Hugging Face model card: `License: apache-2.0`).

Apache 2.0 permits:
- Commercial use (including regulated-industry deployment)
- Modification and redistribution
- Private deployment
- Sublicensing under compatible terms

Attribution requirement: the license itself requires preserving copyright
and license notices when redistributing. The model card additionally
requests citation of the Qwen3 Technical Report (arXiv 2505.09388) if the
work is "helpful" — this is a soft request, not a license condition.

**No commercial-use restrictions, no regulated-industry carve-outs, no
human-oversight requirement from the model side.** The AUP conditions
discussed above come from the *hosting provider* (Groq), not from the
*model license* — which means BPI could switch from Groq to any other
Qwen3-compatible provider (self-hosted vLLM, AWS Bedrock if Qwen3 is
onboarded there, or GCP Vertex) without re-negotiating the underlying
model license.

**Optionality matters for bank-pilot risk.** If a pilot bank's
procurement team pushes back on a third-party ToS chain, BPI's fallback is:
spin up Qwen3 on a private inference endpoint. The model license does not
obstruct that path.

## 3. Repo hygiene — gitignore and history scan

### Step 3a: `.gitignore` posture

```
git check-ignore -v artifacts/                               → .gitignore:36 (artifacts/)
git check-ignore -v lip/c6_aml_velocity/c6_corpus_example.json → .gitignore:40 (**/c6_corpus_*.json)
```

Both CLAUDE.md-mandated exclusions are actively enforced. Additionally:
`**/c6_corpus_*.json.sha256` is also gitignored (defense-in-depth against
committing the hash of a typology file and leaking shape information).

Tracked-file check: `git ls-files artifacts/` returns 0 files — nothing in
the `artifacts/` directory has ever been committed.

### Step 3b: full-history search for c6 corpus

```
git log --all --full-history -- 'lip/c6_aml_velocity/c6_corpus_*.json'
```

Returns empty. **No C6 AML typology file has ever been committed to this
repository's history.** The CIPHER rule has been honored for every commit.

### Step 4: gitleaks full-history scan

Ran `gitleaks detect --log-level=info` across all 511 commits (11.82 MB of
diff content). Result: **no leaks found.** Report written to
`gitleaks-report.json` (empty findings array).

This covers the standard Gitleaks ruleset (AWS, Azure, GCP, GitHub PATs,
Stripe, Slack tokens, private keys, generic high-entropy strings). No
secrets detected in the repository's full history.

### Verdict — Trigger #4?

**No escalation.** artifacts/ never tracked, c6_corpus_*.json never
committed, gitleaks history is clean.

## 4. Summary of actions

- [x] Reviewed Groq Services Agreement + AUP — no prohibition, conditional
      permissions already satisfied by LIP architecture.
- [x] Reviewed Qwen3-32B license — Apache 2.0, no restrictions.
- [x] Verified `artifacts/` gitignored and never tracked.
- [x] Verified `c6_corpus_*.json` gitignored and never present in history.
- [x] gitleaks full-history scan: no leaks.
- [ ] *(Follow-up, counsel/procurement)* Execute Groq DPA if not already
      signed; negotiate supplemental SLA before bank-pilot contract; confirm
      input retention window for EU data flow.
- [ ] *(Follow-up, counsel)* Flag GLBA / FCRA / PIPEDA data-handling
      questions in LIP → bank license agreement — not a Groq-specific issue.

## 5. Artefacts

- `groq-qwen3-tos-review.md` — this document
- `gitleaks-report.json` — gitleaks output (empty findings)
