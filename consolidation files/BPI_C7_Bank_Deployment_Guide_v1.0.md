# BRIDGEPOINT INTELLIGENCE INC.
## C7 EMBEDDED EXECUTION AGENT — BANK DEPLOYMENT GUIDE v1.0
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** NOVA — Payments Infrastructure Engineer
**Support:** FORGE (infrastructure validation), CIPHER (security onboarding),
             REX (compliance gates), LEX (claim language in bank-facing materials)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

---

## TABLE OF CONTENTS

1.  Purpose & Audience
2.  Overview: What C7 Does and Does Not Do
    2.1 What C7 Does
    2.2 What C7 Does Not Do
3.  Prerequisites Checklist
    3.1 Infrastructure Prerequisites
    3.2 KMS Prerequisites
    3.3 Compliance Prerequisites
4.  Bank Kafka Topic Setup
5.  C7 Container Image
    5.1 Image Delivery
    5.2 Signature Verification (Pre-Deployment Gate)
    5.3 Image Properties
6.  Redis Deployment (Bank-Managed)
    6.1 Deployment Specification
    6.2 Redis Key Namespace for C7
    6.3 Redis Health Validation
7.  Kubernetes Deployment
    7.1 Namespace Setup
    7.2 Service Account and RBAC
    7.3 ConfigMap: Core Configuration
    7.4 ConfigMap: AML Thresholds
    7.5 Deployment Manifest
8.  Core Banking Adapter (CBA) Specification
    8.1 CBA API Contract
    8.2 CBA Latency Requirements
    8.3 CBA Integration Validation
9.  Network Policy
10. Kill Switch Operations
    10.1 Global Kill Switch
    10.2 Corridor Kill Switch
    10.3 Emergency Entity Block
11. Human Override Procedure
    11.1 When Override Is Permitted
    11.2 Override API
12. Monitoring & Alerting (Bank-Side)
    12.1 Required Metrics
    12.2 Required Alerts
    12.3 Compliance Monitoring
13. Operational Runbook
    13.1 C7 Pod Restart (Planned)
    13.2 Unplanned Pod Failure Recovery
    13.3 CBA Degradation Response
    13.4 Loan Overdue Response
14. Pre-Go-Live Validation Checklist
15. Escalation and Support
    15.1 Escalation Matrix
    15.2 What to Provide When Contacting Bridgepoint
16. Appendix: Salt Derivation CLI Utility

---

## 1. PURPOSE & AUDIENCE

This guide is written for the bank's infrastructure, integration, and compliance
teams responsible for deploying and operating Component 7 (C7) — the Embedded
Execution Agent — within the bank's own environment.

C7 is a bank-side software component. Bridgepoint Intelligence supplies the
container image, the configuration schema, and this guide. The bank owns the
deployment, the infrastructure it runs on, the KMS keys it uses, and every
transaction it executes. Bridgepoint's intelligence engine (MIPLO) makes the
decision. The bank's C7 executes it. The separation is absolute and permanent.

**This guide is not for Bridgepoint staff. It is for bank staff.**
Bridgepoint personnel have no access to Zone C (ELO). They cannot see C7 logs,
Redis state, KMS keys, or transaction execution records. All of that is
bank-owned.

**Audience:**
- Bank infrastructure / DevOps team (Sections 3–7)
- Bank integration / payments team (Sections 8–10)
- Bank compliance / AML team (Sections 11–12)
- Bank operations / on-call team (Sections 13–15)

---

## 2. OVERVIEW: WHAT C7 DOES AND DOES NOT DO

### 2.1 What C7 Does

```
C7 receives LoanOffers from Bridgepoint's MIPLO engine via Kafka.
For each individual UETR, C7:

  1. Validates the LoanOffer (HMAC integrity, expiry, AML clearance)
  2. Enforces hard block signals from Bridgepoint's C6 AML engine
  3. Calls the bank's Core Banking Adapter to fund the bridge loan
  4. Writes an immutable, HMAC-signed decision log entry
  5. Publishes an ExecutionConfirmation to MIPLO
  6. Monitors for settlement signals (pacs.002 final, camt.054)
     via Bridgepoint's C3 Repayment Engine
  7. On settlement signal: calls Core Banking Adapter to repay the loan
  8. Writes repayment log entry; publishes RepaymentConfirmation

Everything C7 executes is traceable to a specific individual UETR
and a specific LoanOffer signed by Bridgepoint's MIPLO engine.
C7 never makes a credit decision. It only executes decisions
that MIPLO has already made and cryptographically signed.
```

### 2.2 What C7 Does Not Do

```
C7 does NOT:
  Assess credit risk            — that is C2 (MIPLO)
  Predict payment failure       — that is C1 (MIPLO)
  Run AML screening             — that is C6 (MIPLO); C7 enforces C6 output
  Classify commercial disputes  — that is C4 (embedded in C7, advisory only)
  Generate LoanOffers           — that is the Decision Engine (MIPLO)
  Contact SWIFT/FedNow/RTP/SEPA — C7 calls the bank's Core Banking Adapter only
  Store raw BIC codes           — all entity references are SHA-256 hashed
  Send data to Bridgepoint      — C7 has zero outbound to MIPLO systems
                                  (only to MIPLO Kafka topics — 5 specified topics)
```

---

## 3. PREREQUISITES CHECKLIST

The following must be confirmed complete before C7 deployment begins.
None of these items can be skipped.
**[BANK]** = bank's responsibility.
**[BPI]** = confirmed by Bridgepoint before image delivery.

### 3.1 Infrastructure Prerequisites [BANK]

```
[ ] Kubernetes cluster in bank environment
      Version     : 1.28+
      Namespace   : lip-execution (create before deployment)
      Nodes       : >= 2 nodes, >= 4 vCPU / >= 8GB RAM per node
      Anti-affinity: 2 C7 replicas must land on 2 different nodes

[ ] Redis Cluster in bank environment (Section 6)
      Mode        : Redis Cluster (NOT standalone — standalone has no HA)
      Version     : Redis 7.2+
      Shards      : 3 primary + 3 replica minimum
      Memory      : >= 16GB per shard
      Policy      : noeviction — MANDATORY
      TLS         : TLS 1.3 required
      Persistence : AOF enabled (appendonly yes)

[ ] Bank Kafka cluster available
      Version     : Kafka 3.x (KRaft mode preferred)
      Topics      : 8 topics required (Section 4)
      Replication : factor = 3 on all C7 topics
      Auth        : SASL/SCRAM-SHA-512 enabled

[ ] Private container registry accessible from Kubernetes cluster
      C7 image digest provided by Bridgepoint (Section 5)
      Image pull credentials configured in lip-execution namespace

[ ] Outbound Kafka connectivity from lip-execution to MIPLO
      C7 consumes from : lip.offers.pending        (MIPLO Kafka)
      C7 consumes from : lip.repayment.instructions (MIPLO Kafka)
      C7 produces to   : lip.loans.funded           (MIPLO Kafka)
      C7 produces to   : lip.repayment.confirmations (MIPLO Kafka)
      C7 produces to   : lip.decisions.log           (MIPLO Kafka)
      Protocol         : TLS 1.3, port 9093 (or bank-agreed port)
      Auth             : SASL/SCRAM-SHA-512 (credentials from Bridgepoint)
      No other outbound from Zone C to Bridgepoint — only these 5 topics

[ ] Core Banking Adapter (CBA) deployed and reachable from lip-execution
      Bank-built component wrapping bank's core banking system
      C7 calls CBA API — never core banking directly
      CBA API specification: Section 8
      CBA must be deployed and passing health checks before C7 deployment
```

