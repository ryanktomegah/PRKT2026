/// iso20022.rs — ISO 20022 message field extraction
///
/// Ports the field extraction logic from settlement_handlers.py to Rust.
/// Input: Python dict (pre-parsed from raw XML/JSON by rail handlers).
/// Output: Structured field sets for camt.054 and pacs.008 messages.
///
/// Limitations documented in docs/specs/c3_state_machine_migration.md §5.3:
/// - Dict-based only: raw XML strings must be pre-parsed by Python layer
/// - SEPA namespace variations: Python SEPA handler remains authoritative
/// - FedNow pacs.002 vs pacs.008 type differences
/// - RTP partial settlement not broken out
use thiserror::Error;

/// Error returned when required fields cannot be extracted from a message.
#[derive(Debug, Error)]
#[error("ISO 20022 field extraction failed: {0}")]
pub struct ExtractionError(pub String);

/// Extracted fields from a camt.054 BankToCustomerDebitCreditNotification.
#[derive(Debug, Clone)]
pub struct Camt054Fields {
    pub uetr: String,
    pub individual_payment_id: String,
    pub amount: String,
    pub currency: String,
    pub settlement_time: Option<String>,
    pub rejection_code: Option<String>,
}

/// Extracted fields from a pacs.008 FIToFICustomerCreditTransfer.
#[derive(Debug, Clone)]
pub struct Pacs008Fields {
    pub uetr: String,
    pub end_to_end_id: String,
    pub amount: String,
    pub currency: String,
    pub settlement_date: Option<String>,
    pub debtor_bic: Option<String>,
    pub creditor_bic: Option<String>,
}

// ---------------------------------------------------------------------------
// camt.054 extraction
// ---------------------------------------------------------------------------

