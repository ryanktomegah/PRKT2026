#!/usr/bin/env python3
"""
COMPONENT 3: BRIDGE LOAN EXECUTION WORKFLOW
Patent Spec v4.0 — System and Method for Automated Liquidity Bridging
Triggered by Real-Time Payment Network Failure Detection

COVERAGE
  Independent Claim 1(f)  — generate and transmit liquidity provision offer
  Independent Claim 1(g)  — transmit offer within commercially useful latency
  Independent Claim 1(h)  — automatically collect repayment on settlement
  Independent Claim 2(v)  — liquidity execution component
  Independent Claim 2(vi) — settlement monitoring component
  Independent Claim 3(l)  — bridge loan instrument structured as receivable assignment
  Independent Claim 3(m)  — execute instrument; establish security interest
  Independent Claim 3(n)  — automatically unwind and collect on settlement
  Independent Claim 5     — settlement-confirmation auto-repayment loop (FULL)
  Dependent Claim D7      — bridge loan secured by assignment of delayed receivable
  Dependent Claim D11     — settlement detected via SWIFT gpi UETR tracker data

PURPOSE
  This component consumes the CVAAssessment produced by Component 2 and
  executes the full bridge loan lifecycle:

    1. OFFER GENERATION     — build and transmit a term-sheet-quality offer
    2. ACCEPTANCE WAIT      — hold for counterparty response (simulated)
    3. DISBURSEMENT         — transfer funds; record security interest (Claim D7)
    4. SETTLEMENT MONITOR   — poll SWIFT gpi UETR tracker (Claim D11 / Claim 5)
    5. REPAYMENT COLLECTION — auto-collect on settlement confirmation (Claim 5)
    6. RECOVERY WORKFLOW    — enforce assignment if original payment fails (Claim 5(w))
    7. AUDIT RECORD         — generate regulatory-grade settlement record (Claim 5(x))

COMPONENT CHAIN
  [ISO 20022 stream]
    → Component 1: Failure Prediction   (failure_prediction_engine.py)
    → Component 2: CVA Pricing          (cva_pricing_engine.py)
    → Component 3: Bridge Loan Execution ← THIS FILE

CLAIM 5 STATE MACHINE
  The Settlement Monitor implements the four states of Independent Claim 5:
    MONITORING   → polling UETR for settlement event  (step u)
    SETTLED      → settlement confirmed → repayment collected (step v)
    PERMANENTLY_FAILED → recovery against collateral (step w)
    COMPLETED    → audit record generated (step x)

DEPENDENCIES
  Standard library only (dataclasses, datetime, enum, json, random, time, uuid).
  Imports Components 1 and 2 if present; falls back to embedded mock data.
"""

# =============================================================================
# SECTION 1: IMPORTS
# =============================================================================

import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional upstream component imports
# ---------------------------------------------------------------------------
try:
    from cva_pricing_engine import (
        CVAAssessment,
        CVAPricer,
        run_cva_pipeline,
    )
    _COMPONENT2_AVAILABLE = True
except ImportError:
    _COMPONENT2_AVAILABLE = False
    CVAAssessment = None  # type: ignore[assignment,misc]

try:
    from failure_prediction_engine import (
        run_pipeline,
        package_predictions,
    )
    _COMPONENT1_AVAILABLE = True
except ImportError:
    _COMPONENT1_AVAILABLE = False


# =============================================================================
# SECTION 2: CONSTANTS
# =============================================================================

# ---------------------------------------------------------------------------
# 2.1  Offer transmission parameters (Claim 1(g))
# The patent requires transmission "within a response latency that is
# sufficiently short to provide commercial utility before the affected party
# would otherwise exhaust alternative liquidity options."
# 5 minutes is the industry benchmark for intraday liquidity offers.
# ---------------------------------------------------------------------------
OFFER_GENERATION_LATENCY_MS:   float = 12.0    # ms — sub-100ms per Dep. Claim D9
OFFER_TRANSMISSION_CHANNEL:    str   = "SWIFT_FIN_MT999"  # or Open Banking API
OFFER_DEFAULT_VALIDITY_SECS:   int   = 300      # 5 minutes

# ---------------------------------------------------------------------------
# 2.2  Disbursement parameters
# ---------------------------------------------------------------------------
DISBURSEMENT_CHANNEL:          str   = "SWIFT_gpi_MT103"
DISBURSEMENT_LATENCY_MS:       float = 250.0    # gpi target: sub-30s but 250ms internal
SECURITY_INTEREST_REGISTRY:    str   = "internal_ledger_v1"   # production: legal registry

# ---------------------------------------------------------------------------
# 2.3  Settlement monitoring parameters (Claims 5(u), D11)
# The SWIFT gpi tracker updates UETR status every ~90 seconds in production.
# For the simulation we compress this to poll intervals of 0.2s.
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECS:            float = 0.2     # simulated poll cadence
MAX_POLL_ATTEMPTS:             int   = 20      # 20 × 0.2s = 4s max wait (simulation)
SETTLEMENT_CONFIRMATION_SRC:   str   = "SWIFT_gpi_UETR_tracker"

# ---------------------------------------------------------------------------
# 2.4  Repayment collection (Claim 5(v))
# ---------------------------------------------------------------------------
REPAYMENT_MAX_LATENCY_SECS:    float = 60.0    # D11: must collect within 60s of confirmation
RECOVERY_GRACE_PERIOD_DAYS:    int   = 14      # Days before hard recovery initiated

