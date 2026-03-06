# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 5 — PLATFORM INFRASTRUCTURE & ORCHESTRATION
## Build Specification v1.0 — Part 1 (Sections 1–9)
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0 — Part 1 of 2
**Lead:** FORGE — DevOps & Platform Engineering Lead
**Support:** NOVA (Kafka/Flink topology), ARIA (GPU sizing),
             REX (DORA resilience), CIPHER (network segmentation)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

**Part 1 covers:** Sections 1–9
Infrastructure Topology, Kubernetes, Kafka, Flink, Redis, GPU, CI/CD, Observability
**Part 2 covers:** Sections 10–16
Load Testing, Chaos Engineering, Security Hardening, SOC2 Roadmap,
Known Limitations, Validation Requirements, Audit Gate 2.4

---

## TABLE OF CONTENTS (PART 1)

1.  Purpose & Scope
2.  Infrastructure Topology
    2.1 Three-Zone Deployment Model
    2.2 Network Segmentation
3.  Kubernetes Cluster Design
    3.1 Node Pools (Zone A + B)
    3.2 Namespace Isolation
    3.3 Pod Anti-Affinity
    3.4 Resource Requests and Limits
    3.5 C7 Scaling Policy (Fixed — Non-Negotiable)
4.  Apache Kafka
    4.1 Deployment Model
    4.2 Cluster Configuration
    4.3 Topic Inventory and Configuration
    4.4 Producer Configuration
    4.5 Consumer Configuration
5.  Apache Flink
    5.1 Flink Version and Deployment
    5.2 Flink Cluster Configuration
    5.3 Flink HA Design
6.  Redis Cluster
    6.1 MIPLO Redis (C3 + C6 state)
    6.2 ELO Redis (C7 state — bank-managed)
    6.3 Redis Key Expiry Monitoring
7.  GPU Infrastructure (C1)
    7.1 C1 GPU Requirements
    7.2 GPU Node Scheduling
8.  CI/CD Pipeline
    8.1 Pipeline Structure
    8.2 Image Security Requirements
    8.3 Infrastructure as Code
9.  Observability Stack
    9.1 Metrics
    9.2 Logging
    9.3 Alerting

---

## 1. PURPOSE & SCOPE

C5 is not a runtime component that processes payments. It is the infrastructure
layer that every other component runs on. Its job is to make every latency target,
resilience guarantee, and security boundary specified in C1–C7 actually hold under
production load.

Every decision in this spec is traceable to a constraint established in a component
spec. C5 does not introduce new requirements — it operationalizes existing ones.
Where a component spec said "Redis Sorted Set" or "Kafka topic with
replication.factor=3" or "Kubernetes HPA," C5 defines the authoritative
configuration that makes those statements true.

**FORGE Self-Critique Before Delivery:**
The primary risk in infrastructure specs is SLA claims without load test evidence.
This spec does not make a single latency or resilience claim that is not accompanied
by a specific test that must pass before the claim is considered valid. p50 <100ms is
a load-tested fact or it is not in this document. p99 <200ms is a chaos-tested result
or it is not in this document. Every number here is a target until the test in
Section 15 (Part 2) runs and passes. Until then it is a hypothesis.

---

## 2. INFRASTRUCTURE TOPOLOGY

### 2.1 Three-Zone Deployment Model

```
ZONE A — MLO (Machine Learning Operator) — Bridgepoint-managed
  Components : C1 (Failure Prediction), C2 (PD Model)
  Runtime    : Kubernetes namespace: lip-ml
  Compute    : GPU node pool (C1) + CPU node pool (C2)
  Network    : Produces to Kafka only — no direct connection to ELO (Zone C)

ZONE B — MIPLO (Monitoring, Intelligence & Processing Operator) — Bridgepoint-managed
  Components : C3 (Repayment Engine), C6 (AML Velocity), Decision Engine
               (C4 runs embedded inside C7 — not in Zone B)
  Runtime    : Kubernetes namespace: lip-miplo
  Compute    : CPU node pool
  Network    : Consumes from Kafka (Zone A output)
               Produces to Kafka (consumed by Zone C)
               Zero direct connection to Zone C execution systems

ZONE C — ELO (Execution Lending Operator) — Bank-managed
  Components : C7 (Embedded Execution Agent) including embedded C4
  Runtime    : Bank Kubernetes cluster, namespace: lip-execution
  Compute    : Bank-managed CPU nodes
  Network    : Consumes from Kafka (Zone B output)
               Zero outbound to Zones A or B
               Connects only to bank-internal systems (core banking, KMS, Redis)

Shared infrastructure (Zone A + B — NOT Zone C):
  Apache Kafka   : message backbone between MLO and MIPLO
  Redis Cluster  : MIPLO-side state (C3, C6 velocity, C6 graph)
  Apache Flink   : stream processing runtime (C3, C6)
  Kubernetes     : orchestration for all Zone A + B components

Zone C has its own separate Redis cluster and Kafka (bank-managed).
No shared infrastructure between MIPLO and ELO.
```

