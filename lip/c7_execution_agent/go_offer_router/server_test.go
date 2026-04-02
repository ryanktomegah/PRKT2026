// server_test.go — Unit tests for the C7 Go offer router server.
//
// Tests cover:
//   - Config: defaults, env overrides, validation errors
//   - KillSwitch: missing SHM → fail-closed, SHM read (active/inactive)
//   - TriggerOffer: happy path, duplicate, kill switch blocked, expired, missing fields
//   - AcceptOffer: happy path, not found, already resolved, missing operator ID
//   - RejectOffer: happy path, missing reason, already resolved
//   - CancelOffer: happy path, idempotent cancel
//   - QueryOffer: pending, accepted, rejected, expired, unknown
//   - HealthCheck: alive, kill switch reflected, active offer count
//   - Expiry: goroutine fires at ExpiresAt; accept before expiry wins
//   - Concurrency: 50 simultaneous offers with mixed accept/cancel, no goroutine leaks
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"sync"
	"testing"
	"time"
)

// ─────────────────────────────────────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────────────────────────────────────

// newTestServer creates an OfferRouterServer with noop metrics and a mock
// kill switch reader that starts in INACTIVE state (permits TriggerOffer).
func newTestServer(t *testing.T) *OfferRouterServer {
	t.Helper()
	clearEnv(t)

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	cfg.MaxConcurrentOffers = 0
	cfg.DefaultExpirySeconds = 60
	cfg.KillSwitchSHMPath = "/tmp/nonexistent_ks_for_test"

	log := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	// Start with a KillSwitchReader pointed at a non-existent path, but
	// override the atomic flag to false (inactive) so tests can trigger offers.
	ks := NewKillSwitchReader(cfg.KillSwitchSHMPath, log)
	ks.killed.Store(false) // override fail-closed for general tests

	return NewOfferRouterServer(cfg, ks, newNoopMetrics(), log)
}

// call invokes a server handler directly (bypasses gRPC transport) and returns
// the decoded JSON response map.
func call(
	t *testing.T,
	s *OfferRouterServer,
	handler func(context.Context, []byte) ([]byte, error),
	req interface{},
) map[string]interface{} {
	t.Helper()
	body, err := json.Marshal(req)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}
	resp, err := handler(context.Background(), body)
	if err != nil {
		t.Fatalf("handler returned gRPC error: %v", err)
	}
	var out map[string]interface{}
	if err := json.Unmarshal(resp, &out); err != nil {
		t.Fatalf("unmarshal response %q: %v", resp, err)
	}
	return out
}

// triggerOffer is a convenience wrapper for call around handleTriggerOffer.
func triggerOffer(t *testing.T, s *OfferRouterServer, req TriggerOfferRequest) map[string]interface{} {
	t.Helper()
	return call(t, s, s.handleTriggerOffer, req)
}

// mustTrigger triggers an offer with a 30s expiry and fails if it does not succeed.
func mustTrigger(t *testing.T, s *OfferRouterServer, offerID string) {
	t.Helper()
	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:    offerID,
		UETR:       "uetr-" + offerID,
		LoanAmount: "1000000.00",
		FeeBPS:     "300",
		ExpiresAt:  time.Now().Add(30 * time.Second).Format(time.RFC3339),
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("mustTrigger(%s) failed: %v", offerID, resp["error"])
	}
}

