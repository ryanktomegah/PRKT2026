/// taxonomy.rs — ISO 20022 rejection code taxonomy
///
/// Architecture Spec S8: Full rejection code → RejectionClass mapping.
/// Mirrors lip/c3_repayment_engine/rejection_taxonomy.py exactly.
///
/// T = f(rejection_code_class):
///   Class A → 3 days maturity  (technical/routing errors)
///   Class B → 7 days maturity  (systemic/processing errors)
///   Class C → 21 days maturity (investigation/complex errors)
///   BLOCK   → no bridge offered (compliance, dispute, legal)
///
/// B6-01: The BLOCK-class code list is loaded at compile time from
/// `lip/common/block_codes.json` — the single source of truth shared with
/// Python and Go. The cross-language drift test (B13-02) keeps every
/// consumer in sync. Do not hand-maintain a parallel list in this file.
use std::sync::OnceLock;

use thiserror::Error;

// ---------------------------------------------------------------------------
// Shared BLOCK-codes ground truth (B6-01)
// ---------------------------------------------------------------------------

/// JSON payload bundled into the binary at compile time. The matching Python
/// loader (`lip/common/block_codes.py`) reads the same file at import time;
/// the regression test in `lip/tests/test_block_code_drift.py` verifies that
/// every consumer (Python/Rust/Go) sees the same set.
const BLOCK_CODES_JSON: &str = include_str!("../../../common/block_codes.json");

struct BlockCodes {
    compliance_hold: Vec<String>,
    all_block: Vec<String>,
}

fn block_codes() -> &'static BlockCodes {
    static CELL: OnceLock<BlockCodes> = OnceLock::new();
    CELL.get_or_init(|| {
        // We avoid the serde-derive dep by parsing via the loosely-typed
        // serde_json::Value API and pulling the two known arrays out by name.
        let value: serde_json::Value = serde_json::from_str(BLOCK_CODES_JSON)
            .expect("lip/common/block_codes.json is malformed; refusing to start");

        let extract = |key: &str| -> Vec<String> {
            value
                .get(key)
                .and_then(|v| v.as_array())
                .unwrap_or_else(|| panic!("block_codes.json missing array '{key}'"))
                .iter()
                .map(|v| {
                    v.as_str()
                        .unwrap_or_else(|| panic!("block_codes.json '{key}' contains non-string"))
                        .to_string()
                })
                .collect()
        };

        let compliance_hold = extract("epg19_compliance_hold");
        let dispute_fraud = extract("dispute_fraud_block");
        let mut all_block = compliance_hold.clone();
        all_block.extend(dispute_fraud);

        // Defensive invariants matching the Python loader.
        assert_eq!(
            compliance_hold.len(),
            8,
            "EPG-19 compliance-hold set must have exactly 8 codes"
        );
        assert_eq!(
            all_block.len(),
            12,
            "BLOCK class must have exactly 12 codes (8 compliance + 4 dispute/fraud)"
        );

        BlockCodes {
            compliance_hold,
            all_block,
        }
    })
}

/// EPG-19: Compliance-hold codes that must always be classified BLOCK.
/// Loaded from `lip/common/block_codes.json` (B6-01 single source of truth).
/// Defense-in-depth: these codes are also blocked at Layer 1 (pipeline
/// short-circuit) and Layer 2 (C7 gate) per the EPG-19 architecture decision.
pub fn compliance_hold_codes() -> &'static [String] {
    &block_codes().compliance_hold
}

/// Full BLOCK class — EPG-19 compliance holds plus dispute/fraud codes.
/// Loaded from `lip/common/block_codes.json`.
pub fn all_block_codes() -> &'static [String] {
    &block_codes().all_block
}

/// Classification tier for an ISO 20022 rejection reason code.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum RejectionClass {
    ClassA,
    ClassB,
    ClassC,
    Block,
}

/// Error returned when an unrecognised rejection code is classified.
#[derive(Debug, Error)]
#[error("Unknown rejection code '{0}'. Add it to REJECTION_CODE_TAXONOMY before use.")]
pub struct UnknownCodeError(pub String);

impl RejectionClass {
    /// Return the canonical string representation (matches Python enum values).
    pub fn as_str(&self) -> &'static str {
        match self {
            RejectionClass::ClassA => "CLASS_A",
            RejectionClass::ClassB => "CLASS_B",
            RejectionClass::ClassC => "CLASS_C",
            RejectionClass::Block => "BLOCK",
        }
    }

    /// Return the maturity window in calendar days.
    /// BLOCK codes return 0 — no bridge is offered.
    pub fn maturity_days(&self) -> u32 {
        match self {
            RejectionClass::ClassA => 3,
            RejectionClass::ClassB => 7,
            RejectionClass::ClassC => 21,
            RejectionClass::Block => 0,
        }
    }
}