### 3.2 KMS Prerequisites [BANK]

```
[ ] Bank KMS available and reachable from lip-execution namespace
      Supported: AWS KMS, Azure Key Vault, GCP Cloud KMS, HashiCorp Vault
      HSM-backed: required for production

[ ] Two key slots provisioned in KMS before C7 deployment:

    Slot 1 — C7 HMAC Key
      Algorithm : HMAC-SHA-256
      Purpose   : Signs all C7 DecisionLogEntry records
      Label     : "lip-c7-hmac-key"
      Rotation  : Quarterly
      Access    : c7-execution-agent service account only

    Slot 2 — C6 SHA-256 Salt
      Algorithm : AES-256 (raw bytes)
      Purpose   : C6 entity hash salt (used by C7 for hash verification)
      Label     : "lip-c6-entity-salt"
      Rotation  : Quarterly — coordinate with Bridgepoint
                  (rotation resets C6 velocity windows — joint scheduling required)
      Access    : c7-execution-agent service account only

[ ] External Secrets Operator (ESO) deployed
      Syncs from bank KMS to Kubernetes Secrets in lip-execution
      ESO service account: read-only access to two key slots above only

[ ] KMS key access audit logging enabled
      All accesses logged (timestamp, service account, operation type)
      Bank security team reviews monthly
```

### 3.3 Compliance Prerequisites [BANK + BPI]

```
[ ] Bank AML officer has reviewed C6 AML Velocity Module design
      Specifically: velocity thresholds, sanctions methodology,
      SAR queue publishing (C6 Spec Sections 5–7)

[ ] Bank SAR processing system ready to consume lip.aml.sar.queue
      This is a MIPLO Kafka topic produced by Bridgepoint's C6 engine
      Bank compliance system must be a consumer before go-live

[ ] Bank AML officer has set and signed off initial velocity thresholds
      (Section 7.4 ConfigMap — AML thresholds require AML officer sign-off)

[ ] Bank has assessed applicable automated lending regulations:
      EU   : EU AI Act Article 6 (high-risk AI system assessment)
      US   : SR 11-7 (model risk management)
      CA   : OSFI B-10 (third-party risk management)
      SG   : MAS guidance on automated lending
      UAE  : CBUAE guidance on AI in financial services

[ ] DORA Art.30 third-party register updated (EU banks only):
      Bridgepoint Intelligence Inc. added as ICT third-party service provider
      Description: "AI-based payment failure detection and bridge loan
      decision engine — bank executes, Bridgepoint decides"

[ ] Licensing and data processing agreements executed [SUSPENDED IN STEALTH]
      Placeholder: Technology Licensing Agreement, Data Processing Agreement (GDPR Art.28)
```

---

## 4. BANK KAFKA TOPIC SETUP

C7 requires 8 topics in the bank's local Kafka cluster (Zone C).
These are separate from MIPLO Kafka topics.

```
Topic                         Partitions  Retention  Purpose
c7.offer.inbox                12          60s        LoanOffers mirrored from MIPLO
c7.offer.processed            12          24h        Processed offer audit trail
c7.loan.active                12          30d        Active loan state events
c7.repayment.inbox            12          30d        Repayment instructions from MIPLO
c7.repayment.processed        12          30d        Repayment completion audit
c7.cba.requests               12          24h        Core Banking Adapter requests
c7.cba.responses              12          24h        Core Banking Adapter responses
c7.audit.local                12          7 years    Local HMAC-signed audit log copy

Apply to all 8 topics:
  replication.factor  = 3
  min.insync.replicas = 2
  compression.type    = lz4

c7.audit.local special handling:
  Retention: 7 years (DORA Art.30 + bank audit obligation)
  Local copy of lip.decisions.log (C7 writes to both simultaneously)
  If MIPLO Kafka becomes unavailable: local audit copy remains intact
  Archive to cold storage after 90 days hot retention
  Accessible to bank auditors on request (no Bridgepoint access)

Partition key for all C7 topics: UETR
  Guarantees: all events for a given individual UETR in same partition
  Enforces: in-order processing per individual payment through C7 state machine

Bank Kafka consumer groups (create before C7 deployment):
  c7-offer-processor      reads c7.offer.inbox
  c7-repayment-processor  reads c7.repayment.inbox
```

---

## 5. C7 CONTAINER IMAGE

### 5.1 Image Delivery

```
Bridgepoint delivers per release:
  Image path    : {bank-private-registry}/bridgepoint/c7-execution-agent
  Image tag     : v{major}.{minor}.{patch}
  Image digest  : sha256:{64-char-hex}  ← ALWAYS pin to digest, not tag
  Cosign bundle : signature bundle for admission controller verification
  Release notes : changelog, schema changes, config changes
  SBOM          : CycloneDX format (dependency inventory)
  Trivy report  : zero CRITICAL CVEs confirmed by Bridgepoint before delivery

Transfer path:
  Bridgepoint pushes to shared staging registry
  Bank pulls + re-pushes to bank private registry
  Bank verifies Cosign signature before re-push (Section 5.2)
  Bank admission controller re-verifies on every pod schedule
```

### 5.2 Signature Verification (Pre-Deployment Gate)

