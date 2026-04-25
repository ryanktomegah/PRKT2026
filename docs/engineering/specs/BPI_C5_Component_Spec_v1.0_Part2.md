# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 5 — PLATFORM INFRASTRUCTURE & ORCHESTRATION
## Build Specification v1.0 — Part 2 (Sections 10–16)
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0 — Part 2 of 2
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

## TABLE OF CONTENTS (PART 2)

10. Load Testing Plan
    10.1 Test Environments
    10.2 Load Test Scenarios
    10.3 Performance Baselines (Targets Until Tested)
11. Chaos Engineering
    11.1 Chaos Test Library
    11.2 Chaos Test Tooling
12. Security Hardening
    12.1 Pod Security Standards
    12.2 Secret Management
    12.3 Container Image Supply Chain
13. SOC2 Readiness Roadmap
14. Known Limitations & Open Items (FORGE Self-Critique)
    14.1 Managed vs. Self-Hosted Kafka Decision
    14.2 GPU Node Availability for Development
    14.3 Flink Job Topology Changes Require Downtime
    14.4 Load Test Data Quality
15. Validation Requirements
    15.1 Infrastructure Smoke Tests
    15.2 End-to-End Integration Test
    15.3 Load Tests
    15.4 Chaos Tests
    15.5 Security Tests
16. Audit Gate 2.4 Checklist

---

## 10. LOAD TESTING PLAN

### 10.1 Test Environments

```
Load test environment specification:
  Topology     : mirrors production exactly
                 (same node types, same Kafka config, same Redis cluster mode)
  Synthetic data: realistic pacs.002 messages generated from corridor statistics
                 (rejection code distribution: 55% Class A, 30% Class B, 15% Class C
                  per Architecture Spec baseline — updated post-pilot)
  CoreBankingAdapter: mock (configurable response latency: default 5ms p50)
  KMS          : mock (configurable response latency: default 1ms p50)
  Sanctions lists: real OFAC/EU/UN lists (public data — no PII risk)
  C7           : mock ExecutionConfirmation responder (not real bank system)

Load test tooling:
  Traffic injection : custom Kafka producer (Go) — injects synthetic pacs.002
                      at configurable TPS with realistic UETR distribution
  HTTP/gRPC load    : k6 (for any direct API endpoints)
  Metrics collection: Prometheus scraping throughout; exported to Thanos
  Results archival  : BPI_LoadTest_Report_{date}.md (required per run)

Test data isolation:
  Separate Kafka consumer groups for load test (suffix: -loadtest)
  Separate Redis namespace prefix: "lt:" (TTL 2 hours — auto-cleans after test)
  Load test results must not contaminate production state
```

### 10.2 Load Test Scenarios

```
SCENARIO 1 — Baseline (1K TPS)
  Injection rate : 1,000 pacs.002 messages/second
  Duration       : 30 minutes (10-minute ramp-up + 20-minute steady state)
  Purpose        : Establish performance baseline; validate all p50/p99 targets

  Pass criteria:
    p50 end-to-end offer generation    < 26ms
    p99 end-to-end offer generation    < 100ms
    p50 C6 AML processing              < 8ms
    p99 C6 AML processing              < 20ms
    p50 C1 inference (GPU)             < 8ms
    p99 C1 inference (GPU)             < 30ms
    p50 C2 inference (CPU)             < 6ms
    p99 C2 inference (CPU)             < 20ms
    Redis op latency p99               < 3ms
    Kafka consumer lag at steady state : stable (not growing)
    Error rate                         < 0.1%
    No OOMKilled pods during test
    GPU utilization at 1K TPS          < 80% (headroom confirmed)

SCENARIO 2 — Peak (10K TPS)
  Injection rate : 10,000 pacs.002 messages/second
  Duration       : 15 minutes steady state (after 5-minute ramp)
  Purpose        : Validate system at 10x baseline; confirm HPA fires correctly

  Pass criteria:
    p50 offer generation               < 50ms   (relaxed — 10x load)
    p99 offer generation               < 200ms
    p99 C6 AML processing              < 50ms
    Error rate                         < 1%
    No data loss (all offers eventually generated — lag recovers)
    Kafka consumer lag: recovers to zero within 5 minutes after load ends
    No OOMKilled pods during test
    HPA fires for CPU Standard pool: new nodes provision within 3 minutes

SCENARIO 3 — Stress (50K TPS)
  Injection rate : 50,000 pacs.002 messages/second
  Duration       : 5 minutes
  Purpose        : Find degradation mode; confirm graceful behavior at extreme load

  Pass criteria:
    System does not crash (no OOMKilled pods, no Flink cluster down)
    No data loss (Kafka retains messages; processed after load recedes)
    No incorrect decisions under load
      (hard blocks must not false-positive; clear transactions must not be blocked)
    Kafka consumer lag grows during test but recovers within 30 minutes after
    Graceful degradation: latency increases are acceptable; errors are not

SCENARIO 4 — Ramp (1K → 50K TPS)
  Injection rate : linear ramp from 1K to 50K TPS over 10 minutes
  Hold           : 5 minutes at 50K TPS
  Purpose        : Identify system breaking point; characterize degradation curve

  Deliverables (required in test report):
    TPS at which p99 first exceeds 200ms
    TPS at which error rate first exceeds 1%
    TPS at which first pod restart is observed
    Recovery time from 50K back to zero consumer lag
    Degradation mode description (latency-first? error-first? crash?)

  Pass criteria:
    No permanent data loss at any TPS level
    System recovers fully (consumer lag = 0, error rate = 0) within 60 minutes
    Breaking point is documented — not hidden
```

