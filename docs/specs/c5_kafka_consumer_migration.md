# C5 Kafka Consumer Migration — Python → Go Service

**Status:** Implemented  
**Priority:** 3 (after C7 kill switch, C3 state machine)  
**Author:** LIP Engineering  
**Date:** 2026-04-02  
**Approved by:** Architecture review (see prior conversation context)

---

## 1. Context

The LIP C5 streaming component is the ingest layer for all payment events —
Step 0 of Algorithm 1. It consumes from `lip.payment.events` (24 partitions),
normalizes raw ISO 20022 / FedNow / RTP / SEPA messages to a canonical
`NormalizedEvent` struct, and routes to downstream components (C1, C2, C6).

The Python implementation (`kafka_worker.py`) wraps `confluent-kafka-python`,
which is a thin layer over C `librdkafka`. The raw Kafka I/O is already native
speed. The migration to Go targets the **deserialization and routing hot path**
inside the Python asyncio event loop, which becomes the bottleneck at sustained
10K+ TPS:

- Python asyncio next-tick delivery latency: ~50–200 μs
- Python JSON decoder: ~5 μs/message (vs <1 μs in Go)
- GIL contention in multi-worker deployments limits concurrency
- Python GC pauses (refcount + cyclic GC) create tail latency spikes

Go's goroutine model and native memory management eliminate these bottlenecks
without sacrificing the existing ML component boundaries (C1/C2/C4/C6 remain
Python — see approved migration plan).

---

## 2. Pre-Migration Baseline

### Methodology

Load test harness: `lip/c5_streaming/load_test/load_test_harness.py`  
Scope: `EventNormalizer` hot path only (deserialization + field normalization)  
Environment: Ubuntu 22.04, Python 3.11, CPython, single-process

**Note:** This measures the normalization hot path only. Full end-to-end
latency (Kafka I/O + ML inference + Redis + produce) should be measured in
canary with the live pipeline.

### Python Consumer Baseline — 10K TPS, 10 seconds

| Metric | Python Baseline |
|--------|----------------|
| Target TPS | 10,000 |
| Actual TPS | 10,000 |
| Total messages | 100,001 |
| Duration | 10.0 s |
| Error rate | 0.00% |
| **p50 latency** | **0.005 ms** |
| **p95 latency** | **0.007 ms** |
| **p99 latency** | **0.010 ms** |
| Max latency | 0.083 ms |
| Min latency | 0.003 ms |

Full results: [`docs/benchmark-results/c5_baseline_10ktps.json`](../benchmark-results/c5_baseline_10ktps.json)

### Known Python Bottlenecks

1. **asyncio event loop:** Next-tick delivery latency ~50–200 μs under high TPS
2. **Python JSON decoder:** ~5 μs per message (Go is 10–50× faster)
3. **GIL contention:** Multi-worker deployments cannot use true CPU parallelism
4. **GC pauses:** Python cyclic GC creates unpredictable tail latency at p99+
5. **Avro not yet integrated:** Production uses JSON; Avro would reduce message size ~40%

### Go Consumer Target SLOs

| Metric | Target |
|--------|--------|
| Ingestion latency p50 | < 0.5 ms |
| Ingestion latency p99 | < 2 ms (spec budget) |
| Max throughput (single instance) | ≥ 25K TPS |
| Error rate | < 0.01% |
| GC pauses | < 10 ms (Go GC is stop-the-world but sub-millisecond) |

---

## 3. Architecture

### Component Roles (unchanged)

```
Bank Connectors
      │
      ▼
lip.payment.events (Kafka, 24 partitions)
      │
      ▼
┌─────────────────────────────────────┐
│  C5 Go Consumer (NEW HOT PATH)      │
│  • Avro / JSON deserialization      │
│  • EventNormalizer (Go port)        │
│  • Redis corridor lookup            │
│  • gRPC fan-out: C1, C2, C6        │
└─────────────────────────────────────┘
      │
      ▼
lip.failure.predictions (Kafka, 12 partitions)
```

### File Structure