```
Before deploying any C7 image to production:

Step 1 — Pull image:
  docker pull {staging-registry}/bridgepoint/c7:{version}@sha256:{digest}

Step 2 — Verify Cosign signature:
  cosign verify     --certificate-identity=https://github.com/bridgepoint-intelligence/lip/.github/workflows/release.yml     --certificate-oidc-issuer=https://token.actions.githubusercontent.com     {staging-registry}/bridgepoint/c7:{version}@sha256:{digest}

  Expected output: "Verified OK"
  If verification fails: DO NOT deploy. Contact Bridgepoint immediately.

Step 3 — Verify SBOM attestation:
  cosign verify-attestation --type cyclonedx     {staging-registry}/bridgepoint/c7:{version}@sha256:{digest}

Step 4 — Re-push to bank registry:
  docker tag {staging-registry}/bridgepoint/c7:{version}              {bank-registry}/lip/c7:{version}
  docker push {bank-registry}/lip/c7:{version}

Step 5 — Admission dry-run:
  Deploy test pod (dry-run) — verify bank admission controller accepts image
  kubectl apply --dry-run=server -f c7-test-pod.yaml
```

### 5.3 Image Properties

```
Base image    : gcr.io/distroless/static-debian12 (no shell, no package manager)
User          : nonroot (UID 65532)
Filesystem    : read-only root
Ports         : 8080 (HTTP API + health probes), 9090 (Prometheus /metrics)
Entrypoint    : /app/c7-agent
No shell      : kubectl exec into production C7 container is not possible.
                This is intentional (distroless base). It is not a bug.
                Development debugging: use ephemeral debug containers.
```

---

## 6. REDIS DEPLOYMENT (BANK-MANAGED)

### 6.1 Deployment Specification

```
Redis Cluster: 6 nodes (3 primary + 3 replica)

Helm install (recommended):
  helm repo add bitnami https://charts.bitnami.com/bitnami
  helm install lip-redis bitnami/redis-cluster     --namespace lip-redis-c7     --set cluster.nodes=6     --set cluster.replicas=1     --set redis.maxmemoryPolicy=noeviction     --set persistence.enabled=true     --set tls.enabled=true     --set auth.enabled=true     --set auth.existingSecret=lip-redis-auth     --set persistence.storageClass={bank-storage-class}

Manual redis.conf (if not using Helm):
  maxmemory-policy  noeviction
  appendonly        yes
  appendfsync       everysec
  save              60 1
  tls-port          6380
  tls-cert-file     /certs/redis.crt
  tls-key-file      /certs/redis.key
  tls-ca-cert-file  /certs/ca.crt
  requirepass       {AUTH token from KMS via ESO}

Why noeviction is mandatory:
  C7 holds loan execution state in Redis.
  If Redis evicts a loan key under memory pressure, C7's state machine
  loses track of an in-flight loan. That loan may never be repaid.
  noeviction causes write errors on full memory — C7 detects this and
  transitions to hard-block mode. That is the correct failure behavior.
  Do not change to any other eviction policy.
```

### 6.2 Redis Key Namespace for C7

```
All C7 Redis keys prefixed "c7:" — do not modify key structure.

Active loan state:
  "c7:loan:{uetr}"                   Hash
    funded_at, amount_usd, fee_bps, maturity_utc,
    status, loan_reference, hashed_borrower_id, offer_id

Idempotency guards:
  "c7:idem:offer:{offer_id}"         String: "PROCESSED" | "DECLINED"
    TTL: 24h
  "c7:idem:repay:{uetr}"             String: "PROCESSED"
    TTL: 35d (30d loan term + 5d buffer)

Kill switch:
  "c7:kill:global"                   String: "ACTIVE" (presence = active)
  "c7:kill:corridor:{corridor_id}"   String: "ACTIVE"

Emergency AML blocks:
  "c7:emergency:blocks"              Set: hashed_entity_ids (no TTL)

Human override records:
  "c7:override:{uetr}"               Hash: operator_id, reason, timestamp,
                                          approved_by, original_decision
    TTL: 90d

Clock skew detection:
  "c7:clock:skew_detected"           String: "TRUE"
    TTL: 1h (auto-clears if clock re-syncs)

All entity references: SHA-256 hashed — no raw BIC codes stored anywhere.
```

### 6.3 Redis Health Validation

```
Before C7 deployment, run all five checks:

Check 1 — Cluster health:
  redis-cli -h {endpoint} -p 6380 --tls             --cert {cert} --key {key} --cacert {ca}             -a {auth} CLUSTER INFO
  Expected: cluster_state:ok
            cluster_slots_assigned:16384
            cluster_known_nodes:6

Check 2 — Eviction policy:
  CONFIG GET maxmemory-policy
  Expected: noeviction

Check 3 — AOF persistence:
  CONFIG GET appendonly
  Expected: yes

Check 4 — Write + read:
  SET c7:healthcheck "ok" EX 10
  GET c7:healthcheck
  Expected: "ok"

Check 5 — Failover (pre-production only):
  Kill one primary shard pod
  Verify: CLUSTER INFO shows cluster_state:ok within 10 seconds
  Verify: C7 logs show hard_block=true during ~10s failover window
  Restore pod; verify cluster returns to 6 nodes in ok state
```

---

## 7. KUBERNETES DEPLOYMENT

### 7.1 Namespace Setup

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: lip-execution
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
    owner: bank-infrastructure
    component: lip-elo
```

### 7.2 Service Account and RBAC

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: c7-execution-agent
  namespace: lip-execution
  annotations:
    # AWS EKS IRSA (adjust for Azure/GCP KMS as needed):
    eks.amazonaws.com/role-arn: arn:aws:iam::{account}:role/lip-c7-kms-role
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: c7-execution-agent
  namespace: lip-execution
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get"]
    resourceNames:
      - lip-c7-hmac-key
      - lip-c6-entity-salt
      - lip-redis-auth
      - lip-kafka-sasl-c7
      - lip-miplo-kafka-sasl
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "watch"]
    resourceNames:
      - lip-c7-config
      - lip-c7-aml-thresholds
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: c7-execution-agent
  namespace: lip-execution
subjects:
  - kind: ServiceAccount
    name: c7-execution-agent
    namespace: lip-execution
roleRef:
  kind: Role
  name: c7-execution-agent
  apiGroup: rbac.authorization.k8s.io
```

### 7.3 ConfigMap: Core Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lip-c7-config
  namespace: lip-execution