### 2.2 Network Segmentation

```
Zone A <-> Zone B communication:
  Via Kafka only (TLS 1.3, SASL/SCRAM-SHA-512)
  No direct service-to-service calls across zones
  Kafka brokers are the only cross-zone network endpoints

Zone B <-> Zone C communication:
  Via Kafka only (same TLS/SASL config)
  Bank Kafka cluster is Zone C infrastructure
  MIPLO publishes to it; C7 consumes from it
  MIPLO has no read access to Zone C Kafka topics

Zone C internal:
  Bank network policies govern (C7 Spec Section 14)
  Zero outbound from Zone C to Zones A or B
  Zero internet egress from Zone C

DNS and service discovery:
  Zone A + B: Kubernetes CoreDNS (cluster-internal only)
  Cross-zone: Kafka bootstrap server addresses only
  No service mesh required (Kafka is the integration layer)
  No direct pod-to-pod connectivity across zones — ever
```

---

## 3. KUBERNETES CLUSTER DESIGN

### 3.1 Node Pools (Zone A + B)

```
Pool 1 — GPU (MLO — C1 inference):
  Instance type   : GPU-optimized (e.g., A10G or equivalent)
  GPU             : 1x per node (NVIDIA CUDA — C1 inference only)
  CPU             : 8 vCPU
  Memory          : 32GB RAM
  Node count      : 2 (primary + standby for HA)
  Autoscaling     : Disabled (inference latency requires resident GPU;
                    cold GPU node startup is ~2-5 minutes — unacceptable)
  Namespace       : lip-ml
  Taint           : gpu=true:NoSchedule
  Toleration      : required on all C1 pods (prevents non-GPU workloads here)

Pool 2 — CPU Standard (MIPLO — C2, C6, Decision Engine):
  Instance type   : CPU-optimized (16 vCPU / 64GB recommended)
  Node count      : 3 minimum (for pod anti-affinity distribution)
  Autoscaling     : HPA on CPU utilization (target 60%)
                    Min replicas: 3, Max replicas: 12
  Namespace       : lip-miplo

Pool 3 — Flink (C3 + C6 stream processing):
  Instance type   : Memory-optimized (Flink TaskManagers are memory-heavy)
  Memory          : 64GB per node (Flink heap + RocksDB state backend)
  Node count      : 3 minimum
  Autoscaling     : Manual only (Flink job topology changes require restart;
                    HPA-triggered restarts during processing = unacceptable)
  Namespace       : lip-flink
```

### 3.2 Namespace Isolation

```
lip-ml          C1, C2 deployments; GPU node pool affinity
lip-miplo       C6 (Flink job), Decision Engine
lip-flink       Flink JobManager, TaskManagers (C3 + C6)
lip-kafka       Kafka brokers (if self-hosted — see Section 4.1)
lip-redis       Redis cluster (MIPLO-side)
lip-monitoring  Prometheus, Grafana, Alertmanager, Jaeger/Tempo
lip-execution   C7 (bank-managed; referenced for topology completeness only)

NetworkPolicy per namespace:
  Default: deny-all ingress + egress on every namespace
  Explicit allow rules only (whitelisted per component requirement)
  Cross-namespace: only via Kafka (no direct pod-to-pod across namespaces)
  All NetworkPolicies version-controlled in Git (IaC — Section 8.3)
```

### 3.3 Pod Anti-Affinity

```
All multi-replica deployments MUST use:

  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: {component-name}
        topologyKey: kubernetes.io/hostname

Required (not preferred):
  Rationale: "preferred" anti-affinity is a hint — Kubernetes can ignore it
  under resource pressure. A single node failure must not take down a component.
  "Required" enforces hard separation — if only one node is available,
  the second replica will not schedule rather than co-locate.
  This surfaces capacity problems explicitly rather than silently degrading HA.

No exceptions in production namespaces.
```

### 3.4 Resource Requests and Limits

```
Component        Replicas  CPU Req  CPU Limit  Mem Req  Mem Limit  Notes
C1               2         2        4          8Gi      16Gi       + 1x GPU per pod
C2               3         1        2          4Gi      8Gi
C6 Flink TM      3         2        4          16Gi     32Gi       RocksDB state
C3 Flink TM      3         2        4          16Gi     32Gi       RocksDB state
Decision Engine  3         0.5      1          2Gi      4Gi
C7 (Zone C)      2         1        2          4Gi      8Gi        Bank-managed

Flink JobManager (shared C3 + C6 — separate per cluster):
  CPU Req: 1    CPU Limit: 2
  Mem Req: 4Gi  Mem Limit: 8Gi
  Replicas: 1 active + 1 standby (HA — Section 5.3)

Rules:
  Requests AND limits must be set on all production pods.
  BestEffort QoS (no requests/limits) is prohibited in production namespaces.
  All production pods must be Guaranteed (req = limit) or Burstable (req < limit).
  Burstable is acceptable; BestEffort is not.
```