```
lip/c5_streaming/
├── go_consumer/              ← NEW: Go microservice
│   ├── go.mod
│   ├── go.sum
│   ├── main.go               ← Entry point, signal handling
│   ├── config.go             ← Env-driven config (mirrors Python KafkaConfig)
│   ├── consumer.go           ← Kafka consumer/producer loop (exactly-once)
│   ├── normalizer.go         ← EventNormalizer Go port (field-exact Python parity)
│   ├── grpc_client.go        ← gRPC fan-out to C1/C2/C6 Python services
│   ├── metrics.go            ← Prometheus /metrics endpoint
│   ├── normalizer_test.go    ← Unit tests (mirrors test_c5_streaming.py)
│   └── config_test.go        ← Config unit tests
├── schemas/                  ← NEW: Avro schema definitions
│   ├── payment_event.avsc    ← Inbound event schema
│   └── normalized_event.avsc ← Output canonical schema
├── load_test/                ← NEW: Load test harness
│   └── load_test_harness.py  ← 10K TPS synthetic replay
├── kafka_worker.py           ← EXISTING Python consumer (unchanged, fallback)
├── event_normalizer.py       ← EXISTING Python normalizer (source of truth)
└── kafka_config.py           ← EXISTING Python config (mirrors Go config.go)
```

---

## 4. Design Decisions

### 4.1 Goroutine Model

The Go consumer uses a **shared message channel** pattern:
- Main goroutine: polls Kafka, pushes to `msgCh` (buffered, size = `NumWorkers × 2`)
- N worker goroutines: drain `msgCh`, each running `normalize → gRPC fan-out → produce`

This avoids per-partition goroutine overhead and provides natural backpressure.
Default `NUM_WORKERS=8` matches the Flink `PAYMENT_SCORING` job parallelism.

### 4.2 Exactly-Once Semantics

Mirrors the Python implementation:
- **Producer:** `enable.idempotence=true`, `acks=all`
- **Consumer:** `enable.auto.commit=false`, `isolation.level=read_committed`
- **Offset commit:** `StoreMessage()` (async) called only after successful produce

### 4.3 Avro + JSON Compatibility

The Go normalizer supports both:
- **JSON** (legacy, current production): full backward compatibility
- **Avro** (future): enabled when `SCHEMA_REGISTRY_URL` is set

This allows a rolling migration from JSON to Avro without a flag day.
Avro schema files: `schemas/payment_event.avsc` and `schemas/normalized_event.avsc`.

### 4.4 gRPC Fan-Out

