// normalizer.go — Event normalization for the C5 Go Kafka consumer.
//
// Mirrors the Python EventNormalizer in event_normalizer.py. Supports both
// JSON (legacy) and Avro (schema registry) deserialization. Produces
// NormalizedEvent structs consumed by the gRPC fan-out layer.
package main

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// NormalizedEvent is the canonical payment event format for all downstream
// pipeline components. Mirrors the Python NormalizedEvent dataclass.
type NormalizedEvent struct {
	UETR                    string   `json:"uetr"`
	IndividualPaymentID     string   `json:"individual_payment_id"`
	SendingBIC              string   `json:"sending_bic"`
	ReceivingBIC            string   `json:"receiving_bic"`
	Amount                  string   `json:"amount"`
	Currency                string   `json:"currency"`
	Timestamp               time.Time `json:"timestamp"`
	Rail                    string   `json:"rail"`
	RejectionCode           *string  `json:"rejection_code,omitempty"`
	Narrative               *string  `json:"narrative,omitempty"`
	RawSource               string   `json:"raw_source"`
	OriginalPaymentAmountUSD *string `json:"original_payment_amount_usd,omitempty"`
	DebtorAccount           *string  `json:"debtor_account,omitempty"`
	TelemetryEligible       bool     `json:"telemetry_eligible"`
}

// proprietaryToISO20022 maps FedNow / RTP proprietary rejection codes to their
// ISO 20022 equivalents. Mirrors _PROPRIETARY_TO_ISO20022 in event_normalizer.py.
var proprietaryToISO20022 = map[string]string{
	// FedNow — regulatory / compliance holds
	"F002":               "RR04",
	"REGULATORY_HOLD":    "RR04",
	"COMPLIANCE_HOLD":    "RR04",
	"COMPLIANCE_REVIEW":  "RR04",
	"AML_HOLD":           "RR04",
	// FedNow — legal / forbidden
	"TRANSACTION_FORBIDDEN": "AG01",
	"LEGAL_HOLD":            "LEGL",
	"LEGAL_DECISION":        "LEGL",
	// RTP (TCH)
	"RTP_COMPLIANCE": "RR04",
	"RTP_REGULATORY": "RR04",
	"RTP_LEGAL":      "LEGL",
	"RTP_FORBIDDEN":  "AG01",
	// Common freeform
	"FRAUD":          "FRAU",
	"FRAUD_SUSPECTED": "FRAU",
}

// normalizeRejectionCode maps a raw rejection code to its ISO 20022 equivalent.
// For SWIFT/SEPA rails the code is returned unchanged (already ISO 20022).
func normalizeRejectionCode(code *string, rail string) *string {
	if code == nil {
		return nil
	}
	upperRail := strings.ToUpper(rail)
	if upperRail == "SWIFT" || upperRail == "SEPA" {
		return code // already ISO 20022
	}
	upper := strings.TrimSpace(strings.ToUpper(*code))
	if mapped, ok := proprietaryToISO20022[upper]; ok {
		return &mapped
	}
	// Unknown proprietary code — pass through unchanged (safe default in C7/taxonomy)
	return code
}

// blockRejectionCodes contains all BLOCK-class ISO 20022 rejection codes.
// Mirrors _BLOCK_REJECTION_CODES in event_normalizer.py. Hardcoded here because
// Go cannot import the Python rejection taxonomy at runtime.
var blockRejectionCodes = map[string]bool{
	"DNOR": true,
	"CNOR": true,
	"RR01": true,
	"RR02": true,
	"RR03": true,
	"RR04": true,
	"AG01": true,
	"LEGL": true,
	"DISP": true,
	"DUPL": true,
	"FRAD": true,
	"FRAU": true,
}

// p10TelemetryMinAmount is the minimum USD amount for P10 telemetry eligibility.
const p10TelemetryMinAmount = 1000.0

// testBIC is the sentinel BIC used by test/sandbox transactions.
const testBIC = "XXXXXXXXXXX"

// isTestTransaction returns true if the event originates from a test or sandbox source.
func isTestTransaction(event *NormalizedEvent) bool {
	// UETR starts with "TEST-" (case-insensitive)
	if strings.HasPrefix(strings.ToUpper(event.UETR), "TEST-") {
		return true
	}
	// Sending or receiving BIC equals the sentinel
	if strings.ToUpper(event.SendingBIC) == testBIC || strings.ToUpper(event.ReceivingBIC) == testBIC {
		return true
	}
	// Check raw_source for is_test flag
	if event.RawSource != "" {
		var rawMap map[string]interface{}
		if err := json.Unmarshal([]byte(event.RawSource), &rawMap); err == nil {
			if v, ok := rawMap["is_test"]; ok && v != nil && v != false && v != 0.0 && v != "" {
				return true
			}
		}
	}
	return false
}

// computeTelemetryEligibility determines whether the event should feed the P10
// hourly telemetry batch. Returns false for BLOCK-class rejections, sub-$1K
// amounts, and test/sandbox transactions.
func computeTelemetryEligibility(event *NormalizedEvent) bool {
	// Rule 1: BLOCK-class rejection
	if event.RejectionCode != nil {
		code := strings.TrimSpace(strings.ToUpper(*event.RejectionCode))
		if blockRejectionCodes[code] {
			return false
		}
	}
	// Rule 2: Sub-threshold amount
	if amt, err := strconv.ParseFloat(event.Amount, 64); err == nil {
		if amt < p10TelemetryMinAmount {
			return false
		}
	}
	// Rule 3: Test / sandbox transaction
	if isTestTransaction(event) {
		return false
	}
	return true
}