### 3.5 C7 Scaling Policy (Fixed — Non-Negotiable)

```
C7 is NOT auto-scaled. Ever.

Reason: C7 holds in-flight loan state in Redis keyed by pod identity.
HPA spinning up new replicas during a traffic spike creates state
management complexity that is not worth the operational risk for a
component that moves money. Vertical scaling (larger nodes) is the
correct approach for C7 capacity growth.

Fixed replica count: 2 (primary + hot standby)
HPA: explicitly disabled on lip-execution namespace (Kyverno policy blocks HPA creation)
Failover: if primary pod fails, Kubernetes reschedules on remaining node
Recovery SLA: < 30 seconds to new pod in Running + Ready state
Capacity planning: nodes must handle 2x peak expected TPS on a single pod
  (if one pod fails, the survivor handles full load without degradation)

FORGE note: if transaction volume grows beyond single-pod capacity,
correct response is: resize node (vertical) then validate chaos CH-04 again.
Do not re-enable HPA without a full state management redesign.
```

---

## 4. APACHE KAFKA

### 4.1 Deployment Model

```
Option A — Managed Kafka service (recommended):
  Confluent Cloud, Amazon MSK, or equivalent
  Rationale: broker management, patching, HA, and failure response
  delegated to vendor SLA. Operational burden near-zero for MIPLO team.
  SLA-backed availability (typically 99.95%+).

Option B — Self-hosted KRaft-mode Kafka 3.6+:
  Acceptable if bank mandates on-premises for data residency.
  Requires: dedicated Kafka operations runbook (NOVA owns)
            on-call expertise for broker failure response
            Adds ~2 weeks to infrastructure build timeline.

Decision: confirm Option A vs. B with bank partner before infrastructure build.
This is a hard pre-build gate item (Section 14.1).

Zone C (ELO): bank's own Kafka cluster — Bridgepoint does not manage it.
```

### 4.2 Cluster Configuration

```
Brokers             : 3 minimum (odd number for leader election quorum)
Replication factor  : 3 (all topics — every partition on 3 brokers)
Min in-sync replicas: 2 (all topics)
  Producer write fails if < 2 replicas in sync.
  Protects against: data loss on broker failure during write.
Rack awareness      : enabled (brokers spread across availability zones)
Retention default   : 7 days (overridden per topic — see Section 4.3)
Compression         : LZ4 (producer-side; best balance of CPU vs. network)
Max message size    : 10MB (adequate for all LIP message types)
Log retention check : 5-minute interval (default; acceptable)
```

### 4.3 Topic Inventory and Configuration

```
ZONE A + B TOPICS (MIPLO-managed):

Topic                        Partitions  Retention  Notes
lip.payments.raw             12          24h        Raw pacs.002 ingest
lip.payments.classified      12          24h        C3 classification output
lip.ml.features              12          24h        C1+C2 feature vectors
lip.ml.predictions           12          24h        C1+C2 scores
lip.aml.results              12          24h        C6 VelocityResponse
lip.aml.sar.queue            3           7d         SAR candidates -> bank compliance
lip.aml.entity.updates       1           7d         Sanctions list refresh events
lip.offers.pending           12          60s        LoanOffers to C7
                                                    (short retention: offers expire)
lip.loans.funded             12          30d        ExecutionConfirmations from C7
lip.payments.outbound        12          30d        pacs.008 events for C3 RTP path
lip.repayment.instructions   12          30d        C3 -> C7 repayment triggers
lip.repayment.confirmations  12          30d        C7 -> MIPLO confirmations
lip.decisions.log            12          7 years    HMAC-signed audit log (C7)
lip.state.transitions        12          90d        Loan lifecycle events
lip.human.review.queue       3           60s        Human review requests
lip.alerts                   3           7d         System alerts
lip.aml.blocks               3           7d         C6 hard block signals

Total: 18 topics

Partition key for all payment topics: UETR
  Guarantees: all events for a given individual UETR land in the same partition
  Enables: in-order processing per UETR across C1 -> C2 -> C6 -> Decision Engine
  Enforced at producer level (custom partitioner on UETR field)

Partition count rationale:
  12 partitions = 12 maximum parallel consumer threads
  Sized for 10K TPS peak with processing headroom
  If volume grows beyond 10K TPS sustained: add partitions (requires consumer
  group restart — plan as maintenance window operation)

lip.decisions.log special handling:
  7-year retention: DORA Art.30 + bank audit obligation
  Compaction: none (delete — retain all records for full audit history)
  Consumer: bank compliance / audit system (read-only access)
  Write access: C7 only (SASL ACL enforced)
```

### 4.4 Producer Configuration

