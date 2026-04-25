# P9: CBDC Protocol Research — LIP Cross-Border Payment Rail Extension

**Document type**: Patent Portfolio Research + Architecture Decision Record
**Patent reference**: P9 — Automated Liquidity Bridging on CBDC Payment Rails
**Status**: Research complete — implementation stubs defined for Phase 2
**Date**: 2026-03-15
**Authors**: NOVA (payments), REX (regulatory), QUANT (financial)

---

## Executive Summary

Central Bank Digital Currencies (CBDCs) are becoming operational cross-border payment
rails. LIP's core patent covers bridge lending triggered by SWIFT payment failures.
This document analyses how LIP's architecture must extend to cover CBDC rail failures
and settlement signals, supporting Patent P9 claims and preserving the moat as SWIFT
volume migrates to CBDC infrastructure.

**Key finding**: CBDC rail failures map cleanly onto LIP's existing failure taxonomy,
but require three protocol-specific extensions: (1) a new event normalizer handler for
CBDC message formats, (2) a new `SettlementRail.CBDC` enumeration in C3, and (3)
corridor-specific settlement timing constants calibrated to CBDC finality rules.

---

## 1. CBDC Landscape: Operational and Near-Operational Rails

### 1.1 BIS Project mBridge (Multi-CBDC Cross-Border Settlement)

**Status**: Minimum viable product (MVP) reached June 2024; moving toward full
commercial launch under BIS Innovation Hub governance.

**Participants**: People's Bank of China (digital yuan), Hong Kong HKMA (e-HKD),
Bank of Thailand (digital baht), UAE Central Bank (digital dirham).
Observers: Saudi Arabia, BIS member central banks.