/// Classify an ISO 20022 rejection reason code.
///
/// Normalises the code (strip + uppercase) before lookup.
/// Returns `Err(UnknownCodeError)` for codes not in the taxonomy.
pub fn classify(code: &str) -> Result<RejectionClass, UnknownCodeError> {
    let normalised = code.trim().to_uppercase();
    match normalised.as_str() {
        // ── CLASS A — Temporary / Technical (3-day maturity) ────────────
        "AC01" => Ok(RejectionClass::ClassA), // IncorrectAccountNumber
        "AC04" => Ok(RejectionClass::ClassA), // ClosedAccountNumber
        "AC06" => Ok(RejectionClass::ClassA), // BlockedAccount
        "AM01" => Ok(RejectionClass::ClassA), // ZeroAmount
        "AM02" => Ok(RejectionClass::ClassA), // NotAllowedAmount
        "AM03" => Ok(RejectionClass::ClassA), // NotAllowedCurrency
        "AM04" => Ok(RejectionClass::ClassA), // InsufficientFunds
        "AM05" => Ok(RejectionClass::ClassA), // Duplication
        "AM06" => Ok(RejectionClass::ClassA), // TooLowAmount
        "AM09" => Ok(RejectionClass::ClassA), // WrongAmount
        "AM10" => Ok(RejectionClass::ClassA), // InvalidControlSum
        "AM12" => Ok(RejectionClass::ClassA), // InvalidAmount
        "BE01" => Ok(RejectionClass::ClassA), // InconsistentWithEndCustomer
        "BE05" => Ok(RejectionClass::ClassA), // UnrecognisedInitiatingParty
        "DT01" => Ok(RejectionClass::ClassA), // InvalidDate
        "ED01" => Ok(RejectionClass::ClassA), // CorrespondentBankNotAllowed
        "ED03" => Ok(RejectionClass::ClassA), // BalanceInfoRequest
        "ED05" => Ok(RejectionClass::ClassA), // SettlementFailed
        "FF01" => Ok(RejectionClass::ClassA), // InvalidFileFormat
        "FF03" => Ok(RejectionClass::ClassA), // InvalidPaymentTypeInfo
        "FF05" => Ok(RejectionClass::ClassA), // InvalidLocalInstrumentCode
        "MD01" => Ok(RejectionClass::ClassA), // NoMandate
        "MD02" => Ok(RejectionClass::ClassA), // MissingMandatoryInfo
        "MD06" => Ok(RejectionClass::ClassA), // RefundRequestedByEndCustomer
        "RC01" => Ok(RejectionClass::ClassA), // BankIdentifierIncorrect

        // ── CLASS B — Systemic / Processing (7-day maturity) ────────────
        "AG02" => Ok(RejectionClass::ClassB), // InvalidBankOperationCode
        "CURR" => Ok(RejectionClass::ClassB), // UnrecognisedCurrency
        "CUST" => Ok(RejectionClass::ClassB), // RequestedByCustomer
        "FOCR" => Ok(RejectionClass::ClassB), // FollowingCancellationRequest
        "MS02" => Ok(RejectionClass::ClassB), // NotSpecifiedReasonCustomerGenerated
        "MS03" => Ok(RejectionClass::ClassB), // NotSpecifiedReasonAgentGenerated
        "NARR" => Ok(RejectionClass::ClassB), // Narrative
        "NOAS" => Ok(RejectionClass::ClassB), // NoAnswerFromCustomer
        "NOOR" => Ok(RejectionClass::ClassB), // NoOriginalTransactionReceived
        "PTNA" => Ok(RejectionClass::ClassB), // PassThroughNotAllowed
        "RCON" => Ok(RejectionClass::ClassB), // SettlementFailedContinuous
        "SVNR" => Ok(RejectionClass::ClassB), // ServiceNotRendered
        "TECH" => Ok(RejectionClass::ClassB), // TechnicalProblem
        "TIMO" => Ok(RejectionClass::ClassB), // TimeOut
        "UPAY" => Ok(RejectionClass::ClassB), // UnduePayment

        // ── CLASS C — Investigation / Complex (21-day maturity) ─────────
        "AGNT" => Ok(RejectionClass::ClassC), // IncorrectAgent
        "CVCY" => Ok(RejectionClass::ClassC), // CurrencyConversionFailed
        "FRSP" => Ok(RejectionClass::ClassC), // FollowUpResponseToBankReceived
        "INDM" => Ok(RejectionClass::ClassC), // IndemnificationRequest
        "INVB" => Ok(RejectionClass::ClassC), // InvalidBIC
        "INVR" => Ok(RejectionClass::ClassC), // InvalidReference
        "OPAY" => Ok(RejectionClass::ClassC), // OtherPayment
        "PCOR" => Ok(RejectionClass::ClassC), // PartiallyCorrupt
        "QMIS" => Ok(RejectionClass::ClassC), // QualityMismatch
        "SMND" => Ok(RejectionClass::ClassC), // SpecificMandateInformation
        "UMKA" => Ok(RejectionClass::ClassC), // UnmatchedAmount

        // ── BLOCK — Compliance / Dispute / Legal (no bridge offered) ────
        "DISP" => Ok(RejectionClass::Block), // DisputedTransaction
        "DUPL" => Ok(RejectionClass::Block), // DuplicateDetected
        "FRAD" => Ok(RejectionClass::Block), // FraudulentOrigin
        "FRAU" => Ok(RejectionClass::Block), // Fraud
        "RR01" => Ok(RejectionClass::Block), // MissingDebtorAccountOrIdentification (EPG-01)
        "RR02" => Ok(RejectionClass::Block), // MissingDebtorNameOrAddress (EPG-01)
        "RR03" => Ok(RejectionClass::Block), // MissingCreditorNameOrAddress (EPG-01)
        "RR04" => Ok(RejectionClass::Block), // RegulatoryReason (EPG-07)
        "AG01" => Ok(RejectionClass::Block), // TransactionForbidden (EPG-08)
        "LEGL" => Ok(RejectionClass::Block), // LegalDecision (EPG-08)
        "DNOR" => Ok(RejectionClass::Block), // DebtorNotAllowedToSend (EPG-02)
        "CNOR" => Ok(RejectionClass::Block), // CreditorNotAllowedToReceive (EPG-03)

        other => Err(UnknownCodeError(other.to_string())),
    }
}

