// server.go — gRPC server for the C7 Go offer router.
//
// Implements the goroutine-per-offer architecture described in
// docs/specs/c7_offer_routing_migration.md.
//
// Each TriggerOffer call spawns a dedicated goroutine that races:
//   - time.Timer at ExpiresAt                 → expiry
//   - AcceptCh channel signal                 → acceptance
//   - RejectCh channel signal                 → rejection
//   - CancelCh channel signal                 → cancellation
//   - shutdownCh broadcast close              → graceful shutdown
//
// All state mutations are mediated by the offerState channels so no
// shared-lock contention exists on the hot path.
//
// Protocol: JSON-over-gRPC (raw []byte frames), matching the C5 Go consumer
// pattern. Python callers use grpc.Channel.unary_unary without proto stubs.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ─────────────────────────────────────────────────────────────────────────────
// Outcome constants (mirrors Python OfferDeliveryOutcome)
// ─────────────────────────────────────────────────────────────────────────────

const (
	OutcomePending   = "PENDING"
	OutcomeAccepted  = "ACCEPTED"
	OutcomeRejected  = "REJECTED"
	OutcomeExpired   = "EXPIRED"
	OutcomeCancelled = "CANCELLED"
)

// ─────────────────────────────────────────────────────────────────────────────
// Wire types — JSON request / response structs
// ─────────────────────────────────────────────────────────────────────────────

// TriggerOfferRequest carries the minimal offer fields needed to start the
// expiry race. Python provides all fields from the agent._build_loan_offer dict.
type TriggerOfferRequest struct {
	OfferID      string `json:"offer_id"`
	UETR         string `json:"uetr"`
	LoanAmount   string `json:"loan_amount"`
	FeeBPS       string `json:"fee_bps"`
	MaturityDays int    `json:"maturity_days"`
	ExpiresAt    string `json:"expires_at"`  // RFC3339
	ELOEntityID  string `json:"elo_entity_id"`
}

// AcceptOfferRequest carries the ELO acceptance payload.
type AcceptOfferRequest struct {
	OfferID        string `json:"offer_id"`
	ELOOperatorID  string `json:"elo_operator_id"`
}

// RejectOfferRequest carries the ELO rejection payload.
type RejectOfferRequest struct {
	OfferID         string `json:"offer_id"`
	ELOOperatorID   string `json:"elo_operator_id"`
	RejectionReason string `json:"rejection_reason"`
}

// CancelOfferRequest cancels an in-flight offer.
type CancelOfferRequest struct {
	OfferID string `json:"offer_id"`
	Reason  string `json:"reason"`
}

// QueryOfferRequest queries the current outcome of an offer.
type QueryOfferRequest struct {
	OfferID string `json:"offer_id"`
}

// genericResponse is the standard response envelope.
type genericResponse struct {
	Accepted bool   `json:"accepted"`
	Error    string `json:"error,omitempty"`
}

// queryResponse is the response to QueryOffer.
type queryResponse struct {
	Outcome    string `json:"outcome"`
	ResolvedAt string `json:"resolved_at,omitempty"` // RFC3339
	Error      string `json:"error,omitempty"`
}

// healthResponse is the HealthCheck response.
type healthResponse struct {
	OK           bool   `json:"ok"`
	ActiveOffers int    `json:"active_offers"`
	KillSwitch   bool   `json:"kill_switch_active"`
	Error        string `json:"error,omitempty"`
}

// ─────────────────────────────────────────────────────────────────────────────
// Per-offer state
// ─────────────────────────────────────────────────────────────────────────────

// acceptSignal carries the acceptance payload through the AcceptCh channel.
type acceptSignal struct {
	ELOOperatorID string
}

// rejectSignal carries the rejection payload through the RejectCh channel.
type rejectSignal struct {
	ELOOperatorID   string
	RejectionReason string
}

// offerState holds all mutable state and communication channels for one
// in-flight offer goroutine. Immutable fields are set at TriggerOffer time
// and never modified.
type offerState struct {
	// Immutable after creation
	OfferID      string
	UETR         string
	LoanAmount   string
	FeeBPS       string
	MaturityDays int
	ExpiresAt    time.Time
	ELOEntityID  string
	TriggeredAt  time.Time

	// Resolution channels — written at most once each; goroutine selects.
	AcceptCh chan acceptSignal
	RejectCh chan rejectSignal
	CancelCh chan struct{}

	// Outcome written by the goroutine; read by Query/status endpoints.
	outcomeMu  sync.RWMutex
	outcome    string
	resolvedAt time.Time
}