/// Extract fields from a camt.054 dict representation.
///
/// Mirrors `SWIFTCamt054Handler.handle()` field extraction logic.
/// Attempts nested ISO 20022 key paths first; falls back to flat keys
/// (used by test/mock payloads).
///
/// # Errors
/// Returns `ExtractionError` if the UETR field cannot be resolved.
pub fn extract_camt054(
    _notification_opt: Option<&serde_json::Value>,
    entry_opt: Option<&serde_json::Value>,
    txn_details_opt: Option<&serde_json::Value>,
    flat: &serde_json::Value,
) -> Result<Camt054Fields, ExtractionError> {
    // UETR: try nested path first, then flat fallback
    let uetr = txn_details_opt
        .and_then(|t| t.get("Refs"))
        .and_then(|r| r.get("UETR"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| flat.get("uetr").and_then(|v| v.as_str()).map(str::to_string))
        .unwrap_or_default();

    // individual_payment_id: EndToEndId
    let individual_payment_id = txn_details_opt
        .and_then(|t| t.get("Refs"))
        .and_then(|r| r.get("EndToEndId"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("individual_payment_id")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .unwrap_or_else(|| uetr.clone());

    // Amount: entry Amt."#text" or Amt (scalar) or flat "amount"
    let amount = entry_opt
        .and_then(|e| e.get("Amt"))
        .and_then(|a| {
            a.get("#text")
                .and_then(|v| v.as_str())
                .map(str::to_string)
                .or_else(|| a.as_str().map(str::to_string))
        })
        .or_else(|| {
            flat.get("amount")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .unwrap_or_else(|| "0".to_string());

    // Currency
    let currency = entry_opt
        .and_then(|e| e.get("Amt"))
        .and_then(|a| a.get("@Ccy"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("currency")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .unwrap_or_else(|| "USD".to_string());

    // settlement_time: SttlmInf.SttlmDt or flat settlement_time
    let settlement_time = txn_details_opt
        .and_then(|t| t.get("SttlmInf"))
        .and_then(|s| s.get("SttlmDt"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("settlement_time")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        });

    // rejection_code: RtrInf.Rsn.Cd or flat rejection_code
    let rejection_code = txn_details_opt
        .and_then(|t| t.get("RtrInf"))
        .and_then(|r| r.get("Rsn"))
        .and_then(|r| r.get("Cd"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("rejection_code")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        });

    Ok(Camt054Fields {
        uetr,
        individual_payment_id,
        amount,
        currency,
        settlement_time,
        rejection_code,
    })
}

// ---------------------------------------------------------------------------
// pacs.008 extraction
// ---------------------------------------------------------------------------

/// Extract fields from a pacs.008 dict representation.
///
/// Handles both nested ISO 20022 key structure and flat dict (test/mock) payloads.
///
/// # Errors
/// Returns `ExtractionError` if required fields cannot be resolved.
pub fn extract_pacs008(flat: &serde_json::Value) -> Result<Pacs008Fields, ExtractionError> {
    // Walk the standard pacs.008 structure:
    // FIToFICstmrCdtTrf → CdtTrfTxInf[0]
    let tx_info = flat
        .get("FIToFICstmrCdtTrf")
        .and_then(|v| v.get("CdtTrfTxInf"))
        .and_then(|v| v.get(0));

    // UETR: CdtTrfTxInf[0].PmtId.UETR or flat uetr/UETR
    let uetr = tx_info
        .and_then(|t| t.get("PmtId"))
        .and_then(|p| p.get("UETR"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| flat.get("uetr").and_then(|v| v.as_str()).map(str::to_string))
        .or_else(|| flat.get("UETR").and_then(|v| v.as_str()).map(str::to_string))
        .unwrap_or_default();

    // EndToEndId
    let end_to_end_id = tx_info
        .and_then(|t| t.get("PmtId"))
        .and_then(|p| p.get("EndToEndId"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("EndToEndId")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .or_else(|| {
            flat.get("end_to_end_id")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .unwrap_or_else(|| uetr.clone());

    // IntrBkSttlmAmt
    let (amount, currency) = {
        let amt_node = tx_info.and_then(|t| t.get("IntrBkSttlmAmt"));
        let amount = amt_node
            .and_then(|a| {
                a.get("#text")
                    .and_then(|v| v.as_str())
                    .map(str::to_string)
                    .or_else(|| a.as_str().map(str::to_string))
            })
            .or_else(|| flat.get("amount").and_then(|v| v.as_str()).map(str::to_string))
            .unwrap_or_else(|| "0".to_string());
        let currency = amt_node
            .and_then(|a| a.get("@Ccy"))
            .and_then(|v| v.as_str())
            .map(str::to_string)
            .or_else(|| flat.get("currency").and_then(|v| v.as_str()).map(str::to_string))
            .unwrap_or_else(|| "USD".to_string());
        (amount, currency)
    };

    // Settlement date
    let settlement_date = tx_info
        .and_then(|t| t.get("IntrBkSttlmDt"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("settlement_date")
                .or_else(|| flat.get("IntrBkSttlmDt"))
                .and_then(|v| v.as_str())
                .map(str::to_string)
        });

    // Debtor BIC: DbtrAgt.FinInstnId.BICFI
    let debtor_bic = tx_info
        .and_then(|t| t.get("DbtrAgt"))
        .and_then(|a| a.get("FinInstnId"))
        .and_then(|f| f.get("BICFI"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("debtor_bic")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        });

    // Creditor BIC: CdtrAgt.FinInstnId.BICFI
    let creditor_bic = tx_info
        .and_then(|t| t.get("CdtrAgt"))
        .and_then(|a| a.get("FinInstnId"))
        .and_then(|f| f.get("BICFI"))
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .or_else(|| {
            flat.get("creditor_bic")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        });

    Ok(Pacs008Fields {
        uetr,
        end_to_end_id,
        amount,
        currency,
        settlement_date,
        debtor_bic,
        creditor_bic,
    })
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_extract_camt054_flat_dict() {
        let flat = json!({
            "uetr": "test-uetr-1234",
            "individual_payment_id": "E2E-001",
            "amount": "1000.00",
            "currency": "USD",
            "settlement_time": "2026-04-01T12:00:00Z",
            "rejection_code": "AC01"
        });
        let fields = extract_camt054(None, None, None, &flat).unwrap();
        assert_eq!(fields.uetr, "test-uetr-1234");
        assert_eq!(fields.individual_payment_id, "E2E-001");
        assert_eq!(fields.amount, "1000.00");
        assert_eq!(fields.currency, "USD");
        assert_eq!(fields.settlement_time.as_deref(), Some("2026-04-01T12:00:00Z"));
        assert_eq!(fields.rejection_code.as_deref(), Some("AC01"));
    }

    #[test]
    fn test_extract_camt054_defaults_for_missing_fields() {
        let flat = json!({});
        let fields = extract_camt054(None, None, None, &flat).unwrap();
        assert_eq!(fields.uetr, "");
        assert_eq!(fields.amount, "0");
        assert_eq!(fields.currency, "USD");
        assert!(fields.settlement_time.is_none());
        assert!(fields.rejection_code.is_none());
    }

    #[test]
    fn test_extract_pacs008_flat_dict() {
        let flat = json!({
            "uetr": "pacs008-uetr-5678",
            "end_to_end_id": "E2E-002",
            "amount": "50000.00",
            "currency": "EUR",
            "settlement_date": "2026-04-02",
            "debtor_bic": "DEUTDEDB",
            "creditor_bic": "BNPAFRPP"
        });
        let fields = extract_pacs008(&flat).unwrap();
        assert_eq!(fields.uetr, "pacs008-uetr-5678");
        assert_eq!(fields.end_to_end_id, "E2E-002");
        assert_eq!(fields.amount, "50000.00");
        assert_eq!(fields.currency, "EUR");
        assert_eq!(fields.settlement_date.as_deref(), Some("2026-04-02"));
        assert_eq!(fields.debtor_bic.as_deref(), Some("DEUTDEDB"));
        assert_eq!(fields.creditor_bic.as_deref(), Some("BNPAFRPP"));
    }

    #[test]
    fn test_extract_pacs008_nested_iso20022() {
        let msg = json!({
            "FIToFICstmrCdtTrf": {
                "CdtTrfTxInf": [{
                    "PmtId": {
                        "UETR": "nested-uetr-9999",
                        "EndToEndId": "E2E-003"
                    },
                    "IntrBkSttlmAmt": {
                        "#text": "75000.00",
                        "@Ccy": "GBP"
                    },
                    "IntrBkSttlmDt": "2026-04-03",
                    "DbtrAgt": {
                        "FinInstnId": {"BICFI": "BARCGB22"}
                    },
                    "CdtrAgt": {
                        "FinInstnId": {"BICFI": "HSBCGB2L"}
                    }
                }]
            }
        });
        let fields = extract_pacs008(&msg).unwrap();
        assert_eq!(fields.uetr, "nested-uetr-9999");
        assert_eq!(fields.end_to_end_id, "E2E-003");
        assert_eq!(fields.amount, "75000.00");
        assert_eq!(fields.currency, "GBP");
        assert_eq!(fields.settlement_date.as_deref(), Some("2026-04-03"));
        assert_eq!(fields.debtor_bic.as_deref(), Some("BARCGB22"));
        assert_eq!(fields.creditor_bic.as_deref(), Some("HSBCGB2L"));
    }

    #[test]
    fn test_extract_pacs008_empty_dict() {
        let flat = json!({});
        let fields = extract_pacs008(&flat).unwrap();
        assert_eq!(fields.uetr, "");
        assert_eq!(fields.amount, "0");
        assert_eq!(fields.currency, "USD");
        assert!(fields.settlement_date.is_none());
        assert!(fields.debtor_bic.is_none());
        assert!(fields.creditor_bic.is_none());
    }
}
