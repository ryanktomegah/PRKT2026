# EPG-20 / EPG-21 — Patent Counsel Briefing + Language Scrub

**Status:** 🟡 Pending non-provisional filing
**Decided:** 2026-03-19
**Decision authority:** Founder + patent counsel
**Source rationale:** [`/CLAUDE.md`](../../CLAUDE.md) § EPG-20/21
**Related briefing:** [`../patent_counsel_briefing.md`](../patent_counsel_briefing.md)
**Related ref:** [`../patent/Provisional-Specification-v5.2.md`](../patent/Provisional-Specification-v5.2.md), [`../patent/Patent-Family-Architecture-v2.1.md`](../patent/Patent-Family-Architecture-v2.1.md)

---

## EPG-20 — Core novel claim scope

The novel claim being filed is **two-step classification + conditional offer logic**, *not* the bridge loan mechanics.

### What this means

Bridge loan mechanics — funding a temporarily-failed payment, collecting a fee, repaying on settlement — are partially covered by JPMorgan US7089207B1 (Tier 1 listed counterparties only). LIP's contribution and the only thing patent counsel should be claiming is the **classification gate** that decides which payments are eligible for an offer in the first place: the two-step structure where (a) ISO 20022 events are classified against a failure taxonomy, and (b) the offer logic is conditionally gated by the classification result, with sub-classification of certain hold types into bridgeable / non-bridgeable categories even when the current implementation codes one of those categories as block-all.

### What the claims must cover

1. Classification of ISO 20022 events against a failure taxonomy
2. Conditional gating of the offer logic by classification result
3. The sub-classification mechanism (B1/B2 or equivalent) — claimed *as a structure*, even though current code is block-all on the entire class. The structure is the patentable artifact; the current default policy is configuration.

### What the claims must NOT do

Claim Tier 1 mechanics that JPMorgan already covers. Claim the bridge loan instrument structure without the classification gate (which would invalidate over prior art). Tie the claims to a specific implementation rather than the gate concept.

---

## EPG-21 — Language scrub for the published spec

The following words must **never appear** anywhere in the published patent spec:

- AML
- SAR
- OFAC
- SDN
- compliance investigation
- tipping-off
- suspicious activity
- PEP

### Replacement vocabulary

| Forbidden term | Replacement |
|----------------|-------------|
| AML / SAR / compliance hold | classification gate |
| SAR investigation | hold type discriminator |
| `hold_bridgeable` flag | bridgeability flag |
| Procedurally-resolvable hold | procedural hold |
| AML/SAR-typed hold | investigatory hold |

### Why this matters

The patent is a published, indexed, full-text-searchable document. Once filed, it is permanently associated with the BPI brand in any compliance-related search. Two failure modes follow from sloppy language:

1. **FATF tipping-off exposure.** Publishing a spec that says "we detect SAR-coded payments and route them differently" is a written admission that BPI's technology is designed around the existence of SARs at customer banks. Even though LIP doesn't actually see SAR codes (see [`EPG-19`](EPG-19_compliance_hold_bridging.md) and [`EPG-04-05`](EPG-04-05_hold_bridgeable.md) — that's the whole point of the `hold_bridgeable` design), the claim language *describing* such a system creates the appearance of one. FATF examiners do not read the difference.

2. **Pilot bank reputational concern.** A bank's legal team searching the patent literature for "AML" + "bridging" will find LIP's spec and immediately escalate to their head of compliance. The conversation that follows cannot be unwound. Using the neutral vocabulary above means the spec describes a classification system, which is how it should read to anyone who is not already inside the EPIGNOSIS conversation.

### Non-enumeration rule

The list of BLOCK-class ISO 20022 codes (DNOR, CNOR, RR01–RR04, AG01, LEGL) **must not appear in any claim or example.** Enumerating them publishes a circumvention roadmap: any party that wanted to route a payment around LIP's gate now knows exactly which codes to avoid. Claim the existence of the gate, not its contents. If counsel needs example codes for clarity, use generic placeholders (CODE_X, CODE_Y) and document the real list only in the trade-secret schedule.

## Open dependency

Both EPG-20 and EPG-21 are pending non-provisional filing. The provisional specification [`../patent/Provisional-Specification-v5.2.md`](../patent/Provisional-Specification-v5.2.md) already conforms to these rules, but counsel review and the non-provisional filing have not yet happened. Until they do, the patent moat is provisional only. See [`../../engineering/OPEN_BLOCKERS.md`](../../engineering/OPEN_BLOCKERS.md).