func newOfferState(req *TriggerOfferRequest, expiresAt time.Time) *offerState {
	return &offerState{
		OfferID:      req.OfferID,
		UETR:         req.UETR,
		LoanAmount:   req.LoanAmount,
		FeeBPS:       req.FeeBPS,
		MaturityDays: req.MaturityDays,
		ExpiresAt:    expiresAt,
		ELOEntityID:  req.ELOEntityID,
		TriggeredAt:  time.Now(),
		AcceptCh:     make(chan acceptSignal, 1),
		RejectCh:     make(chan rejectSignal, 1),
		CancelCh:     make(chan struct{}, 1),
		outcome:      OutcomePending,
	}
}

func (s *offerState) setOutcome(o string) {
	s.outcomeMu.Lock()
	defer s.outcomeMu.Unlock()
	s.outcome = o
	s.resolvedAt = time.Now()
}

func (s *offerState) getOutcome() (string, time.Time) {
	s.outcomeMu.RLock()
	defer s.outcomeMu.RUnlock()
	return s.outcome, s.resolvedAt
}

// ─────────────────────────────────────────────────────────────────────────────
// OfferRouterServer
// ─────────────────────────────────────────────────────────────────────────────

// resolvedEntry records the terminal outcome for a completed offer.
// Kept in the resolved map so QueryOffer can answer after the goroutine exits.
type resolvedEntry struct {
	outcome    string
	resolvedAt time.Time
}

// OfferRouterServer is the gRPC server that implements the C7 offer router.
// It owns the registry of in-flight offers and coordinates their lifecycle.
type OfferRouterServer struct {
	cfg        *Config
	ks         *KillSwitchReader
	metrics    *Metrics
	log        *slog.Logger
	shutdownCh chan struct{}

	// offers maps offer_id → *offerState for in-flight offers.
	// Protected by offersMu for registry mutations (add/delete).
	// Individual offerState channels are accessed without the lock on the hot path.
	offersMu sync.RWMutex
	offers   map[string]*offerState

	// resolved maps offer_id → resolvedEntry for completed offers.
	// Written by runOfferGoroutine before it exits; read by QueryOffer.
	resolvedMu sync.RWMutex
	resolved   map[string]resolvedEntry

	grpcServer *grpc.Server
}

// NewOfferRouterServer constructs and wires up the server.
func NewOfferRouterServer(cfg *Config, ks *KillSwitchReader, metrics *Metrics, log *slog.Logger) *OfferRouterServer {
	s := &OfferRouterServer{
		cfg:        cfg,
		ks:         ks,
		metrics:    metrics,
		log:        log,
		shutdownCh: make(chan struct{}),
		offers:     make(map[string]*offerState),
		resolved:   make(map[string]resolvedEntry),
	}

	s.grpcServer = grpc.NewServer(
		grpc.MaxRecvMsgSize(cfg.GRPCMaxMsgSize),
		grpc.MaxSendMsgSize(cfg.GRPCMaxMsgSize),
		grpc.UnaryInterceptor(s.metricsInterceptor()),
	)

	// Register service handler using raw byte codec (JSON-over-gRPC).
	// This matches the C5 Go consumer pattern — no protobuf stubs required.
	registerRawService(s.grpcServer, s)

	// Background goroutine: evict stale resolved entries to prevent unbounded growth.
	go s.evictResolvedLoop()

	return s
}

// evictResolvedLoop periodically removes entries older than cfg.ResolvedTTL
// from the resolved map. Runs until shutdownCh is closed.
func (s *OfferRouterServer) evictResolvedLoop() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()
	for {
		select {
		case <-s.shutdownCh:
			return
		case <-ticker.C:
			s.evictStaleResolved()
		}
	}
}

func (s *OfferRouterServer) evictStaleResolved() {
	cutoff := time.Now().Add(-s.cfg.ResolvedTTL)
	s.resolvedMu.Lock()
	defer s.resolvedMu.Unlock()
	evicted := 0
	for id, entry := range s.resolved {
		if entry.resolvedAt.Before(cutoff) {
			delete(s.resolved, id)
			evicted++
		}
	}
	if evicted > 0 {
		s.log.Info("evicted stale resolved entries", "count", evicted, "remaining", len(s.resolved))
	}
}

// Serve starts the gRPC listener and blocks until Shutdown is called.
func (s *OfferRouterServer) Serve(lis net.Listener) error {
	return s.grpcServer.Serve(lis)
}