data:
  # MIPLO Kafka (Bridgepoint-managed)
  MIPLO_KAFKA_BOOTSTRAP:          "{miplo-kafka-bootstrap-servers}"
  MIPLO_KAFKA_TOPIC_OFFERS:       "lip.offers.pending"
  MIPLO_KAFKA_TOPIC_REPAYMENTS:   "lip.repayment.instructions"
  MIPLO_KAFKA_TOPIC_FUNDED:       "lip.loans.funded"
  MIPLO_KAFKA_TOPIC_REPAY_CONF:   "lip.repayment.confirmations"
  MIPLO_KAFKA_TOPIC_DECISIONS:    "lip.decisions.log"

  # Bank-local Kafka (Zone C)
  LOCAL_KAFKA_BOOTSTRAP:          "{bank-local-kafka-bootstrap}"
  LOCAL_KAFKA_TOPIC_AUDIT:        "c7.audit.local"

  # Redis
  REDIS_CLUSTER_ENDPOINTS:        "{node1}:6380,{node2}:6380,{node3}:6380"
  REDIS_TLS_ENABLED:              "true"

  # Core Banking Adapter
  CBA_ENDPOINT:                   "http://core-banking-adapter.{ns}.svc:8080"
  CBA_TIMEOUT_MS:                 "5000"
  CBA_RETRY_MAX:                  "3"
  CBA_RETRY_BACKOFF_MS:           "200"

  # Offer processing
  OFFER_EXPIRY_GRACE_MS:          "500"
  CLOCK_SKEW_THRESHOLD_MS:        "2000"
  KILL_SWITCH_CHECK_INTERVAL_MS:  "100"
  DECISION_LOG_LOCAL_COPY:        "true"

  # Logging
  LOG_LEVEL:                      "INFO"
  LOG_FORMAT:                     "json"
```

### 7.4 ConfigMap: AML Thresholds

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lip-c7-aml-thresholds
  namespace: lip-execution
  annotations:
    last-reviewed-by: "{aml-officer-name}"
    last-reviewed-at: "{ISO-8601-date}"
    # POLICY: every change to this ConfigMap requires AML officer sign-off
    # and a pod restart. Changes are logged to lip.decisions.log automatically.
data:
  # Dollar velocity thresholds (USD)
  VELOCITY_DOLLAR_24H_HARD_BLOCK:   "5000000"
  VELOCITY_DOLLAR_7D_HARD_BLOCK:    "15000000"
  VELOCITY_DOLLAR_30D_HARD_BLOCK:   "40000000"
  VELOCITY_DOLLAR_24H_REVIEW:       "2000000"

  # Count velocity thresholds
  VELOCITY_COUNT_24H_HARD_BLOCK:    "50"
  VELOCITY_COUNT_7D_HARD_BLOCK:     "200"
  VELOCITY_COUNT_24H_REVIEW:        "20"

  # Beneficiary concentration (percentage 0-100)
  BENEFICIARY_CONC_HARD_BLOCK:      "15"
  BENEFICIARY_CONC_REVIEW:          "8"

  # ML anomaly escalation
  # WARNING: keep both "false" at pilot launch.
  # ANOMALY_HARD_BLOCK_ENABLED: enable only after ARIA confirms
  #   Isolation Forest is retrained on real pilot data (C6 Spec Section 8.3).
  # STRUCTURING_HARD_BLOCK_ENABLED: enable only after AML officer review
  #   of false positive rate post-pilot.
  ANOMALY_HARD_BLOCK_ENABLED:       "false"
  STRUCTURING_HARD_BLOCK_ENABLED:   "false"
```

### 7.5 Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: c7-execution-agent
  namespace: lip-execution
  labels:
    app: c7-execution-agent
    version: v1.0.0
spec:
  replicas: 2
  # NO HPA — fixed replica count. See C5 Spec Section 3.5.
  # HPA is blocked by Kyverno policy on lip-execution namespace.
  selector:
    matchLabels:
      app: c7-execution-agent
  template:
    metadata:
      labels:
        app: c7-execution-agent
        version: v1.0.0
    spec:
      serviceAccountName: c7-execution-agent

      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: c7-execution-agent
              topologyKey: kubernetes.io/hostname

      containers:
        - name: c7-agent
          image: {bank-registry}/lip/c7:{version}@sha256:{digest}
          imagePullPolicy: Always

          ports:
            - name: api
              containerPort: 8080
            - name: metrics
              containerPort: 9090

          envFrom:
            - configMapRef:
                name: lip-c7-config
            - configMapRef:
                name: lip-c7-aml-thresholds

          volumeMounts:
            - name: kms-secrets
              mountPath: /secrets
              readOnly: true
            - name: kafka-certs
              mountPath: /certs/kafka
              readOnly: true
            - name: redis-certs
              mountPath: /certs/redis
              readOnly: true

          resources:
            requests:
              cpu: "1"
              memory: "4Gi"
            limits:
              cpu: "2"
              memory: "8Gi"

          securityContext:
            runAsNonRoot: true
            runAsUser: 65532
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            seccompProfile:
              type: RuntimeDefault

          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 3

          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3

          startupProbe:
            httpGet:
              path: /health/startup
              port: 8080
            failureThreshold: 12
            periodSeconds: 5
            # 60 seconds total startup time (model load + Redis/Kafka connect)

      volumes:
        - name: kms-secrets
          secret:
            secretName: lip-c7-kms-secrets
            defaultMode: 0400
        - name: kafka-certs
          secret:
            secretName: lip-kafka-certs
            defaultMode: 0400
        - name: redis-certs
          secret:
            secretName: lip-redis-certs
            defaultMode: 0400

      imagePullSecrets:
        - name: bank-registry-credentials
```

---

## 8. CORE BANKING ADAPTER (CBA) SPECIFICATION

C7 calls the bank's Core Banking Adapter. The bank builds and owns the CBA.
C7 never calls the core banking system directly.

### 8.1 CBA API Contract

```
Base URL: {CBA_ENDPOINT} from ConfigMap

ENDPOINT 1 — Fund Bridge Loan

  POST /v1/bridge-loans/fund
  Content-Type: application/json
  Authorization: Bearer {bank-internal-token}

  Request:
  {
    "loan_reference"      : "BPI-{uetr}-{timestamp}",
    "uetr"                : "{individual-uetr}",
    "hashed_borrower_id"  : "{sha256-hash}",
    "amount_usd"          : 125000.00,
    "fee_bps"             : 325,
    "maturity_utc"        : "2026-04-04T14:32:00Z",
    "corridor"            : "USD-EUR",
    "funded_account"      : "{bank-internal-account-reference}",
    "idempotency_key"     : "{offer_id}"
  }

  Success response (HTTP 200):
  {
    "status"              : "FUNDED",
    "loan_reference"      : "BPI-{uetr}-{timestamp}",
    "bank_transaction_id" : "{bank-internal-tx-id}",
    "funded_at_utc"       : "2026-03-04T22:15:00.123Z",
    "funded_amount_usd"   : 125000.00
  }

  Failure response (HTTP 422):
  {
    "status"              : "REJECTED",
    "rejection_code"      : "{bank-code}",
    "rejection_reason"    : "INSUFFICIENT_NOSTRO_BALANCE"
                          | "ACCOUNT_FROZEN"
                          | "COMPLIANCE_HOLD"
                          | "TECHNICAL_ERROR"
                          | "DUPLICATE_IDEMPOTENCY_KEY"
  }

  Idempotency requirement (MANDATORY):
    Same idempotency_key received twice -> HTTP 200 with original FUNDED response
    Not HTTP 422. This handles C7 retries without double-funding.
    If the CBA cannot guarantee idempotency: go-live is blocked.