// waitForOutcome polls QueryOffer until a non-PENDING outcome is observed or
// timeout is exceeded.
func waitForOutcome(t *testing.T, s *OfferRouterServer, offerID string, timeout time.Duration) string {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		resp := call(t, s, s.handleQueryOffer, QueryOfferRequest{OfferID: offerID})
		if out := strField(resp, "outcome"); out != OutcomePending {
			return out
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("offer %s still PENDING after %s", offerID, timeout)
	return ""
}

func boolField(m map[string]interface{}, key string) bool {
	v, _ := m[key].(bool)
	return v
}

func strField(m map[string]interface{}, key string) string {
	v, _ := m[key].(string)
	return v
}

// ─────────────────────────────────────────────────────────────────────────────
// Config tests
// ─────────────────────────────────────────────────────────────────────────────

func TestConfigDefaults(t *testing.T) {
	clearEnv(t)
	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	if cfg.GRPCAddr != ":50057" {
		t.Errorf("GRPCAddr: want :50057, got %s", cfg.GRPCAddr)
	}
	if cfg.MetricsAddr != ":9091" {
		t.Errorf("MetricsAddr: want :9091, got %s", cfg.MetricsAddr)
	}
	if cfg.MaxConcurrentOffers != 0 {
		t.Errorf("MaxConcurrentOffers: want 0, got %d", cfg.MaxConcurrentOffers)
	}
	if cfg.DefaultExpirySeconds != 120 {
		t.Errorf("DefaultExpirySeconds: want 120, got %d", cfg.DefaultExpirySeconds)
	}
	if cfg.KillSwitchSHMPath != "/dev/shm/lip_kill_switch" {
		t.Errorf("KillSwitchSHMPath: want /dev/shm/lip_kill_switch, got %s", cfg.KillSwitchSHMPath)
	}
}

func TestConfigEnvOverride(t *testing.T) {
	clearEnv(t)
	t.Setenv("C7_GRPC_ADDR", ":50099")
	t.Setenv("C7_MAX_CONCURRENT_OFFERS", "500")
	t.Setenv("C7_DEFAULT_EXPIRY_SECONDS", "45")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	if cfg.GRPCAddr != ":50099" {
		t.Errorf("GRPCAddr: want :50099, got %s", cfg.GRPCAddr)
	}
	if cfg.MaxConcurrentOffers != 500 {
		t.Errorf("MaxConcurrentOffers: want 500, got %d", cfg.MaxConcurrentOffers)
	}
	if cfg.DefaultExpirySeconds != 45 {
		t.Errorf("DefaultExpirySeconds: want 45, got %d", cfg.DefaultExpirySeconds)
	}
}

func TestConfigInvalidMaxConcurrent(t *testing.T) {
	clearEnv(t)
	t.Setenv("C7_MAX_CONCURRENT_OFFERS", "not-a-number")
	if _, err := LoadConfig(); err == nil {
		t.Error("expected error for non-integer C7_MAX_CONCURRENT_OFFERS")
	}
}

func TestConfigNegativeMaxConcurrent(t *testing.T) {
	clearEnv(t)
	t.Setenv("C7_MAX_CONCURRENT_OFFERS", "-1")
	if _, err := LoadConfig(); err == nil {
		t.Error("expected error for negative C7_MAX_CONCURRENT_OFFERS")
	}
}

func TestConfigZeroExpirySeconds(t *testing.T) {
	clearEnv(t)
	t.Setenv("C7_DEFAULT_EXPIRY_SECONDS", "0")
	if _, err := LoadConfig(); err == nil {
		t.Error("expected error for C7_DEFAULT_EXPIRY_SECONDS=0")
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Kill switch tests
// ─────────────────────────────────────────────────────────────────────────────

func TestKillSwitchMissingSHMFailsClosed(t *testing.T) {
	log := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
	ks := NewKillSwitchReader("/tmp/missing_shm_file_"+fmt.Sprintf("%d", time.Now().UnixNano()), log)
	if !ks.IsKilled() {
		t.Error("missing SHM should return killed=true (fail-closed)")
	}
}

func TestKillSwitchSHMKilledFlag(t *testing.T) {
	f, err := os.CreateTemp("", "ks_test_active_*.bin")
	if err != nil {
		t.Fatalf("CreateTemp: %v", err)
	}
	defer os.Remove(f.Name())

	seg := make([]byte, 288)
	seg[0] = 0x01 // kill_flag = KILLED
	_, _ = f.Write(seg)
	f.Close()

	log := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
	ks := NewKillSwitchReader(f.Name(), log)
	if !ks.IsKilled() {
		t.Error("kill_flag=0x01 should be killed=true")
	}
}

func TestKillSwitchSHMInactiveFlag(t *testing.T) {
	f, err := os.CreateTemp("", "ks_test_inactive_*.bin")
	if err != nil {
		t.Fatalf("CreateTemp: %v", err)
	}
	defer os.Remove(f.Name())

	seg := make([]byte, 288)
	seg[0] = 0x00 // kill_flag = INACTIVE
	_, _ = f.Write(seg)
	f.Close()

	log := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
	ks := NewKillSwitchReader(f.Name(), log)
	if ks.IsKilled() {
		t.Error("kill_flag=0x00 should be killed=false")
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// TriggerOffer tests
// ─────────────────────────────────────────────────────────────────────────────

func TestTriggerOfferHappyPath(t *testing.T) {
	s := newTestServer(t)
	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:    "to-happy",
		UETR:       "uetr-to-happy",
		LoanAmount: "1000000.00",
		FeeBPS:     "300",
		ExpiresAt:  time.Now().Add(60 * time.Second).Format(time.RFC3339),
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("expected accepted=true, got error=%q", resp["error"])
	}
	// clean up
	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "to-happy"})
}

func TestTriggerOfferDuplicate(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "to-dup")

	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "to-dup",
		UETR:      "uetr-to-dup-2",
		ExpiresAt: time.Now().Add(60 * time.Second).Format(time.RFC3339),
	})
	if boolField(resp, "accepted") {
		t.Error("duplicate TriggerOffer should fail")
	}
	errMsg := strField(resp, "error")
	if errMsg == "" {
		t.Error("duplicate TriggerOffer should return an error message")
	}

	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "to-dup"})
}