// Shutdown gracefully stops the server and cancels all in-flight offer
// goroutines. Waits up to cfg.ShutdownTimeout for all goroutines to exit.
func (s *OfferRouterServer) Shutdown() {
	close(s.shutdownCh)
	s.grpcServer.GracefulStop()

	// Cancel all remaining in-flight offers
	s.offersMu.Lock()
	ids := make([]string, 0, len(s.offers))
	for id := range s.offers {
		ids = append(ids, id)
	}
	s.offersMu.Unlock()

	for _, id := range ids {
		s.offersMu.RLock()
		st, ok := s.offers[id]
		s.offersMu.RUnlock()
		if ok {
			select {
			case st.CancelCh <- struct{}{}:
			default:
			}
		}
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// gRPC handlers
// ─────────────────────────────────────────────────────────────────────────────

// handleTriggerOffer registers a new offer and spawns a goroutine to manage it.
func (s *OfferRouterServer) handleTriggerOffer(ctx context.Context, body []byte) ([]byte, error) {
	if ctx.Err() != nil {
		return errorResp("client context cancelled before processing")
	}
	var req TriggerOfferRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return errorResp(fmt.Sprintf("decode TriggerOfferRequest: %v", err))
	}
	if req.OfferID == "" {
		return errorResp("offer_id is required")
	}
	if req.UETR == "" {
		return errorResp("uetr is required")
	}

	// Kill switch gate — fail-closed
	if s.ks.IsKilled() {
		s.metrics.KillSwitchBlocks.Inc()
		s.log.Warn("TriggerOffer blocked by kill switch", "offer_id", req.OfferID, "uetr", req.UETR)
		return errorResp("kill switch active — no new offers permitted")
	}

	// Parse ExpiresAt — accept both RFC3339 (no fractions) and RFC3339Nano
	var expiresAt time.Time
	if req.ExpiresAt != "" {
		t, err := time.Parse(time.RFC3339Nano, req.ExpiresAt)
		if err != nil {
			t, err = time.Parse(time.RFC3339, req.ExpiresAt)
		}
		if err != nil {
			return errorResp(fmt.Sprintf("invalid expires_at %q (want RFC3339): %v", req.ExpiresAt, err))
		}
		expiresAt = t
	} else {
		expiresAt = time.Now().Add(time.Duration(s.cfg.DefaultExpirySeconds) * time.Second)
	}

	if time.Until(expiresAt) <= 0 {
		return errorResp("expires_at is already in the past")
	}

	st := newOfferState(&req, expiresAt)

	// B4-06: Concurrency gate and duplicate check are performed atomically under
	// a single write-lock acquisition so no other goroutine can slip in between
	// the len(s.offers) read and the s.offers[req.OfferID] write (TOCTOU fix).
	s.offersMu.Lock()
	if s.cfg.MaxConcurrentOffers > 0 && len(s.offers) >= s.cfg.MaxConcurrentOffers {
		s.offersMu.Unlock()
		return errorResp(fmt.Sprintf("max concurrent offers (%d) reached", s.cfg.MaxConcurrentOffers))
	}
	if _, exists := s.offers[req.OfferID]; exists {
		s.offersMu.Unlock()
		return errorResp(fmt.Sprintf("offer_id %q already registered", req.OfferID))
	}
	s.offers[req.OfferID] = st
	s.offersMu.Unlock()

	s.metrics.OffersTriggered.Inc()
	s.metrics.ActiveOffers.Inc()
	s.log.Info("TriggerOffer: goroutine starting",
		"offer_id", req.OfferID, "uetr", req.UETR,
		"expires_at", expiresAt.Format(time.RFC3339))

	go s.runOfferGoroutine(st)

	return okResp()
}

// handleAcceptOffer delivers an ELO acceptance signal to the offer goroutine.
func (s *OfferRouterServer) handleAcceptOffer(ctx context.Context, body []byte) ([]byte, error) {
	if ctx.Err() != nil {
		return errorResp("client context cancelled before processing")
	}
	var req AcceptOfferRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return errorResp(fmt.Sprintf("decode AcceptOfferRequest: %v", err))
	}
	if req.OfferID == "" {
		return errorResp("offer_id is required")
	}
	if req.ELOOperatorID == "" {
		return errorResp("elo_operator_id is required")
	}

	st := s.lookupOffer(req.OfferID)
	if st == nil {
		return errorResp(fmt.Sprintf("offer_id %q not found", req.OfferID))
	}

	outcome, _ := st.getOutcome()
	if outcome != OutcomePending {
		return errorResp(fmt.Sprintf("offer_id %q already resolved: %s", req.OfferID, outcome))
	}

	select {
	case st.AcceptCh <- acceptSignal{ELOOperatorID: req.ELOOperatorID}:
	default:
		return errorResp(fmt.Sprintf("offer_id %q already resolving", req.OfferID))
	}
	return okResp()
}

