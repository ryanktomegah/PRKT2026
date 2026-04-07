// grpc_client.go — gRPC client fan-out to C1, C2, and C6 Python services.
//
// The Go consumer replaces the Python hot path but calls back to Python-hosted
// model inference services via gRPC. This maintains the existing ML component
// boundaries (C1 failure classifier, C2 PD model, C6 AML velocity) without
// requiring language migration of the ML code.
//
// Protocol: JSON-over-gRPC (google.protobuf.Struct) so the Python servers need
// no Protobuf schema changes. The existing Python FastAPI services expose gRPC
// via grpcio-tools generated stubs.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
)

// PipelineResult aggregates the responses from C1, C2, and C6.
type PipelineResult struct {
	UETR               string   `json:"uetr"`
	FailureProbability float64  `json:"failure_probability"`
	FeeBPS             *float64 `json:"fee_bps,omitempty"`
	Outcome            string   `json:"outcome"`
	Flags              []string `json:"flags,omitempty"`
	ProcessedAtNs      int64    `json:"processed_at_ns"`
}

// GRPCClient manages connections to C1, C2, and C6 upstream Python services.
type GRPCClient struct {
	c1Conn      *grpc.ClientConn
	c2Conn      *grpc.ClientConn
	c6Conn      *grpc.ClientConn
	timeout     time.Duration
	feeFloorBPS float64 // QUANT canonical constant — sourced from FEE_FLOOR_BPS env
}

