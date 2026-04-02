# C7 Offer Routing Migration — Python → Go Service

**Status:** In Progress  
**Priority:** 6  
**Authors:** FORGE + NOVA + ARIA  
**Sign-off required:** QUANT (fee math), CIPHER (AML integration), REX (compliance posture)

---

## 1. Background

C7 is the bank-side execution agent (ELO). Its hot path — `agent.py` and
`offer_delivery.py` — manages in-flight loan offers with per-offer expiry
timers, concurrent acceptance/rejection, and ELO treasury callbacks. Python's
GIL limits true concurrency for offer expiry races.

This migration ports the hot path to a Go microservice
(`lip/c7_execution_agent/go_offer_router/`) to unlock:

- **Goroutine-per-offer**: each in-flight offer managed as an independent
  `select` race between acceptance, rejection, cancellation, and expiry
  timer channels — no shared-lock contention.
- **Deterministic expiry**: `time.AfterFunc` / `time.Timer` per goroutine;
  expiry fires exactly once regardless of sweep interval.
- **Real-time throughput scaling**: Go scheduler handles thousands of
  concurrent in-flight offers without GIL serialisation.

Human override flow and non-hot-path orchestration remain in Python.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│  Python ExecutionAgent (agent.py)                   │
│                                                     │
│  process_payment()                                  │
│    │                                                │
│    ├── [canary=off]  offer_delivery.py (Python)     │
│    │                                                │
│    └── [canary=on]   go_router_client.py            │
│                         │ gRPC (JSON-over-gRPC)     │
│                         ▼                           │
│              Go Offer Router Service                │
│              lip/c7_execution_agent/                │
│              go_offer_router/                       │
│                                                     │
│              ┌──────────────────┐                  │
│              │  gRPC Server     │                  │
│              │  :50057          │                  │
│              │                  │                  │
│              │  TriggerOffer ──►│──► goroutine     │
│              │  AcceptOffer  ──►│      │           │
│              │  RejectOffer  ──►│      ├─ timer    │
│              │  CancelOffer  ──►│      │   expiry  │
│              │  QueryOffer   ──►│      │           │
│              │  ELOResponse  ──►│◄─────┘           │
│              └──────────────────┘                  │
│                                                     │
│  ── Kill switch gate ──────────────────────────────  │
│  Reads /dev/shm/lip_kill_switch (Rust AtomicBool)  │
│  before admitting any new offer goroutine.          │
│                                                     │
│  ── Metrics (:9091) ───────────────────────────────  │
│  c7_go_offers_triggered_total                      │
│  c7_go_offers_accepted_total                       │
│  c7_go_offers_rejected_total                       │
│  c7_go_offers_expired_total                        │
│  c7_go_offers_cancelled_total                      │
│  c7_go_offer_latency_seconds (histogram)           │
│  c7_go_expiry_latency_seconds (histogram)          │
│  c7_go_active_offers (gauge)                       │
└─────────────────────────────────────────────────────┘
```

---

## 3. Concurrency Model

Each call to `TriggerOffer` spawns a **dedicated goroutine** that manages
the offer lifecycle via channel-select:

```go
func (s *OfferRouterServer) runOfferGoroutine(state *OfferState) {
    timer := time.NewTimer(time.Until(state.ExpiresAt))
    defer timer.Stop()
    for {
        select {
        case <-timer.C:           // expiry wins
            s.handleExpiry(state)
            return
        case req := <-state.AcceptCh:   // ELO accepted
            s.handleAccept(state, req)
            return
        case req := <-state.RejectCh:   // ELO rejected
            s.handleReject(state, req)
            return
        case <-state.CancelCh:          // upstream cancel
            s.handleCancel(state)
            return
        case <-s.shutdownCh:            // service shutdown
            s.handleCancel(state)
            return
        }
    }
}
```

This guarantees:
- Exactly one terminal transition per offer (no double-fire).
- Expiry fires at wall-clock `ExpiresAt`, not at the next sweep interval.
- Goroutine exits immediately on resolution — no leaked goroutines.

---

## 4. gRPC Interface (JSON-over-gRPC)

Following the C5 precedent, the Go service uses **JSON-over-gRPC** (raw
byte frames, no generated Protobuf stubs) so the Python caller can use
standard `grpc.Channel.unary_unary` without proto code generation in CI.

### Methods

| Method | Direction | Description |
|--------|-----------|-------------|
| `/lip.C7OfferRouter/TriggerOffer` | Python → Go | Register new offer; spawns goroutine |
| `/lip.C7OfferRouter/AcceptOffer` | Python → Go | ELO treasury acceptance |
| `/lip.C7OfferRouter/RejectOffer` | Python → Go | ELO treasury rejection |
| `/lip.C7OfferRouter/CancelOffer` | Python → Go | Upstream cancel (e.g., kill switch) |
| `/lip.C7OfferRouter/QueryOffer` | Python → Go | Query current outcome |
| `/lip.C7OfferRouter/HealthCheck` | Python → Go | Liveness / readiness |

### TriggerOffer request
```json
{
  "offer_id":    "uuid",
  "uetr":        "uuid",
  "loan_amount": "1000000.00",
  "fee_bps":     "300",
  "maturity_days": 7,
  "expires_at":  "2026-04-02T19:00:00Z",
  "elo_entity_id": "DEUTDEDBXXX"
}
```

### TriggerOffer response
```json
{ "accepted": true, "error": "" }
```

### QueryOffer response
```json
{
  "outcome": "PENDING|ACCEPTED|REJECTED|EXPIRED|CANCELLED",
  "resolved_at": "2026-04-02T18:35:12Z"
}
```

---

## 5. Kill Switch Integration

The Go service reads the Rust kill switch shared memory segment
(`/dev/shm/lip_kill_switch`) at byte offset 0. If the kill flag byte is
`0x01`, `TriggerOffer` returns an error immediately — no goroutine is
spawned. This is the same fail-closed posture as the Rust binary.

Fallback: if `/dev/shm/lip_kill_switch` does not exist or cannot be read,
the Go service treats the kill switch as **active** (fail-closed).

---

## 6. Python Integration & Canary Rollout

### go_router_client.py

```python
class GoOfferRouterClient:
    def trigger_offer(self, offer: dict) -> dict: ...
    def accept_offer(self, offer_id: str, elo_operator_id: str) -> dict: ...
    def reject_offer(self, offer_id: str, elo_operator_id: str, reason: str) -> dict: ...
    def cancel_offer(self, offer_id: str) -> dict: ...
    def query_offer(self, offer_id: str) -> dict: ...
    def health_check(self) -> dict: ...