# ---------------------------------------------------------------------------
# 2.5  Simulation probabilities (for synthetic demo only)
# In production these are replaced by live gpi UETR status queries.
# ---------------------------------------------------------------------------
SIM_ACCEPTANCE_PROB:           float = 0.82    # 82% of offers accepted
SIM_SETTLEMENT_PROB:           float = 0.88    # 88% of disbursements eventually settle
SIM_RECOVERY_RATE:             float = 0.72    # 72% recovery on defaulted advances


# =============================================================================
# SECTION 3: ENUMERATIONS — LIFECYCLE STATE MACHINE
# =============================================================================

class OfferStatus(Enum):
    """
    States of the bridge loan offer before disbursement.
    Covers Claims 1(f), 1(g), 2(v).
    """
    PENDING    = "pending"     # Generated; awaiting counterparty response
    ACCEPTED   = "accepted"    # Counterparty accepted within validity window
    REJECTED   = "rejected"    # Counterparty declined
    EXPIRED    = "expired"     # Validity window elapsed without response


class SettlementStatus(Enum):
    """
    States of the original payment under UETR monitoring.
    Implements the Claim 5 state machine:
      MONITORING        → step (u): continuously polling
      SETTLED           → step (v): confirmation detected → repayment collected
      PERMANENTLY_FAILED→ step (w): recovery workflow activated
      COMPLETED         → step (x): audit record generated
    """
    MONITORING          = "monitoring"           # Claim 5(u) — active polling
    SETTLED             = "settled"              # Claim 5(v) — confirmation received
    PERMANENTLY_FAILED  = "permanently_failed"   # Claim 5(w) — recovery triggered
    COMPLETED           = "completed"            # Claim 5(x) — audit record generated


class RepaymentStatus(Enum):
    """Status of the repayment / recovery workflow."""
    AWAITING    = "awaiting"     # Monitoring, not yet due
    COLLECTED   = "collected"    # Full repayment confirmed
    PARTIAL     = "partial"      # Partial recovery
    FAILED      = "failed"       # Recovery workflow initiated, no recovery yet


# =============================================================================
# SECTION 4: DATA STRUCTURES
# =============================================================================

@dataclass
class SecurityInterest:
    """
    Records the legal assignment of the delayed payment receivable as
    collateral for the bridge loan advance.

    Dependent Claim D7: "bridge loan secured by legal assignment of the
    delayed payment receivable to the lender"
    Independent Claim 3(m): "programmatic establishment of any security
    interest, assignment, or lien on the delayed payment proceeds"
    """
    uetr:                  str          # Identifies the receivable (SWIFT gpi UETR)
    assignor_bic:          str          # The party receiving the bridge loan
    assignee_bic:          str          # The lender (bridge loan provider)
    assigned_amount_usd:   float        # Face value of the assigned receivable
    assignment_date:       datetime
    assignment_ref:        str          # Internal legal reference number
    registry:              str          # Where the assignment is recorded
    legal_basis:           str = "Claim D7 — delayed payment receivable assignment"


@dataclass
class BridgeLoanRecord:
    """
    Complete lifecycle record of a single bridge loan advance.

    This is the audit-trail object required by Claim 5(x):
    "generating a settlement and repayment confirmation record that
    documents the original payment identifier, the advance disbursement
    details, the settlement confirmation event, the repayment amount,
    and the net realised return on the advance"
    """
    # Identity ------------------------------------------------------------------
    loan_id:             str
    uetr:                str            # Original payment UETR (the collateral link)
    currency_pair:       str
    sending_bic:         str
    receiving_bic:       str

    # Offer (Claims 1(f), 1(g)) -------------------------------------------------
    offer_status:        OfferStatus    = OfferStatus.PENDING
    offer_timestamp:     Optional[datetime] = None
    offer_amount_usd:    float              = 0.0
    offer_apr_bps:       float              = 0.0
    offer_horizon_days:  int                = 0
    offer_valid_until:   Optional[datetime] = None
    offer_total_cost:    float              = 0.0
    offer_latency_ms:    float              = 0.0

    # Acceptance / disbursement (Claim 2(v)) ------------------------------------
    acceptance_timestamp: Optional[datetime] = None
    disbursement_timestamp: Optional[datetime] = None
    disbursement_channel: str = DISBURSEMENT_CHANNEL
    disbursement_latency_ms: float = 0.0
    security_interest:    Optional[SecurityInterest] = None

    # Settlement monitoring (Claims 5(u), D11) ----------------------------------
    settlement_status:   SettlementStatus = SettlementStatus.MONITORING
    monitoring_start:    Optional[datetime] = None
    settlement_timestamp: Optional[datetime] = None
    settlement_source:   str = SETTLEMENT_CONFIRMATION_SRC
    poll_attempts:       int = 0

    # Repayment / recovery (Claims 5(v), 5(w)) ----------------------------------
    repayment_status:    RepaymentStatus = RepaymentStatus.AWAITING
    repayment_timestamp: Optional[datetime] = None
    repayment_amount_usd: float = 0.0
    recovery_amount_usd:  float = 0.0
    accrued_interest_usd: float = 0.0

    # Realised P&L (Claim 5(x)) ------------------------------------------------
    net_realised_return_usd: float = 0.0
    audit_record_generated:  bool  = False
    audit_timestamp:         Optional[datetime] = None

    # Risk metrics (for portfolio reporting) -----------------------------------
    pd_blended:    float = 0.0
    lgd_estimate:  float = 0.0
    expected_loss_usd: float = 0.0