### 10.3 Performance Baselines (Targets Until Load-Tested)

```
These numbers are targets until Scenario 1 passes.
They become validated baselines when the load test report is archived.
Until Scenario 1 passes, no document external to this spec may
claim these as facts. FORGE will not sign any SLA document that
references these numbers before the load test evidence exists.

Metric                              Target       Status
p50 end-to-end offer generation     < 26ms       HYPOTHESIS
p99 end-to-end offer generation     < 100ms      HYPOTHESIS
p50 C6 AML processing               < 8ms        HYPOTHESIS
p99 C6 AML processing               < 20ms       HYPOTHESIS
p50 C1 inference (GPU batch)        < 8ms        HYPOTHESIS
p99 C1 inference (GPU)              < 30ms       HYPOTHESIS
p50 C2 inference (CPU)              < 6ms        HYPOTHESIS
p99 C2 inference (CPU)              < 20ms       HYPOTHESIS
Redis operation latency p99         < 3ms        HYPOTHESIS
Kafka consumer lag at 1K TPS        stable       HYPOTHESIS
Peak sustained TPS without error    >= 10K       HYPOTHESIS
GPU utilization at 1K TPS           < 80%        HYPOTHESIS

These become VALIDATED when:
  Scenario 1 report archived + FORGE signs off.
  Section 15.3 checklist items checked.
```

---

## 11. CHAOS ENGINEERING

### 11.1 Chaos Test Library

FORGE posture: every SLA claim must survive a chaos test. "Pass" means the system
behaves as specified under failure — not that it continues at full performance.
Latency increases under failure are acceptable. Data loss is not. Incorrect
decisions (wrong blocks, wrong clearances) are not.

All 8 scenarios must pass before any component is considered production-ready.
Results must be archived as `BPI_Chaos_Test_Report_{date}.md`.