```
All MIPLO producers (Zone A + B):
  acks                                         = all
  enable.idempotence                           = true
  max.in.flight.requests.per.connection        = 1
    (preserve per-UETR ordering; idempotence requires <= 5,
     setting to 1 is conservative and correct for payment flows)
  compression.type                             = lz4
  retries                                      = 10
  retry.backoff.ms                             = 100
  delivery.timeout.ms                          = 30000

  Rationale for acks=all: a write acknowledged by only 1 broker that then
  fails before replication means data loss. For payment decisions, this is
  unacceptable. acks=all adds ~1-2ms latency vs. acks=1. Worth it.

C7 producers (bank-managed Kafka, Zone C):
  Same configuration enforced by bank Kafka admin
  Bank confirms compliance before pilot onboarding
```

### 4.5 Consumer Configuration

```
All MIPLO consumers (Zone A + B):
  isolation.level       = read_committed
    (only consume messages from committed transactions;
     prevents reading uncommitted messages from failed producers)
  auto.offset.reset     = earliest
    (on new consumer group: start from beginning of retained messages)
  enable.auto.commit    = false
    (manual offset commit after processing — prevents offset commit
     before processing is confirmed, which would cause data loss on restart)
  max.poll.records      = 500
  session.timeout.ms    = 30000
  heartbeat.interval.ms = 10000

Consumer group registry:
  lip-classifier-c3      C3 payment classification (Flink)
  lip-ml-c1              C1 inference consumer
  lip-ml-c2              C2 inference consumer
  lip-aml-c6             C6 AML processing (Flink)
  lip-decision-engine    Decision Engine offer generator
  lip-repayment-c3       C3 repayment monitoring (Flink)
  lip-c7-offers          C7 offer processor (Zone C — bank-managed)
  lip-c7-repayments      C7 repayment executor (Zone C — bank-managed)

Consumer lag monitoring:
  Alert threshold: > 1,000 messages on any payment topic for > 5 minutes (HIGH)
  Alert threshold: > 10,000 messages for > 2 minutes (CRITICAL)
  Metric: kafka_consumergroup_lag (kafka-exporter)
```

---

## 5. APACHE FLINK

### 5.1 Flink Version and Deployment

```
Version    : Flink 1.19+ (Java 17 runtime)
Operator   : Flink Kubernetes Operator 1.8+
Mode       : Application mode (one Flink cluster per job group)

Two separate Flink clusters:
  Cluster A — C3 Repayment Engine (C3 Spec Sections 7-11)
  Cluster B — C6 AML Velocity Module (C6 Spec Section 3)

Rationale for separation:
  C6 is on the critical path for offer generation (~26ms end-to-end target).
  C3 processes repayment signals on a longer time horizon (seconds to minutes).
  A shared cluster means C3 backpressure propagates to C6.
  Shared cluster also means C3 job failure could take down C6.
  Separation is a hard requirement — no shared Flink cluster in production.
```

### 5.2 Flink Cluster Configuration

```
Per cluster (C3 cluster and C6 cluster each independently):

JobManager:
  Replicas     : 1 active + 1 standby (HA)
  CPU          : 1 request, 2 limit
  Memory       : 4Gi request, 8Gi limit
  HA storage   : Kubernetes ConfigMap or bank-approved persistent volume
  HA mode      : Kubernetes HA provider (native; no ZooKeeper dependency)

TaskManagers:
  Count        : 3 (minimum)
  Slots per TM : 4 (12 total processing slots per cluster)
                 Matches Kafka partition count (12) — no slot contention
  CPU          : 2 request, 4 limit per TM
  Memory       : 16Gi request, 32Gi limit per TM
  JVM Heap     : 8Gi  (-Xms8g -Xmx8g)
  Off-heap     : 4Gi  (network buffers, RocksDB native memory)
  Node anti-affinity: required (3 TMs on 3 different nodes)

State backend: RocksDB (both C3 and C6)
  Incremental checkpointing: enabled
  Rationale: velocity windows (C6) and UETR state (C3) are large
  and grow with transaction volume. RocksDB handles this without
  full state snapshots on every checkpoint.

Checkpointing:
  Interval          : 30 seconds
  Timeout           : 60 seconds (checkpoint fails if not complete in 60s)
  Min pause         : 5 seconds (minimum gap between checkpoint completions)
  Max concurrent    : 1 (no overlapping checkpoints)
  Storage           : bank-approved S3-compatible object store or HDFS
  Retained checkpoints: 3 (allows rollback up to ~90 seconds)
  Alert if checkpoint duration > 60s (HIGH)
  Alert if checkpoint fails 2x consecutively (CRITICAL)

Savepoints:
  Manual savepoint taken before any job upgrade or topology change
  Automated savepoint on graceful job shutdown
  Savepoint storage: same as checkpoint storage
  Naming convention: {cluster}-{job}-{timestamp}-manual.savepoint
                     {cluster}-{job}-{timestamp}-shutdown.savepoint
```

### 5.3 Flink HA Design

