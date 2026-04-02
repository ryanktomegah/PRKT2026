// normalizer_test.go — Unit tests for the C5 Go event normalizer.
//
// Tests mirror the Python TestNormalizeSwift / TestNormalizeFedNow / etc.
// suites in test_c5_streaming.py to ensure field-level parity between
// Python and Go normalization.
package main

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestNormalizeSwiftBasic(t *testing.T) {
	raw := map[string]interface{}{
		"rail":                 "SWIFT",
		"message_type":         "pacs.002",
		"uetr":                 "97ed4827-7b6f-4491-a06f-b548d5a7512d",
		"individual_payment_id": "DEUTDEDB-20240315-001",
		"sending_bic":          "DEUTDEDBXXX",
		"receiving_bic":        "CHASUS33XXX",
		"amount":               "1500000.00",
		"currency":             "USD",
		"timestamp":            "2024-03-15T14:23:00Z",
		"rejection_code":       nil,
		"narrative":            nil,
		"raw_source":           "{}",
	}
	event := mustNormalize(t, raw)

	assertEqual(t, "uetr", "97ed4827-7b6f-4491-a06f-b548d5a7512d", event.UETR)
	assertEqual(t, "sending_bic", "DEUTDEDBXXX", event.SendingBIC)
	assertEqual(t, "receiving_bic", "CHASUS33XXX", event.ReceivingBIC)
	assertEqual(t, "amount", "1500000.00", event.Amount)
	assertEqual(t, "currency", "USD", event.Currency)
	assertEqual(t, "rail", "SWIFT", event.Rail)

	if event.RejectionCode != nil {
		t.Errorf("rejection_code: expected nil, got %q", *event.RejectionCode)
	}
}

func TestNormalizeSwiftRejectionCode(t *testing.T) {
	code := "MS03"
	raw := swiftBase()
	raw["rejection_code"] = code
	event := mustNormalize(t, raw)

	if event.RejectionCode == nil || *event.RejectionCode != "MS03" {
		t.Errorf("rejection_code: expected MS03, got %v", event.RejectionCode)
	}
}

func TestNormalizeSwiftComplianceHoldCodes(t *testing.T) {
	// EPG-19: compliance hold codes must pass through unchanged on SWIFT rail
	codes := []string{"DNOR", "CNOR", "RR01", "RR02", "RR03", "RR04", "AG01", "LEGL"}
	for _, code := range codes {
		c := code
		raw := swiftBase()
		raw["rejection_code"] = c
		event := mustNormalize(t, raw)
		if event.RejectionCode == nil || *event.RejectionCode != c {
			t.Errorf("compliance code %s: expected pass-through, got %v", c, event.RejectionCode)
		}
	}
}

func TestNormalizeFedNowBasic(t *testing.T) {
	raw := fedNowBase()
	event := mustNormalize(t, raw)

	assertEqual(t, "rail", "FEDNOW", event.Rail)
	// 9-digit routing numbers should be wrapped in USRT prefix
	if !strings.HasPrefix(event.SendingBIC, "USRT") {
		t.Errorf("FedNow sending_bic should have USRT prefix, got %q", event.SendingBIC)
	}
}

func TestNormalizeFedNowRegulatoryHold(t *testing.T) {
	// F002 → RR04 mapping (compliance hold — CIPHER rule)
	code := "F002"
	raw := fedNowBase()
	raw["rejection_code"] = code
	event := mustNormalize(t, raw)

	if event.RejectionCode == nil || *event.RejectionCode != "RR04" {
		t.Errorf("F002 should map to RR04, got %v", event.RejectionCode)
	}
}

func TestNormalizeFedNowComplianceHold(t *testing.T) {
	cases := map[string]string{
		"COMPLIANCE_HOLD":   "RR04",
		"REGULATORY_HOLD":   "RR04",
		"LEGAL_HOLD":        "LEGL",
		"AML_HOLD":          "RR04",
		"LEGAL_DECISION":    "LEGL",
		"TRANSACTION_FORBIDDEN": "AG01",
	}
	for proprietary, expected := range cases {
		p := proprietary
		e := expected
		raw := fedNowBase()
		raw["rejection_code"] = p
		event := mustNormalize(t, raw)
		if event.RejectionCode == nil || *event.RejectionCode != e {
			t.Errorf("%s → expected %s, got %v", p, e, event.RejectionCode)
		}
	}
}

func TestNormalizeRTP(t *testing.T) {
	raw := map[string]interface{}{
		"rail":                 "RTP",
		"message_type":         "TCH-RTP",
		"uetr":                 "33333333-7b6f-4491-a06f-b548d5a75123",
		"individual_payment_id": "RTP-2024-XYZ",
		"sending_bic":          "021000021", // 9-digit routing number
		"receiving_bic":        "026009593",
		"amount":               "50000.00",
		"currency":             "USD",
		"timestamp":            "2024-03-15T14:23:00Z",
		"raw_source":           "{}",
	}
	event := mustNormalize(t, raw)

	assertEqual(t, "rail", "RTP", event.Rail)
	if event.SendingBIC != "USRT021000021" {
		t.Errorf("RTP sending_bic: expected USRT021000021, got %q", event.SendingBIC)
	}
}