ENDPOINT 2 — Execute Repayment

  POST /v1/bridge-loans/repay
  Content-Type: application/json

  Request:
  {
    "loan_reference"       : "BPI-{uetr}-{timestamp}",
    "uetr"                 : "{individual-uetr}",
    "repayment_amount_usd" : 125406.25,
    "fee_amount_usd"       : 406.25,
    "principal_amount_usd" : 125000.00,
    "settlement_signal"    : "PACS002_FINAL" | "CAMT054" | "STATISTICAL",
    "settlement_uetr"      : "{settlement-uetr}",
    "idempotency_key"      : "REPAY-{loan_reference}"
  }

  Success response (HTTP 200):
  {
    "status"               : "REPAID",
    "loan_reference"       : "BPI-{uetr}-{timestamp}",
    "bank_transaction_id"  : "{bank-internal-tx-id}",
    "repaid_at_utc"        : "2026-03-05T14:32:00.456Z",
    "repaid_amount_usd"    : 125406.25
  }

  Failure response (HTTP 422):
  {
    "status"               : "REPAYMENT_FAILED",
    "failure_code"         : "ACCOUNT_CLOSED"
                           | "INSUFFICIENT_FUNDS"
                           | "TECHNICAL_ERROR"
  }
```

### 8.2 CBA Latency Requirements

```
CBA is called synchronously in the C7 funding critical path.

Required performance:
  p50  : < 20ms
  p99  : < 100ms
  Timeout: CBA_TIMEOUT_MS = 5000ms (configurable)

On timeout:
  C7 treats as CBA_TIMEOUT
  Loan transitions to FUNDING_FAILED
  ExecutionConfirmation.status = "DECLINED" (not retried)
  Idempotency_key prevents re-fund if bank system eventually processes

Bank must ensure:
  CBA >= 2 replicas with load balancer (single replica = single point of failure)
  CBA >= 99.9% availability during agreed operating hours
  Idempotent responses on all endpoints (non-negotiable)
```

### 8.3 CBA Integration Validation

```
Run before C7 deployment. All must pass.

  [ ] Fund endpoint — success path:
      Valid loan_reference -> HTTP 200, bank_transaction_id present

  [ ] Fund endpoint — idempotency:
      Duplicate idempotency_key -> HTTP 200 (same bank_transaction_id)
      NOT HTTP 422

  [ ] Fund endpoint — insufficient balance:
      Simulate insufficient nostro -> HTTP 422,
      rejection_reason = "INSUFFICIENT_NOSTRO_BALANCE"

  [ ] Repay endpoint — success path:
      Valid loan_reference -> HTTP 200,
      repaid_amount_usd = principal + fee (arithmetic verified)

  [ ] Repay endpoint — idempotency:
      Duplicate idempotency_key -> HTTP 200 (idempotent)

  [ ] CBA latency under load:
      k6 script, 100 virtual users, 5 minutes
      p50 < 20ms, p99 < 100ms — must pass before C7 load testing

  [ ] CBA unreachable simulation:
      Kill CBA pods; send fund request
      Verify: C7 transitions to FUNDING_FAILED (not FUNDING_RETRY loop)
```

---

## 9. NETWORK POLICY

Apply all policies after namespace creation, before C7 deployment.

```yaml
# Policy 1: Default deny-all
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: lip-execution
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
# Policy 2: C7 egress to MIPLO Kafka (Bridgepoint)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: c7-to-miplo-kafka
  namespace: lip-execution
spec:
  podSelector:
    matchLabels:
      app: c7-execution-agent
  policyTypes: [Egress]
  egress:
    - to:
        - ipBlock:
            cidr: "{miplo-kafka-ip}/32"
      ports:
        - protocol: TCP
          port: 9093
---
# Policy 3: C7 egress to bank-local Kafka
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: c7-to-local-kafka
  namespace: lip-execution
spec:
  podSelector:
    matchLabels:
      app: c7-execution-agent
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: lip-kafka-local
      ports:
        - protocol: TCP
          port: 9093
---
# Policy 4: C7 egress to Redis
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: c7-to-redis
  namespace: lip-execution
spec:
  podSelector:
    matchLabels:
      app: c7-execution-agent
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: lip-redis-c7
      ports:
        - protocol: TCP
          port: 6380
---
# Policy 5: C7 egress to Core Banking Adapter
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: c7-to-cba
  namespace: lip-execution
spec:
  podSelector:
    matchLabels:
      app: c7-execution-agent
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: {bank-cba-namespace}
      ports:
        - protocol: TCP
          port: 8080
---
# Policy 6: C7 egress to bank KMS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: c7-to-kms
  namespace: lip-execution
spec:
  podSelector:
    matchLabels:
      app: c7-execution-agent
  policyTypes: [Egress]
  egress:
    - to:
        - ipBlock:
            cidr: "{bank-kms-ip}/32"
      ports:
        - protocol: TCP
          port: 443
---
# Policy 7: Allow metrics ingress (bank monitoring only)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-metrics-ingress
  namespace: lip-execution
spec:
  podSelector:
    matchLabels:
      app: c7-execution-agent
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: lip-monitoring
      ports:
        - protocol: TCP
          port: 9090

# ENFORCED RESTRICTIONS (no policy exists to allow these):
#   lip-execution -> any Bridgepoint system other than MIPLO Kafka port 9093
#   lip-execution -> public internet
#   lip-execution -> any Bridgepoint API endpoint
# Verify all blocked paths in Section 14 checklist.
```

---

## 10. KILL SWITCH OPERATIONS

### 10.1 Global Kill Switch

```
Purpose: immediately halt all new bridge loan offer acceptance.
Use when: systemic risk event, regulatory directive, technical emergency.

Activate (requires TWO authorized operators):
  Operator 1:
    redis-cli -h {redis} -p 6380 --tls ... SET c7:kill:global "ACTIVE"
  Operator 2:
    Confirms in lip.decisions.log: event_type = "KILL_SWITCH_GLOBAL_ACTIVATED"
    Fields: operator_1_hashed_id, operator_2_hashed_id, timestamp_utc, reason