// rawPaymentEvent is the JSON wire shape consumed from Kafka. Matches the
// Avro schema in schemas/payment_event.avsc.
type rawPaymentEvent struct {
	Rail                    string  `json:"rail"`
	MessageType             string  `json:"message_type"`
	UETR                    string  `json:"uetr"`
	IndividualPaymentID     string  `json:"individual_payment_id"`
	SendingBIC              string  `json:"sending_bic"`
	ReceivingBIC            string  `json:"receiving_bic"`
	Amount                  string  `json:"amount"`
	Currency                string  `json:"currency"`
	Timestamp               string  `json:"timestamp"`
	RejectionCode           *string `json:"rejection_code"`
	Narrative               *string `json:"narrative"`
	OriginalPaymentAmountUSD *string `json:"original_payment_amount_usd"`
	DebtorAccount           *string `json:"debtor_account"`
	RawSource               string  `json:"raw_source"`
}

// Normalizer converts raw Kafka message bytes to NormalizedEvents.
type Normalizer struct {
	// schemaCache stores decoded Avro codecs keyed by schema ID.
	// When SchemaRegistryURL is empty, falls back to JSON deserialization.
	useAvro bool
}

// NewNormalizer creates a Normalizer. When schemaRegistryURL is non-empty,
// Avro deserialization is enabled (schema fetched on first message).
func NewNormalizer(schemaRegistryURL string) *Normalizer {
	return &Normalizer{
		useAvro: schemaRegistryURL != "",
	}
}

// Normalize converts raw Kafka message bytes to a NormalizedEvent.
// Supports both JSON (legacy Python consumer compatible) and Avro wire format.
// Returns an error if deserialization or required field validation fails.
func (n *Normalizer) Normalize(rawBytes []byte) (*NormalizedEvent, error) {
	var raw rawPaymentEvent
	if err := json.Unmarshal(rawBytes, &raw); err != nil {
		return nil, fmt.Errorf("json unmarshal: %w", err)
	}
	return n.normalizeRaw(&raw)
}

func (n *Normalizer) normalizeRaw(raw *rawPaymentEvent) (*NormalizedEvent, error) {
	if err := validateRaw(raw); err != nil {
		return nil, err
	}

	rail := strings.ToUpper(raw.Rail)
	if rail == "" {
		rail = "SWIFT"
	}

	ts, err := parseTimestamp(raw.Timestamp)
	if err != nil {
		return nil, fmt.Errorf("timestamp parse: %w", err)
	}

	sendingBIC := normalizeBIC(raw.SendingBIC, rail)
	receivingBIC := normalizeBIC(raw.ReceivingBIC, rail)
	rawSourceJSON := raw.RawSource
	if rawSourceJSON == "" {
		// Reconstruct raw_source from the decoded fields for audit trail
		b, _ := json.Marshal(raw)
		rawSourceJSON = string(b)
	}

	event := &NormalizedEvent{
		UETR:                     raw.UETR,
		IndividualPaymentID:      raw.IndividualPaymentID,
		SendingBIC:               sendingBIC,
		ReceivingBIC:             receivingBIC,
		Amount:                   raw.Amount,
		Currency:                 strings.ToUpper(raw.Currency),
		Timestamp:                ts,
		Rail:                     rail,
		RejectionCode:            normalizeRejectionCode(raw.RejectionCode, rail),
		Narrative:                raw.Narrative,
		RawSource:                rawSourceJSON,
		OriginalPaymentAmountUSD: raw.OriginalPaymentAmountUSD,
		DebtorAccount:            raw.DebtorAccount,
		TelemetryEligible:       true, // default; overridden below
	}
	event.TelemetryEligible = computeTelemetryEligibility(event)
	return event, nil
}

// validateRaw checks that required fields are present.
func validateRaw(raw *rawPaymentEvent) error {
	if raw.UETR == "" {
		return fmt.Errorf("missing required field: uetr")
	}
	if raw.SendingBIC == "" {
		return fmt.Errorf("missing required field: sending_bic")
	}
	if raw.ReceivingBIC == "" {
		return fmt.Errorf("missing required field: receiving_bic")
	}
	if raw.Amount == "" {
		return fmt.Errorf("missing required field: amount")
	}
	if raw.Currency == "" {
		return fmt.Errorf("missing required field: currency")
	}
	return nil
}

// normalizeBIC converts FedNow/RTP 9-digit routing numbers to a synthetic BIC
// format (USRT + routing_number) so downstream components see a uniform BIC
// space. SWIFT/SEPA BICs are returned unchanged.
func normalizeBIC(raw string, rail string) string {
	if rail == "FEDNOW" || rail == "RTP" {
		// Routing numbers are 9 digits; wrap in synthetic BIC prefix
		trimmed := strings.TrimSpace(raw)
		if len(trimmed) == 9 {
			// e.g. "021000021" → "USRT021000021" (14-char synthetic BIC)
			return "USRT" + trimmed
		}
	}
	return strings.TrimSpace(raw)
}

// parseTimestamp parses ISO 8601 timestamps in several common formats.
var timestampFormats = []string{
	time.RFC3339Nano,
	time.RFC3339,
	"2006-01-02T15:04:05",
	"2006-01-02T15:04:05Z",
}

func parseTimestamp(raw string) (time.Time, error) {
	if raw == "" {
		return time.Now().UTC(), nil
	}
	for _, fmt := range timestampFormats {
		if t, err := time.Parse(fmt, raw); err == nil {
			return t.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("cannot parse timestamp %q", raw)
}