/// Return the maturity window in days for a given `RejectionClass`.
/// BLOCK returns 0 — no bridge is offered.
pub fn maturity_days(cls: RejectionClass) -> u32 {
    cls.maturity_days()
}

/// Return `true` if the code maps to `RejectionClass::Block`.
/// Returns `false` for unknown codes (never raises).
pub fn is_block(code: &str) -> bool {
    matches!(classify(code), Ok(RejectionClass::Block))
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_class_a_code() {
        assert_eq!(classify("AC01").unwrap(), RejectionClass::ClassA);
        assert_eq!(classify("ac01").unwrap(), RejectionClass::ClassA); // lowercase
        assert_eq!(classify(" AM04 ").unwrap(), RejectionClass::ClassA); // whitespace
    }

    #[test]
    fn test_class_b_code() {
        assert_eq!(classify("AG02").unwrap(), RejectionClass::ClassB);
        assert_eq!(classify("NARR").unwrap(), RejectionClass::ClassB);
    }

    #[test]
    fn test_class_c_code() {
        assert_eq!(classify("AGNT").unwrap(), RejectionClass::ClassC);
        assert_eq!(classify("INVB").unwrap(), RejectionClass::ClassC);
    }

    #[test]
    fn test_block_codes() {
        let block_codes = ["DISP", "DUPL", "FRAD", "FRAU", "RR01", "RR02", "RR03", "RR04",
                           "AG01", "LEGL", "DNOR", "CNOR"];
        for code in block_codes {
            assert_eq!(
                classify(code).unwrap(),
                RejectionClass::Block,
                "{code} should be BLOCK"
            );
        }
    }

    #[test]
    fn test_unknown_code_error() {
        let err = classify("ZZZZ").unwrap_err();
        assert!(err.to_string().contains("ZZZZ"));
    }

    #[test]
    fn test_maturity_days() {
        assert_eq!(RejectionClass::ClassA.maturity_days(), 3);
        assert_eq!(RejectionClass::ClassB.maturity_days(), 7);
        assert_eq!(RejectionClass::ClassC.maturity_days(), 21);
        assert_eq!(RejectionClass::Block.maturity_days(), 0);
    }

    #[test]
    fn test_is_block() {
        assert!(is_block("DNOR"));
        assert!(is_block("CNOR"));
        assert!(is_block("RR01"));
        assert!(!is_block("AC01"));
        assert!(!is_block("UNKNOWN_CODE")); // false for unknown, never panics
    }

    #[test]
    fn test_class_str_representation() {
        assert_eq!(RejectionClass::ClassA.as_str(), "CLASS_A");
        assert_eq!(RejectionClass::ClassB.as_str(), "CLASS_B");
        assert_eq!(RejectionClass::ClassC.as_str(), "CLASS_C");
        assert_eq!(RejectionClass::Block.as_str(), "BLOCK");
    }

    // EPG-compliance: every compliance-hold code from the shared JSON must be BLOCK
    #[test]
    fn test_compliance_hold_codes_are_block() {
        for code in compliance_hold_codes() {
            assert_eq!(
                classify(code).unwrap(),
                RejectionClass::Block,
                "Compliance-hold code {code} must be BLOCK (EPG-19)"
            );
        }
    }

    // B6-01: every code in the shared JSON BLOCK list must classify as Block
    #[test]
    fn test_all_block_codes_from_json_are_block() {
        for code in all_block_codes() {
            assert_eq!(
                classify(code).unwrap(),
                RejectionClass::Block,
                "BLOCK code {code} (from block_codes.json) must classify as BLOCK"
            );
        }
        assert_eq!(all_block_codes().len(), 12);
        assert_eq!(compliance_hold_codes().len(), 8);
    }
}