```
JobManager HA:
  Active JM fails -> standby JM promotes from HA storage metadata
  Promotion time: < 30 seconds
  In-flight records during failover: replayed from Kafka (exactly-once
  semantics via idempotent Kafka sink + checkpointed Kafka source offsets)
  State: restored from last successful checkpoint (max 30s state loss)
  Alert: "FLINK_JM_FAILOVER" fires on standby promotion

TaskManager failure:
  Flink reschedules failed TM tasks to remaining healthy TMs
  Requires: at least 1 TM with free slots available
  With 3 TMs at 4 slots each = 12 total: losing 1 TM leaves 8 slots
    (adequate for all 12 partitions if tasks are redistributed — Flink handles this)
  Backpressure during reschedule: expected; consumer lag will temporarily increase
  Recovery SLA: < 60 seconds to full processing capacity
  Alert: "FLINK_TM_FAILURE" fires on any TM pod loss

Full cluster failure (all JM + TM pods):
  Restart from last savepoint (manual trigger) or checkpoint (automatic on restart)
  Kafka consumer offsets preserved in committed offsets — no message loss
  In-flight state: replayed from Kafka from last committed offset
  Alert: "FLINK_CLUSTER_DOWN" — CRITICAL, immediate page required
  Recovery procedure: restart cluster via FlinkDeployment manifest update;
                      Flink Operator handles pod recreation

Known limitation: topology changes require savepoint + job restart (2-5 minutes
downtime for C6). Decision Engine must handle C6 unavailability gracefully
(hold new offers during restart — see Section 14.3 of this spec).
```

---

## 6. REDIS CLUSTER

### 6.1 MIPLO Redis (C3 + C6 State)

```
Mode        : Redis Cluster (3 primary + 3 replica shards = 6 nodes total)
Version     : Redis 7.2+
Persistence : AOF (appendonly yes, fsync: everysec)
              RDB snapshots every 60 seconds
              Both enabled: AOF for durability; RDB for fast node restart
TLS         : TLS 1.3 (client-to-server and intra-cluster replication)
Auth        : AUTH token per shard (bank-managed secret; rotated quarterly)
              Token stored in Kubernetes Secret (bank KMS-backed via ESO)

Memory sizing per shard:
  C6 velocity state       : ~10GB (50K active entities x 5 rolling windows)
  C6 graph embeddings     : ~5GB  (50K nodes x 64 floats x 4 bytes = ~12MB;
                                   with overhead and cluster growth: ~5GB)
  C6 structuring state    : ~2GB
  C3 UETR mapping         : ~2GB  (30d active loans)
  C3 corridor buffers     : ~1GB
  Buffer headroom         : ~4GB
  Total per shard         : ~24GB
  Recommended node RAM    : 32GB per node (6 nodes = 192GB cluster total)

Eviction policy: noeviction
  Rationale: C6 velocity state must never be silently evicted.
             A missing velocity entry defaults to zero, which could allow
             a blocked loan to proceed. This is fail-open behavior.
             noeviction forces a write error on full memory, which
             C6 detects and treats as a hard block.
  Consequence: if Redis fills up, writes fail. The correct response
               is to increase memory — not to allow eviction.
  Alert: "REDIS_MEMORY_HIGH" at 85% per shard (HIGH)
         "REDIS_MEMORY_CRITICAL" at 93% per shard (CRITICAL — page immediately)

HA failover:
  Automatic (Redis Cluster native — no manual intervention required)
  Primary shard fails -> replica promotes in < 10 seconds
  During failover (~10s): writes to failed shard return CLUSTERDOWN error
  C6 fail-safe: CLUSTERDOWN on any shard = hard_block = true (not fail-open)
  Alert: "REDIS_SHARD_FAILOVER" fires on any promotion event

Replication lag monitoring:
  Alert if replica replication_offset lags primary by > 1000 ops (HIGH)
  Replication lag = potential data loss on primary failure
```

### 6.2 ELO Redis (C7 State — Bank-Managed)

```
Spec ownership: bank infrastructure team (not Bridgepoint).
C7 Spec Section 12 defines the authoritative key schema.

Bank MUST provide:
  Redis Cluster mode    : required (standalone = no HA; unacceptable for C7)
  TLS 1.3 + AUTH token  : required
  noeviction policy     : required (same rationale as MIPLO Redis — C7 holds
                          loan execution state; eviction = corrupt state machine)
  AOF persistence       : required (appendonly yes, fsync: everysec)
  Memory                : >= 16GB (C7 state is smaller than MIPLO-side)
  Automated failover    : < 10 seconds replica promotion required

Bank Redis readiness is a hard gate for C7 pilot onboarding.
C7 readiness probe validates Redis connectivity on pod startup.
If Redis is unreachable: C7 pod does not enter Running state.
A pilot cannot begin with C7 in a non-Running state.
```

### 6.3 Redis Key Expiry Monitoring