func TestTriggerOfferKillSwitchBlocked(t *testing.T) {
	s := newTestServer(t)
	s.ks.killed.Store(true)

	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "to-ks",
		UETR:      "uetr-to-ks",
		ExpiresAt: time.Now().Add(60 * time.Second).Format(time.RFC3339),
	})
	if boolField(resp, "accepted") {
		t.Error("TriggerOffer should be blocked when kill switch is active")
	}
}

func TestTriggerOfferMissingOfferID(t *testing.T) {
	s := newTestServer(t)
	resp := triggerOffer(t, s, TriggerOfferRequest{
		UETR:      "uetr-x",
		ExpiresAt: time.Now().Add(60 * time.Second).Format(time.RFC3339),
	})
	if boolField(resp, "accepted") {
		t.Error("TriggerOffer without offer_id should fail")
	}
}

func TestTriggerOfferMissingUETR(t *testing.T) {
	s := newTestServer(t)
	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "to-nouetr",
		ExpiresAt: time.Now().Add(60 * time.Second).Format(time.RFC3339),
	})
	if boolField(resp, "accepted") {
		t.Error("TriggerOffer without uetr should fail")
	}
}

func TestTriggerOfferExpiredExpiresAt(t *testing.T) {
	s := newTestServer(t)
	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "to-pastexp",
		UETR:      "uetr-past",
		ExpiresAt: time.Now().Add(-1 * time.Second).Format(time.RFC3339),
	})
	if boolField(resp, "accepted") {
		t.Error("TriggerOffer with past expires_at should fail")
	}
}

func TestTriggerOfferMaxConcurrentLimit(t *testing.T) {
	s := newTestServer(t)
	s.cfg.MaxConcurrentOffers = 2

	mustTrigger(t, s, "mc-1")
	mustTrigger(t, s, "mc-2")

	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "mc-3",
		UETR:      "uetr-mc-3",
		ExpiresAt: time.Now().Add(60 * time.Second).Format(time.RFC3339),
	})
	if boolField(resp, "accepted") {
		t.Error("third offer should be rejected at MaxConcurrentOffers=2")
	}

	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "mc-1"})
	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "mc-2"})
}

// ─────────────────────────────────────────────────────────────────────────────
// AcceptOffer tests
// ─────────────────────────────────────────────────────────────────────────────

func TestAcceptOfferHappyPath(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "ao-happy")

	resp := call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "ao-happy",
		ELOOperatorID: "op-treasury-001",
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("AcceptOffer failed: %v", resp["error"])
	}

	outcome := waitForOutcome(t, s, "ao-happy", 2*time.Second)
	if outcome != OutcomeAccepted {
		t.Errorf("expected ACCEPTED, got %s", outcome)
	}
}

func TestAcceptOfferNotFound(t *testing.T) {
	s := newTestServer(t)
	resp := call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "nonexistent-offer",
		ELOOperatorID: "op-001",
	})
	if boolField(resp, "accepted") {
		t.Error("AcceptOffer on unknown offer_id should fail")
	}
}

func TestAcceptOfferMissingOperatorID(t *testing.T) {
	s := newTestServer(t)
	resp := call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID: "ao-noopid",
	})
	if boolField(resp, "accepted") {
		t.Error("AcceptOffer without elo_operator_id should fail")
	}
}