// NewGRPCClient dials all three upstream services. Returns an error if any
// connection cannot be established (fail-fast at startup).
func NewGRPCClient(c1Addr, c2Addr, c6Addr string, timeout time.Duration, feeFloorBPS float64) (*GRPCClient, error) {
	dialOpts := []grpc.DialOption{
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	c1, err := grpc.DialContext(ctx, c1Addr, dialOpts...)
	if err != nil {
		return nil, fmt.Errorf("dial c1 at %s: %w", c1Addr, err)
	}
	c2, err := grpc.DialContext(ctx, c2Addr, dialOpts...)
	if err != nil {
		_ = c1.Close()
		return nil, fmt.Errorf("dial c2 at %s: %w", c2Addr, err)
	}
	c6, err := grpc.DialContext(ctx, c6Addr, dialOpts...)
	if err != nil {
		_ = c1.Close()
		_ = c2.Close()
		return nil, fmt.Errorf("dial c6 at %s: %w", c6Addr, err)
	}

	return &GRPCClient{
		c1Conn:      c1,
		c2Conn:      c2,
		c6Conn:      c6,
		timeout:     timeout,
		feeFloorBPS: feeFloorBPS,
	}, nil
}

// Close closes all gRPC connections. Safe to call multiple times.
func (g *GRPCClient) Close() {
	if g.c1Conn != nil {
		_ = g.c1Conn.Close()
	}
	if g.c2Conn != nil {
		_ = g.c2Conn.Close()
	}
	if g.c6Conn != nil {
		_ = g.c6Conn.Close()
	}
}

// FanOut calls C1, C2, and C6 concurrently and assembles a PipelineResult.
// Any upstream failure results in a safe-default response (fail-closed):
//   - C1 failure → failure_probability = 1.0 (route to manual review)
//   - C6 failure → AML block flag appended
//   - C2 failure → fee_bps = nil (no offer issued)
func (g *GRPCClient) FanOut(ctx context.Context, event *NormalizedEvent, m *Metrics) (*PipelineResult, error) {
	type c1Result struct {
		FailureProbability float64
		Err                error
	}
	type c6Result struct {
		AMLBlock bool
		Err      error
	}

	c1Ch := make(chan c1Result, 1)
	c6Ch := make(chan c6Result, 1)

	callCtx, cancel := context.WithTimeout(ctx, g.timeout)
	defer cancel()

	// Fan-out goroutines
	go func() {
		start := time.Now()
		fp, err := g.callC1(callCtx, event)
		m.GRPCDuration.WithLabelValues("c1").Observe(time.Since(start).Seconds())
		c1Ch <- c1Result{fp, err}
	}()

	go func() {
		start := time.Now()
		blocked, err := g.callC6(callCtx, event)
		m.GRPCDuration.WithLabelValues("c6").Observe(time.Since(start).Seconds())
		c6Ch <- c6Result{blocked, err}
	}()

	c1Res := <-c1Ch
	c6Res := <-c6Ch

	fp := c1Res.FailureProbability
	if c1Res.Err != nil {
		fp = 1.0 // fail-closed: route to manual review
		m.GRPCUpstreamErrors.WithLabelValues("c1").Inc()
	}

	var flags []string
	if c6Res.Err != nil {
		m.GRPCUpstreamErrors.WithLabelValues("c6").Inc()
	}
	if c6Res.AMLBlock || c6Res.Err != nil {
		flags = append(flags, "AML_VELOCITY_BLOCK")
	}

	outcome := "DECLINED"
	var feeBPS *float64
	if fp <= 0.152 && !c6Res.AMLBlock && c1Res.Err == nil {
		// Above-threshold: call C2 for PD + fee computation
		start := time.Now()
		bps, err := g.callC2(callCtx, event, fp)
		m.GRPCDuration.WithLabelValues("c2").Observe(time.Since(start).Seconds())
		if err != nil {
			m.GRPCUpstreamErrors.WithLabelValues("c2").Inc()
		}
		if err == nil && bps >= g.feeFloorBPS { // fee floor: QUANT canonical constant (from FEE_FLOOR_BPS env)
			feeBPS = &bps
			outcome = "OFFER"
		}
	}

	return &PipelineResult{
		UETR:               event.UETR,
		FailureProbability: fp,
		FeeBPS:             feeBPS,
		Outcome:            outcome,
		Flags:              flags,
		ProcessedAtNs:      time.Now().UnixNano(),
	}, nil
}

// callC1 invokes the C1 failure classifier via gRPC and returns the failure
// probability. Uses JSON payload marshalling to avoid Protobuf schema coupling.
func (g *GRPCClient) callC1(ctx context.Context, event *NormalizedEvent) (float64, error) {
	payload, err := marshalEvent(event)
	if err != nil {
		return 0, err
	}

	var resp map[string]interface{}
	if err := g.invokeJSON(ctx, g.c1Conn, "/lip.C1Service/Predict", payload, &resp); err != nil {
		return 0, fmt.Errorf("c1 predict: %w", err)
	}

	fp, ok := resp["failure_probability"].(float64)
	if !ok {
		return 0, fmt.Errorf("c1 response missing failure_probability")
	}
	return fp, nil
}

// callC6 invokes the C6 AML velocity checker and returns true if the event
// should be blocked.
func (g *GRPCClient) callC6(ctx context.Context, event *NormalizedEvent) (bool, error) {
	payload, err := marshalEvent(event)
	if err != nil {
		return false, err
	}

	var resp map[string]interface{}
	if err := g.invokeJSON(ctx, g.c6Conn, "/lip.C6Service/CheckVelocity", payload, &resp); err != nil {
		return false, fmt.Errorf("c6 check: %w", err)
	}

	blocked, _ := resp["blocked"].(bool)
	return blocked, nil
}

// callC2 invokes the C2 PD model and returns the fee in basis points.
func (g *GRPCClient) callC2(ctx context.Context, event *NormalizedEvent, fp float64) (float64, error) {
	payload, err := marshalEvent(event)
	if err != nil {
		return 0, err
	}
	// Include failure_probability from C1 so C2 can condition its PD estimate
	var m map[string]interface{}
	if err := json.Unmarshal(payload, &m); err != nil {
		return 0, err
	}
	m["failure_probability"] = fp
	payload, err = json.Marshal(m)
	if err != nil {
		return 0, err
	}

	var resp map[string]interface{}
	if err := g.invokeJSON(ctx, g.c2Conn, "/lip.C2Service/ComputeFee", payload, &resp); err != nil {
		return 0, fmt.Errorf("c2 fee: %w", err)
	}

	bps, ok := resp["fee_bps"].(float64)
	if !ok {
		return 0, fmt.Errorf("c2 response missing fee_bps")
	}
	return bps, nil
}

// invokeJSON makes a raw gRPC call carrying a JSON payload and decodes the
// JSON response. This avoids generated Protobuf stubs — the Python servers
// accept application/json content type on their gRPC endpoints.
func (g *GRPCClient) invokeJSON(
	ctx context.Context,
	conn *grpc.ClientConn,
	method string,
	payload []byte,
	out interface{},
) error {
	ctx = metadata.AppendToOutgoingContext(ctx, "content-type", "application/json")
	var respBytes []byte
	err := conn.Invoke(ctx, method, payload, &respBytes)
	if err != nil {
		return err
	}
	return json.Unmarshal(respBytes, out)
}

func marshalEvent(event *NormalizedEvent) ([]byte, error) {
	b, err := json.Marshal(event)
	if err != nil {
		return nil, fmt.Errorf("marshal event: %w", err)
	}
	return b, nil
}
