# RBC Contamination Scan — Findings

**Scan date:** 2026-04-17
**Scope:** Entire `PRKT2026` repository tree (source + docs + scripts)
**Scanner:** Task 2.1 of Pre-Lawyer Review Plan
**Status of this document:** Scan + classification complete; NO FIXES APPLIED in this task
(per plan, fixes are Task 2.2's responsibility)

---

## 1. Summary counts

### File-level (unique files containing at least one match)

| Metric | Value |
|---|---|
| Files with matches (org/people sweep) | 31 |
| Files with BIC-code (`ROYC…`) matches | 2 (both are the search-terms/plan doc) |
| Files with job-title matches | 10 |
| Total raw match lines (case-sensitive) | 568 |
| Total raw match lines (case-insensitive, incl. duplicates) | 827 |
| Combined raw-match file size | ~145 KB |

### Classification (unique files)

| Class | # files | Meaning |
|---|---|---|
| **A — Acceptable** | 22 | Expected use of RBC name: as a named prospective pilot bank, as a Canadian commercial-bank example in public filings/market-size context, or referenced in the review/plan scaffolding itself. |
| **B — Attention (needs review)** | 7 | RBC mentioned in a way that _looks_ public but the specific information could have been reinforced or refined by internal exposure; counsel / human review needed before clearing. |
| **C — Contamination** | 2 | RBC-specific info that Ryan could plausibly only know from internal exposure, requiring active fix. |
| **F — False positive** | 1 | Literal string match on RBC-unrelated content (e.g. `rbc` as substring of a base64 Go module hash). |

> Note: "A" is expected and not individually listed below per plan instruction.
> "F" is called out explicitly so Task 2.2 does not waste time on non-findings.

---

## 2. Per-file table (all 32 files, including the one F-class)

| # | File | Match lines | Class | Context / Reason |
|---|---|---|---|---|
| 1 | `docs/business/fundraising/ip-risk-pre-counsel-analysis.md` | 568 | A | The IP-risk analysis doc intentionally enumerates RBC facts (employment date, offer-letter clauses, retail banking role) — it is the canonical record of exposure. Entire purpose is to capture the RBC–IP nexus. |
| 2 | `docs/business/fundraising/ip-risk-pre-counsel-analysis-revised.md` | 230 | A | Revised version of #1, same purpose. |
| 3 | `docs/business/bank-pilot/rbc-pilot-strategy.md` | 126 | **B** | RBC pilot kit — expected to name RBC — but contains executive-level org-chart detail (Derek Neldner, Sean Amato-Gauci, Erica Nielsen, Naim Kazmi, Sid Paquette), specific org-reorg date ("post Sept 2024 reorg"), and one line that explicitly self-references: `Erica Nielsen — Group Head, Personal Banking — your former division` (line 17). That "your former division" phrasing *confirms internal knowledge* and is the flag. Individual officer names are publicly disclosed (RBC investor relations), but the aggregation + "your former division" framing is exactly the class of B-ordering that counsel will want to re-review before pilot engagement. Task 2.2 target. |
| 4 | `docs/business/GTM-Strategy-v1.0.md` | 88 | **B** | Contains: "AI Group (Bruce Ross) formed February 2026, CEO-direct, hunting for AI-generated P&L use cases". The *fact* that AI Group exists under Bruce Ross has been publicly reported; the specific internal framing ("hunting for AI-generated P&L use cases") is the kind of phrasing that sounds like internal corridor talk, not a public press release. Also names Sid Paquette as RBCx head (public). Needs line-level review in Task 2.2. |
| 5 | `docs/superpowers/plans/2026-04-17-pre-lawyer-review.md` | 76 | A | This is the review plan itself — contains RBC as search-target meta text, not source info. Scaffolding. |
| 6 | `docs/business/fundraising/ip-risk-analysis-prompt.md` | 72 | A | Prompt that was used to generate #1. Same purpose. |
| 7 | `docs/business/fundraising/pre-fundraising-checklist.md` | 39 | A | Fundraising checklist — references RBC clause resolution as a blocking item. No internal info. |
| 8 | `docs/superpowers/specs/2026-04-17-pre-lawyer-review-design.md` | 26 | A | Design doc for the review process; RBC is mentioned only as a search target. |
| 9 | `docs/business/fundraising/investor-risk-disclosure.md` | 24 | A | Investor disclosure listing the RBC IP risk as a known issue. Transparency, not contamination. |
| 10 | `docs/engineering/review/2026-04-17/week-1-ip-timing/appendix-commit-forensics.md` | 20 | A | Commit forensics appendix (output of Task 1.x). RBC mentioned as timing anchor (employment start date). |
| 11 | `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-search-terms.md` | 16 | A | This scan's own search-term list. Trivially self-matches. |
| 12 | `docs/superpowers/plans/2026-04-10-repo-cleanup.md` | 14 | A | Historical repo-cleanup plan; RBC mentioned only as context (pilot kit lives in `bank-pilot/`). |
| 13 | `docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline-summary.md` | 14 | A | Commit timeline summary referencing RBC employment as the anchor date. |
| 14 | `docs/operations/Operational-Playbook-v2.1.md` | 12 | A | Public guidance: open a business account, RBC is one option; Canadian commercial-bank market context. No internal info. |
| 15 | `docs/engineering/Next-Session-Production-Push-Plan.md` | 10 | A | Mentions RBCx in the context of `hold_bridgeable` pilot API clause (EPG-04/05). Pilot-target reference. |
| 16 | `docs/INDEX.md` | 8 | A | Navigation index; lists `bank-pilot/` kit as "RBC pilot kit". |
| 17 | `docs/business/fundraising/valuation-analysis.md` | 8 | A | RBC referenced only as Canadian bank comp. Public comparable. |
| 18 | `README.md` | 6 | A | RBC listed as first Canadian commercial-bank target. Public marketing. |
| 19 | `docs/business/Project-Status-Report-2026-04-11.md` | 6 | A | Status report flagging the RBC IP clause as critical-path. Awareness, not leakage. |
| 20 | `docs/legal/governance/Founder-Protection-Strategy.md` | 4 | A | Mentions "RBC work hours/resources must not be used for patent filing" — protective guidance, not contamination. |
| 21 | `docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline.csv` | 4 | A | CSV of commits; RBC appears in commit-message text of `docs(founder-fluency)` and `docs(bank-pilot)` commits. Already tracked. |
| 22 | `docs/business/fundraising/ff-round-structure.md` | 4 | A | F&F round structure — RBC IP clause listed as use-of-proceeds item #1. Planning, not leakage. |
| 23 | `PROGRESS.md` | 2 | A | Mentions RBCx in pilot-engagement pre-condition list. |
| 24 | `lip/c5_streaming/go_consumer/go.sum` | 2 | **F** (false positive) | Matches `mrbc=` and `brBc=` inside base64 Go module hashes (`github.com/emicklei/go-restful/…` and `github.com/serialx/hashring`). NOT an RBC reference. Zero action required. |
| 25 | `docs/superpowers/specs/2026-04-10-repo-cleanup-design.md` | 2 | A | Historical cleanup design; references `bank-pilot/` directory only. |
| 26 | `docs/legal/patent/Patent-Family-Architecture-v2.1.md` | 2 | A | Market-strategy: Canada is an incorporation jurisdiction; RBC is listed as one of several Canadian prospects. Public comparable. |
| 27 | `docs/legal/inventors-notebook/README.md` | 2 | A | Legal dates-anchor list. Notes 2026-01-12 as RBC employment start (IP clause attach). Intentional record. |
| 28 | `docs/engineering/specs/BPI_C7_Component_Spec_v1.0_Part2.md` | 2 | **B** | Line 689 references `RBCCoreAdapter` as an example class name in C7 spec. Pattern `{BankName}CoreAdapter` is benign in principle, but this is **patent-claim-adjacent spec** — naming RBC specifically (vs. `ExampleBankCoreAdapter`) could be read in litigation as evidence the patent was drafted with RBC-specific integration in mind. Review recommended; low-effort rename. |
| 29 | `docs/engineering/specs/BPI_C7_Component_Spec_v1.0_Part1.md` | 2 | **B** | Same issue as #28 — line 749 lists `RBCCoreAdapter` alongside `CitiCoreAdapter`, `BNSCoreAdapter`. Not internal info; naming-hygiene concern for patent-adjacent spec. |
| 30 | `docs/engineering/review/2026-04-17/week-1-ip-timing/commits-off-hours.txt` | 2 | A | Output of off-hours commit audit; references RBC hours only as schedule anchor. |
| 31 | `docs/engineering/OPEN_BLOCKERS.md` | 2 | A | Blockers register: RBC IP clause, RBCx pilot. Tracking. |
| 32 | `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-raw-matches.txt` | self | A | Grep output from this scan. Self-reference. (Not in the "31 source files" count; this is the scan output itself.) |

---

## 3. C-class findings (contamination requiring fix)

**Count: 2 line-level findings across 1 file**

### C-1 — `docs/business/bank-pilot/rbc-pilot-strategy.md:17`

```
| **Erica Nielsen** | Group Head, Personal Banking | **LOW** — your former division, retail-focused, not relevant to LIP |
```

**Why C (not B):** the phrase "**your former division**" is an explicit, first-person acknowledgement of Ryan's internal RBC history, embedded in a document that is nominally for pilot-strategy planning. This is NOT information a stranger would have. It is a leakage vector because:

1. It is a contemporaneous admission that internal RBC context was used to author the doc.
2. If this doc were ever discovered in litigation (and it would be, in any RBC-initiated dispute), this line is Exhibit A: "defendant's own pilot-strategy document shows they leveraged their former RBC insider position."

**Recommended fix in Task 2.2:** delete the "your former division" phrasing and replace with neutral framing (e.g. simply "LOW — retail-focused, not relevant to LIP"). The executive-name row itself is public org-chart info and can stay.

### C-2 — `docs/business/bank-pilot/rbc-pilot-strategy.md` (file-level)

The entire document is titled "RBC Pilot Strategy — Internal Planning Document" and declares itself "CONFIDENTIAL — BPI internal use only." Task 2.2 must do a **line-by-line review** to check every factual claim (org-chart, reorg dates, specific executive remits, "hunting for AI use cases" phrasing) against publicly-sourceable references (RBC press releases, investor day decks, LinkedIn). Any unsourced claim is a candidate for C-reclassification.

**Recommended fix in Task 2.2:**
1. Full line-by-line review of the file against public sources.
2. Add inline citations for every executive fact (e.g. "Derek Neldner [RBC 2024 Annual Report, p. 12]").
3. Any fact with no public source gets struck from the doc and logged to Red-Flag Register.

---

## 4. B-class findings (needs human review before final classification)

These are kept distinct from C because they could plausibly resolve either way after review.

### B-1 — `docs/business/bank-pilot/rbc-pilot-strategy.md` (entire file)

Covered above under C-2 — the file has both confirmed C (line 17) and pending B content (the rest).

### B-2 — `docs/business/GTM-Strategy-v1.0.md`

Lines of concern:

- L186: `| 2024–2026 developments | Acquired HSBC Bank Canada (2024)…; AI Group (Bruce Ross) formed February 2026, CEO-direct, hunting for AI-generated P&L use cases; new Transaction Banking unit launched per McKinsey Global Payments 2025 |`
- L191: `| Entry — Door 3 | **Bruce Ross, AI Group** (Feb 2026, CEO-direct)…`
- L194: `| AI Group angle | Bruce Ross's AI Group needs demonstrable AI P&L by 2027…`
- L353: `Simultaneously reach Bruce Ross (AI Group) through SIBOS or Borealis AI Vancouver events`
- L621: `RBC entry activated | RBCx application via rbcx.com; Borealis AI Vancouver events; initiate connection with Bruce Ross and Sid Paquette`

**Why B:** The existence of RBC AI Group and Bruce Ross's role is publicly reported. The specific phrasing ("hunting for AI-generated P&L use cases", "needs demonstrable AI P&L by 2027") reads like internal corridor framing, not a quote from a press release. Task 2.2 must source-verify each claim. If a claim has no public source, it is C.

### B-3 — `docs/engineering/specs/BPI_C7_Component_Spec_v1.0_Part1.md:749` and `Part2.md:689`

```
Part1.md:749:   RBCCoreAdapter         — implements CoreBankingAdapter for RBC
Part2.md:689:   adapter — `CitiCoreAdapter`, `RBCCoreAdapter`, etc. — cannot be validated until
```

**Why B:** This is the C7 Component Spec, which is patent-claim-adjacent. Naming `RBCCoreAdapter` (vs. a generic `ExampleBankCoreAdapter`) could be read in litigation as evidence that RBC-specific integration was contemplated as part of the inventive concept. No internal RBC info is disclosed (the adapter is not implemented), but **patent-hygiene rule from EPG-20/21 in CLAUDE.md says specs must not name specific banks in claim-bearing passages.** Recommend rename to generic `BankXCoreAdapter` or similar in Task 2.2.

**This is adjacent to Escalation Trigger #1** (RBC contamination in patent-claim-critical code or docs). It is not yet an escalation — the spec names RBC only as one of a list of examples, not as the sole or novel integration — but counsel should be told about this cluster.

---

## 5. BIC-code sweep (`ROYC[A-Z0-9]{4,8}`)

**2 hits, both in scan/plan scaffolding. Zero BIC codes in source, fixtures, or code.**

- `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-search-terms.md:20` — the example BICs listed in the search terms. A.
- `docs/superpowers/plans/2026-04-17-pre-lawyer-review.md:338` — the same example BICs in the plan template that we copied from. A.

No `ROYCCAT2` / `ROYCCAT2XXX` / `ROYCUS33` usage anywhere in `lip/` or test fixtures. This is a **negative contamination signal** (good): test corridors do not point at a real RBC BIC. The plan noted that `ROYCCAT2` would be "CORRECT usage as a counterparty in test data" — we don't even need to defend that, because it isn't present.

---

## 6. Job-title sweep (`Credit Management Resolution Officer` | `Resolution Officer`)

**10 hits across 5 files, all A-class.**

- 3 in `docs/business/fundraising/ip-risk-pre-counsel-analysis.md` + 1 in `-revised.md` — intentional identity-context statements for counsel ("I am currently employed at RBC as a Credit Management Resolution Officer…"). These are required for a counsel briefing and are not contamination.
- 1 in `docs/business/fundraising/ip-risk-analysis-prompt.md` — the prompt that produced the analysis docs.
- 1 in `docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline-summary.md:114` — note on off-hours flex hours in the commit audit. Operational context.
- 2 in the pre-lawyer review plan and this scan's own search-terms (scaffolding).

**Zero job-title matches in source code, fixtures, CI configs, or commit metadata.**

---

## 7. Commit-message sweep (separate from file-content sweep)

```
f0951e485710c67148b6133c72adbbe72c9b129c  docs(founder-fluency): write Patent bear-case with META-01 (RBC IP clause)
238bb6220cbc82ca9c79dd2ee59061e0143e4628  docs: add RBC pilot bank engagement strategy
```

Both commits name RBC in their subject line. Classification: **A** — these are docs-only commits that introduce pilot-strategy / IP-risk content, where naming RBC in the subject is appropriate (that is what the commit is about). No fix required. Listed here so the record is complete.

---

## 8. POTENTIAL ESCALATION items

**None at this time.**

The C-class findings are in a docs-only file (`bank-pilot/rbc-pilot-strategy.md`), not in `lip/` patent-claim-critical code. Escalation Trigger #1 is "RBC contamination found in patent-claim-critical code or docs" — the B-class `RBCCoreAdapter` naming in `BPI_C7_Component_Spec_v1.0_*` is patent-claim-adjacent but does not disclose internal info; it is a naming-hygiene issue. Counsel should be told, but it does not meet the escalation bar.

If Task 2.2 review of the pilot-kit reveals specific non-public facts (e.g. internal strategy quotes, compensation figures, internal-only organisational changes), those become escalation items at that point.

---

## 9. Next steps

**Task 2.2 will:**
1. Perform line-by-line public-source verification of `docs/business/bank-pilot/rbc-pilot-strategy.md` and apply fixes (including the C-1 "your former division" edit).
2. Source-verify each Bruce Ross / AI Group / Transaction Banking claim in `docs/business/GTM-Strategy-v1.0.md`; strike unsourced claims.
3. Rename `RBCCoreAdapter` → generic placeholder in `BPI_C7_Component_Spec_v1.0_Part1.md` and `Part2.md` (patent-hygiene; coordinate with REX).
4. Add any stripped-out internal-only facts to the Red-Flag Register for counsel to triage.
5. Report back to Task 2.1's record with the applied fixes.

No fixes were applied in Task 2.1. Raw scan outputs are preserved in the sibling files:
- `rbc-raw-matches.txt`
- `rbc-bic-matches.txt`
- `rbc-job-title-matches.txt`
- `rbc-search-terms.md` (source-of-truth for the patterns used)