func TestAcceptOfferAlreadyResolved(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "ao-double")

	call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "ao-double",
		ELOOperatorID: "op-001",
	})
	waitForOutcome(t, s, "ao-double", 2*time.Second)

	resp := call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "ao-double",
		ELOOperatorID: "op-001",
	})
	if boolField(resp, "accepted") {
		t.Error("second AcceptOffer on resolved offer should fail")
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// RejectOffer tests
// ─────────────────────────────────────────────────────────────────────────────

func TestRejectOfferHappyPath(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "ro-happy")

	resp := call(t, s, s.handleRejectOffer, RejectOfferRequest{
		OfferID:         "ro-happy",
		ELOOperatorID:   "op-treasury-002",
		RejectionReason: "insufficient liquidity",
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("RejectOffer failed: %v", resp["error"])
	}

	outcome := waitForOutcome(t, s, "ro-happy", 2*time.Second)
	if outcome != OutcomeRejected {
		t.Errorf("expected REJECTED, got %s", outcome)
	}
}

func TestRejectOfferMissingReason(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "ro-noreason")

	resp := call(t, s, s.handleRejectOffer, RejectOfferRequest{
		OfferID:       "ro-noreason",
		ELOOperatorID: "op-001",
	})
	if boolField(resp, "accepted") {
		t.Error("RejectOffer without rejection_reason should fail")
	}

	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "ro-noreason"})
}

func TestRejectOfferAlreadyAccepted(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "ro-already-accepted")

	call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "ro-already-accepted",
		ELOOperatorID: "op-001",
	})
	waitForOutcome(t, s, "ro-already-accepted", 2*time.Second)

	resp := call(t, s, s.handleRejectOffer, RejectOfferRequest{
		OfferID:         "ro-already-accepted",
		ELOOperatorID:   "op-001",
		RejectionReason: "too late",
	})
	if boolField(resp, "accepted") {
		t.Error("RejectOffer on already-accepted offer should fail")
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// CancelOffer tests
// ─────────────────────────────────────────────────────────────────────────────

func TestCancelOfferHappyPath(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "co-happy")

	resp := call(t, s, s.handleCancelOffer, CancelOfferRequest{
		OfferID: "co-happy",
		Reason:  "pipeline shut down",
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("CancelOffer failed: %v", resp["error"])
	}

	outcome := waitForOutcome(t, s, "co-happy", 2*time.Second)
	if outcome != OutcomeCancelled {
		t.Errorf("expected CANCELLED, got %s", outcome)
	}
}

func TestCancelOfferIdempotent(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "co-idem")

	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "co-idem"})
	waitForOutcome(t, s, "co-idem", 2*time.Second)

	// Second cancel after resolution must not panic
	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "co-idem"})
}

func TestCancelOfferNotFound(t *testing.T) {
	s := newTestServer(t)
	resp := call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "nope"})
	if boolField(resp, "accepted") {
		t.Error("CancelOffer on unknown offer should fail")
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// QueryOffer tests
// ─────────────────────────────────────────────────────────────────────────────

func TestQueryOfferPending(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "qo-pending")

	resp := call(t, s, s.handleQueryOffer, QueryOfferRequest{OfferID: "qo-pending"})
	if strField(resp, "outcome") != OutcomePending {
		t.Errorf("expected PENDING, got %s", resp["outcome"])
	}

	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "qo-pending"})
}

func TestQueryOfferUnknown(t *testing.T) {
	s := newTestServer(t)
	resp := call(t, s, s.handleQueryOffer, QueryOfferRequest{OfferID: "does-not-exist"})
	if strField(resp, "outcome") != "UNKNOWN" {
		t.Errorf("expected UNKNOWN, got %s", resp["outcome"])
	}
}

func TestQueryOfferAfterAcceptance(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "qo-accept")
	call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "qo-accept",
		ELOOperatorID: "op-qa",
	})
	outcome := waitForOutcome(t, s, "qo-accept", 2*time.Second)
	if outcome != OutcomeAccepted {
		t.Errorf("expected ACCEPTED, got %s", outcome)
	}
}

func TestQueryOfferAfterRejection(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "qo-reject")
	call(t, s, s.handleRejectOffer, RejectOfferRequest{
		OfferID:         "qo-reject",
		ELOOperatorID:   "op-qa",
		RejectionReason: "test rejection",
	})
	outcome := waitForOutcome(t, s, "qo-reject", 2*time.Second)
	if outcome != OutcomeRejected {
		t.Errorf("expected REJECTED, got %s", outcome)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// HealthCheck tests
// ─────────────────────────────────────────────────────────────────────────────

func TestHealthCheckAlive(t *testing.T) {
	s := newTestServer(t)
	resp := call(t, s, s.handleHealthCheck, map[string]interface{}{})
	if !boolField(resp, "ok") {
		t.Error("HealthCheck should return ok=true")
	}
}

func TestHealthCheckReflectsKillSwitch(t *testing.T) {
	s := newTestServer(t)
	s.ks.killed.Store(true)

	resp := call(t, s, s.handleHealthCheck, map[string]interface{}{})
	if !boolField(resp, "kill_switch_active") {
		t.Error("HealthCheck should reflect kill_switch_active=true when kill switch is on")
	}
}

func TestHealthCheckActiveOfferCount(t *testing.T) {
	s := newTestServer(t)
	mustTrigger(t, s, "hc-1")
	mustTrigger(t, s, "hc-2")

	resp := call(t, s, s.handleHealthCheck, map[string]interface{}{})
	n, _ := resp["active_offers"].(float64) // JSON numbers decode as float64
	if int(n) != 2 {
		t.Errorf("expected active_offers=2, got %v", resp["active_offers"])
	}

	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "hc-1"})
	call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: "hc-2"})
}