```
Redis TTL misconfigurations are silent data integrity failures:
  TTL too short: velocity window loses history early -> under-counts -> bypass risk
  TTL missing:   keys accumulate indefinitely -> memory exhaustion

Monitoring requirements:
  [ ] Alert if any c6:vel:* key TTL < (window_duration - 1h)
      Indicates key created with wrong TTL (C6 code defect)
  [ ] Alert if total MIPLO Redis key count grows > 10% week-over-week
      Indicates TTL not set on new key type (deployment defect)
  [ ] Weekly key count report: FORGE + NOVA review
  [ ] Daily: sample 100 random keys; verify TTL set and within expected range
      Automated by monitoring job in lip-monitoring namespace
```

---

## 7. GPU INFRASTRUCTURE (C1)

### 7.1 C1 GPU Requirements

```
C1 (GraphSAGE + TabTransformer combined inference) requires GPU for p50 ~8ms target.
CPU inference of the combined GNN + TabTransformer is ~80-120ms per request.
That is 10x over the C1 latency budget. GPU is non-negotiable for production SLA.

GPU specification:
  Minimum  : NVIDIA A10G (24GB VRAM)
             Adequate for current C1 model size (~1.4GB VRAM)
  Preferred: NVIDIA A100 40GB
             Headroom for model size growth + larger batch sizes

C1 model VRAM footprint:
  GraphSAGE encoder   : ~800MB
  TabTransformer      : ~400MB
  Feature buffers     : ~200MB
  Safety margin       : ~200MB
  Total               : ~1.6GB VRAM (well within A10G 24GB)

Batching strategy (mandatory for GPU efficiency):
  Batch window: 5ms (collect incoming inference requests; flush as batch)
  Batch size  : 1–50 (whatever arrives within the 5ms window)
  Single request: processed immediately (no minimum batch hold)
  Latency impact: up to 5ms additional per request from batch window
                  5ms batch window + 3ms GPU compute = 8ms p50 (within budget)

Runtime:
  CUDA    : 12.x (required for PyTorch 2.x or JAX 0.4.x)
  Driver  : version locked in container image (never rely on host driver)
            Rationale: host driver upgrades must not silently break C1

CPU inference fallback:
  Required for development environment (no GPU available during development)
  CPU path: ~80-120ms latency (acceptable for dev — not for production SLA)
  Toggle: environment variable C1_INFERENCE_DEVICE = "gpu" | "cpu"
  Production: C1_INFERENCE_DEVICE = "gpu" enforced by admission policy
```

### 7.2 GPU Node Scheduling

```
Node configuration:
  Label      : gpu: "true" (applied to GPU node pool)
  Taint      : gpu=true:NoSchedule (prevents non-GPU pods landing on GPU nodes)

C1 pod configuration:
  nodeSelector   : gpu: "true"
  tolerations    : [{key: "gpu", operator: "Equal", value: "true",
                     effect: "NoSchedule"}]
  resources:
    limits:
      nvidia.com/gpu: 1
    requests:
      nvidia.com/gpu: 1

GPU allocation: exclusive per pod (Kubernetes GPU device plugin)
2 C1 replicas = 2 GPU nodes required minimum.

GPU utilization monitoring (DCGM Exporter):
  Alert: GPU utilization < 20% for > 1 hour (model may not be loading on GPU)
  Alert: GPU utilization > 90% for > 5 minutes (capacity risk — batch queue building)
  Alert: GPU temperature > 85C (hardware risk)
  Metric: DCGM_FI_DEV_GPU_UTIL, DCGM_FI_DEV_GPU_TEMP, DCGM_FI_DEV_FB_USED
  Dashboard: Grafana "C1 GPU Performance" panel

Node management:
  GPU nodes are expensive. Do not over-provision.
  Standard: 2 nodes in production (1 per C1 replica).
  If GPU utilization consistently > 80% at peak: add third node.
  Cost review: monthly (FORGE + QUANT).
```

---

## 8. CI/CD PIPELINE

### 8.1 Pipeline Structure

```
Stage 1 — Build & Test (every pull request):
  - Go build: C3, C6, C7, Decision Engine
  - Python build: C1, C2 training code + inference wrappers
  - Unit tests: all components
    Pass threshold: >= 80% line coverage (enforced — PR blocked below 80%)
  - Linting: golangci-lint (Go), ruff (Python)
  - Container image build: Docker buildx (multi-arch: amd64 + arm64)
  - Image signing: Cosign (keyless, OIDC-based signing in CI)
  - SBOM generation: Syft (per image; attached to registry as attestation)
  - Trivy vulnerability scan: CRITICAL CVE = build failure (no exceptions)

Stage 2 — Integration Tests (merge to main):
  - Kafka integration: Testcontainers (real Kafka 3.6 — not mocks)
  - Redis integration: Testcontainers (real Redis 7.2 Cluster — not mocks)
  - Flink job: local Flink minicluster (job submission + processing validation)
  - C6 sanctions: sanctions screening test suite (Section 16.2 of C6 Spec)
  - C6 velocity: velocity control test suite (Section 16.1 of C6 Spec)
  - C3/C7 repayment: mock CoreBankingAdapter (configurable response latency)
  - End-to-end smoke: synthetic pacs.002 -> ExecutionConfirmation (mock C7)

Stage 3 — Staging Deployment (merge to release branch):
  - Deploy to staging environment (mirrors production topology exactly)
  - Smoke tests: happy path end-to-end at 100 TPS (p50, p99, error rate)
  - Performance tests: Scenario 1 (1K TPS) — must pass before Stage 4 gate
  - Chaos test: at least 1 scenario per release (see Part 2 Section 11)
  - Staging gate: manual approval required (FORGE sign-off)

Stage 4 — Production Deployment (manual gate after staging):
  - Strategy: blue/green (zero downtime)
  - Canary option: route 5% traffic to new version for 10 minutes before full rollout
  - Automated rollback trigger: error rate > 1% within 5 minutes of deployment
  - Post-deploy validation: smoke test runs automatically (100 synthetic transactions)
  - Deployment record: component version, image SHA256, deploying operator ID,
                       timestamp — written to lip.decisions.log
```