```

### Canary gate in agent.py

Controlled by `LIP_C7_GO_ROUTER_CANARY_PCT` (0–100). When set, a
deterministic hash of the UETR mod 100 determines which path executes:

```python
_CANARY_PCT = int(os.environ.get("LIP_C7_GO_ROUTER_CANARY_PCT", "0"))

def _use_go_router(uetr: str) -> bool:
    if _CANARY_PCT <= 0:
        return False
    h = int(hashlib.sha256(uetr.encode()).hexdigest(), 16)
    return (h % 100) < _CANARY_PCT
```

Python fallback (`OfferDeliveryService`) remains live at all times. If the
Go service returns a non-OK status the agent falls back to Python and
increments `c7_go_router_fallback_total`.

---

## 7. Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `c7_go_offers_triggered_total` | Counter | — | New offers registered |
| `c7_go_offers_accepted_total` | Counter | — | ELO acceptances |
| `c7_go_offers_rejected_total` | Counter | — | ELO rejections |
| `c7_go_offers_expired_total` | Counter | — | Timer-fired expirations |
| `c7_go_offers_cancelled_total` | Counter | — | Upstream cancellations |
| `c7_go_active_offers` | Gauge | — | Current in-flight goroutines |
| `c7_go_offer_latency_seconds` | Histogram | `outcome` | Trigger→resolution wall time |
| `c7_go_expiry_latency_seconds` | Histogram | — | `ExpiresAt`→goroutine-exit skew |
| `c7_go_kill_switch_blocks_total` | Counter | — | Offers blocked by kill switch |
| `c7_go_grpc_duration_seconds` | Histogram | `method` | gRPC handler latency |

---

## 8. Rollback / Dual-Pipeline Plan

1. **Phase 0 (now):** canary at 0% — Go service runs but receives no
   traffic. Python path active for all payments.
2. **Phase 1:** canary at 10% — monitor offer latency and expiry accuracy.
3. **Phase 2:** canary at 50% — compare accepted/rejected/expired rates
   between Go and Python paths.
4. **Phase 3:** canary at 100% — Python `OfferDeliveryService` kept as
   dormant fallback.
5. **Phase 4:** remove Python hot path; Python retains human override.

Rollback: set `LIP_C7_GO_ROUTER_CANARY_PCT=0`. Python path resumes
immediately without restart.

---

## 9. Service Restart & Offer Rebroadcast

On Go service restart, all in-flight goroutines terminate. The Python
orchestrator detects gRPC connection failures and falls back to the Python
`OfferDeliveryService`, which re-delivers outstanding offers. The C3
repayment loop (via `on_accept` callback) is idempotent per UETR — safe
to re-deliver.

---

## 10. CI/CD

A new `go-build-c7` job in `.github/workflows/ci.yml`:

```yaml
go-build-c7:
  name: Go Build & Test (C7 offer router)
  steps:
    - go build ./...
    - go test -v -count=1 -run "TestOffer|TestConfig|TestKillSwitch|TestExpiry|TestMetrics" ./...
```

No CGO required (no librdkafka dependency). Pure Go + gRPC.

---

## 11. Definition of Done

- [x] Spec committed
- [x] Go service with unit tests passing in CI (35 tests, `go test ./...`)
- [x] Python gRPC client bridge with canary routing (`go_router_client.py`)
- [x] Python tests for canary routing and fallback (`test_c7_go_router.py`, 20 tests)
- [x] CI `go-build-c7` job green (`.github/workflows/ci.yml`)
- [x] `c7_go_router_fallback_total` Prometheus counter incremented on Go service error
- [ ] Offer success/expiry metrics validated in smoke test (Phase 1 canary ramp)
- [ ] QUANT, CIPHER, REX sign-off on fee-path and AML posture