```
CH-01 — Kafka Broker Failure
  Action     : Kill one of three Kafka brokers at 1K TPS steady state
  Injector   : Chaos Mesh PodChaos or manual pod delete
  Expected   : ISR rebalance completes; consumer lag < 5,000 within 60s;
               all messages eventually processed after recovery
  Pass if    : Zero message loss (confirmed by comparing injected count
               vs. processed count); no duplicate decisions per UETR

CH-02 — Redis Primary Shard Failure
  Action     : Kill one Redis primary shard at 1K TPS steady state
  Injector   : Chaos Mesh PodChaos or manual pod delete
  Expected   : Replica promotes within 10s; C6 returns hard_block=true
               for transactions requiring state from failed shard during
               promotion window (~10s); C6 resumes normal after promotion
  Pass if    : No fail-open behavior during failover window
               (hard_block=true on CLUSTERDOWN, not false clearance);
               velocity state intact after recovery (AOF replay);
               zero incorrect decisions post-recovery
  CIPHER confirms: fail-safe not fail-open during failover window

CH-03 — Flink TaskManager Failure
  Action     : Kill one of three Flink TMs (C6 cluster) at 1K TPS
  Injector   : Chaos Mesh PodChaos
  Expected   : Flink reschedules affected tasks within 60s;
               consumer lag temporarily increases then recovers;
               no incorrect AML decisions during task migration
  Pass if    : Consumer lag recovers to zero within 5 minutes of TM restart;
               zero incorrect decisions during migration window;
               checkpoint resumes within 30s of task reschedule

CH-04 — GPU Node Failure (C1 Unavailable)
  Action     : Cordon and drain GPU node 1 (simulate hardware failure)
  Injector   : kubectl cordon + kubectl drain
  Expected   : C1 pod reschedules to GPU node 2 within 30s;
               in-flight C1 requests queue in lip.ml.features Kafka topic;
               offer generation resumes after C1 pod becomes ready;
               no offers permanently lost (offer expiry handles edge case)
  Pass if    : No permanent offer loss; all queued transactions processed;
               p99 returns to baseline within 5 minutes of pod ready
  Note       : C1 pod restart time includes model loading to GPU (~15-30s)
               This is the dominant factor — test must account for it

CH-05 — Network Partition (Zone A → Zone B Kafka)
  Action     : Block Kafka traffic between Zone A and Zone B for 60 seconds
  Injector   : Chaos Mesh NetworkChaos (iptables DROP on Kafka port)
  Expected   : C1 + C2 scores queue in lip.ml.predictions Kafka topic;
               C6 + Decision Engine idle (no input to process);
               after partition heals: backlog processes in UETR order;
               no incorrect decisions; no duplicate offers
  Pass if    : Zero data loss; zero incorrect decisions;
               consumer lag returns to zero within 10 minutes of heal;
               idempotency confirmed (no duplicate LoanOffer per UETR)

CH-06 — Decision Engine Total Restart
  Action     : Delete all Decision Engine pods simultaneously
  Injector   : kubectl delete pod -l app=decision-engine -n lip-miplo
  Expected   : Kubernetes reschedules pods within 30s;
               Kafka consumer group rebalances;
               unprocessed LoanOffer candidates replay from Kafka;
               idempotency prevents duplicate LoanOffers per UETR
  Pass if    : Zero duplicate LoanOffers per UETR (confirmed by audit);
               zero offers permanently lost (within offer_expiry_utc window);
               consumer group rebalance completes within 60s

CH-07 — Memory Pressure (C6 Flink TM OOM Boundary)
  Action     : Inject memory pressure on one C6 Flink TM to 90% heap usage
  Injector   : Chaos Mesh StressChaos (memory stress)
  Expected   : Flink backpressure propagates upstream (Kafka consumer slows);
               GC pressure visible in JVM metrics (gc_pause_seconds increases);
               no OOMKilled (memory limit set correctly in Section 3.4);
               TM recovers when pressure removed
  Pass if    : No OOMKilled pods during pressure window;
               Flink job remains in RUNNING state (not FAILED);
               zero incorrect AML decisions during pressure window;
               consumer lag recovers within 5 minutes of pressure removal

CH-08 — Clock Skew Injection
  Action     : Advance one node clock by 10 seconds (affects C7 node)
  Injector   : Chaos Mesh TimeChaos
  Expected   : C7 clock skew detection alert fires within 60s;
               offer expiry calculations on affected node are conservative
               (offers expire slightly early — acceptable);
               no offers accepted past their true expiry_utc timestamp;
               no funded loans with incorrect maturity_date calculations
  Pass if    : Alert "CLOCK_SKEW_DETECTED" fires within 60s of injection;
               zero offers accepted past true expiry;
               zero funded loans with wrong maturity_date;
               C7 HMAC chain integrity maintained (timestamp in log is skewed
               but chain is unbroken — skew is visible in audit log)
  CIPHER confirms: clock skew does not enable extension of loan expiry window
```

### 11.2 Chaos Test Tooling

```
Primary tooling: Chaos Mesh (Kubernetes-native)
  Supports: PodChaos, NetworkChaos, StressChaos, TimeChaos
  Deployment: lip-chaos namespace (staging only — never in production)
  Version: 2.6+

Alternative (simpler scenarios): manual kubectl + iptables
  CH-04: kubectl cordon/drain (no Chaos Mesh required)
  CH-05: custom iptables DROP rule on Kafka port (verify + revert script)

Chaos test execution protocol:
  1. Confirm staging environment is at 1K TPS steady state (Scenario 1 passing)
  2. Start recording: all metrics, all Kafka consumer lag, all error rates
  3. Inject chaos event
  4. Observe for specified duration
  5. Remove chaos injection
  6. Wait for full recovery (consumer lag = 0, error rate = 0)
  7. Compare: actual behavior vs. expected behavior from Section 11.1
  8. PASS or FAIL verdict
  9. Archive: BPI_Chaos_Test_Report_{date}.md

Cadence:
  Pre-release: minimum 1 scenario per production release (FORGE chooses)
  Full suite (CH-01 through CH-08): quarterly
  On any infrastructure configuration change: relevant scenarios re-run
    (e.g., Redis config change -> CH-02 must re-run)

FORGE note: chaos tests are the only way to know if the fail-safe behaviors
in C6 and C7 actually work. Unit tests mock the failure conditions.
Chaos tests cause them for real. There is no substitute.
```

---

## 12. SECURITY HARDENING

### 12.1 Pod Security Standards

```
All production namespaces enforce Kubernetes restricted pod security standard
via Pod Security Admission (PSA) controller.

Restricted standard enforces (automatically; no per-pod configuration needed):
  No privileged containers
  No hostNetwork, hostPID, hostIPC
  No hostPath volume mounts
  Must run as non-root user (runAsNonRoot: true)
  Must drop ALL capabilities (securityContext.capabilities.drop: [ALL])
  May add only NET_BIND_SERVICE if explicitly required (no LIP component needs this)
  Read-only root filesystem (readOnlyRootFilesystem: true)
  seccompProfile: RuntimeDefault or Localhost

Namespace labels (applied to all production namespaces):
  pod-security.kubernetes.io/enforce: restricted
  pod-security.kubernetes.io/warn:    restricted
  pod-security.kubernetes.io/audit:   restricted

Exceptions: none.
If a component requires a capability excluded by restricted standard:
  Escalate to FORGE + CIPHER for architecture review.
  Re-architect before granting exception.
  No exceptions granted without documented justification and dual sign-off.
```

