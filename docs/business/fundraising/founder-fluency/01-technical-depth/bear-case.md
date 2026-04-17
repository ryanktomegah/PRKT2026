# Technical Depth — Bear Case

**How to read this file:** Each entry below names a real weakness, writes an honest structured answer, and flags the don't-say traps. Master Index ranks entries by `(likelihood of being asked) × (severity if fumbled)`. Spend 50% of drill time on ranks 1-3.

## Cross-volume META references

See also: **META-01 (RBC IP clause)** — master entry in `02-patent-ip/bear-case.md`. Referenced here because the founder-employment angle intersects with the non-technical founder question (META-03).

## Master Index

| Rank | ID | Weakness | Resolution event |
|---|---|---|---|
| 1 | META-03 | Non-technical founder | (ongoing — no single event; fluency is proven continuously) |
| 2 | META-02 | No production traffic yet | First live UETR in RBC pilot |
| 3 | B-TECH-01 | Model performance on real data unknown | First real-traffic validation run |
| 4 | B-TECH-02 | 94ms SLO untested at bank throughput | Load test against bank-realistic traffic |
| 5 | B-TECH-03 | Polyglot stack = hiring/scaling risk | First external hire; engineering lead in place |
| 6 | B-TECH-04 | C4 Dispute Classifier single-vendor ML risk (Groq/Qwen3) | Second LLM backend validated |
| 7 | B-TECH-05 | Early infra fragility signals (PyTorch+LightGBM macOS deadlock) | CI-level regression gates in place |

---

## META-03 — Non-technical founder who earned fluency
**(Master entry — referenced from all volumes; governs the founder-fit question)**

**Honest Truth:** Correct. My background is strategic, not engineering. I did not write the Rust velocity engine, the Go gRPC router, or the GraphSAGE training loop. That is the accurate framing. The question is whether a non-technical founder can govern a technically complex company. The answer depends on the quality of the fluency, not whether the founder can write code.

**Structured Answer:**
1. Acknowledge clean. "Correct. My background is strategic, not engineering. I want to be precise about what I built and what the team built."
2. Show the work. I know the architecture at a decision level, not a credential level. I can defend the 94ms SLO at p99 — it was set at that threshold because it clears the straight-through-processing window before a treasury officer opens the case manually. I can defend the C1 architecture: GraphSAGE on corridor graph structure (output dim 384), TabTransformer on pacs.002 tabular features (output dim 88), LightGBM on the combined embedding, threshold 0.110 F2-optimal. I can defend the 300 bps fee floor — below it, the loan is capital-negative at p99 cost of capital. I can defend the polyglot stack: Python for ML pipelines, Rust via PyO3 for latency-critical velocity engine, Go gRPC for C7 delivery to treasury. I studied these decisions. I challenged them. The team pushed back when I was wrong. That is the governance model.
3. Name the governance. The Ford Principle: my team translates direction into correct technical decisions and has explicit authority to push back before implementing anything flawed. QUANT has final authority on all financial math and canonical fee constants — nothing changes the 300 bps floor without QUANT sign-off on the underlying cost-of-capital arithmetic. CIPHER has final authority on security and AML — AML typology patterns never appear in version control. REX has final authority on compliance — no model goes to a bank without a data card and out-of-time validation record. These are not management layers. They are vetoes.
4. Close. "The fluency you're testing for is earned, not delegated. I can take any architectural decision in this stack to the whiteboard and defend it. What I will not do is pretend I wrote the code."

**Don't-say-this:**
- ❌ "I rely on my team" (implies passive dependence — the opposite of the Ford Principle)
- ❌ "I'm learning as we go" (signals ongoing gap, not resolved fluency)
- ❌ "I have a great technical co-founder who handles that" (hides behind headcount)
- ❌ Any apology or hedging — "I'm not super technical but..." or "I know enough to be dangerous"
- ❌ "My background gives me unique insight" (deflection, not demonstration)

**Resolution Milestone:** Ongoing — fluency is demonstrated, not resolved by a single event. Each investor conversation where the founder defends architecture at depth without hedging is evidence.

**Investor Intuition target:** "He knows this stack better than most technical founders know their own — and he's built a governance model that catches his blind spots before they matter."

**Drill linkage:** Q-TECH-17 (Adversarial — "Non-technical founder, current RBC employee, no production traffic. Convince me this isn't a pipe dream.") and Q-TECH-24 (Crushing — "You're not technical. If your senior engineer leaves tomorrow, what happens?"). Both confirmed in drill.md.

---

## META-02 — No production traffic yet
**(Master entry — referenced from all volumes; governs the pre-revenue / pre-pilot question)**