// handleRejectOffer delivers an ELO rejection signal to the offer goroutine.
func (s *OfferRouterServer) handleRejectOffer(ctx context.Context, body []byte) ([]byte, error) {
	if ctx.Err() != nil {
		return errorResp("client context cancelled before processing")
	}
	var req RejectOfferRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return errorResp(fmt.Sprintf("decode RejectOfferRequest: %v", err))
	}
	if req.OfferID == "" {
		return errorResp("offer_id is required")
	}
	if req.ELOOperatorID == "" {
		return errorResp("elo_operator_id is required")
	}
	if req.RejectionReason == "" {
		return errorResp("rejection_reason is required")
	}

	st := s.lookupOffer(req.OfferID)
	if st == nil {
		return errorResp(fmt.Sprintf("offer_id %q not found", req.OfferID))
	}

	outcome, _ := st.getOutcome()
	if outcome != OutcomePending {
		return errorResp(fmt.Sprintf("offer_id %q already resolved: %s", req.OfferID, outcome))
	}

	select {
	case st.RejectCh <- rejectSignal{
		ELOOperatorID:   req.ELOOperatorID,
		RejectionReason: req.RejectionReason,
	}:
	default:
		return errorResp(fmt.Sprintf("offer_id %q already resolving", req.OfferID))
	}
	return okResp()
}

// handleCancelOffer cancels an in-flight offer.
func (s *OfferRouterServer) handleCancelOffer(ctx context.Context, body []byte) ([]byte, error) {
	if ctx.Err() != nil {
		return errorResp("client context cancelled before processing")
	}
	var req CancelOfferRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return errorResp(fmt.Sprintf("decode CancelOfferRequest: %v", err))
	}
	if req.OfferID == "" {
		return errorResp("offer_id is required")
	}

	st := s.lookupOffer(req.OfferID)
	if st == nil {
		return errorResp(fmt.Sprintf("offer_id %q not found", req.OfferID))
	}

	select {
	case st.CancelCh <- struct{}{}:
	default:
		// Already resolving — idempotent cancel is fine
	}
	return okResp()
}

// handleQueryOffer returns the current outcome for an offer.
func (s *OfferRouterServer) handleQueryOffer(ctx context.Context, body []byte) ([]byte, error) {
	var req QueryOfferRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return errorResp(fmt.Sprintf("decode QueryOfferRequest: %v", err))
	}
	if req.OfferID == "" {
		return errorResp("offer_id is required")
	}

	// Check in-flight offers first
	st := s.lookupOffer(req.OfferID)
	if st != nil {
		outcome, resolvedAt := st.getOutcome()
		resp := queryResponse{Outcome: outcome}
		if !resolvedAt.IsZero() {
			resp.ResolvedAt = resolvedAt.Format(time.RFC3339Nano)
		}
		return marshal(resp)
	}

	// Check resolved (completed) offers
	s.resolvedMu.RLock()
	entry, ok := s.resolved[req.OfferID]
	s.resolvedMu.RUnlock()
	if ok {
		return marshal(queryResponse{
			Outcome:    entry.outcome,
			ResolvedAt: entry.resolvedAt.Format(time.RFC3339Nano),
		})
	}

	return marshal(queryResponse{
		Outcome: "UNKNOWN",
		Error:   fmt.Sprintf("offer_id %q not found", req.OfferID),
	})
}

// handleHealthCheck returns liveness / readiness info.
func (s *OfferRouterServer) handleHealthCheck(ctx context.Context, body []byte) ([]byte, error) {
	s.offersMu.RLock()
	n := len(s.offers)
	s.offersMu.RUnlock()

	return marshal(healthResponse{
		OK:           true,
		ActiveOffers: n,
		KillSwitch:   s.ks.IsKilled(),
	})
}

// ─────────────────────────────────────────────────────────────────────────────
// Core offer goroutine
// ─────────────────────────────────────────────────────────────────────────────