### 12.2 Secret Management

```
Secret lifecycle:

Storage:
  All secrets in bank KMS (Zone A+B: bank KMS accessible to MIPLO)
  External Secrets Operator (ESO) syncs from KMS to Kubernetes Secrets
  Kubernetes Secrets: projected into pods as files (not env vars)
    Rationale: env vars appear in process listings; files are harder to leak
  Zone C (C7): bank KMS directly — Bridgepoint has no access path

What is a secret (requires KMS + ESO treatment):
  Kafka SASL/SCRAM credentials
  Redis AUTH tokens
  KMS key references (C6 SHA-256 salt, C7 HMAC key)
  Container registry pull credentials
  ArgoCD Git credentials

What is not a secret (ConfigMap is appropriate):
  AML velocity thresholds (bank AML policy — Section 5.3 of C6 Spec)
  Kafka topic names
  Kafka bootstrap server addresses
  Feature flags

Rotation schedule:
  C7 HMAC key        : quarterly (bank KMS schedule — C7 Spec Section 13)
  C6 SHA-256 salt    : quarterly (Architecture Spec S2.4 — C6 Spec Section 4.2)
  Redis AUTH tokens  : quarterly
  Kafka SASL creds   : quarterly
  Emergency rotation : within 4 hours of any credential compromise suspicion

Secret access auditing:
  All KMS key access events logged (KMS native audit log)
  Alert: any key access outside 06:00–22:00 bank local time (HIGH)
  Alert: any key access from unrecognized service account (CRITICAL)
  Monthly review: KMS audit log sample — CIPHER reviews

Prohibited locations (enforced by CI + admission control):
  Git repositories (Trivy secret scanning in CI — fails on secret detection)
  Container images (Trivy secret scanning in CI)
  Kubernetes ConfigMaps
  Environment variables in manifests or Dockerfiles
  Log output (log auditing in staging environment)
```

### 12.3 Container Image Supply Chain

```
Supply chain security gates (every image, every build):

Gate 1 — Build origin:
  All production images built in CI pipeline only.
  Developer-built images ("works on my machine") are never deployed.
  Enforcement: admission controller checks image was built by CI system
               (Cosign keyless signing uses CI OIDC token — locally built
               images cannot produce a valid CI-origin signature)

Gate 2 — Vulnerability scan:
  Trivy scans every image at build time
  CRITICAL CVE: build fails immediately
  HIGH CVE: build fails if fix is available (unfixed HIGH: warning, not block)
  Results: archived per build (Trivy SARIF output to CI artifact storage)

Gate 3 — SBOM generation:
  Syft generates SBOM (CycloneDX format) per image
  SBOM attached to image in registry as OCI attestation
  Enables: future CVE scanning against known dependency inventory

Gate 4 — Image signing:
  Cosign keyless signing (OIDC: CI system identity -> Sigstore Fulcio CA)
  Signature stored in Sigstore Rekor transparency log
  Signature attached to image in registry

Gate 5 — Admission control:
  OPA Gatekeeper or Kyverno policy on all production namespaces:
    Reject if: image not signed (no valid Cosign signature)
    Reject if: image from non-approved registry
    Reject if: image tag is mutable ("latest", branch names)
    Reject if: image digest not pinned (tag-only reference)
  All rejections logged to lip.alerts

Base image pinning:
  Go components  : gcr.io/distroless/static-debian12@sha256:{digest}
  Python (C1/C2) : gcr.io/distroless/python3-debian12@sha256:{digest}
  Digest updated : Renovate Bot raises weekly PRs for base image digest bumps
                   PRs require 1 reviewer approval + Trivy scan pass

Image registry:
  Private registry only (no Docker Hub in production — ever)
  Registry access: pull credentials via ESO from KMS
  Registry immutability: production tags are immutable (registry-enforced)
```

---

## 13. SOC2 READINESS ROADMAP

C5 owns the infrastructure evidence for SOC2 Type II readiness.
This is a pre-pilot preparation item — not a current blocker.
External audit is scheduled post-pilot (timeline TBD with bank).