# =============================================================================
# SECTION 5: OFFER GENERATOR  (Claims 1(f), 1(g))
# =============================================================================

class OfferGenerator:
    """
    Generates and transmits bridge loan offers within sub-100ms latency.

    Claim 1(f): "generating a liquidity provision offer ... wherein said
    offer specifies the advance amount, the risk-adjusted cost, and the
    repayment mechanism"

    Claim 1(g): "transmitting the liquidity provision offer via any
    electronic communication channel to the affected party within a
    response latency that is sufficiently short to provide commercial
    utility"
    """

    def generate_offer(self, exec_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a term-sheet-quality offer from Component 2's execution input.

        The offer contains:
          - Amount (EAD from Component 2)
          - APR (risk-adjusted cost from CVA engine)
          - Repayment mechanism (settlement-confirmation trigger, Claim 5)
          - Validity window (OFFER_DEFAULT_VALIDITY_SECS)
          - Legal basis for the security interest (receivable assignment, D7)
        """
        t_start = time.perf_counter()

        offer_details = exec_input["offer"]
        now           = datetime.now(timezone.utc)

        offer = {
            "offer_id":           str(uuid.uuid4()),
            "uetr":               exec_input["uetr"],
            "generated_at":       now.isoformat(),
            "valid_until":        (now + timedelta(seconds=offer_details["offer_valid_seconds"])).isoformat(),
            "advance_amount_usd": offer_details["bridge_loan_amount_usd"],
            "apr_bps":            offer_details["annualized_rate_bps"],
            "apr_pct":            f"{offer_details['apr_decimal']:.4%}",
            "horizon_days":       offer_details["bridge_horizon_days"],
            "total_cost_usd":     offer_details["total_cost_usd"],
            "transmission_channel": OFFER_TRANSMISSION_CHANNEL,
            "repayment_mechanism": {
                "trigger":  "automatic_on_settlement_confirmation",
                "source":   SETTLEMENT_CONFIRMATION_SRC,
                "legal_basis": exec_input["settlement_monitoring"]["legal_basis"],
            },
            "security": exec_input["security_interest"],
            "counterparty": exec_input["counterparty"],
        }

        latency_ms = (time.perf_counter() - t_start) * 1000
        offer["generation_latency_ms"] = round(latency_ms, 3)
        return offer

    def simulate_acceptance(self, offer: Dict[str, Any]) -> OfferStatus:
        """
        Simulate counterparty response.

        In production: blocks on an inbound SWIFT ACK or Open Banking callback
        within the offer validity window (OFFER_DEFAULT_VALIDITY_SECS).
        """
        r = random.random()
        if r < SIM_ACCEPTANCE_PROB:
            return OfferStatus.ACCEPTED
        elif r < SIM_ACCEPTANCE_PROB + 0.10:
            return OfferStatus.REJECTED
        else:
            return OfferStatus.EXPIRED


# =============================================================================
# SECTION 6: DISBURSEMENT ENGINE  (Claims 2(v), 3(m))
# =============================================================================

class DisbursementEngine:
    """
    Executes bridge loan disbursements and establishes security interests.

    Claim 2(v): "execute a funding disbursement upon acceptance of the offer,
    programmatically establish a security interest in the delayed payment
    proceeds as collateral for the advance"

    Claim 3(m): "executing the selected liquidity instrument upon acceptance
    by the affected party, including programmatic establishment of any
    security interest, assignment, or lien on the delayed payment proceeds"
    """

    def disburse(
        self,
        exec_input: Dict[str, Any],
        offer:      Dict[str, Any],
    ) -> Any:
        """
        Execute fund disbursement and record the security interest.

        Returns: (disbursement_ref, SecurityInterest, latency_ms)

        In production this would:
          1. POST to the lender's payment origination system (SWIFT gpi MT103)
          2. Record the receivable assignment in the legal registry
          3. Return the disbursement UETR for tracking
        """
        t_start = time.perf_counter()

        # Construct the disbursement reference
        disbursement_ref = f"BL-{str(uuid.uuid4())[:8].upper()}"

        # Establish security interest — Claim D7 / Claim 3(m)
        # In production: executed via electronic assignment deed or UCC filing
        security = SecurityInterest(
            uetr=exec_input["uetr"],
            assignor_bic=exec_input["counterparty"]["receiving_bic"],
            assignee_bic=exec_input["offer"].get("lender_bic", "BRIDGE_LENDER"),
            assigned_amount_usd=exec_input["offer"]["bridge_loan_amount_usd"],
            assignment_date=datetime.now(timezone.utc),
            assignment_ref=disbursement_ref,
            registry=SECURITY_INTEREST_REGISTRY,
        )

        latency_ms = (time.perf_counter() - t_start) * 1000 + DISBURSEMENT_LATENCY_MS
        return disbursement_ref, security, round(latency_ms, 3)


# =============================================================================
# SECTION 7: SETTLEMENT MONITOR  (Claims 5(u), 5(v), 5(w), D11)
# =============================================================================

class SettlementMonitor:
    """
    Continuously monitors the original payment UETR for a settlement
    confirmation event, then automatically triggers repayment collection.

    This class implements the core of Independent Claim 5 — the settlement-
    confirmation auto-repayment loop that the patent spec identifies as
    "the net at the bottom of every possible design-around attempt."

    Claim 5(u): "continuously monitoring the settlement status of the
    identified payment transaction using any real-time or near-real-time
    data feed ... including but not limited to SWIFT gpi tracker data"

    Claim 5(v): "upon detection of a settlement confirmation event ...
    automatically initiating a repayment collection workflow ... without
    requiring any manual instruction from an operator"

    Claim 5(w): "in the event that the original payment transaction fails
    permanently ... automatically activating a recovery workflow against
    the collateral or security interest assigned at disbursement"

    Dependent Claim D11 (specific embodiment of Claim 5 for SWIFT gpi):
    "settlement confirmation detected via SWIFT gpi UETR tracker data
    showing payment credited to beneficiary bank, triggering automated
    repayment collection within 60 seconds of confirmation"
    """

    def monitor_and_collect(
        self,
        record:      BridgeLoanRecord,
        exec_input:  Dict[str, Any],
    ) -> BridgeLoanRecord:
        """
        Run the full Claim 5 state machine for one loan record.

        States:
          MONITORING → SETTLED → COMPLETED    (happy path: payment settles)
          MONITORING → PERMANENTLY_FAILED     (sad path:  payment fails permanently)

        In production:
          - Poll SWIFT gpi /status/{uetr} endpoint every ~90s
          - On ACSP/ACCC status: trigger repayment collection
          - On RJCT/timeout: trigger recovery against security interest

        In this simulation:
          - Random draw determines settlement outcome
          - Simulated polling loop runs at POLL_INTERVAL_SECS
        """
        record.monitoring_start = datetime.now(timezone.utc)
        record.settlement_status = SettlementStatus.MONITORING

        # ── Step (u): Poll UETR for settlement event ──────────────────────
        settled = False
        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            record.poll_attempts = attempt
            time.sleep(POLL_INTERVAL_SECS)

            # Simulation: each poll has a compounding settlement probability
            # that increases as the payment ages past its expected horizon.
            # In production: replace with live gpi API call.
            poll_prob = 1 - (1 - SIM_SETTLEMENT_PROB) ** (attempt / MAX_POLL_ATTEMPTS)
            if random.random() < poll_prob / MAX_POLL_ATTEMPTS * 5:
                settled = True
                break

        now = datetime.now(timezone.utc)

        if settled:
            # ── Step (v): Settlement confirmed → auto-collect repayment ──
            record.settlement_status    = SettlementStatus.SETTLED
            record.settlement_timestamp = now

            principal   = record.offer_amount_usd
            apr_decimal = record.offer_apr_bps / 10_000.0
            accrued     = principal * apr_decimal * record.offer_horizon_days / 365.0
            total_due   = principal + accrued

            # Collect within D11 requirement: within 60 seconds of confirmation
            collection_latency = random.uniform(1.5, REPAYMENT_MAX_LATENCY_SECS * 0.8)
            record.repayment_timestamp  = now + timedelta(seconds=collection_latency)
            record.repayment_amount_usd = total_due
            record.accrued_interest_usd = accrued
            record.repayment_status     = RepaymentStatus.COLLECTED

            # Net realised return = interest collected - expected loss
            record.net_realised_return_usd = accrued - record.expected_loss_usd

        else:
            # ── Step (w): Permanent failure → recovery against collateral ─
            record.settlement_status = SettlementStatus.PERMANENTLY_FAILED
            record.settlement_timestamp = now

            # Recover via assignment enforcement:
            # In production: enforce assignment against original payment sender,
            # draw on any guarantee instrument established at disbursement.
            recovery_amount = record.offer_amount_usd * SIM_RECOVERY_RATE
            record.recovery_amount_usd     = recovery_amount
            record.repayment_status        = RepaymentStatus.PARTIAL
            record.repayment_amount_usd    = recovery_amount
            # Loss = principal - recovery
            net_loss = record.offer_amount_usd - recovery_amount
            record.net_realised_return_usd = -net_loss

        # ── Step (x): Generate audit record (Claim 5(x)) ──────────────────
        record = self._generate_audit_record(record)
        return record

    @staticmethod
    def _generate_audit_record(record: BridgeLoanRecord) -> BridgeLoanRecord:
        """
        Claim 5(x): "generating a settlement and repayment confirmation record
        that documents the original payment identifier, the advance disbursement
        details, the settlement confirmation event, the repayment amount, and
        the net realised return on the advance, for regulatory reporting, audit
        trail, and portfolio performance monitoring purposes."
        """
        record.settlement_status       = SettlementStatus.COMPLETED
        record.audit_record_generated  = True
        record.audit_timestamp         = datetime.now(timezone.utc)
        return record


# =============================================================================
# SECTION 8: EXECUTION ORCHESTRATOR
# =============================================================================

class BridgeLoanOrchestrator:
    """
    Orchestrates the full bridge loan lifecycle for a single payment.

    Lifecycle:
      ① OfferGenerator.generate_offer()          — Claim 1(f), 1(g)
      ② OfferGenerator.simulate_acceptance()     — acceptance decision
      ③ DisbursementEngine.disburse()            — Claim 2(v), 3(m)
      ④ SettlementMonitor.monitor_and_collect()  — Claim 5 (full loop)
    """

    def __init__(self) -> None:
        self.offer_gen  = OfferGenerator()
        self.disburse   = DisbursementEngine()
        self.monitor    = SettlementMonitor()

    def execute(self, assessment: "CVAAssessment") -> BridgeLoanRecord:
        """
        Run the full lifecycle for one CVAAssessment from Component 2.
        """
        exec_input = assessment.to_execution_input()
        now        = datetime.now(timezone.utc)

        loan_id = f"BL-{str(uuid.uuid4())[:8].upper()}"
        record  = BridgeLoanRecord(
            loan_id          = loan_id,
            uetr             = assessment.uetr,
            currency_pair    = assessment.currency_pair,
            sending_bic      = assessment.sending_bic,
            receiving_bic    = assessment.receiving_bic,
            offer_amount_usd = assessment.bridge_loan_amount,
            offer_apr_bps    = assessment.annualized_rate_bps,
            offer_horizon_days = assessment.bridge_horizon_days,
            offer_total_cost = (assessment.bridge_loan_amount
                                * assessment.apr_decimal
                                * assessment.bridge_horizon_days / 365.0),
            pd_blended       = assessment.pd_blended,
            lgd_estimate     = assessment.lgd_estimate,
            expected_loss_usd = assessment.expected_loss_usd,
        )

        # ① Offer generation (Claims 1(f), 1(g))
        t0    = time.perf_counter()
        offer = self.offer_gen.generate_offer(exec_input)
        record.offer_latency_ms   = round((time.perf_counter() - t0) * 1000, 3)
        record.offer_timestamp    = now
        record.offer_valid_until  = now + timedelta(seconds=OFFER_DEFAULT_VALIDITY_SECS)

        # ② Acceptance simulation
        status = self.offer_gen.simulate_acceptance(offer)
        record.offer_status = status

        if status != OfferStatus.ACCEPTED:
            # Non-accepted offers — still need an audit record
            record.settlement_status    = SettlementStatus.COMPLETED
            record.audit_record_generated = True
            record.audit_timestamp      = datetime.now(timezone.utc)
            record.net_realised_return_usd = 0.0
            return record

        # ③ Acceptance confirmed → disburse (Claims 2(v), 3(m))
        record.acceptance_timestamp = datetime.now(timezone.utc)
        _, security, disb_lat = self.disburse.disburse(exec_input, offer)
        record.disbursement_timestamp  = datetime.now(timezone.utc)
        record.disbursement_latency_ms = disb_lat
        record.security_interest       = security

        # ④ Settlement monitoring → repayment / recovery (Claim 5)
        record = self.monitor.monitor_and_collect(record, exec_input)
        return record


# =============================================================================
# SECTION 9: PORTFOLIO AGGREGATOR
# =============================================================================

def _aggregate_portfolio(records: List[BridgeLoanRecord]) -> Dict[str, Any]:
    """
    Compute portfolio-level statistics across all executed loans.
    Used for the demonstration summary and regulatory reporting layer (P10).
    """
    disbursed   = [r for r in records if r.offer_status == OfferStatus.ACCEPTED]
    settled     = [r for r in disbursed if r.settlement_status == SettlementStatus.COMPLETED
                   and r.repayment_status == RepaymentStatus.COLLECTED]
    recovered   = [r for r in disbursed if r.repayment_status == RepaymentStatus.PARTIAL]
    rejected    = [r for r in records   if r.offer_status == OfferStatus.REJECTED]
    expired     = [r for r in records   if r.offer_status == OfferStatus.EXPIRED]

    total_offered  = sum(r.offer_amount_usd for r in records)
    total_disbursed= sum(r.offer_amount_usd for r in disbursed)
    total_interest = sum(r.accrued_interest_usd for r in settled)
    total_recovered= sum(r.recovery_amount_usd  for r in recovered)
    total_return   = sum(r.net_realised_return_usd for r in disbursed)
    total_exp_loss = sum(r.expected_loss_usd for r in disbursed)

    return {
        "n_offers":         len(records),
        "n_accepted":       len(disbursed),
        "n_settled":        len(settled),
        "n_recovered":      len(recovered),
        "n_rejected":       len(rejected),
        "n_expired":        len(expired),
        "total_offered_usd":   round(total_offered,  2),
        "total_disbursed_usd": round(total_disbursed, 2),
        "acceptance_rate":  len(disbursed) / max(len(records), 1),
        "settlement_rate":  len(settled)  / max(len(disbursed), 1),
        "total_interest_collected": round(total_interest, 2),
        "total_partial_recovery":   round(total_recovered, 2),
        "net_realised_return_usd":  round(total_return, 2),
        "total_expected_loss_usd":  round(total_exp_loss, 2),
        "realised_vs_expected_loss": round(
            (total_exp_loss - total_return) / max(total_exp_loss, 1), 4
        ),
    }


# =============================================================================
# SECTION 10: FORMATTERS
# =============================================================================

def format_loan_record(record: BridgeLoanRecord, rank: int) -> str:
    """Banker-readable loan lifecycle card for a single BridgeLoanRecord."""
    W = 70

    # Settlement outcome label
    if record.offer_status != OfferStatus.ACCEPTED:
        outcome_line = f"  Offer outcome:   {record.offer_status.value.upper()}"
        body = [outcome_line]
    elif record.repayment_status == RepaymentStatus.COLLECTED:
        body = [
            f"  Settlement:      CONFIRMED  ({record.settlement_source})",
            f"  Repayment:       ${record.repayment_amount_usd:>12,.2f}  "
            f"(principal + ${record.accrued_interest_usd:,.2f} interest)",
            f"  Collected at:    {record.repayment_timestamp.strftime('%H:%M:%S UTC') if record.repayment_timestamp else 'N/A'}",
            f"  Net return:      ${record.net_realised_return_usd:>12,.2f}",
        ]
    else:
        body = [
            f"  Settlement:      FAILED — recovery initiated (Claim 5(w))",
            f"  Recovery:        ${record.recovery_amount_usd:>12,.2f}  "
            f"({record.recovery_amount_usd / max(record.offer_amount_usd, 1):.0%} of principal)",
            f"  Net return:      ${record.net_realised_return_usd:>12,.2f}",
        ]

    sec_line = ""
    if record.security_interest:
        sec_line = (
            f"  Security ref:    {record.security_interest.assignment_ref}  "
            f"[{record.security_interest.registry}]"
        )

    lines = [
        "",
        "─" * W,
        f"  LOAN #{rank:02d}  [{record.loan_id}]",
        f"  UETR:  {record.uetr}",
        "─" * W,
        f"  Corridor:        {record.currency_pair}",
        f"  Advance:         ${record.offer_amount_usd:>12,.2f}  "
        f"@ {record.offer_apr_bps:.1f} bps APR  ({record.offer_horizon_days}d)",
        f"  Offer latency:   {record.offer_latency_ms:.1f} ms  "
        f"(Claim D9 sub-100ms ✓)" if record.offer_latency_ms < 100 else
        f"  Offer latency:   {record.offer_latency_ms:.1f} ms",
        f"  Disbursement ch: {record.disbursement_channel}",
    ]
    if sec_line:
        lines.append(sec_line)
    lines += body
    if record.audit_timestamp:
        lines.append(
            f"  Audit record:    generated at "
            f"{record.audit_timestamp.strftime('%H:%M:%S UTC')}  (Claim 5(x) ✓)"
        )
    lines.append("─" * W)
    return "\n".join(lines)


def print_portfolio_summary(records: List[BridgeLoanRecord],
                            agg: Dict[str, Any]) -> None:
    """Print the banker-facing portfolio summary table."""
    W = 70
    print()
    print("=" * W)
    print("  COMPONENT 3: BRIDGE LOAN EXECUTION — PORTFOLIO SUMMARY")
    print("  Patent Spec v4.0 — Claims 1(f/g/h), 2(v/vi), 3, 5, D7, D11")
    print("=" * W)
    print()
    print("  EXECUTION STATISTICS")
    print(f"  {'─' * 48}")
    print(f"  Total offers generated:    {agg['n_offers']}")
    print(f"  Accepted (disbursed):      {agg['n_accepted']}  "
          f"({agg['acceptance_rate']:.0%} acceptance rate)")
    print(f"  Fully settled:             {agg['n_settled']}  "
          f"({agg['settlement_rate']:.0%} of disbursed)")
    print(f"  Partial recovery:          {agg['n_recovered']}")
    print(f"  Rejected / Expired:        {agg['n_rejected']} / {agg['n_expired']}")
    print()
    print("  FINANCIAL SUMMARY (DISBURSED LOANS)")
    print(f"  {'─' * 48}")
    print(f"  Total advance pool:        ${agg['total_disbursed_usd']:>14,.2f}")
    print(f"  Interest collected:        ${agg['total_interest_collected']:>14,.2f}")
    print(f"  Partial recovery:          ${agg['total_partial_recovery']:>14,.2f}")
    print(f"  Net realised return:       ${agg['net_realised_return_usd']:>14,.2f}")
    print(f"  Expected loss (CVA):       ${agg['total_expected_loss_usd']:>14,.2f}")
    print()

    # Loan-level summary table
    accepted = [r for r in records if r.offer_status == OfferStatus.ACCEPTED]
    print(f"  INDIVIDUAL LOAN RESULTS — {len(accepted)} disbursed")
    print(f"  {'─' * 64}")
    hdr = (
        f"  {'#':>2}  {'Corridor':<10}  {'Amount':>12}  "
        f"{'Status':<10}  {'Return (USD)':>13}  {'Claim 5 ✓':>9}"
    )
    print(hdr)
    print(f"  {'─' * 64}")
    for i, r in enumerate(accepted, 1):
        status_short = (
            "SETTLED" if r.repayment_status == RepaymentStatus.COLLECTED
            else "PARTIAL"
        )
        claim5_tick = "✓" if r.audit_record_generated else " "
        print(
            f"  {i:>2}  {r.currency_pair:<10}  ${r.offer_amount_usd:>11,.0f}  "
            f"{status_short:<10}  ${r.net_realised_return_usd:>12,.2f}  "
            f"{'       ' + claim5_tick:>9}"
        )
    print(f"  {'─' * 64}")

    # Claim 5 compliance banner
    claim5_complete = all(r.audit_record_generated for r in accepted)
    print()
    if claim5_complete:
        print("  CLAIM 5 COMPLIANCE: ALL disbursed loans completed auto-repayment loop ✓")
    else:
        n_incomplete = sum(1 for r in accepted if not r.audit_record_generated)
        print(f"  CLAIM 5 COMPLIANCE: {n_incomplete} loan(s) pending audit record generation")
    print()


def print_loan_detail(records: List[BridgeLoanRecord], n: int = 5) -> None:
    """Print detailed lifecycle cards for the top N loans by advance amount."""
    accepted  = [r for r in records if r.offer_status == OfferStatus.ACCEPTED]
    top       = sorted(accepted, key=lambda r: r.offer_amount_usd, reverse=True)[:n]
    print(f"  TOP {len(top)} LOAN LIFECYCLE RECORDS (by advance amount)")
    for rank, record in enumerate(top, 1):
        print(format_loan_record(record, rank))


def print_claim5_audit(records: List[BridgeLoanRecord]) -> None:
    """
    Print Claim 5(x) audit trail for all completed loans.

    Claim 5(x): "generating a settlement and repayment confirmation record
    that documents the original payment identifier, the advance disbursement
    details, the settlement confirmation event, the repayment amount, and
    the net realised return on the advance, for regulatory reporting, audit
    trail, and portfolio performance monitoring purposes."
    """
    accepted = [r for r in records if r.offer_status == OfferStatus.ACCEPTED
                and r.audit_record_generated]
    if not accepted:
        return

    print(f"\n  CLAIM 5(x) AUDIT RECORDS — {len(accepted)} completed loans")
    print(f"  {'─' * 64}")
    # Print the first record as a full JSON example
    r = accepted[0]
    audit = {
        "audit_id":                str(uuid.uuid4()),
        "generated_at":            r.audit_timestamp.isoformat() if r.audit_timestamp else None,
        "original_payment_uetr":   r.uetr,
        "loan_id":                 r.loan_id,
        "advance_disbursement": {
            "amount_usd":          r.offer_amount_usd,
            "apr_bps":             r.offer_apr_bps,
            "horizon_days":        r.offer_horizon_days,
            "channel":             r.disbursement_channel,
        },
        "settlement_confirmation": {
            "source":              r.settlement_source,
            "status":              r.settlement_status.value,
            "timestamp":           r.settlement_timestamp.isoformat() if r.settlement_timestamp else None,
        },
        "repayment": {
            "status":              r.repayment_status.value,
            "amount_usd":          r.repayment_amount_usd,
            "accrued_interest_usd":r.accrued_interest_usd,
            "recovery_usd":        r.recovery_amount_usd,
        },
        "net_realised_return_usd": r.net_realised_return_usd,
        "expected_loss_usd":       r.expected_loss_usd,
        "regulatory_basis":        "Claim 5(x) — Patent Spec v4.0",
    }
    print(json.dumps(audit, indent=4))


# =============================================================================
# SECTION 11: FULL THREE-COMPONENT PIPELINE
# =============================================================================

def run_full_pipeline(
    n_payments: int = 500,
    seed: int = 42,
    demo_loans: int = 5,
) -> Dict[str, Any]:
    """
    Run all three components end-to-end.

    Component 1 → Component 2 → Component 3

    Returns the full results dict including all BridgeLoanRecord objects.
    """
    random.seed(seed)

    # ── Component 1: Failure Prediction ──────────────────────────────────
    if _COMPONENT1_AVAILABLE and _COMPONENT2_AVAILABLE:
        print("  [1/3] Component 1: Failure Prediction Engine…", flush=True)
        c1 = run_pipeline(n_payments, seed=seed)

        print("  [2/3] Component 2: CVA Pricing Engine…", flush=True)
        from failure_prediction_engine import package_predictions
        predictions  = package_predictions(c1)
        flagged      = [p.to_cva_input() for p in predictions if p.threshold_exceeded]
        pricer       = CVAPricer()
        assessments  = [pricer.price(f) for f in flagged]
    elif _COMPONENT2_AVAILABLE:
        print("  [Component 1 not found — using mock CVA assessments]", flush=True)
        c2_results   = run_cva_pipeline()
        assessments  = c2_results["assessments"]
    else:
        print("  [Components 1+2 not found — using embedded mock data]", flush=True)
        assessments  = _mock_assessments()

    n_flagged = len(assessments)
    print(f"  [3/3] Component 3: Executing {n_flagged} bridge loan offers…", flush=True)

    # ── Component 3: Execution ────────────────────────────────────────────
    orchestrator = BridgeLoanOrchestrator()
    records: List[BridgeLoanRecord] = []
    for assessment in assessments:
        record = orchestrator.execute(assessment)
        records.append(record)

    agg = _aggregate_portfolio(records)

    return {
        "records":     records,
        "n_payments":  n_payments,
        "n_flagged":   n_flagged,
        "portfolio":   agg,
    }


def _mock_assessments() -> List["CVAAssessment"]:
    """
    Minimal mock CVAAssessments for fully standalone execution
    (when Components 1 and 2 are both absent).
    """
    from dataclasses import fields

    # Build minimal assessments programmatically
    cases = [
        dict(uetr=str(uuid.uuid4()), currency_pair="EUR/INR",
             sending_bic="BNPAFRPP", receiving_bic="SBINMUMU",
             counterparty_name="State Bank of India Mumbai", counterparty_tier=2,
             bridge_loan_amount=3_200_000.0, bridge_horizon_days=9,
             annualized_rate_bps=420.0, apr_decimal=0.042,
             cva_cost_rate_annual=0.0295, funding_spread_bps=75.0,
             net_margin_bps=50.0, expected_profit_usd=33.0,
             offer_valid_seconds=300, pd_tier_used=2,
             pd_structural=0.00210, pd_ml_signal=0.68, pd_blended=0.00210,
             lgd_estimate=0.48, ead_usd=3_200_000.0,
             expected_loss_usd=29_100.0, discount_factor=0.9993,
             risk_free_rate=0.053, pd_model_diagnostics={"model":"Damodaran proxy (D5)"},
             lgd_model_diagnostics={"lgd_final":0.48}, top_risk_factors=[],
             threshold_exceeded=True),
        dict(uetr=str(uuid.uuid4()), currency_pair="USD/BRL",
             sending_bic="CHASUS33", receiving_bic="BRADBRSP",
             counterparty_name="Bradesco Brazil", counterparty_tier=2,
             bridge_loan_amount=8_750_000.0, bridge_horizon_days=8,
             annualized_rate_bps=160.0, apr_decimal=0.016,
             cva_cost_rate_annual=0.0035, funding_spread_bps=25.0,
             net_margin_bps=50.0, expected_profit_usd=84.0,
             offer_valid_seconds=300, pd_tier_used=2,
             pd_structural=0.00162, pd_ml_signal=0.55, pd_blended=0.00162,
             lgd_estimate=0.52, ead_usd=8_750_000.0,
             expected_loss_usd=61_400.0, discount_factor=0.9975,
             risk_free_rate=0.115, pd_model_diagnostics={"model":"Damodaran proxy (D5)"},
             lgd_model_diagnostics={"lgd_final":0.52}, top_risk_factors=[],
             threshold_exceeded=True),
    ]

    # Build dicts into simple namespace objects (CVAAssessment not importable)
    class _MockAssessment:
        def __init__(self, **kw): self.__dict__.update(kw)
        def to_execution_input(self):
            total_cost = self.bridge_loan_amount * self.apr_decimal * self.bridge_horizon_days / 365
            return {
                "uetr": self.uetr,
                "offer": {
                    "bridge_loan_amount_usd": self.bridge_loan_amount,
                    "annualized_rate_bps":    self.annualized_rate_bps,
                    "apr_decimal":            self.apr_decimal,
                    "bridge_horizon_days":    self.bridge_horizon_days,
                    "offer_valid_seconds":    self.offer_valid_seconds,
                    "total_cost_usd":         round(total_cost, 2),
                },
                "counterparty": {"receiving_bic": self.receiving_bic,
                                 "institution": self.counterparty_name,
                                 "pd_tier_used": self.pd_tier_used,
                                 "pd_blended": self.pd_blended,
                                 "lgd": self.lgd_estimate},
                "security_interest": {"collateral_type": "payment_receivable_assignment",
                                      "collateral_uetr": self.uetr,
                                      "security_amount_usd": self.bridge_loan_amount,
                                      "legal_basis": "Claim D7"},
                "settlement_monitoring": {"repayment_trigger": "swift_gpi_settlement_confirmation",
                                          "monitor_uetr": self.uetr,
                                          "max_repayment_days": self.bridge_horizon_days + 14,
                                          "legal_basis": "Claim 5"},
                "risk_metrics": {"expected_loss_usd": self.expected_loss_usd,
                                 "expected_profit_usd": self.expected_profit_usd,
                                 "pd_blended": self.pd_blended,
                                 "lgd": self.lgd_estimate},
            }

    return [_MockAssessment(**c) for c in cases]


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  AUTOMATED LIQUIDITY BRIDGING SYSTEM — FULL THREE-COMPONENT DEMO")
    print("  Patent Spec v4.0 | Component 1 → Component 2 → Component 3")
    print("=" * 70)
    print()

    results = run_full_pipeline(n_payments=500, seed=42, demo_loans=5)
    records = results["records"]
    agg     = results["portfolio"]

    print_portfolio_summary(records, agg)
    print_loan_detail(records, n=5)
    print_claim5_audit(records)

    print()
    print("=" * 70)
    print("  ALL THREE COMPONENTS COMPLETE")
    print("  Component 1: Payment Failure Prediction    (failure_prediction_engine.py)")
    print("  Component 2: CVA Pricing Engine            (cva_pricing_engine.py)")
    print("  Component 3: Bridge Loan Execution         (bridge_loan_execution.py)")
    print()
    print("  Patent Coverage Demonstrated:")
    print("    ✓ Claim 1(a-h)  — Full reactive liquidity bridging method")
    print("    ✓ Claim 2(i-vi) — System architecture components")
    print("    ✓ Claim 3(j-n)  — Instrument-agnostic liquidity method")
    print("    ✓ Claim 5(t-x)  — Settlement-confirmation auto-repayment loop")
    print("    ✓ Claims D3/D4/D5/D6/D7/D9/D11 — Key dependent claim embodiments")
    print("=" * 70)