// runOfferGoroutine is the heart of the goroutine-per-offer model.
// It races expiry, acceptance, rejection, cancellation, and shutdown.
// Exactly one terminal branch executes; goroutine exits immediately after.
func (s *OfferRouterServer) runOfferGoroutine(st *offerState) {
	defer func() {
		// Record the terminal outcome in the resolved map before removing from
		// the in-flight registry, so QueryOffer can still answer after exit.
		outcome, resolvedAt := st.getOutcome()
		s.resolvedMu.Lock()
		s.resolved[st.OfferID] = resolvedEntry{outcome: outcome, resolvedAt: resolvedAt}
		s.resolvedMu.Unlock()

		s.offersMu.Lock()
		delete(s.offers, st.OfferID)
		s.offersMu.Unlock()
		s.metrics.ActiveOffers.Dec()
	}()

	d := time.Until(st.ExpiresAt)
	if d <= 0 {
		// Already expired before goroutine started
		st.setOutcome(OutcomeExpired)
		s.metrics.OffersExpired.Inc()
		s.metrics.OfferLatency.WithLabelValues(OutcomeExpired).Observe(
			time.Since(st.TriggeredAt).Seconds())
		s.log.Warn("offer expired before goroutine started",
			"offer_id", st.OfferID, "expires_at", st.ExpiresAt)
		return
	}

	timer := time.NewTimer(d)
	defer timer.Stop()

	select {
	case <-timer.C:
		st.setOutcome(OutcomeExpired)
		skew := time.Since(st.ExpiresAt).Seconds()
		s.metrics.OffersExpired.Inc()
		s.metrics.ExpiryLatency.Observe(skew)
		s.metrics.OfferLatency.WithLabelValues(OutcomeExpired).Observe(
			time.Since(st.TriggeredAt).Seconds())
		s.log.Info("offer expired",
			"offer_id", st.OfferID,
			"uetr", st.UETR,
			"skew_ms", int(skew*1000))

	case sig := <-st.AcceptCh:
		st.setOutcome(OutcomeAccepted)
		s.metrics.OffersAccepted.Inc()
		s.metrics.OfferLatency.WithLabelValues(OutcomeAccepted).Observe(
			time.Since(st.TriggeredAt).Seconds())
		s.log.Info("offer accepted",
			"offer_id", st.OfferID,
			"uetr", st.UETR,
			"operator", sig.ELOOperatorID)

	case sig := <-st.RejectCh:
		st.setOutcome(OutcomeRejected)
		s.metrics.OffersRejected.Inc()
		s.metrics.OfferLatency.WithLabelValues(OutcomeRejected).Observe(
			time.Since(st.TriggeredAt).Seconds())
		s.log.Info("offer rejected",
			"offer_id", st.OfferID,
			"uetr", st.UETR,
			"operator", sig.ELOOperatorID,
			"reason", sig.RejectionReason)

	case <-st.CancelCh:
		st.setOutcome(OutcomeCancelled)
		s.metrics.OffersCancelled.Inc()
		s.metrics.OfferLatency.WithLabelValues(OutcomeCancelled).Observe(
			time.Since(st.TriggeredAt).Seconds())
		s.log.Info("offer cancelled",
			"offer_id", st.OfferID,
			"uetr", st.UETR)

	case <-s.shutdownCh:
		st.setOutcome(OutcomeCancelled)
		s.metrics.OffersCancelled.Inc()
		s.metrics.OfferLatency.WithLabelValues(OutcomeCancelled).Observe(
			time.Since(st.TriggeredAt).Seconds())
		s.log.Warn("offer cancelled — service shutdown",
			"offer_id", st.OfferID,
			"uetr", st.UETR)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────────────────────────────────────

// lookupOffer returns the offerState for offer_id, or nil.
func (s *OfferRouterServer) lookupOffer(offerID string) *offerState {
	s.offersMu.RLock()
	defer s.offersMu.RUnlock()
	return s.offers[offerID]
}

// metricsInterceptor returns a gRPC UnaryInterceptor that records handler
// latency in the GRPCDuration histogram.
func (s *OfferRouterServer) metricsInterceptor() grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
		t0 := time.Now()
		resp, err := handler(ctx, req)
		s.metrics.GRPCDuration.WithLabelValues(info.FullMethod).Observe(
			time.Since(t0).Seconds())
		return resp, err
	}
}

// okResp returns a JSON-encoded genericResponse with accepted=true.
func okResp() ([]byte, error) {
	return marshal(genericResponse{Accepted: true})
}

// errorResp returns a JSON-encoded genericResponse with an error message.
func errorResp(msg string) ([]byte, error) {
	return marshal(genericResponse{Accepted: false, Error: msg})
}

// marshal encodes v to JSON, returning a gRPC Internal error on failure.
func marshal(v interface{}) ([]byte, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal response: %v", err)
	}
	return b, nil
}