```
Control Area 1 — Availability (Trust Service Criterion A1):
  Evidence required:
    Load test reports: Scenarios 1–4 (archived BPI_LoadTest_Report files)
    Chaos test reports: CH-01 through CH-08 (archived BPI_Chaos_Test_Report files)
    Uptime metrics: 13-month Thanos retention (export for auditor)
    RTO documentation: < 30 minutes (scenario-by-scenario from chaos tests)
    RPO documentation: < 30 seconds (Flink checkpoint interval = max state loss)
    Incident response: documented recovery procedure per CH scenario
  Owner: FORGE

Control Area 2 — Security (Trust Service Criteria CC6–CC9):
  Evidence required:
    Trivy scan reports: per release (archived in CI artifact storage)
    SBOM inventory: per image version (OCI attestations in registry)
    Network policy review: per namespace (Git history is evidence)
    Secret rotation logs: KMS audit log exports (quarterly)
    Penetration test: external firm, pre-pilot (budget and vendor TBD)
    Access review: Kubernetes RBAC review quarterly (who can deploy to production)
  Owner: CIPHER

Control Area 3 — Confidentiality (Trust Service Criterion C1):
  Evidence required:
    No-PII log policy: staging log audit reports (weekly automated scan)
    SHA-256 hashing: C6 Spec Section 4 + test evidence (Gate 2.3)
    Zero Zone C outbound: network test (CH-05 analog + NetworkPolicy audit)
    GDPR Art.28: processing agreement with bank (legal document — suspended in stealth)
    Data residency: Kafka and Redis deployment region confirmed within bank jurisdiction
  Owner: REX (compliance) + FORGE (technical evidence)

Control Area 4 — Processing Integrity (Trust Service Criterion PI1):
  Evidence required:
    HMAC decision log integrity: C7 Spec Section 11 + Gate 2.2 checklist
    Idempotency tests: C3, C7 test suites (no duplicate decisions per UETR)
    Fee arithmetic tests: C7 Spec Section 19.5 (all combinations verified)
    Dual-auth kill switch: C7 Spec Section 6 (tested in chaos CH-06 analog)
    Audit trail completeness: lip.decisions.log 7-year retention verified
  Owner: NOVA + FORGE

Control Area 5 — Change Management (Trust Service Criteria CC8):
  Evidence required:
    GitOps deployment logs: ArgoCD sync history (all changes traceable to commit)
    IaC change records: Terraform plan outputs + PR approval records
    CI/CD pipeline logs: all production deployments traceable to pipeline run
    Change control: proof that no manual kubectl apply occurred in production
    Deployment approvals: PR review history (2 required approvals for main branch)
  Owner: FORGE

SOC2 readiness gate:
  All 5 control areas evidenced before engaging external auditor.
  Estimated readiness: 3 months post-pilot launch (sufficient evidence accumulation).
  External audit engagement: suspended until stealth lifts and bank partner confirmed.
```

---

## 14. KNOWN LIMITATIONS & OPEN ITEMS (FORGE SELF-CRITIQUE)

### 14.1 Managed vs. Self-Hosted Kafka — Decision Pending

The spec recommends managed Kafka (Confluent Cloud, Amazon MSK) for Zone A+B.
This is not decided — it is a recommendation. The bank partner may mandate
self-hosted for data residency or regulatory reasons.

**Consequence of self-hosted:**
- Adds broker failure response to on-call responsibilities
- Adds ~2 weeks to infrastructure build timeline (KRaft setup, tuning, runbook)
- Adds NOVA's kafka operations runbook as a required deliverable before pilot

**Decision gate:** confirm managed vs. self-hosted before infrastructure build begins.
This is item 1 on the pre-build checklist. Everything else in Section 4 applies
regardless of deployment model.

### 14.2 GPU Node Availability for Development

GPU nodes (A10G or A100) are expensive. Maintaining two GPU nodes during development
may be cost-prohibitive. The recommended development posture:

- Development environment: CPU inference only (C1_INFERENCE_DEVICE = "cpu")
  Latency on CPU: ~80-120ms (not SLA-compliant; acceptable for development)
- Staging environment: GPU inference enabled (full SLA validation)
- Production: GPU required (SLA enforcement)

**Implication for C1:** C1 must implement a CPU inference path that produces
identical outputs at lower performance. The model weights are the same;
only the device changes. This is a PyTorch/JAX standard capability —
not a new requirement. ARIA must confirm the CPU path is implemented and tested.

### 14.3 Flink Job Topology Changes Require Planned Downtime

Adding new operators, changing parallelism, or modifying C3/C6 job topologies
requires: savepoint → job cancel → restart with new topology.
Typical duration: 2–5 minutes of C3 or C6 unavailability.

**During C6 downtime:**
- No new AML clearances processed
- Decision Engine cannot generate new offers (C6 result absent = hard block)
- In-flight loans continue in their current state (no new actions)
- Kafka consumer lag builds during downtime (processes after C6 restarts)

**During C3 downtime:**
- No new repayment instructions processed
- Active loans remain in MONITORING_ACTIVE state (no repayment actions)
- Settlement signals queue in Kafka (processed after C3 restarts)
- No loan losses expected — signals are not lost, only delayed

**Mitigation:**
1. Schedule Flink job upgrades during low-volume windows (e.g., weekend 02:00-04:00)
2. Decision Engine "MAINTENANCE_WINDOW_ACTIVE" mode:
   Hold new offers for up to 5 minutes during planned C6 Flink restart.
   If C6 unavailable > 5 minutes: transition to hard-block mode (not hold mode).
   This mode must be implemented in the Decision Engine before pilot.
   Flag: NOVA to add MAINTENANCE_WINDOW_ACTIVE to Decision Engine spec.