### 8.2 Image Security Requirements

```
Base image standard: distroless
  Go components  : gcr.io/distroless/static-debian12@sha256:{pinned-digest}
  Python C1/C2   : gcr.io/distroless/python3-debian12@sha256:{pinned-digest}

Pinned to digest (not tag):
  Rationale: image tags are mutable — :latest today is different from :latest tomorrow.
             A digest pin is immutable — the exact bytes are specified.
  Update process: Renovate Bot PRs for base image digest updates (weekly)

Build-time enforced requirements:
  [ ] No shell binary in final image (Trivy check: fail if /bin/sh or /bin/bash present)
  [ ] No root user (fail if USER = root or USER not set)
  [ ] Read-only root filesystem (enforced in Kubernetes SecurityContext)
  [ ] Trivy CRITICAL CVE: 0 (fail build if any CRITICAL in base or app deps)
  [ ] Cosign signature present (fail if signing step fails)

Admission control (production gate):
  OPA Gatekeeper or Kyverno policy on all production namespaces:
    Reject pod creation if:
      - Image is not signed by Cosign
      - Image is not from approved private registry
      - Image tag is "latest" or mutable tag (must be digest or immutable tag)

Image pull policy: Always (never use cached image in production)
  Rationale: Always ensures the admission webhook runs on every pod start,
             verifying the signature and policy compliance each time.
```

### 8.3 Infrastructure as Code

```
IaC toolchain:
  Kubernetes manifests : Helm charts (one chart per component)
                         values-{env}.yaml per environment (dev/staging/prod)
  Cloud infrastructure : Terraform (node pools, managed Kafka, VPC, networking)
  Secret management    : External Secrets Operator (ESO)
                         Syncs secrets from bank KMS to Kubernetes Secrets
                         No secrets stored in Git — ever
  GitOps               : ArgoCD
                         Declarative sync from Git to cluster
                         Drift detection: ArgoCD alerts on any out-of-sync state
                         Auto-sync: enabled for staging; manual sync approval for prod

Git branching model:
  main        : production-ready; protected branch (requires 2 reviewer approvals)
  release/*   : staging deployments (1 approval required)
  feature/*   : development; PRs to main (automated tests must pass)

Hard rules:
  No secrets in Git (ESO + KMS is the only secret path)
  No secrets in ConfigMaps
  No secrets in environment variables in manifests
  No manual kubectl apply in production (ArgoCD drift detection will flag it)
  All IaC changes: PR-reviewed before merge

Verification: monthly ArgoCD audit — confirm no out-of-band changes to production
```

---

## 9. OBSERVABILITY STACK

### 9.1 Metrics

```
Backend    : Prometheus (collection) + Thanos (long-term storage, federation)
Retention  : Thanos: 13 months (DORA Art.30 audit requirement)
Dashboards : Grafana (pre-built dashboards per component + system-level)

Exporters deployed:
  kube-state-metrics     Kubernetes object state (deployments, pods, PVCs)
  node-exporter          Hardware: CPU, memory, disk, network per node
  kafka-exporter         Consumer lag, broker ISR, topic throughput
  redis-exporter         Memory usage, hit rate, replication lag, evictions
  flink-metrics-reporter Checkpoint duration, job uptime, task throughput
  dcgm-exporter          GPU utilization, VRAM usage, temperature (C1 nodes)
  Custom /metrics        All components expose on :9090/metrics

Key application metrics (per component):

C1 (GPU Inference):
  c1_inference_latency_seconds{quantile="0.5|0.99"}
  c1_batch_size_histogram          distribution of GPU batch sizes per window
  c1_gpu_utilization_pct           from DCGM
  c1_model_version                 label on all C1 metrics

C2 (PD Model):
  c2_inference_latency_seconds{quantile="0.5|0.99"}
  c2_pd_estimate_histogram         distribution of PD scores across corridors
  c2_model_version

C6 (AML):
  c6_processing_latency_seconds{quantile="0.5|0.99"}   end-to-end per UETR
  c6_hard_block_total{reason}       by block reason
  c6_sanctions_screen_latency       bloom-miss vs. full-scan paths
  c6_velocity_threshold_proximity   % of threshold reached per dimension
  c6_anomaly_score_histogram
  c6_redis_op_latency_seconds{op}
  c6_sanctions_list_age_hours       alert if > 24h

Decision Engine:
  de_offer_generation_rate          offers/second
  de_offer_acceptance_rate          % reaching LoanOffer (vs. pre-offer filters)
  de_e2e_latency_seconds{q="0.5|0.99"}  pacs.002 receipt to offer publish

C7 (bank-managed — Bridgepoint provides definitions):
  Metric definitions: C7 Spec Sections 17.1–17.3
  Bank exposes via agreed reporting interface (format TBD with bank)
  Minimum required: offer acceptance rate, execution success rate,
                    repayment success rate, hard block counts
```