**Honest Truth:** Pre-production. The full pipeline runs on synthetic pacs.002 — two million (2M) records calibrated to BIS/SWIFT GPI settlement P95 data. No real bank has sent a live pacs.002 into LIP. No live UETR has been processed. The 94ms SLO is validated on synthetic traffic, not bank-realistic throughput.

**Structured Answer:**
1. Acknowledge clean. "Correct. No real bank traffic. No live UETR processed. I want to be precise about what synthetic means and what the pilot resolves."
2. Reframe as design choice, not gap. The synthetic-first build was deliberate. Two million (2M) records calibrated to BIS/SWIFT GPI failure-rate distributions let the eight-component stack — C1 through C8 — run to completion before spending pilot goodwill on debugging. The pilot is a validation exercise, not a beta test the bank funds while we discover what breaks. The distinction matters in procurement.
3. State the evidence. One thousand two hundred eighty-four (1,284) tests passing, ninety-two percent (92%) coverage. Every QUANT-locked constant — 300 bps floor, 94ms SLO, 0.110 C1 threshold — is traceable to code, not a slide. DGEN generated the corpus. QUANT signed off on calibration against BIS/SWIFT GPI settlement P95 distributions. The confidence is in the architecture, not in claimed production metrics we don't have.
4. Name the milestone. "First live UETR in the RBC pilot is the resolution event. That run tells us the real rejection distribution, the live inference time, and the C1 AUC on actual bank data. We know what we don't know — and we've built a system disciplined enough to tell you the number once we have it."

**Don't-say-this:**
- ❌ "We're basically ready, just need a pilot" — weasel word ("basically") plus understatement of what a pilot actually validates
- ❌ "No one has production data at this stage" — true but defensive; deflects rather than demonstrates
- ❌ "The synthetic data is as good as real" — DGEN would refuse this claim; synthetic-to-real distribution shift is a real and known risk; never speak it
- ❌ "We've stress-tested it extensively" — overstatement; correct framing is "calibrated against BIS/SWIFT GPI distributions on synthetic records"

**Resolution Milestone:** First live UETR processed in the RBC pilot — produces real rejection distribution, live inference time, and C1 AUC on actual bank data.

**Investor Intuition target:** "They built the hard thing first — the architecture — and they know exactly what the pilot proves. They're not guessing."

**Drill linkage:** Q-TECH-22 (Crushing — "Prove 94ms. Real traffic, real bank, real numbers — or admit you don't know.") is the direct test. Q-TECH-15 (Adversarial — "You have no production traffic. What do you actually know about your model's behaviour?") is the related entry. Both confirmed in drill.md.

---

## B-TECH-01 — Model performance on real data unknown

**Honest Truth:** C1 baseline AUC is 0.739 on synthetic records; target is 0.850 after production training. The synthetic corpus is calibrated to BIS/SWIFT GPI settlement P95 distributions, but synthetic-to-real distribution shift is a documented risk. How much C1 AUC moves on live rejection code distributions is unknown. ARIA reports model metrics only with explicit data-quality caveats — this is one of them.