// ─────────────────────────────────────────────────────────────────────────────
// Expiry tests
// ─────────────────────────────────────────────────────────────────────────────

func TestOfferExpiryFires(t *testing.T) {
	s := newTestServer(t)
	expiresAt := time.Now().Add(80 * time.Millisecond)
	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "exp-fire",
		UETR:      "uetr-exp-fire",
		ExpiresAt: expiresAt.UTC().Format(time.RFC3339Nano),
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("TriggerOffer failed: %v", resp["error"])
	}

	outcome := waitForOutcome(t, s, "exp-fire", 600*time.Millisecond)
	if outcome != OutcomeExpired {
		t.Errorf("expected EXPIRED, got %s", outcome)
	}
}

func TestAcceptWinsOverExpiry(t *testing.T) {
	s := newTestServer(t)
	expiresAt := time.Now().Add(200 * time.Millisecond)
	resp := triggerOffer(t, s, TriggerOfferRequest{
		OfferID:   "exp-race-win",
		UETR:      "uetr-exp-race",
		ExpiresAt: expiresAt.UTC().Format(time.RFC3339Nano),
	})
	if !boolField(resp, "accepted") {
		t.Fatalf("TriggerOffer failed: %v", resp["error"])
	}

	// Accept before expiry fires
	call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
		OfferID:       "exp-race-win",
		ELOOperatorID: "op-fast",
	})
	outcome := waitForOutcome(t, s, "exp-race-win", 600*time.Millisecond)
	if outcome != OutcomeAccepted {
		t.Errorf("accept-before-expiry: expected ACCEPTED, got %s", outcome)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Concurrency stress test
// ─────────────────────────────────────────────────────────────────────────────

func TestConcurrentOffersNoGoroutineLeak(t *testing.T) {
	s := newTestServer(t)
	const N = 50

	var wg sync.WaitGroup

	// Trigger N offers in parallel
	wg.Add(N)
	for i := 0; i < N; i++ {
		i := i
		go func() {
			defer wg.Done()
			id := fmt.Sprintf("stress-%d", i)
			resp := triggerOffer(t, s, TriggerOfferRequest{
				OfferID:   id,
				UETR:      "uetr-" + id,
				ExpiresAt: time.Now().Add(5 * time.Second).Format(time.RFC3339),
			})
			if !boolField(resp, "accepted") {
				t.Errorf("TriggerOffer(%s) failed: %v", id, resp["error"])
			}
		}()
	}
	wg.Wait()

	// Accept half, cancel half concurrently
	wg.Add(N)
	for i := 0; i < N; i++ {
		i := i
		go func() {
			defer wg.Done()
			id := fmt.Sprintf("stress-%d", i)
			if i%2 == 0 {
				call(t, s, s.handleAcceptOffer, AcceptOfferRequest{
					OfferID:       id,
					ELOOperatorID: "op-stress",
				})
			} else {
				call(t, s, s.handleCancelOffer, CancelOfferRequest{OfferID: id})
			}
		}()
	}
	wg.Wait()

	// Wait for all goroutines to drain from the registry
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		s.offersMu.RLock()
		n := len(s.offers)
		s.offersMu.RUnlock()
		if n == 0 {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}

	s.offersMu.RLock()
	remaining := len(s.offers)
	s.offersMu.RUnlock()
	if remaining > 0 {
		t.Errorf("%d goroutines still in registry after 2s — goroutine leak", remaining)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

func clearEnv(t *testing.T) {
	t.Helper()
	keys := []string{
		"C7_GRPC_ADDR", "C7_METRICS_ADDR", "C7_MAX_CONCURRENT_OFFERS",
		"C7_DEFAULT_EXPIRY_SECONDS", "C7_KILL_SWITCH_SHM_PATH",
		"C7_LOG_LEVEL", "C7_SHUTDOWN_TIMEOUT_SECONDS", "C7_GRPC_MAX_MSG_SIZE",
	}
	for _, k := range keys {
		os.Unsetenv(k)
	}
}
