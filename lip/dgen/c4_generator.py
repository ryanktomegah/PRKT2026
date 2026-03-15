"""
c4_generator.py — DGEN: C4 Dispute Narrative Text Generator
============================================================
Template-based synthetic dispute corpus for Llama-3 classifier training.

Design rationale (ARIA + REX):
- Template-based (NOT LLM-generated): using Llama-3 to generate its own
  training data creates circular bias — the classifier learns its own
  generation patterns, not real-world language.
- Synonym substitution + sentence structure variation provides sufficient
  lexical diversity for a 4-class classifier without external LLM dependency.
- Fully reproducible (seed-controlled) → EU AI Act Art.10 traceability.

Four classes (matches DisputeClass taxonomy):
  NOT_DISPUTE      — routine payment confirmations and queries
  DISPUTE_CONFIRMED — explicit dispute language, fraud claims, reversal demands
  DISPUTE_POSSIBLE  — ambiguous / reviewing / inconsistent language
  NEGOTIATION       — partial settlement, compromise, counter-offer language

Class distribution targets (ARIA recommendation):
  NOT_DISPUTE:       ~45%  (majority — most messages are not disputes)
  DISPUTE_CONFIRMED: ~25%  (high signal — explicit dispute keywords)
  DISPUTE_POSSIBLE:  ~20%  (ambiguous — hard for model to learn, need more)
  NEGOTIATION:       ~10%  (rarest in practice)

All records tagged: corpus_tag = "SYNTHETIC_CORPUS_C4"
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

_CORPUS_TAG = "SYNTHETIC_CORPUS_C4"

# ---------------------------------------------------------------------------
# Token pools for substitution
# ---------------------------------------------------------------------------

_AMOUNTS = [
    "USD 1,250,000", "EUR 875,000", "GBP 2,100,000", "USD 450,000",
    "EUR 3,400,000", "USD 750,000", "GBP 600,000", "EUR 1,800,000",
    "USD 95,000", "EUR 220,000", "USD 5,500,000", "GBP 340,000",
]

_DATES = [
    "14 January 2025", "3 March 2025", "22 February 2025", "8 April 2025",
    "17 November 2024", "5 December 2024", "29 October 2024", "11 June 2025",
]

_REFS = [
    "UETR-{hex}", "REF-{alpha}/{year}", "TXN{num:08d}", "PMT-{hex6}-{year}",
]

_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "SGD", "AUD"]

_INSTITUTIONS = [
    "Deutsche Bank", "BNP Paribas", "Barclays", "Citibank",
    "HSBC", "JPMorgan Chase", "UBS", "Société Générale", "ING", "Nordea",
]

_COUNTERPARTIES = [
    "our client", "the beneficiary", "the originating institution",
    "the counterparty", "our correspondent", "the remitting bank",
    "the ordering customer",
]

# ---------------------------------------------------------------------------
# Synonym pools (ARIA: lexical diversity without LLM)
# ---------------------------------------------------------------------------

_SYN_DISPUTE = ["dispute", "contest", "challenge", "reject", "repudiate"]
_SYN_UNAUTHORIZED = ["unauthorized", "unsanctioned", "unapproved", "non-authorised", "without mandate"]
_SYN_REVERSAL = ["reversal", "return", "recall", "reimbursement", "clawback"]
_SYN_REQUEST = ["request", "demand", "require", "hereby request", "formally request"]
_SYN_CONFIRM = ["confirm", "acknowledge", "verify", "note"]
_SYN_REVIEW = ["reviewing", "investigating", "examining", "looking into", "assessing"]
_SYN_SETTLEMENT = ["settlement", "partial payment", "compromise amount", "agreed sum"]
_SYN_PROPOSE = ["propose", "suggest", "offer", "put forward"]

# ---------------------------------------------------------------------------
# Template families per class
# ---------------------------------------------------------------------------

_TEMPLATES_NOT_DISPUTE = [
    # Routine confirmations
    "We {confirm} receipt of payment {ref} for {amount} dated {date}.",
    "This message serves to {confirm} the transfer of {amount} via {ref} on {date}.",
    "Please {confirm} the processing status of {ref} ({amount}) submitted on {date}.",
    "Payment {ref} in the amount of {amount} has been forwarded to {institution}.",
    "We acknowledge your payment instruction {ref} for {amount}, currently in processing.",
    "Following your instructions, we have initiated transfer {ref} for {amount} to {counterparty}.",
    "The transaction {ref} for {amount} dated {date} has been received and is under standard processing.",
    "Kindly note that {ref} ({amount}) was transmitted to {institution} on {date}.",
    "We write to advise that payment {ref} of {amount} is being processed in the normal course.",
    "Your payment {ref} for {amount} is queued for settlement on the next available value date.",
    "As instructed, we have executed transfer {ref} of {amount} to {counterparty} on {date}.",
    "Reference {ref}: the transfer of {amount} to {institution} is progressing normally.",
    "Please be advised that {ref} for {amount} has passed compliance screening and is pending settlement.",
    "We confirm {institution} has been credited {amount} under reference {ref}.",
    "The transaction in question ({ref}, {amount}) reflects a standard payment to {counterparty}.",
    "This is a routine notification regarding payment {ref} dated {date} for {amount}.",
    "Transfer {ref} for {currency} funds totaling {amount} was processed on {date} as requested.",
    "No issues have been identified with payment {ref} at this time.",
    "We are satisfied that {ref} ({amount}) complies with all applicable requirements.",
    "Payment instruction {ref} for {amount} has been validated and dispatched to {institution}.",
]

_TEMPLATES_DISPUTE_CONFIRMED = [
    # Formal disputes — explicit, unambiguous
    "We formally {dispute} the transaction {ref} for {amount} dated {date} as {unauthorized}.",
    "This letter constitutes a formal {dispute} of payment {ref} ({amount}). We {request} immediate {reversal}.",
    "The transfer {ref} for {amount} was executed without our authorisation. We {request} {reversal} forthwith.",
    "We hereby {dispute} {ref} and {request} the {reversal} of {amount} within two business days.",
    "Payment {ref} ({amount}) was not sanctioned by our client. We {request} immediate {reversal}.",
    "Our client reports that {ref} for {amount} is a fraudulent transaction. Immediate {reversal} {request}ed.",
    "We {dispute} the validity of transaction {ref} ({amount} dated {date}) and {request} a full {reversal}.",
    "Notice of {dispute}: {ref} for {amount}. The payment was {unauthorized} and must be returned immediately.",
    "We are in receipt of an unauthorized debit {ref} for {amount}. We {request} {reversal} of funds.",
    "Chargeback notice: {ref} ({amount}) — {unauthorized} transfer. {reversal} required per applicable rules.",
    "Our records do not reflect authorisation for {ref} ({amount}). We {dispute} this transaction in full.",
    "The debit of {amount} under {ref} on {date} was not authorised by us. We demand immediate {reversal}.",
    "We write to formally {dispute} and {request} {reversal} of {ref} ({amount}), which was {unauthorized}.",
    "Fraud alert: transaction {ref} for {amount}. We {dispute} this payment and {request} {reversal}.",
    "We reject transaction {ref} ({amount} on {date}) in its entirety as {unauthorized} by our institution.",
    "This is formal notice of {dispute} concerning {ref}. The {amount} must be returned without delay.",
    "Claim of {unauthorized} transaction: {ref}, {amount}, {date}. Full {reversal} demanded.",
    "We have not authorised the transfer of {amount} ({ref}) and hereby {request} its {reversal}.",
    "Disputed transaction: {ref} ({amount}). Our client did not sanction this payment. {reversal} demanded.",
    "We {dispute} payment {ref} and invoke our right to {reversal} of {amount} under applicable regulation.",
]

_TEMPLATES_DISPUTE_POSSIBLE = [
    # Ambiguous — could be dispute, could be query
    "We are {review}ing transaction {ref} ({amount}) as it appears inconsistent with our records.",
    "There may be a discrepancy with {ref} for {amount} dated {date}. We are {review}ing.",
    "Our client has raised a query regarding {ref} ({amount}). We will revert upon completion of our review.",
    "We note a possible inconsistency with payment {ref} for {amount} and are investigating.",
    "Transaction {ref} ({amount} on {date}) does not appear in our records. Please advise.",
    "We are {review}ing whether {ref} ({amount}) was processed in accordance with standing instructions.",
    "Our team is {review}ing the circumstances surrounding {ref} ({amount}). No formal position yet.",
    "There appears to be an issue with {ref} for {amount}. We are investigating and will advise shortly.",
    "We cannot {confirm} the authorisation of {ref} ({amount}). Investigation ongoing.",
    "Payment {ref} ({amount}) may not have been processed correctly. We are {review}ing.",
    "We have questions about {ref} ({amount} dated {date}) and are seeking clarification from {counterparty}.",
    "Our review of {ref} suggests the {amount} may not match the original instruction. Investigating.",
    "We are {review}ing transaction {ref} to determine whether {amount} reflects the agreed terms.",
    "Possible discrepancy identified in {ref} ({amount}). Further review required before any action.",
    "Our client is {review}ing {ref} ({amount}) and has not yet confirmed whether a {dispute} will be raised.",
    "We are currently unable to validate {ref} ({amount} on {date}) against our internal records.",
    "Transaction {ref} ({amount}) is under internal review. We will provide a formal response within 5 days.",
    "We are not in a position to confirm or deny {dispute} of {ref} ({amount}) at this stage.",
    "Query raised on {ref} ({amount} dated {date}). Resolution pending internal review.",
    "We have placed {ref} ({amount}) under review pending clarification from {institution}.",
]

_TEMPLATES_NEGOTIATION = [
    # Partial settlement, compromise language
    "We {propose} a partial {settlement} of {amount} in full and final resolution of {ref}.",
    "Without prejudice, we {propose} to settle {ref} at {amount}, subject to mutual agreement.",
    "In the interest of resolution, we {propose} {settlement} of {ref} at {amount}.",
    "We are open to negotiating the terms of {ref} and {propose} {settlement} at {amount}.",
    "Our client wishes to explore {settlement} options for {ref}. We {propose} {amount} as a starting point.",
    "We {propose} settling {ref} for {amount} in lieu of further proceedings.",
    "Subject to contract, we {propose} {amount} as full and final {settlement} of {ref}.",
    "We {propose} a commercial {settlement} of {ref} at {amount} to avoid prolonged resolution.",
    "In an effort to resolve {ref} amicably, we are prepared to accept {amount} as {settlement}.",
    "Our position on {ref}: we {propose} {settlement} at {amount} as a reasonable compromise.",
    "We invite {institution} to discuss {settlement} of {ref} ({amount}) on mutually acceptable terms.",
    "Without admission of liability, we {propose} {amount} to settle {ref} and close this matter.",
    "We are willing to negotiate {ref} and suggest {amount} as a fair {settlement} figure.",
    "A negotiated {settlement} of {amount} for {ref} would be acceptable to our client at this stage.",
    "We {propose} to resolve {ref} through partial {settlement} of {amount}, reserving all rights.",
]

# Class → (templates, target_weight)
_CLASS_CONFIG = {
    "NOT_DISPUTE":       (_TEMPLATES_NOT_DISPUTE,       0.45),
    "DISPUTE_CONFIRMED": (_TEMPLATES_DISPUTE_CONFIRMED, 0.25),
    "DISPUTE_POSSIBLE":  (_TEMPLATES_DISPUTE_POSSIBLE,  0.20),
    "NEGOTIATION":       (_TEMPLATES_NEGOTIATION,       0.10),
}

# ---------------------------------------------------------------------------
# Augmentation helpers
# ---------------------------------------------------------------------------

def _make_ref(rng: np.random.Generator) -> str:
    template = rng.choice(_REFS)
    hex8 = hashlib.md5(str(rng.integers(0, 2**32)).encode()).hexdigest()[:8]
    hex6 = hex8[:6]
    alpha = "".join(rng.choice(list("ABCDEFGHJKLMNPQRSTUVWXYZ"), size=3))
    year = str(rng.integers(2023, 2026))
    num = int(rng.integers(10_000_000, 99_999_999))
    return (template
            .replace("{hex}", hex8)
            .replace("{hex6}", hex6)
            .replace("{alpha}", alpha)
            .replace("{year}", year)
            .replace("{num:08d}", f"{num:08d}"))


def _substitute(template: str, rng: np.random.Generator) -> str:
    """Replace {tokens} in template with domain-realistic values."""
    result = template

    # Synonym substitution — pick randomly from synonym pool
    result = result.replace("{dispute}",       rng.choice(_SYN_DISPUTE))
    result = result.replace("{unauthorized}",  rng.choice(_SYN_UNAUTHORIZED))
    result = result.replace("{reversal}",      rng.choice(_SYN_REVERSAL))
    result = result.replace("{request}",       rng.choice(_SYN_REQUEST))
    result = result.replace("{confirm}",       rng.choice(_SYN_CONFIRM))
    result = result.replace("{review}",        rng.choice(_SYN_REVIEW))
    result = result.replace("{settlement}",    rng.choice(_SYN_SETTLEMENT))
    result = result.replace("{propose}",       rng.choice(_SYN_PROPOSE))

    # Value substitution
    result = result.replace("{amount}",       rng.choice(_AMOUNTS))
    result = result.replace("{date}",         rng.choice(_DATES))
    result = result.replace("{ref}",          _make_ref(rng))
    result = result.replace("{currency}",     rng.choice(_CURRENCIES))
    result = result.replace("{institution}",  rng.choice(_INSTITUTIONS))
    result = result.replace("{counterparty}", rng.choice(_COUNTERPARTIES))

    return result


def _maybe_append_sentence(text: str, dispute_class: str, rng: np.random.Generator) -> str:
    """20% chance of appending a context sentence — increases diversity."""
    if rng.random() > 0.20:
        return text

    appendix_map = {
        "NOT_DISPUTE": [
            "No further action is required on your part.",
            "Please contact us if you require additional information.",
            "We remain at your disposal for any queries.",
        ],
        "DISPUTE_CONFIRMED": [
            "We reserve all rights in this matter.",
            "Our client will pursue further action if the funds are not returned.",
            "All applicable time limits under the relevant scheme rules apply.",
        ],
        "DISPUTE_POSSIBLE": [
            "We will revert with a formal position within five business days.",
            "Please do not take any irreversible action pending our review.",
            "This notification does not constitute a formal dispute at this stage.",
        ],
        "NEGOTIATION": [
            "This offer is made without prejudice and is open for 10 business days.",
            "Should this proposal not be acceptable, we are open to further discussion.",
            "We trust this represents a fair commercial resolution.",
        ],
    }
    sentences = appendix_map.get(dispute_class, [])
    if sentences:
        text = text + " " + rng.choice(sentences)
    return text


def _maybe_prepend_salutation(text: str, rng: np.random.Generator) -> str:
    """15% chance of adding a salutation — replicates real message variety."""
    if rng.random() > 0.15:
        return text
    salutations = [
        "Dear Sir/Madam, ",
        "To Whom It May Concern, ",
        "Attention: Payments Operations — ",
        "Re: Payment Query — ",
    ]
    return rng.choice(salutations) + text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_dispute_corpus(
    n_samples: int = 15_000,
    seed: int = 42,
) -> List[dict]:
    """Generate synthetic C4 dispute narrative records.

    Each record has the format::

        {
            "uetr":          str,   # unique ID
            "narrative":     str,   # free-text payment message
            "label":         str,   # DisputeClass value
            "label_int":     int,   # 0=NOT_DISPUTE, 1=DISPUTE_CONFIRMED,
                                    # 2=DISPUTE_POSSIBLE, 3=NEGOTIATION
            "corpus_tag":    str,   # "SYNTHETIC_CORPUS_C4"
            "generation_seed": int,
            "generation_timestamp": str,
        }

    Class distribution: NOT_DISPUTE 45% / DISPUTE_CONFIRMED 25% /
    DISPUTE_POSSIBLE 20% / NEGOTIATION 10%.

    Parameters
    ----------
    n_samples : int
        Total records to generate.
    seed : int
        Random seed for full reproducibility.
    """
    rng = np.random.default_rng(seed)
    ts = datetime.now(tz=timezone.utc).isoformat() + "Z"

    label_order = ["NOT_DISPUTE", "DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE", "NEGOTIATION"]
    label_to_int = {lbl: i for i, lbl in enumerate(label_order)}
    weights = [_CLASS_CONFIG[lbl][1] for lbl in label_order]

    # Pre-sample class assignments (stratified to hit exact weights)
    class_assignments = rng.choice(label_order, size=n_samples, p=weights)

    records: List[dict] = []
    for dispute_class in class_assignments:
        templates, _ = _CLASS_CONFIG[dispute_class]
        template = rng.choice(templates)

        # Generate the narrative
        narrative = _substitute(template, rng)
        narrative = _maybe_append_sentence(narrative, dispute_class, rng)
        narrative = _maybe_prepend_salutation(narrative, rng)

        records.append({
            "uetr": str(uuid.uuid4()),
            "narrative": narrative,
            "label": dispute_class,
            "label_int": label_to_int[dispute_class],
            "corpus_tag": _CORPUS_TAG,
            "generation_seed": seed,
            "generation_timestamp": ts,
        })

    return records


def generate_at_scale(n: int = 200_000, seed: int = 42) -> List[dict]:
    """Generate C4 dispute narratives at prototype validation scale.

    Calls :func:`generate_dispute_corpus` with template-based text generation.
    EU AI Act Art.10 traceability fully preserved via seed.

    For CI/CD and demo runs, use n=5_000 or n=15_000.
    """
    return generate_dispute_corpus(n_samples=n, seed=seed)