**Architecture**:
- Shared distributed ledger: purpose-built mBridge Ledger (not Ethereum or existing DLT)
- Atomic PvP (payment-vs-payment) settlement: eliminates settlement risk across currencies
- Transaction finality: **1–3 seconds** (versus SWIFT's T+1 to T+2 for cross-border)
- Message format: ISO 20022 native (pacs.008, pacs.002, camt.054)
- Failure taxonomy: same ISO 20022 rejection code set as SWIFT GPI

**LIP Implication**: mBridge uses the same ISO 20022 RJCT taxonomy as SWIFT.
LIP's C1 rejection code mappings (AC01, AM04, FRAU, etc.) apply without modification.
The **settlement timing** differs dramatically — see §4.

**Reference**: BIS, "Project mBridge: Experimenting with a multi-CBDC platform for
cross-border payments", June 2024. https://www.bis.org/publ/othp80.htm

### 1.2 ECB DLT Pilot (European Settlement)

**Status**: ECB DLT Interoperability Trials completed Q4 2024; decision on production
roadmap expected H1 2025.

**Architecture**:
- Interconnects TARGET2 (Euro RTGS) with private DLT networks operated by CSDs
- Settlement asset: tokenised central bank reserves ("wholesale CBDC" / wCBDC)
- ISO 20022 extension: ECB is developing ISO 20022 supplement for DLT settlement
  instructions (draft standard: ISO 20022 camt.998 for DLT-specific events)
- Finality: intraday, on-chain atomic settlement
- Geographic scope: EUR zone cross-border

**LIP Implication**: The EUR corridors (EUR/USD, EUR/GBP, EUR/CHF) will migrate to
DLT settlement within 3-5 years. LIP's C3 repayment engine must handle EUR DLT
settlement signals alongside traditional TARGET2 SWIFT confirmations.

**Reference**: ECB, "DLT Trials for Interoperability — Final Report", December 2024.
European Central Bank Working Paper Series.

### 1.3 US FedNow + Digital Dollar Research

**Status**: FedNow launched July 2023 (instant domestic ACH alternative, not CBDC).
Digital dollar (US retail CBDC) remains in research phase; no production timeline.

**Architecture**:
- FedNow: instant domestic settlement (not cross-border, not CBDC)
- Digital dollar research: MIT Digital Currency Initiative (Project Hamilton) concluded
  without production mandate; Federal Reserve Board actively studying but no issuance
  scheduled.

**LIP Implication**:
- FedNow is a **domestic** rail — not in scope for LIP's cross-border model.
- USD CBDC does not affect LIP's USD corridors in the near term.
- Watch: FedNow does create new domestic real-time settlement signals for USD legs
  of cross-border transactions — `SettlementRail.FEDNOW` stub warranted.

**Reference**: Federal Reserve, "FedNow Service", operational since July 2023.
Project Hamilton: https://www.bostonfed.org/project-hamilton

### 1.4 UK CHAPS / Digital Pound

**Status**: Bank of England completed a digital pound consultation (Feb 2023).
Decision to build ("foundation" phase) announced 2024. Not yet operational.

**LIP Implication**: GBP corridors (GBP/USD, EUR/GBP) would eventually see
settlement via digital pound infrastructure. Sterling MPC constraints on corridor
timing may change with on-chain settlement.

---

## 2. CBDC Failure Mode Taxonomy

CBDC rails introduce failure modes that LIP must classify and respond to.
Below maps CBDC-specific failure types onto LIP's existing rejection class taxonomy.

### 2.1 Failure Modes Common to SWIFT and CBDC

These map directly to existing LIP rejection codes — no changes needed:

| ISO 20022 Code | Meaning | Class | CBDC Context |
|---------------|---------|-------|-------------|
| AC01 | Incorrect account / wallet address | A | CBDC wallet address invalid |
| AC04 | Closed account / deactivated wallet | A | CBDC wallet revoked by issuer |
| AM04 | Insufficient funds / insufficient CBDC | B | Central bank reserve shortfall |
| FRAU | Fraud / suspicious transaction | C | Smart contract fraud detection |
| LEGL | Legal decision | C | Sanctions on CBDC wallet |

### 2.2 CBDC-Specific Failure Modes (New to P9)

These require new handling in LIP's event normalizer and C1 classifier:

| Failure Type | ISO Extension | Class | Description |
|-------------|--------------|-------|-------------|
| SMART_CONTRACT_REVERT | CBDC-SC01 | A | On-chain smart contract execution failed |
| CONSENSUS_FAILURE | CBDC-CF01 | B | DLT consensus not reached (mBridge specific) |
| FINALITY_TIMEOUT | CBDC-FT01 | B | Transaction not finalized within DLT slot |
| WALLET_COMPLIANCE | CBDC-WC01 | C | CBDC wallet failed compliance check (KYC/AML) |
| CROSS_CHAIN_BRIDGE | CBDC-CB01 | A | Interoperability bridge between DLT networks failed |

**LIP P9 claim basis**: Detecting `CONSENSUS_FAILURE` and `FINALITY_TIMEOUT` as
triggering events for bridge lending is novel — no existing patent covers liquidity
bridging on DLT consensus failures.

---

## 3. Settlement Timing: CBDC vs. SWIFT

This is the most significant operational difference. LIP's C3 repayment engine
uses corridor-specific settlement buffers calibrated to SWIFT T+1/T+2 norms.
CBDC settlement is near-instantaneous, changing bridge loan economics.

### Settlement Finality by Rail

| Rail | Settlement Finality | LIP Buffer | Bridge Loan Duration |
|------|---------------------|-----------|---------------------|
| SWIFT GPI | T+1 (same-day in GPI) | 45-day UETR TTL | 1–21 days (Class A/B/C) |
| mBridge | 1–3 seconds | 24-hour safety buffer | 30 seconds–4 hours |
| ECB DLT | Intraday | 4-hour safety buffer | Minutes–hours |
| FedNow (domestic) | Seconds | 1-hour safety buffer | N/A (domestic only) |
| CHAPS / Digital Pound | Intraday (target) | 4-hour safety buffer | Minutes–hours |

**Implication for QUANT**: Bridge loan pricing on CBDC rails must account for
**minute-scale** durations rather than day-scale. The 300 bps annualized fee floor
must be re-expressed for sub-day durations:

```
fee_cbdc = max(
    fee_floor_annualized * (duration_seconds / 31_536_000),
    minimum_absolute_fee  # e.g., USD 50 per transaction
)
```

The `minimum_absolute_fee` is a new constant requiring QUANT sign-off for P9.

---

## 4. Architecture Extensions Required

### 4.1 C5 Event Normalizer — New Handler Shape

The existing `event_normalizer.py` processes SWIFT pacs.002 messages.
A CBDC-compatible handler must be added (Phase 2 stub, marked `PHASE-2-STUB`).

```python
# lip/c5_streaming/event_normalizer.py — Phase 2 addition
# PHASE-2-STUB: replace with production mBridge / ECB DLT connector

def normalize_cbdc(msg: dict) -> NormalizedEvent:
    """Normalize a CBDC settlement failure event to LIP's internal format.

    Handles mBridge, ECB DLT pilot, and future CBDC rails.
    Maps CBDC-specific failure codes to ISO 20022 taxonomy.

    Parameters
    ----------
    msg : dict
        Raw CBDC event payload. Expected fields:
            - transaction_id: str (CBDC equivalent of UETR)
            - rail: str ("mbridge" | "ecb_dlt" | "fednow" | "digital_pound")
            - status: str ("REJECTED" | "FAILED" | "REVERTED")
            - failure_code: str (ISO 20022 or CBDC extension code)
            - amount: float
            - currency_pair: str
            - sender_wallet: str (CBDC wallet address)
            - receiver_wallet: str (CBDC wallet address)
            - timestamp_utc: str (ISO 8601)
            - finality_seconds: float (actual DLT finality time)
    """
    # Map CBDC rail identifiers to LIP's internal rail enum
    rail_map = {
        "mbridge": SettlementRail.CBDC,
        "ecb_dlt": SettlementRail.CBDC,
        "fednow": SettlementRail.FEDNOW,
        "digital_pound": SettlementRail.CBDC,
    }

    # Map CBDC-specific failure codes to ISO 20022 equivalents
    code_map = {
        "CBDC-SC01": "AC01",  # Smart contract revert → account error
        "CBDC-CF01": "AM04",  # Consensus failure → treat as liquidity
        "CBDC-FT01": "AM04",  # Finality timeout → treat as liquidity
        "CBDC-WC01": "LEGL",  # Wallet compliance → legal decision
        "CBDC-CB01": "RC01",  # Cross-chain bridge → routing error
    }

    raw_code = msg.get("failure_code", "NARR")
    normalized_code = code_map.get(raw_code, raw_code)

    return NormalizedEvent(
        uetr=msg.get("transaction_id", str(uuid.uuid4())),
        sending_bic=_wallet_to_bic(msg.get("sender_wallet", "")),
        receiving_bic=_wallet_to_bic(msg.get("receiver_wallet", "")),
        amount_usd=_to_usd(msg.get("amount", 0.0), msg.get("currency_pair", "USD")),
        currency_pair=msg.get("currency_pair", "USD/USD"),
        rejection_code=normalized_code,
        timestamp=_parse_timestamp(msg.get("timestamp_utc", "")),
        rail=rail_map.get(msg.get("rail", ""), SettlementRail.CBDC),
        cbdc_finality_seconds=msg.get("finality_seconds"),  # CBDC-specific
    )
```

### 4.2 C3 Repayment Engine — New SettlementRail Values

```python
# lip/c3_repayment_engine/repayment_loop.py — Phase 2 addition

class SettlementRail(str, Enum):
    SWIFT     = "SWIFT"
    CHAPS     = "CHAPS"
    FEDWIRE   = "FEDWIRE"
    TARGET2   = "TARGET2"
    SEPA      = "SEPA"
    # Phase 2 additions (PHASE-2-STUB: add routing logic in RepaymentLoop):
    CBDC      = "CBDC"      # mBridge, ECB DLT, Digital Pound
    FEDNOW    = "FEDNOW"    # US domestic instant — not cross-border

# Settlement buffer by rail (Phase 2 constants — QUANT sign-off required)
_CBDC_BUFFER_SECONDS    = 4 * 3600    # 4-hour safety buffer for DLT finality
_FEDNOW_BUFFER_SECONDS  = 1 * 3600    # 1-hour safety buffer for FedNow
```

### 4.3 C2 PD Model — CBDC Corridor Risk Factors

CBDC rails introduce new corridor-specific risk factors for the PD model:
- DLT network liveness risk (probability of consensus failure)
- Smart contract version risk (newer contracts have higher revert rates)
- Cross-chain bridge counterparty risk (bridge operator default)

These are Phase 2 features to be added to the C2 financial statement vector:

```python
# New fields in C2 Tier-3 borrower record (thin-file CBDC counterparties)
cbdc_rail = str          # "mbridge" | "ecb_dlt" | "fednow" | "digital_pound"
dlt_network_liveness = float  # 30-day uptime (0.0–1.0)
smart_contract_version = int  # 0=legacy, 1=audited, 2=formal-verified
bridge_counterparty_rating = str  # "AA" | "A" | "BBB" | "unrated"
```

---

## 5. Patent Claims Support (P9)

The CBDC extension supports novel patent claims beyond P1 (SWIFT-only):

1. **Claim 1**: Method of providing automated liquidity bridging in response to
   a payment failure event on a Central Bank Digital Currency payment rail,
   wherein the failure event comprises a consensus failure, finality timeout,
   or smart contract reversion on a distributed ledger network.

2. **Claim 2**: The method of Claim 1 wherein the bridge loan duration is
   calibrated to the distributed ledger finality time of the applicable CBDC
   rail, expressed as a minimum fee floor applied to sub-minute durations.

3. **Claim 3**: The method of Claim 1 wherein failure events on multiple
   heterogeneous payment rails (ISO 20022 SWIFT, mBridge multi-CBDC,
   ECB DLT) are normalized to a common internal taxonomy, enabling a single
   failure classifier to operate across rail types.

4. **Claim 4**: A system implementing Claims 1-3, comprising: a CBDC event
   normalizer mapping DLT-specific failure codes to ISO 20022 equivalents;
   a failure classifier operating on normalized events regardless of rail type;
   a bridge lending engine with rail-specific settlement buffer calibration.

**Novelty over JPMorgan US7089207B1**: The prior art covers SWIFT T+1/T+2 settlement
latency bridging for Tier-1 (listed) counterparties only. LIP's P9 covers DLT
near-instantaneous (1–3 second finality) bridging for multi-tier counterparties —
no prior art covers sub-minute bridge loan duration calibrated to DLT consensus time.

---

## 6. Implementation Roadmap

### Phase 2.1 — Protocol Stubs (Clean Interfaces)

| File | Change | Status |
|------|--------|--------|
| `lip/c5_streaming/event_normalizer.py` | Add `normalize_cbdc()` handler | PHASE-2-STUB |
| `lip/c3_repayment_engine/repayment_loop.py` | Add `SettlementRail.CBDC` + `.FEDNOW` | PHASE-2-STUB |
| `lip/common/constants.py` | Add `CBDC_BUFFER_SECONDS`, `CBDC_MIN_FEE_USD` | QUANT sign-off |
| `lip/dgen/c1_generator.py` | Add mBridge corridor (CNH/AED, CNH/THB, AED/THB) | PHASE-2-STUB |

### Phase 2.2 — mBridge Pilot Integration

- Connect C5 Kafka consumer to mBridge settlement event feed (ISO 20022 over HTTPS)
- Validate normalize_cbdc() against live mBridge test environment (BIS Innovation Hub)
- Back-test C1 classifier on mBridge historical failure data (if available under NDA)

### Phase 2.3 — ECB DLT Integration

- Monitor ECB DLT pilot ISO 20022 extension drafts (camt.998 specification)
- Extend normalize_cbdc() for ECB-specific event types when standard is published
- EUR corridor testing on ECB DLT test environment

---

## 7. Competitive Moat Analysis

| Rail | Status | LIP Coverage | Competitors |
|------|--------|-------------|------------|
| SWIFT GPI | Production | ✅ Full (P1) | JPMorgan US7089207B1 (Tier 1 only) |
| mBridge | MVP (2024) | ⚙️ Phase 2 stubs | No known patent coverage |
| ECB DLT | Trials (2024) | ⚙️ Phase 2 stubs | No known patent coverage |
| FedNow | Production (domestic) | ⚙️ Phase 2 stubs | Domestic only — limited cross-border applicability |
| Digital Pound | Research | ⚙️ Phase 2 stubs | 3-5 year horizon |

**Strategic conclusion**: Filing P9 now (CBDC extension) creates a 36–60 month moat
on DLT-based bridge lending before mBridge reaches commercial scale and before
competitors identify the opportunity. The normalized failure taxonomy (Claim 3) is
particularly defensible — a single classifier operating across heterogeneous rails
is the core innovation.

---

## References

| Reference | Section |
|-----------|---------|
| BIS, "Project mBridge: Experimenting with a multi-CBDC platform", June 2024 | §1.1 |
| ECB, "DLT Trials for Interoperability — Final Report", December 2024 | §1.2 |
| Federal Reserve, "FedNow Service", 2023 | §1.3 |
| Bank of England, "The digital pound: a new form of money for households and businesses?", Feb 2023 | §1.4 |
| ISO 20022, pacs.002 Financial Institution Credit Transfer Status Report | §2 |
| JPMorgan, US7089207B1, "System and Method for Detecting and Processing Payment Transactions" | §5 (prior art) |
| BIS CPMI, "Interlinking payment systems and the role of application programming interfaces", 2022 | §4 |

---

*This document is a research and patent strategy record. All Phase 2 implementation
constants (buffer times, minimum fees, DP parameters) require QUANT + REX sign-off
before deployment. Legal review of patent claims by qualified IP counsel is required
before filing.*