**Structured Answer:**
1. Acknowledge clean. "We don't know C1's AUC on real bank data. The honest number is 0.739 on synthetic, with a post-training target of 0.850. That gap is what the pilot resolves."
2. Reframe as known-unknowns discipline. ARIA, the ML governance agent, refuses to report model metrics without stating data-quality caveats. The caveat here is synthetic-to-real distribution shift. The system is built to measure and report that shift on first real-traffic run — it is not buried. The C1 threshold of 0.110 is F2-optimal: the model is calibrated to err on the side of false positives (offering when it shouldn't) rather than false negatives (missing real bridge candidates). False negatives cost the bank a stalled trade; false positives cost a declined offer. The asymmetric BCE alpha of 0.7 reflects that choice.
3. State the architecture. Three signal types, three models. GraphSAGE on corridor graph structure, output dim 384. TabTransformer on pacs.002 tabular features, output dim 88. LightGBM on the combined 472-dim embedding. Each captures what the others miss. The ensemble is designed to generalise.
4. Name the milestone. "First real-traffic validation run measures calibration drift. We know what signal to track. That is the expected pilot output."

**Don't-say-this:**
- ❌ "Our synthetic data is representative of real-world conditions" — DGEN would refuse this; never say it
- ❌ "We've validated the model thoroughly" — overstatement; correct framing is validated on 2M synthetic records calibrated to BIS/SWIFT GPI distributions
- ❌ "AUC will be fine — ensemble models generalise" — assertion without data

**Resolution Milestone:** First real-traffic validation run with calibration drift measurement against synthetic baseline.

**Investor Intuition target:** "They know the risk and they've built the system to measure it. The pilot isn't a mystery box — it's a calibration run."

**Drill linkage:** Q-TECH-15 (Adversarial — "You have no production traffic. What do you actually know about your model's behaviour?"). Confirmed in drill.md.

---

## B-TECH-02 — 94ms SLO untested at bank throughput

**Honest Truth:** The 94ms SLO at p99 is validated on synthetic pacs.002 at mocked throughput. It has not been load-tested against realistic bank QPS — SWIFT peaks at 55 million (55M) messages per day, concentrated in settlement windows. How the p99 moves under live correspondent banking load is unknown.

**Structured Answer:**
1. Acknowledge clean. "The 94ms SLO is QUANT-locked and validated on synthetic traffic. It has not been tested against bank-realistic QPS. That is a pre-pilot gap."
2. Reframe with architecture. The SLO was designed for horizontal scale-out. The pipeline is stateless at inference — every pacs.002 is an independent event with no shared state. Kafka partitioning spreads load across workers. HPA autoscale triggers at queue depth of 100 and scales in at 20. Under back-pressure, the failure mode is queue wait time — the 94ms clock starts on dequeue — not inference errors or data loss. The Rust velocity engine and Go gRPC router were chosen specifically to minimise latency on the hot path. Median latency on synthetic records is under 45ms. The 94ms SLO is the worst-in-hundred case.
3. Name the evidence. GraphSAGE uses five (5) neighbours at inference versus ten (10) at training — deliberate cut to reduce graph traversal time under load. C7 uses Go gRPC to eliminate serialisation overhead at offer delivery.
4. Name the milestone. "Load test against bank-realistic traffic — sustained pacs.002 input calibrated to SWIFT peak QPS — is the validation event. The architecture was designed to pass it."

**Don't-say-this:**
- ❌ "We're confident it will scale — it's Kubernetes" — Kubernetes is infrastructure, not a performance guarantee
- ❌ "94ms is our current benchmark; we'd tune it at scale" — implies the SLO is negotiable; it is QUANT-locked
- ❌ "94ms is just a target" — the SLO is p99 validated on synthetic, not aspirational

**Resolution Milestone:** Load test against bank-realistic sustained throughput; p99 confirmed at or below 94ms.

**Investor Intuition target:** "They built the architecture for scale-out from day one. The load test is a validation run, not an engineering sprint."

**Drill linkage:** Q-TECH-16 (Adversarial — "Why should I believe 94ms holds at scale — say, 53 million messages a day?") and Q-TECH-22 (Crushing — "Prove 94ms."). Both confirmed in drill.md.

---

## B-TECH-03 — Polyglot stack = hiring/scaling risk

**Honest Truth:** The stack is Python plus Rust via PyO3 plus Go. That is a narrower hiring pool than a pure-Python shop. A candidate who can contribute across all three layers is a more constrained search than one who needs only Python. First external engineering hire will face this tradeoff directly.

**Structured Answer:**
1. Acknowledge clean. "Python + Rust (PyO3) + Go is not a broad hiring pool. The first external engineering hire is a longer search than a pure-Python company. That is a real constraint."
2. Reframe as deliberate. Polyglot was not an accident. Python runs the ML pipelines where ecosystem coverage matters — PyTorch, LightGBM, scikit-learn. Rust via PyO3 runs the velocity engine where a Python function taking 40ms would breach the 94ms SLO. Go handles C7 gRPC offer delivery because Go's concurrency model eliminates serialisation overhead at the throughput layer. Each language is in its role for a latency reason, not a preference reason.
3. Current state. The team is small and senior. The codebase has 1,284 tests and 92% coverage. Any senior engineer reads the codebase and trusts it within a week — the documentation discipline is already there. The QUANT-locked constants mean critical invariants are protected by tooling, not tribal knowledge.
4. Name the milestone. "First external engineering hire in place — we accept a longer search for polyglot-comfortable engineers, or we hire at the Python layer and grow into Rust over time. That is a hiring problem, not an architecture problem."

**Don't-say-this:**
- ❌ "Most senior engineers know multiple languages" — true but doesn't address the constraint
- ❌ "We can refactor to pure Python later" — undermines the latency argument for Rust; never offer this
- ❌ "The hiring market for Rust is fine" — it is narrower; don't deny the constraint

**Resolution Milestone:** First external engineering hire on board; engineering lead in place who owns cross-language architecture decisions.

**Investor Intuition target:** "The polyglot choice was made for performance, not fashion. They know the hiring cost and they've decided it's worth it."

**Drill linkage:** Q-TECH-11 (Probing — "Walk me through C1's architecture — GraphSAGE, TabTransformer, LightGBM. Why all three?") is the most proximate drill that tests stack-rationale depth. Confirmed in drill.md.

---

## B-TECH-04 — C4 Dispute Classifier single-vendor ML risk (Groq/Qwen3)

**Honest Truth:** C4, the Dispute Classifier, runs on Qwen3-32B via Groq. Single vendor, single model. Groq models can 403 even when they appear in the model list. Vendor pricing, availability, or model deprecation are single points of failure for C4.

**Structured Answer:**
1. Acknowledge clean. "C4 is currently single-vendor: Qwen3-32B via Groq. If Groq changes pricing, access, or deprecates the model, C4 needs a new backend. That is a real dependency."
2. Reframe with criticality. C4 is NOT on the critical path for loan pricing. The two-step classification + conditional offer mechanism runs on C1 (failure classification) and C2 (PD pricing). C4 classifies whether the underlying payment dispute has characteristics that change the bridge eligibility assessment — it is advisory, with a fallback path. A C4 failure routes to the human review queue, not a pipeline halt. The 94ms SLO is not gated on C4 — C4 runs in parallel with C6 AML/velocity screening, not on the critical latency path.
3. State the current controls. The CLAUDE.md rules for C4 LLM backends are explicit: never switch the model without a full 100-case negation corpus run; never add stop sequences that break Qwen3 generation inside `<think>` blocks; always benchmark through the full DisputeClassifier pipeline, not raw LLM calls. That discipline limits model-swap risk — any new backend must pass the same validation gate.
4. Name the milestone. "Second LLM backend validated — Anthropic Claude or local vLLM Qwen — so C4 has a tested fallback. That removes the single-vendor dependency."

**Don't-say-this:**
- ❌ "Groq is reliable — they're a top inference provider" — reliability is not the risk; vendor lock-in is
- ❌ "We can swap models easily" — the negation corpus validation requirement means a swap is not trivial; don't misrepresent it
- ❌ "C4 is critical to the offer logic" — it is advisory; misclassifying its role overstates the risk

**Resolution Milestone:** Second LLM backend validated against the negation corpus and integrated as a fallback; single-vendor dependency removed.

**Investor Intuition target:** "C4 is advisory, not critical-path. They know the difference and they've built the fallback plan."

**Drill linkage:** No direct Q-TECH drill maps to this bear case — it is a technical diligence question, not a standard investor pitch probe. Closest context is Q-TECH-11 (C1 architecture rationale). Confirmed in drill.md.

---

## B-TECH-05 — Early infra fragility signals (PyTorch+LightGBM macOS deadlock)

**Honest Truth:** During development, the test suite surfaced a specific deadlock: PyTorch (BLAS threads) and LightGBM (OpenMP threads) competing in the same pytest process on macOS. The symptom is a hung test run. This is a local-development issue, not a production issue — production inference runs in isolated containers, one model per process. But it was a real fragility that had to be found and fixed.

**Structured Answer:**
1. Acknowledge clean. "We caught a specific issue during development: PyTorch + LightGBM deadlock on macOS in the same pytest process due to competing thread libraries. It is documented and resolved."
2. Reframe as evidence of rigour. Finding and documenting a threading conflict before production is exactly what a disciplined test suite is supposed to do. The fix is deterministic: a session-scoped autouse pytest fixture sets `torch.set_num_threads(1)` and `torch.set_num_interop_threads(1)` before any test that uses both libraries. The workaround is in CLAUDE.md — it is not tribal knowledge. Any engineer joining the project reads it on day one.
3. Production relevance. This deadlock does not affect production. Production runs C1 (PyTorch + LightGBM) inside a containerised service with a single Python process per container. There is no shared process between model types in the production architecture. The issue was local-development-specific: pytest collecting tests from multiple model files in a single run.
4. Name the milestone. "CI-level regression gates are in place — the threading fix is baked into the test configuration; any regression in the CI environment will surface before it reaches staging."

**Don't-say-this:**
- ❌ "It was just a dev environment issue — doesn't matter" — dismisses a real signal; own the finding
- ❌ "We've fixed all the infra issues" — overstatement; what we know is we fixed this specific one and have gates to catch others
- ❌ "It's a known macOS quirk" — true but generic; the specific answer (thread count fixture) is more credible than a generic deflection

**Resolution Milestone:** CI-level regression gates in place; threading fix is baked into session configuration and reproducible across environments.

**Investor Intuition target:** "They found a threading deadlock, documented it, fixed it, and gated it in CI. That is what rigorous engineering looks like before production."

**Drill linkage:** No direct Q-TECH drill maps to this bear case — it is a technical diligence probe, not a standard pitch question. The evidence it provides reinforces Q-TECH-08 ("Is this real or is it a deck?"). Confirmed in drill.md.