Verify:
  redis-cli ... GET c7:kill:global
  Expected: "ACTIVE"
  C7 metric: c7_kill_switch_active{scope="global"} = 1
  C7 logs: "KILL_SWITCH_GLOBAL_ACTIVE — all new offers blocked"

Effect on new offers:
  All incoming LoanOffers: declined immediately
  ExecutionConfirmation.decline_reason = "KILL_SWITCH_ACTIVE"

Effect on in-flight loans:
  Funded loans NOT affected — repayment monitoring continues
  C3 settlement signals still processed
  Only NEW offers are blocked

Deactivate (same two-operator requirement):
  redis-cli ... DEL c7:kill:global
  Logged: event_type = "KILL_SWITCH_GLOBAL_DEACTIVATED"
```

### 10.2 Corridor Kill Switch

```
Purpose: block a specific payment corridor while all others continue.
Use when: single-corridor risk event without broad systemic risk.

Corridor ID format: "{BIC8_sender}_{BIC8_receiver}_{currency}"
Example           : "BARCGB22_CITIUS33_USD"

Activate (single authorized operator):
  redis-cli ... SET c7:kill:corridor:{corridor_id} "ACTIVE"

Verify:
  redis-cli ... GET c7:kill:corridor:{corridor_id}
  Expected: "ACTIVE"

All activations and deactivations logged to lip.decisions.log.

Deactivate:
  redis-cli ... DEL c7:kill:corridor:{corridor_id}
```

### 10.3 Emergency Entity Block

```
Purpose: immediately block a specific entity (BIC) between daily
         C6 sanctions list refresh cycles.
Use when: new sanctions designation before next 24h refresh.

Owner: bank AML compliance officer.

Step 1 — Compute SHA-256 hash of the entity BIC:
  Use c7-hasher CLI utility (Section 16):
  kubectl exec -n lip-execution deploy/c7-hasher --     c7-hasher hash --bic {BIC8} --currency {ISO-4217}     --kms-endpoint {KMS_URL} --key-id lip-c6-entity-salt

  Output: {"hashed_entity_id": "{64-char-hex}", ...}

Step 2 — Add to emergency block set:
  redis-cli ... SADD c7:emergency:blocks "{hashed_entity_id}"

Step 3 — Verify:
  redis-cli ... SISMEMBER c7:emergency:blocks "{hashed_entity_id}"
  Expected: 1

Effect: C6 (MIPLO) and C7 both check this set on every transaction.
        Takes effect immediately — no refresh wait.

All additions logged:
  event_type = "EMERGENCY_BLOCK_ADDED"
  hashed_entity_id, added_by, timestamp_utc, stated_reason
```

---

## 11. HUMAN OVERRIDE PROCEDURE

### 11.1 When Override Is and Is Not Permitted

```
PERMITTED: offers in PENDING_HUMAN_REVIEW state
  These are offers with soft flags only (anomaly, structuring detected,
  sanctions proximity) but no hard block. Human review window: 300s default.

NOT PERMITTED — immutable hard blocks (no code path for override):
  sanctions_match = true              ← IMMUTABLE. Cannot be overridden.
  velocity_dollar_exceeded = true
  velocity_count_exceeded = true
  beneficiary_conc_exceeded = true
  Kill switch active (global or corridor)

Attempting override on a hard-blocked offer:
  C7 returns HTTP 403 {"status": "OVERRIDE_REJECTED",
                        "reason": "HARD_BLOCK_IMMUTABLE"}
  Attempt is logged to lip.decisions.log regardless.
```

### 11.2 Override API

```
POST /v1/override
Authorization: Bearer {bank-operator-token}
Content-Type: application/json

Request:
{
  "uetr"          : "{individual-uetr}",
  "offer_id"      : "{offer-id}",
  "operator_id"   : "{bank-operator-id}",
  "reason"        : "MANUAL_REVIEW_APPROVED",
  "approved_by"   : "{approving-supervisor-id}",
  "notes"         : "Review completed — anomaly was false positive.
                     Correspondent bank confirmed legitimate trade payment."
}

Success response (HTTP 200):
{
  "status"    : "OVERRIDE_ACCEPTED",
  "uetr"      : "{individual-uetr}",
  "logged_at" : "2026-03-04T22:45:00.123Z"
}

Rejection response (HTTP 403):
{
  "status"     : "OVERRIDE_REJECTED",
  "reason"     : "HARD_BLOCK_IMMUTABLE",
  "block_type" : "SANCTIONS_MATCH"
}

Authorization requirements:
  operator_id and approved_by must be different people (4-eyes principle)
  Both IDs SHA-256 hashed before storage
  Override record written to Redis "c7:override:{uetr}" TTL 90d
  Override written to lip.decisions.log: event_type = "HUMAN_OVERRIDE_EXECUTED"
```

---

## 12. MONITORING & ALERTING (BANK-SIDE)

### 12.1 C7 Metrics (Exposed on :9090/metrics)

```
Metric                                  Type       Description
c7_offer_received_total                 counter    Offers received from MIPLO
c7_offer_accepted_total                 counter    Offers funded successfully
c7_offer_declined_total{reason}         counter    Declined by reason code
c7_offer_expired_total                  counter    Expired before processing
c7_offer_processing_latency_seconds     histogram  p50/p99 offer-to-fund time
c7_hard_block_total{reason}             counter    Hard blocks enforced by type
c7_soft_flag_total{flag_type}           counter    Soft flags by type
c7_human_review_queue_depth             gauge      Offers awaiting review
c7_human_review_timeout_total           counter    Reviews timed out (auto-declined)
c7_kill_switch_active{scope}            gauge      1 = active; 0 = inactive
c7_cba_request_latency_seconds          histogram  CBA API p50/p99
c7_cba_error_total{error_type}          counter    CBA errors by type
c7_repayment_success_total              counter    Successful repayments
c7_repayment_failed_total{reason}       counter    Failed repayments by reason
c7_loan_overdue_total                   counter    Loans past maturity (no repayment)
c7_decision_log_entries_total           counter    Audit log entries written
c7_redis_op_latency_seconds             histogram  Redis op p50/p99
c7_clock_skew_detected                  gauge      1 = skew alert active
c7_model_version_c4                     info       C4 model version label
```

### 12.2 Required Alerts

```
CRITICAL (immediate page — bank 24/7 on-call):
  c7_hard_block_total{reason="SANCTIONS_MATCH"} increases by any amount
    Action: bank AML compliance officer notified immediately; SAR review initiated
  c7_cba_error_total{error_type="TIMEOUT"} > 10 in 5 minutes
    Action: CBA degradation — activate global kill switch; contact CBA owner
  c7_loan_overdue_total > 0
    Action: loan past maturity without repayment; bank capital at risk
  c7 pod in CrashLoopBackOff or OOMKilled
    Action: C7 unavailable; runbook Section 13.2
  c7_decision_log_entries_total stops incrementing while offers received
    Action: audit log failure; compliance risk; contact Bridgepoint immediately