### 14.4 Load Test Data Quality

Load test Scenarios 1–4 use synthetic pacs.002 data generated from assumed
corridor distributions. Synthetic data will not precisely match real
corridor distributions, rejection code mixes, or entity relationship patterns.

**Consequence:** p50/p99 baselines validated against synthetic distribution may
differ from real-world performance by ±20-30%.

**Mitigation:**
After first 30 days of pilot, re-run Scenario 1 with real corridor distribution
profiles (extracted from anonymized pilot data, anonymized via SHA-256 hashing
of BIC codes). Update baselines in Section 10.3 from "VALIDATED (synthetic)"
to "VALIDATED (production-representative)".

FORGE will not claim production SLA compliance until the production-representative
load test is complete.

---

## 15. VALIDATION REQUIREMENTS

### 15.1 Infrastructure Smoke Tests (Pre-Deployment Gate)

Run immediately after each environment deployment. Must all pass before any
functional testing begins.

```
Kubernetes:
  [ ] All pods in lip-ml, lip-miplo, lip-flink, lip-redis,
      lip-kafka, lip-monitoring reach Running state within 5 minutes
  [ ] All readiness probes pass for all pods
  [ ] Pod anti-affinity confirmed: no two replicas of same component on same node
  [ ] GPU node available: C1 pod scheduled on GPU node; nvidia-smi reports GPU
  [ ] C7 fixed replica count: HPA absent from lip-execution namespace (verified)

Kafka:
  [ ] All 18 topics exist with correct partition count and replication factor
  [ ] All MIPLO producer consumer groups connect successfully
  [ ] lip.decisions.log retention confirmed: 7 years (describe topic output)
  [ ] lip.offers.pending retention confirmed: 60s

Redis:
  [ ] MIPLO Redis Cluster: 3 primary + 3 replica shards in CLUSTER OK state
  [ ] All application pods connect to Redis (redis-cli PING returns PONG)
  [ ] noeviction policy confirmed: maxmemory-policy = noeviction
  [ ] AOF persistence confirmed: appendonly = yes

Flink:
  [ ] C3 Flink cluster: JobManager + 3 TaskManagers in RUNNING state
  [ ] C6 Flink cluster: JobManager + 3 TaskManagers in RUNNING state
  [ ] Flink UI accessible; both jobs visible in RUNNING state
  [ ] Checkpointing active: last checkpoint timestamp updating

Observability:
  [ ] All /metrics endpoints reachable on :9090
  [ ] Prometheus scraping all targets (no "target down" in Prometheus UI)
  [ ] Grafana dashboards loading for all components
  [ ] Jaeger/Tempo: trace ingestion active (test trace visible)
  [ ] DCGM metrics for GPU node appearing in Prometheus
```

### 15.2 End-to-End Integration Test (Pre-Production Gate)

Run after smoke tests pass. Validates full pipeline from pacs.002 to offer.

```
Setup: inject 100 synthetic pacs.002 at 100 TPS for 1 minute (6,000 messages)

  [ ] lip.payments.classified populated: verified (C3 classification running)
  [ ] lip.ml.predictions populated: verified (C1 + C2 inference running)
  [ ] lip.aml.results populated: verified (C6 AML processing running)
  [ ] lip.offers.pending populated: verified (Decision Engine generating offers)
  [ ] (C7 mock) ExecutionConfirmations produced for accepted offers
  [ ] End-to-end trace visible in Jaeger from pacs.002 ingestion to offer publish
  [ ] p50 end-to-end offer generation < 26ms at 100 TPS (warm-up — GPU hot)
  [ ] p99 end-to-end offer generation < 100ms at 100 TPS
  [ ] Kafka consumer lag = 0 across all topics after 2 minutes at 100 TPS
  [ ] Zero CRITICAL alerts firing
  [ ] Zero ERROR-level log entries (only INFO and DEBUG)

Idempotency check:
  [ ] Replay same 6,000 messages (same UETRs) through pipeline
  [ ] Verify: no duplicate LoanOffers per UETR in lip.offers.pending
  [ ] Verify: C6 velocity not double-counted on replay
      (idempotency protection: duplicate UETR in Flink = idempotent processing)
```

### 15.3 Load Tests

```
Run in staging environment after integration tests pass.
Results archived as BPI_LoadTest_Report_{YYYY-MM-DD}.md before sign-off.

  [ ] Scenario 1 (1K TPS baseline): all pass criteria met — report archived
  [ ] Scenario 2 (10K TPS peak): all pass criteria met — report archived
  [ ] Scenario 3 (50K TPS stress): no crash/data loss — report archived
  [ ] Scenario 4 (ramp 1K→50K): breaking point documented — report archived
  [ ] Performance baselines in Section 10.3:
      Updated from HYPOTHESIS to VALIDATED (synthetic) after Scenario 1 passes
  [ ] FORGE signs load test report before production deployment is permitted
```