### 9.2 Logging

```
Log format     : JSON structured (no plaintext logs in production)
  Required fields:
    timestamp_utc   : ISO 8601 with millisecond precision
    component       : "C1" | "C2" | "C3" | "C6" | "DE" | "C7"
    level           : "DEBUG" | "INFO" | "WARN" | "ERROR" | "CRITICAL"
    uetr            : individual UETR (where applicable)
    trace_id        : W3C TraceContext trace ID
    span_id         : W3C TraceContext span ID
    message         : human-readable description
    error           : error detail (only on ERROR/CRITICAL)

Log destination : bank-approved log aggregation (Loki, Elasticsearch, or equivalent)
Retention       : 90 days hot (searchable); 7 years cold (archived, retrievable)
                  7-year retention: DORA Art.30 compliance

PII policy (mandatory — no exceptions):
  No raw BIC codes in any log entry
  No entity names in any log entry
  No payment amounts in any log entry
  No account numbers in any log entry
  UETR is acceptable (pseudonymous in audit context)
  All entity references: SHA-256 hashed (C6 standard — applied across all components)

  Enforcement: log review spot-check in CI (sample 50 log lines from integration tests)
               Automated PII scanner run on logs weekly in staging environment

Trace propagation:
  W3C TraceContext headers on all internal HTTP/gRPC calls
  Kafka message headers carry trace_id and span_id
  Enables: full distributed trace from pacs.002 ingest to C7 ExecutionConfirmation
  Backend: Jaeger or Grafana Tempo (deployed in lip-monitoring namespace)
```

### 9.3 Alerting

```
Severity levels and response SLAs:

CRITICAL — Immediate page (PagerDuty, 24/7 on-call):
  Any component pod in CrashLoopBackOff in production
  Any component pod OOMKilled in production
  Kafka consumer lag > 10,000 messages for > 2 minutes (any payment topic)
  Redis shard unreachable for > 30 seconds
  Flink cluster down — C3 or C6 (FLINK_CLUSTER_DOWN)
  GPU node unavailable (C1 inference unreachable)
  End-to-end offer generation p99 > 500ms for > 5 minutes
  Any sanctions_match = true event (compliance immediate notification)
  DECISION_LOG_INTEGRITY_VIOLATION (C7 HMAC chain broken)
  Redis memory > 93% any shard

HIGH — 15-minute response:
  Kafka consumer lag > 1,000 for > 5 minutes
  Redis memory > 85% any shard
  Any production pod in restart loop (2+ restarts in 10 minutes)
  C6 sanctions list age > 24 hours (SANCTIONS_LIST_REFRESH_FAILED)
  GPU utilization > 90% for > 5 minutes
  p99 offer generation latency > 200ms for > 5 minutes
  Flink checkpoint failure 2x consecutive
  Flink JM failover (FLINK_JM_FAILOVER)

MEDIUM — 1-hour response:
  Redis memory > 70% any shard
  Flink checkpoint duration > 60 seconds
  Kafka broker under-replicated partitions detected
  Any Trivy CRITICAL CVE in CI pipeline (build failed — investigate cause)
  ArgoCD drift detected (out-of-sync with Git)

LOW — Daily digest:
  Redis key count growing > 10% week-over-week
  GPU utilization < 20% for > 1 hour (model loading concern)
  Any integration test flakiness (non-deterministic failures in CI)

Alert routing:
  CRITICAL + HIGH : PagerDuty -> on-call engineer
  MEDIUM          : Slack #lip-alerts
  LOW             : Daily digest email to FORGE + NOVA

Alert hygiene:
  All alerts must have a runbook link in the annotation
  Alerts with no owner (no runbook): treated as defect in next sprint
  Alert review: monthly (identify and resolve chronic false positives)
```

---

*C5 Build Specification v1.0 — Part 1 of 2*
*Sections 1–9 complete.*
*Continued in Part 2: Load Testing, Chaos Engineering, Security,*
*SOC2 Roadmap, Known Limitations, Validation, Audit Gate 2.4.*
*Internal use only. Stealth mode active. March 4, 2026.*
*Lead: FORGE | Support: NOVA, ARIA, REX, CIPHER*