HIGH (15-minute response):
  c7_offer_processing_latency_seconds{p99} > 200ms for > 5 minutes
  c7_human_review_queue_depth > 50
  c7_cba_request_latency_seconds{p99} > 500ms for > 5 minutes
  c7_redis_op_latency_seconds{p99} > 20ms for > 5 minutes

MEDIUM (1-hour response):
  c7_human_review_timeout_total increasing rapidly
  c7_offer_expired_total > 5% of c7_offer_received_total in 1 hour
```

### 12.3 Compliance Monitoring (Bank Compliance Team)

```
Daily:
  Monitor lip.aml.sar.queue (MIPLO Kafka):
    Review all structuring_detected = true events
    Review all sanctions_match = true events
    File SAR as required (FinCEN: 30 days; FINTRAC: 30 days from detection)

  Verify c7.audit.local (bank Kafka):
    Confirm log entries flowing (c7_decision_log_entries_total > 0)
    7-year retention active; archival process running

Monthly:
  c7_hard_block_total by reason — trend analysis
  c7_human_review_timeout_total — review staffing adequacy
  c7_offer_accepted_total vs c7_loan_overdue_total — credit performance
  KMS access audit log review (CIPHER standard — Section 3.2)
```

---

## 13. OPERATIONAL RUNBOOK

### 13.1 C7 Pod Restart (Planned)

```
Use case: configuration change, image upgrade, scheduled maintenance.