### 15.4 Chaos Tests

```
Run in staging environment at steady state (Scenario 1 passing).
Results archived as BPI_Chaos_Test_Report_{YYYY-MM-DD}.md before sign-off.

  [ ] CH-01 (Kafka broker failure): passes — no message loss, no duplicate decisions
  [ ] CH-02 (Redis shard failure): passes — CIPHER confirms no fail-open during failover
  [ ] CH-03 (Flink TM failure): passes — consumer lag recovers within 5 minutes
  [ ] CH-04 (GPU node failure): passes — C1 reschedules; no permanent offer loss
  [ ] CH-05 (Network partition): passes — zero data loss; full recovery within 10 minutes
  [ ] CH-06 (Decision Engine restart): passes — no duplicate offers per UETR
  [ ] CH-07 (Memory pressure): passes — no OOMKilled pods; Flink remains RUNNING
  [ ] CH-08 (Clock skew): passes — no offers accepted past true expiry
  [ ] FORGE signs chaos test report before production deployment is permitted
  [ ] CIPHER co-signs CH-02 (fail-safe confirmation) and CH-08 (expiry confirmation)
```

### 15.5 Security Tests

```
Build-time (automated in CI — every commit):
  [ ] Trivy: zero CRITICAL CVEs in all production images — CI enforced
  [ ] Cosign: all images signed by CI identity — CI enforced
  [ ] Secret scanner: no secrets detected in codebase — CI enforced (Trivy + GitLeaks)

Deployment-time (automated in admission control):
  [ ] Unsigned image: admission controller rejects pod — tested on staging
  [ ] Non-registry image: admission controller rejects — tested on staging
  [ ] Mutable tag (:latest): admission controller rejects — tested on staging

Network policy tests (run on staging):
  [ ] Zone A → Zone C direct: blocked (no path from lip-ml to lip-execution)
  [ ] Zone B → Zone C direct: blocked (no path from lip-miplo to lip-execution)
  [ ] lip-ml → lip-redis direct: blocked (C1/C2 do not access MIPLO Redis)
  [ ] All blocked paths confirmed by network policy test (Netpol-verify or equivalent)

Container security (run on staging):
  [ ] Exec into distroless container: fails (no shell — confirmed)
  [ ] Read-only root filesystem: verified (write attempt in container fails)
  [ ] Non-root user: verified (id returns nonroot user in all containers)

Secret audit (run quarterly):
  [ ] No secrets in any Git commit (full history scan — GitLeaks)
  [ ] No secrets in any Kubernetes ConfigMap (kubectl get cm -A -o yaml scan)
  [ ] KMS audit log: no access outside business hours (CIPHER review)
  [ ] SBOM: all images have attached SBOM attestation in registry
```

---

## 16. AUDIT GATE 2.4 CHECKLIST

Gate passes when ALL items are checked.
**FORGE signs.** NOVA verifies Kafka/Flink.
REX verifies DORA resilience requirements. CIPHER verifies security hardening.

### Kubernetes Infrastructure
- [ ] All three node pools deployed with specifications from Section 3.1
- [ ] Pod anti-affinity: requiredDuringScheduling on all multi-replica deployments
- [ ] Resource requests AND limits set on all production pods — BestEffort prohibited
- [ ] C7 fixed replica count: HPA explicitly disabled on lip-execution namespace
- [ ] GPU node taints and tolerations: C1 exclusively on GPU nodes — verified
- [ ] Pod Security Standards: restricted enforced on all namespaces
- [ ] NetworkPolicy: default-deny-all applied; explicit allows only — verified

### Apache Kafka
- [ ] All 18 topics created with correct partition counts (Section 4.3)
- [ ] Replication factor = 3 on all topics — verified
- [ ] min.insync.replicas = 2 on all topics — verified
- [ ] Producer idempotence = true on all MIPLO producers — verified
- [ ] Consumer isolation.level = read_committed on all consumers — verified
- [ ] Partition key = UETR on all payment topics — custom partitioner tested
- [ ] lip.decisions.log: 7-year retention confirmed (describe topic output archived)
- [ ] lip.offers.pending: 60-second retention confirmed

### Apache Flink
- [ ] C3 and C6 Flink clusters deployed separately (no shared cluster)
- [ ] Flink HA: standby JobManager active on both clusters
- [ ] Flink HA failover tested: < 30s promotion (CH-03 analog)
- [ ] Checkpointing: 30s interval, RocksDB backend, 3 checkpoints retained
- [ ] TaskManagers: anti-affinity confirmed (3 TMs on 3 different nodes)
- [ ] Savepoint procedure: tested and documented
- [ ] Flink full cluster failure recovery: tested (Section 5.3 procedure)