func TestNormalizeSEPA(t *testing.T) {
	raw := map[string]interface{}{
		"rail":                 "SEPA",
		"message_type":         "pacs.002",
		"uetr":                 "44444444-7b6f-4491-a06f-b548d5a75123",
		"individual_payment_id": "SEPA-2024-001",
		"sending_bic":          "BNPAFRPPXXX",
		"receiving_bic":        "DEUTDEDBXXX",
		"amount":               "250.00",
		"currency":             "EUR",
		"timestamp":            "2024-03-15T14:23:00Z",
		"raw_source":           "{}",
	}
	event := mustNormalize(t, raw)

	assertEqual(t, "rail", "SEPA", event.Rail)
	assertEqual(t, "currency", "EUR", event.Currency)
}

func TestNormalizeMissingUETR(t *testing.T) {
	raw := swiftBase()
	delete(raw, "uetr")
	n := NewNormalizer("")
	b, _ := json.Marshal(raw)
	_, err := n.Normalize(b)
	if err == nil {
		t.Error("expected error for missing uetr, got nil")
	}
}

func TestNormalizeTimestampFormats(t *testing.T) {
	formats := []string{
		"2024-03-15T14:23:00Z",
		"2024-03-15T14:23:00.123456Z",
		"2024-03-15T14:23:00+00:00",
		"2024-03-15T14:23:00",
	}
	for _, ts := range formats {
		raw := swiftBase()
		raw["timestamp"] = ts
		event := mustNormalize(t, raw)
		if event.Timestamp.IsZero() {
			t.Errorf("timestamp %q parsed to zero time", ts)
		}
		if event.Timestamp.Location() != time.UTC {
			t.Errorf("timestamp %q should be UTC, got %v", ts, event.Timestamp.Location())
		}
	}
}

func TestNormalizeEPG28DebtorAccount(t *testing.T) {
	// EPG-28: debtor_account must be preserved for AML composite velocity key
	account := "DE89370400440532013000"
	raw := swiftBase()
	raw["debtor_account"] = account
	event := mustNormalize(t, raw)
	if event.DebtorAccount == nil || *event.DebtorAccount != account {
		t.Errorf("debtor_account: expected %q, got %v", account, event.DebtorAccount)
	}
}

func TestNormalizeGAP17OriginalAmountUSD(t *testing.T) {
	// GAP-17: original_payment_amount_usd preserved for cross-currency payments
	usdAmount := "1234567.89"
	raw := swiftBase()
	raw["original_payment_amount_usd"] = usdAmount
	raw["currency"] = "EUR"
	event := mustNormalize(t, raw)
	if event.OriginalPaymentAmountUSD == nil || *event.OriginalPaymentAmountUSD != usdAmount {
		t.Errorf("original_payment_amount_usd: expected %q, got %v", usdAmount, event.OriginalPaymentAmountUSD)
	}
}

func TestNormalizeCurrencyUppercase(t *testing.T) {
	raw := swiftBase()
	raw["currency"] = "usd" // lowercase should be normalized
	event := mustNormalize(t, raw)
	assertEqual(t, "currency", "USD", event.Currency)
}

// ── helpers ───────────────────────────────────────────────────────────────────

func mustNormalize(t *testing.T, raw map[string]interface{}) *NormalizedEvent {
	t.Helper()
	b, err := json.Marshal(raw)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	n := NewNormalizer("")
	event, err := n.Normalize(b)
	if err != nil {
		t.Fatalf("normalize: %v", err)
	}
	return event
}

func swiftBase() map[string]interface{} {
	return map[string]interface{}{
		"rail":                 "SWIFT",
		"message_type":         "pacs.002",
		"uetr":                 "97ed4827-7b6f-4491-a06f-b548d5a7512d",
		"individual_payment_id": "DEUTDEDB-20240315-001",
		"sending_bic":          "DEUTDEDBXXX",
		"receiving_bic":        "CHASUS33XXX",
		"amount":               "1500000.00",
		"currency":             "USD",
		"timestamp":            "2024-03-15T14:23:00Z",
		"raw_source":           "{}",
	}
}

func fedNowBase() map[string]interface{} {
	return map[string]interface{}{
		"rail":                 "FEDNOW",
		"message_type":         "FedNow.002",
		"uetr":                 "22222222-7b6f-4491-a06f-b548d5a75123",
		"individual_payment_id": "FN-2024-001",
		"sending_bic":          "021000021", // 9-digit routing number
		"receiving_bic":        "026009593",
		"amount":               "100000.00",
		"currency":             "USD",
		"timestamp":            "2024-03-15T14:23:00Z",
		"raw_source":           "{}",
	}
}

func assertEqual(t *testing.T, field, expected, actual string) {
	t.Helper()
	if actual != expected {
		t.Errorf("%s: expected %q, got %q", field, expected, actual)
	}
}