1. Notify: bank operations team (#lip-ops Slack or equivalent)
2. Verify no loans in FUNDING_IN_PROGRESS:
   redis-cli ... KEYS "c7:loan:*" | while read key; do
     redis-cli ... HGET "$key" status; done | grep FUNDING_IN_PROGRESS
   Wait until all in-progress loans clear before proceeding.
3. Restart:
   kubectl rollout restart deployment/c7-execution-agent -n lip-execution
4. Monitor:
   kubectl rollout status deployment/c7-execution-agent -n lip-execution
   Expected: "successfully rolled out" within 60 seconds
5. Verify readiness:
   kubectl get pods -n lip-execution
   Expected: all pods Running + Ready (2/2)
6. Verify consumer lag:
   Check Kafka consumer lag for c7-offer-processor group
   Expected: lag = 0 within 2 minutes of pod ready
7. Log: who restarted, when, reason (written to operations log)
```

### 13.2 Unplanned Pod Failure Recovery

```
C7 pod crashes or OOMKilled — CRITICAL alert fires.

1. Kubernetes auto-restarts (exponential backoff)
2. On-call assesses root cause:
   kubectl logs {pod} -n lip-execution --previous
   Look for:
     OOMKilled     -> memory limit too low; temporary node resize
     Redis error   -> Redis recovery (Section 6.3)
     Kafka error   -> Kafka ops (bank Kafka team)
     panic/code bug -> escalate to Bridgepoint immediately

3. Loan state after recovery:
   Redis AOF persistence: loan state survives pod crashes
   Check FUNDING_IN_PROGRESS after restart:
     CBA idempotency: prevents double-funding on retry
     C7 re-reads Redis state and resumes correctly

4. Verify consumer lag recovers to zero (within 5 minutes)
5. If root cause unclear after 30 minutes: escalate to Bridgepoint
```

### 13.3 CBA Degradation Response

```
Alert: CBA timeout rate > 10% (HIGH — 15-minute response).

1. Check CBA health:
   curl {CBA_ENDPOINT}/health
   Expected: HTTP 200

2. If CBA unhealthy:
   a. Activate global kill switch (no new loans funded during outage):
      redis-cli ... SET c7:kill:global "ACTIVE"
      (Partially-funded offers during CBA outage = inconsistent state)
   b. Notify bank payments team (CBA owners)
   c. Wait for CBA recovery and health confirmation
   d. Deactivate kill switch:
      redis-cli ... DEL c7:kill:global
   e. Check offer expiry: review Kafka consumer lag on lip.offers.pending
      Offers expired during outage are lost — MIPLO will generate new ones
      for subsequent failures. No manual re-injection needed.

3. If CBA healthy but slow (p99 > 500ms consistently):
   Scale CBA horizontally (bank CBA owner)
   Consider temporary kill switch if p99 > 2000ms (offers timing out anyway)
```

### 13.4 Loan Overdue Response

```
Alert: c7_loan_overdue_total > 0 — CRITICAL — immediate response.

1. Identify overdue loans:
   Query lip.decisions.log for status = "MONITORING_ACTIVE"
   where maturity_utc < now()
   Extract UETRs.

2. Check C3 Repayment Engine (MIPLO-side):
   Contact Bridgepoint on-call:
   "C3 repayment signal missing for UETR: {uetr}. Maturity was {timestamp}."

3. Check settlement independently:
   Was pacs.002 final confirmation received for this UETR?
   Was camt.054 posted?
   Check SWIFT gpi tracker for UETR status.

4. If settlement confirmed but C3 signal missing:
   C3 may be in recovery — await up to 30 minutes
   If not recovering after 30 minutes: manual repayment (step 5)

5. Manual repayment (last resort, bank payments officer):
   Trigger repayment via CBA directly (bank internal process)
   Log in lip.decisions.log:
     event_type = "MANUAL_REPAYMENT_TRIGGERED"
     loan_reference, uetr, triggered_by, reason, timestamp_utc
   Notify Bridgepoint for C3 root cause investigation

6. Post-incident RCA: required within 48 hours.
   File with both bank operations and Bridgepoint.
```

---

## 14. PRE-GO-LIVE VALIDATION CHECKLIST

Complete all items before go-live. Bank infrastructure lead and bank AML
compliance officer must both sign.

### Infrastructure
- [ ] lip-execution namespace: created with restricted Pod Security Standards
- [ ] C7 pods: 2 replicas Running + Ready; anti-affinity confirmed on separate nodes
- [ ] Redis Cluster: 6 nodes, CLUSTER OK, noeviction, AOF enabled — all checks pass
- [ ] Bank Kafka: 8 C7 topics created, replication.factor = 3, min.insync.replicas = 2
- [ ] MIPLO Kafka connectivity: C7 consumer groups connect and consume successfully
- [ ] CoreBankingAdapter: deployed, reachable, all Section 8.3 tests pass
- [ ] Network policies: all 7 applied; all blocked paths verified blocked
- [ ] KMS: lip-c7-hmac-key and lip-c6-entity-salt provisioned and accessible by C7
- [ ] ESO: KMS secrets syncing to Kubernetes Secrets in lip-execution

### Security
- [ ] C7 image: Cosign signature verified (Section 5.2 steps 1–5 complete)
- [ ] C7 image: Trivy report shows zero CRITICAL CVEs (Bridgepoint provides report)
- [ ] Admission controller: rejects unsigned image — tested
- [ ] No shell in C7 container: kubectl exec returns "error: ... no sh" — confirmed
- [ ] No secrets in ConfigMaps or environment variables — manifests reviewed
- [ ] Blocked path test: lip-execution cannot reach any Bridgepoint endpoint except
      MIPLO Kafka port 9093 — network policy test evidence archived

### Compliance
- [ ] AML thresholds: set in lip-c7-aml-thresholds ConfigMap
- [ ] AML officer: signed and dated the ConfigMap annotation
- [ ] SAR consumer: bank compliance system consuming lip.aml.sar.queue — tested
- [ ] Kill switch: global + corridor tested in staging (activate + verify + deactivate)
- [ ] Human override: 4-eyes authorization tested; hard block rejection tested
- [ ] c7.audit.local: 7-year retention confirmed; archival process tested end-to-end
- [ ] DORA third-party register: updated (EU banks)

### Operational
- [ ] All C7 metrics visible in bank Prometheus and Grafana dashboards
- [ ] All CRITICAL + HIGH alerts routing to bank on-call PagerDuty — test alert sent
- [ ] On-call team: briefed on all Section 13 runbooks
- [ ] Escalation path: Bridgepoint technical on-call contact recorded in bank runbook

### Functional (Staging)
- [ ] Full cycle: synthetic pacs.002 -> LoanOffer -> FUNDED -> REPAID (mock CBA + C3)
- [ ] sanctions_match = true -> DECLINED, no fund, logged — verified
- [ ] Global kill switch -> all offers DECLINED — verified
- [ ] Soft-flag offer -> PENDING_HUMAN_REVIEW -> override -> FUNDED — verified
- [ ] Duplicate offer_id -> single funding (no double-fund) — CBA idempotency verified
- [ ] Clock skew 10s -> alert fires; offer expiry honored — verified
- [ ] Redis primary shard kill -> C7 hard-blocks during failover (~10s) ->
      resumes after promotion — verified; no fail-open confirmed

### Sign-Off

```
Bank Infrastructure Lead:
  Name: _______________________  Date: ___________  Signature: ___________

Bank AML Compliance Officer:
  Name: _______________________  Date: ___________  Signature: ___________

Bridgepoint Confirmation (NOVA):
  MIPLO Kafka connectivity confirmed:  ___________
  C7 image digest confirmed:           ___________
  Cosign signature bundle delivered:   ___________
```

---

## 15. ESCALATION AND SUPPORT

### 15.1 Escalation Matrix

```
Scenario                              First Contact           Escalation
C7 pod failure / crash                Bank on-call            Bridgepoint technical on-call
MIPLO Kafka unreachable               Bank on-call            Bridgepoint technical on-call
LoanOffer not arriving (> 30 min)     Bridgepoint on-call     Bridgepoint NOVA lead
CBA failure / degradation             Bank payments team      Bank CTO
Sanctions match event                 Bank AML officer        Bank Chief Compliance Officer
Loan overdue (> 2 hours past maturity) Bridgepoint + bank      Joint incident call
Redis shard failure                   Bank infrastructure     Bank on-call (Runbook 13.2)
Suspected security breach             Bank CISO               Bridgepoint CIPHER lead
Clock skew alert                      Bank infrastructure     Bank NTP team
```

### 15.2 What to Provide When Contacting Bridgepoint

```
PROVIDE (when escalating to Bridgepoint on-call):
  1. Affected UETR(s) — individual payment identifier(s)
  2. C7 log snippet at time of incident (kubectl logs output)
  3. C7 Grafana dashboard screenshot at time of incident
  4. Redis state for affected UETR:
       redis-cli ... HGETALL "c7:loan:{uetr}"
  5. Kafka consumer lag at time of incident
  6. Time of first anomaly (UTC)

DO NOT SEND TO BRIDGEPOINT:
  Raw transaction data
  Borrower or beneficiary identities (even hashed — Bridgepoint does not need them)
  Bank internal account numbers or balances
  Core banking system logs
  Any customer PII of any kind

Bridgepoint has no access to Zone C.
Everything must be explicitly provided by the bank.
Only provide the six items listed above.
```

---

## 16. APPENDIX: SALT DERIVATION CLI UTILITY (c7-hasher)

For computing SHA-256 entity hashes when using the emergency block list
(Section 10.3), Bridgepoint provides `c7-hasher`:

```
c7-hasher — Computes entity hashes using the bank KMS salt.
             The salt value is never written to stdout, logs, or disk.
             Every invocation is recorded by KMS audit.

Deployment:
  Deployed as a separate pod in lip-execution namespace.
  Not part of the C7 execution agent pod.
  Accessible only via kubectl exec (no external API surface).

Usage:
  kubectl exec -n lip-execution deploy/c7-hasher --     c7-hasher hash       --bic {BIC8}       --currency {ISO-4217-code}       --kms-endpoint {KMS_URL}       --key-id lip-c6-entity-salt

Example output:
  {
    "bic":               "BARCGB22",
    "currency":          "USD",
    "hashed_entity_id":  "a3f2d1...{64-char-hex}",
    "algorithm":         "SHA-256",
    "salt_key_id":       "lip-c6-entity-salt",
    "computed_at":       "2026-03-04T22:15:00Z"
  }

Security properties:
  - Connects to bank KMS to retrieve salt (never cached locally)
  - Salt never written to stdout, logs, files, or env vars
  - Runs inside lip-execution namespace only (KMS NetworkPolicy enforces)
  - Every invocation logged by KMS (timestamp, service account, operation)
  - Output hashed_entity_id is safe to share internally and log
```

---

*C7 Bank Deployment Guide v1.0 complete.*
*This document is intended for delivery to the bank under the Technology Licensing Agreement.*
*Bridgepoint retains all IP in the C7 container image and configuration schema.*
*The bank owns all deployment infrastructure, KMS keys, and transaction records.*
*Bridgepoint has zero access to Zone C (ELO) at any time.*
*Internal use only. Stealth mode active. March 4, 2026.*
*Lead: NOVA | Review: FORGE, CIPHER, REX, LEX*