C1, C2, C6 remain Python services. The Go consumer calls them via gRPC:
- C1 and C6 are called **concurrently** (both goroutines launched simultaneously)
- C2 is called **sequentially** after C1 (requires C1's `failure_probability`)
- Total gRPC budget: 80 ms (`GRPC_TIMEOUT_MS=80`, within 94 ms SLO)

**Fail-closed defaults:**
- C1 failure → `failure_probability = 1.0` (route to manual review)
- C6 failure → AML block flag appended (no offer)
- C2 failure → `fee_bps = nil` (no offer issued)

### 4.5 Fee Floor Enforcement

The fee floor of **300 bps** (QUANT canonical constant) is enforced in the
Go consumer's `FanOut()` method — an offer is only issued if `fee_bps >= 300`.

### 4.6 Memory Ordering (Kill Switch)

The kill switch flag (checked before issuing any offer) is read via Redis
key `lip:kill_switch`. Redis reads are sequential and strongly consistent
within a single connection — no additional memory ordering guarantees required.

---

## 5. Configuration

All settings are environment variables. The Go consumer mirrors the Python
`KafkaConfig` field names where possible.

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Broker list |
| `KAFKA_GROUP_ID` | `lip-c5-go-worker` | Consumer group (distinct from Python group) |
| `KAFKA_INPUT_TOPIC` | `lip.payment.events` | Input topic |
| `KAFKA_OUTPUT_TOPIC` | `lip.failure.predictions` | Output topic |
| `KAFKA_DLQ_TOPIC` | `lip.dead.letter` | Dead-letter topic |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT` | SSL/SASL/PLAINTEXT |
| `SCHEMA_REGISTRY_URL` | `` (empty) | Avro schema registry URL (empty = JSON mode) |
| `REDIS_ADDR` | `redis:6379` | Redis address |
| `REDIS_TLS_ENABLE` | `false` | TLS for Redis |
| `GRPC_C1_ADDR` | `c1-service:50051` | C1 gRPC endpoint |
| `GRPC_C2_ADDR` | `c2-service:50052` | C2 gRPC endpoint |
| `GRPC_C6_ADDR` | `c6-service:50056` | C6 gRPC endpoint |
| `GRPC_TIMEOUT_MS` | `80` | gRPC call timeout (ms) |
| `NUM_WORKERS` | `8` | Consumer goroutines |
| `DRY_RUN` | `false` | Consume without producing |
| `METRICS_ADDR` | `:9090` | Prometheus metrics address |
| `LOG_LEVEL` | `info` | debug/info/warn/error |

---

## 6. A/B Deployment (Canary)

Both the Python and Go consumers can run simultaneously using **different
consumer group IDs**:

```yaml
# Python (existing, stable)
KAFKA_GROUP_ID: lip-c5-worker
# routes 100% of partitions initially

# Go (canary, new)
KAFKA_GROUP_ID: lip-c5-go-worker
# receives 0% partitions initially
# Increase by reassigning partitions via kafka-consumer-groups.sh
```

Promotion path:
1. Deploy Go consumer with group `lip-c5-go-worker`, `NUM_WORKERS=1`
2. Assign 2/24 partitions to Go group, monitor metrics for 30 min
3. Ramp: 6/24 → 12/24 → 24/24 over 3 hours if p99 < 2 ms
4. Retire Python group after 48 h of stable Go-only operation

Rollback: Reassign all 24 partitions back to `lip-c5-worker`.
Python consumer continues running with zero-latency partition reassignment.

---

## 7. Testing

### Go Unit Tests (no infrastructure required)

```bash
cd lip/c5_streaming/go_consumer
go test -v ./...
```

Tests cover:
- `normalizer_test.go`: SWIFT/FedNow/RTP/SEPA normalization, EPG-19 compliance
  hold code pass-through, EPG-28 debtor_account preservation, GAP-17 USD amount
- `config_test.go`: Config loading, SSL config, exactly-once config validation

### Python Integration Tests (existing, unchanged)

```bash
PYTHONPATH=. python -m pytest lip/tests/test_c5_streaming.py lip/tests/test_c5_kafka_worker.py -v
```

### Load Test Harness

```bash
# Python baseline (normalizer-only)
PYTHONPATH=. python lip/c5_streaming/load_test/load_test_harness.py \
    --tps 10000 --duration 60 --output /tmp/c5_baseline.json

# Go canary comparison (requires canary deployment + live Kafka)
# Compare /tmp/c5_baseline.json against Go consumer Prometheus metrics
```

---

## 8. CI/CD

### Go Build (`.github/workflows/ci.yml`)

Added `go-build` job:
```yaml
go-build:
  name: Go Build & Test (C5)
  runs-on: ubuntu-latest
  steps:
    - go test -v ./lip/c5_streaming/go_consumer/
    - go build ./lip/c5_streaming/go_consumer/
```

### Docker (`.github/workflows/docker-build.yml`)

Added `c5-go` matrix entry:
```yaml
- component: c5-go
  dockerfile: lip/infrastructure/docker/Dockerfile.c5-go
```

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| gRPC latency adds to budget | Medium | High | 80ms timeout < 94ms SLO; go routine fan-out for C1+C6 parallel |
| Go consumer semantic divergence | Low | High | Field-level parity tests in normalizer_test.go match Python test suite |
| Offset replay on restart | Low | Medium | Exactly-once semantics (idempotent producer + read_committed) |
| Schema registry unavailable | Low | Low | Falls back to JSON deserialization automatically |
| Go GC pause > 2ms SLO | Low | Medium | Go GC is sub-ms; use `GOGC=200` if needed to reduce frequency |

---

## 10. Rollback

**Fast rollback (< 30 seconds):**
1. Kafka partition reassignment: move all 24 partitions to `lip-c5-worker` group
2. Python consumer automatically picks up partitions on rebalance
3. Go consumer drains `msgCh` and exits gracefully on SIGTERM

**Container rollback:**
```bash
kubectl rollout undo deployment/c5-go-consumer
```

**No data loss:** The Python consumer resumes from last committed offset.
Any messages processed by Go but not committed (in-flight at rollback) will
be reprocessed by Python with exactly-once semantics on the producer side.

---

## 11. Lessons from Python Implementation

1. **librdkafka is not the bottleneck.** `confluent-kafka-python` wraps librdkafka
   which is already C-speed. The bottleneck is the Python deserializer + asyncio.
2. **JSON over Avro adds ~40% message size.** Avro should be the default for
   production. The Go consumer supports both.
3. **Manual offset commits are non-negotiable.** Auto-commit leads to message
   loss on restart. Both implementations use `StoreMessage()` (Go) / manual
   commit (Python).
4. **Dead-letter routing must be synchronous.** Async DLQ produce (no
   delivery confirmation) can silently drop messages. Both implementations
   wait for produce confirmation before moving on.
5. **Proprietary code normalization is a maintenance burden.** The
   `_PROPRIETARY_TO_ISO20022` map is duplicated in Go. Any new FedNow/RTP
   codes must be added to both. Consider externalizing to Redis or a shared
   config service (future work).
