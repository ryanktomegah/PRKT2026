# Patent Counsel Briefing — LIP System
## EPG-20 / EPG-21 — Handle in single session before non-provisional filing

---

## Item 1: What LIP actually does (EPG-20)

The core novel claim is **not** "bridges failing payments."

It is the **two-step classification + conditional offer logic**:

1. System receives an ISO 20022 failure event (pacs.002)
2. Classifies the rejection code against a failure taxonomy (Class A / B / C / BLOCK)
3. Generates a bridge loan offer **only if** the classified failure type passes a bridgeability gate

Both steps are independently patentable:
- The **classification logic** — mapping ISO 20022 rejection codes to a novel failure taxonomy with distinct maturity windows
- The **conditional gating** — offer generation predicated on classification outcome, not on raw payment fields

These must appear as independent claims, not only as dependent claims on the downstream bridge mechanics.

---

## Item 2: The B1/B2 sub-classification (EPG-20)

Within Class B, a second classification layer will exist that discriminates:
- **B1** — procedural holds (bridgeable once `hold_bridgeable=true` certified by bank)
- **B2** — investigatory holds (permanently blocked)

**Current code state**: this layer is coded as block-all pending a contractual bank API. The mechanism is implemented; the unlock condition is not yet in place.

**Why this matters for patent**: the *mechanism* — classifying by hold type within a class — is novel and should be covered in claims now. Adding it via continuation post-filing is expensive. Doing it now is free.

Claim language should describe the sub-classification mechanism as: *a second classification gate that receives a bridgeability certification from the originating institution and classifies a Class B failure event as procedural-hold or investigatory-hold*.

---

## Item 3: Language scrub table (EPG-21)

Search entire spec draft for the following terms and replace with the right-column equivalents. **None of the left-column terms should appear in the published document.**

| Remove | Replace with |
|--------|-------------|
| AML | hold-type classification; regulatory gate |
| SAR (Suspicious Activity Report) | investigatory hold |
| OFAC / SDN | external regulatory block |
| Compliance investigation | hold-type determination |
| Tipping-off | classification signal disclosure |
| Suspicious activity | hold-type indicator |
| PEP (Politically Exposed Person) | categorised originator |
| Money laundering | prohibited-party classification |

The spec must describe **what the system computes**, never what the **real-world regulatory event** is.

---

## Item 4: What NOT to claim (EPG-21)

The B2 hard-block enumeration — the specific list of ISO 20022 rejection codes that trigger a block — must **not** appear in any claim.

An enumerated public list of exactly what triggers a block is a roadmap for circumventing it: a bad actor reads the claim, uses a code not on the list, and the gate does not fire.

The claim should describe:
- The **existence** of a classification gate that routes to a hard-block outcome
- The **criterion** (classification result = investigatory-hold or blocked class)
- **Not** the specific enumeration of codes that produce that result

The code enumeration belongs in the specification description (not claims), and even there, counsel should consider whether to publish the complete list.

---

## Dependency note

EPG-20/21 are **independent** of the license agreement (EPG-04/05) and run in parallel. The patent filing timeline does not wait for the pilot bank contract. Both tracks should be active simultaneously.