### Redis
- [ ] MIPLO Redis: 6-shard cluster (3+3) deployed and CLUSTER OK
- [ ] noeviction policy confirmed on MIPLO Redis
- [ ] noeviction policy confirmed on ELO Redis (bank confirms)
- [ ] AOF persistence enabled on both clusters
- [ ] TLS 1.3 + AUTH token on all connections — verified
- [ ] Redis failover test: < 10s shard promotion — CH-02 passes
- [ ] Memory headroom: < 70% used at 1K TPS steady state
- [ ] Key expiry monitoring: alerting configured for TTL anomalies

### GPU / C1
- [ ] GPU node pool: deployed and nvidia-smi reports GPU available
- [ ] C1 pod: scheduled on GPU node (not CPU pool)
- [ ] C1 inference on GPU: p50 < 8ms, p99 < 30ms — Scenario 1 load test verified
- [ ] CPU inference fallback: implemented and tested (C1_INFERENCE_DEVICE=cpu)
- [ ] GPU utilization alerts configured (< 20% and > 90% thresholds)
- [ ] DCGM metrics reporting in Prometheus

### CI/CD & Image Security
- [ ] Distroless base image on all Go components — verified
- [ ] Trivy CRITICAL CVE = build failure — enforced in CI
- [ ] Cosign signing: all images signed by CI OIDC identity
- [ ] Admission controller: unsigned images rejected — tested on staging
- [ ] SBOM generated and attached for all production images
- [ ] ArgoCD GitOps: all namespaces reconciled; zero drift
- [ ] No manual kubectl apply to production — ArgoCD audit confirms
- [ ] Secret scanner (GitLeaks or Trivy): no secrets in Git — CI enforced

### Load Tests (FORGE sign-off required)
- [ ] Scenario 1 (1K TPS): all pass criteria met — BPI_LoadTest_Report archived
- [ ] Scenario 2 (10K TPS): all pass criteria met — report archived
- [ ] Scenario 3 (50K TPS): no crash/data loss — report archived
- [ ] Scenario 4 (ramp): breaking point documented — report archived
- [ ] Performance baselines updated from HYPOTHESIS to VALIDATED
- [ ] FORGE signature on load test report

### Chaos Tests (FORGE + CIPHER sign-off required)
- [ ] CH-01 through CH-08: all pass — BPI_Chaos_Test_Report archived
- [ ] CH-02: no fail-open during Redis shard failover — CIPHER confirms
- [ ] CH-08: no offers funded past true expiry under clock skew — C7 confirms
- [ ] FORGE signature on chaos test report
- [ ] CIPHER co-signature on CH-02 and CH-08

### Observability
- [ ] All components exposing /metrics on :9090 — verified
- [ ] Prometheus scraping all targets; zero "target down"
- [ ] Thanos: 13-month retention configured
- [ ] Grafana: dashboards for all components loading with data
- [ ] Jaeger/Tempo: full trace from pacs.002 to offer visible
- [ ] DCGM (GPU) metrics in Prometheus
- [ ] All CRITICAL alerts have PagerDuty routing — tested (sent test alert)
- [ ] All HIGH alerts have Slack routing — tested

### Security
- [ ] All network policy blocked paths confirmed blocked — test evidence archived
- [ ] Zero direct connectivity Zone A+B to Zone C
- [ ] Distroless containers: no shell exec possible — confirmed
- [ ] Read-only root filesystem on all containers — confirmed
- [ ] Non-root user in all containers — confirmed
- [ ] Secret rotation: automated and tested (KMS, Redis AUTH, Kafka SASL)
- [ ] No PII in any log output — staging log audit passed
- [ ] KMS access audit: CIPHER monthly review process confirmed active

### DORA Art.30 Resilience (REX sign-off required)
- [ ] RTO < 30 minutes: documented per scenario; chaos test evidence supports claim
- [ ] RPO < 30 seconds: Flink checkpoint interval documented as RPO definition
- [ ] Recovery playbook written for each CH-01 through CH-08 failure scenario
- [ ] Third-party dependency register: Kafka vendor, Redis, GPU vendor,
      managed services — documented with version + SLA references
- [ ] ICT third-party risk register: bank has reviewed and accepted all
      Bridgepoint-managed infrastructure dependencies
- [ ] Major incident definition and escalation path documented

---

*C5 Build Specification v1.0 — Part 2 of 2 complete.*
*Audit Gate 2.4 checklist locked.*
*Performance baselines in Section 10.3 remain HYPOTHESIS until load tests run.*
*Open item requiring decision before build: Section 14.1 (Managed vs. Self-hosted Kafka).*
*Open item requiring Decision Engine work: Section 14.3 (MAINTENANCE_WINDOW_ACTIVE mode — NOVA).*
*Next: C7 Bank Deployment Guide (NOVA leads), then Provisional-Spec v5.2 (LEX).*
*Internal use only. Stealth mode active. March 4, 2026.*
*Lead: FORGE | Support: NOVA, ARIA, REX, CIPHER*
