# LIP Demo Walkthrough

> Step-by-step demo script for pilot bank technical teams.
> Estimated duration: 30–45 minutes.

---

## Prerequisites

- Docker and Docker Compose installed
- Python 3.10+ with `pip`
- Repository cloned: `git clone https://github.com/ryanktomegah/PRKT2026.git`
- HMAC key for demo: `export LIP_HMAC_KEY="demo-key-do-not-use-in-production"`

---

## Step 1 — Environment Setup

Start the LIP platform with Redis and Redpanda (Kafka-compatible):

```bash
cd PRKT2026
docker-compose up -d
```

Verify all services are running:

```bash
docker-compose ps
```

Expected: Redis, Redpanda, and LIP C7 container running on port 8080.

For local development without Docker:

```bash
pip install -r requirements.txt -r requirements-ml.txt
cd lip && pip install -e . && cd ..
PYTHONPATH=. REDIS_URL="" LIP_API_HMAC_KEY="" uvicorn lip.api.app:app --host 0.0.0.0 --port 8080
```

**Point out to audience:** LIP starts with no HMAC key in demo mode — auth is disabled for walkthrough simplicity. Production deployments require HMAC authentication on all non-health endpoints.

---

## Step 2 — Health Check

Verify the platform is live and ready:

```bash
# Liveness — should always return 200
curl -s http://localhost:8080/health/live | python3 -m json.tool
```

Expected:
```json
{
    "status": "alive"
}
```

```bash
# Readiness — 200 when all subsystems healthy
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8080/health/ready | python3 -m json.tool
```

Expected:
```json
{
    "status": "ready",
    "checks": {
        "redis": true,
        "kafka": true,
        "kill_switch": true
    }
}
```

**Point out:** These are the K8s probe endpoints. `kill_switch: true` means "not engaged" — the platform is accepting new loans.

---

## Step 3 — Register Known Entity

Register a well-known bank BIC with a Tier 1 (investment-grade) override. Without this, a new counterparty would be classified as Tier 3 (thin-file, 900+ bps fee).

```bash
curl -s -X POST \
  "http://localhost:8080/known-entities?bic=DEUTDEDB&tier=1" | python3 -m json.tool
```

Expected:
```json
{
    "bic": "DEUTDEDB",
    "tier": 1,
    "status": "registered"
}
```

Verify the registration:

```bash
curl -s http://localhost:8080/known-entities | python3 -m json.tool
```

Expected:
```json
[
    {
        "bic": "DEUTDEDB",
        "tier": 1
    }
]
```

**Point out:** This is the known-entity override from GAP-11. Investment-grade banks like Deutsche Bank shouldn't pay thin-file fees just because they're new to the platform. The credit officer registers their BIC once, and C2 uses that tier instead of the data-availability rule.

---

## Step 4 — Submit a Payment Failure Event

Feed an ISO 20022 pacs.002 rejection through the C1→C7 pipeline. In production, this arrives via Kafka from C5 (streaming ingestion). For the demo, we invoke the pipeline directly:

```python
# demo_payment.py — run with: PYTHONPATH=. python3 demo_payment.py
from lip.pipeline import LIPPipeline
from lip.common.event_normaliser import NormalizedEvent
from datetime import datetime, timezone

pipeline = LIPPipeline.from_defaults()

event = NormalizedEvent(
    end_to_end_id="550e8400-e29b-41d4-a716-446655440000",
    rejection_code="MS03",           # Class B — systemic/processing delay (7d maturity per rejection_taxonomy.py)
    amount=1_000_000.0,
    currency="EUR",
    target_currency="USD",
    sending_bic="DEUTDEDB",          # Deutsche Bank — registered Tier 1
    receiving_bic="BNPAFRPP",
    narrative="Missing creditor account number",
    timestamp=datetime.now(tz=timezone.utc),
)

result = pipeline.process(event)
print(f"Outcome:    {result.outcome}")
print(f"Fee (bps):  {result.fee_bps}")
print(f"Maturity:   {result.maturity_days} days")
print(f"Loan ID:    {result.loan_id}")
print(f"Tier:       {result.tier}")
```

Expected output:
```
Outcome:    FUNDED
Fee (bps):  300
Maturity:   3 days
Loan ID:    LN-2026-xxxxx
Tier:       1
```

**Point out:**
- **C1** classified this as a genuine failure (above threshold τ* = 0.110)
- **C4** confirmed no dispute indicators
- **C6** passed velocity/sanctions check
- **C2** assigned Tier 1 (from known-entity registry) → 300 bps floor fee
- **C7** generated the offer and funded the bridge loan
- **Maturity:** 3 days (Class A — technical errors resolve quickly)
- **Fee:** 300 bps annualised — the minimum. For a $1M principal over 3 days: $1M × 300/10000 × 3/365 = **$246.58**

---

## Step 5 — Observe Classification

The pipeline result contains the full classification chain:

```python
# Continuing from Step 4...
print(f"C1 failure probability: {result.failure_probability:.3f}")
print(f"C1 above threshold:     {result.above_threshold}")
print(f"C4 dispute class:       {result.dispute_class}")
print(f"C4 hard block:          {result.dispute_hard_block}")
print(f"C6 velocity passed:     {result.aml_passed}")
print(f"C2 PD score:            {result.pd_score:.4f}")
print(f"Rejection class:        {result.rejection_class}")
```

**Point out:**
- Each component produces an independent signal
- The pipeline gates sequentially: C1 → (C4 ∥ C6) → C2 → C7
- If any gate blocks, the pipeline short-circuits — no unnecessary computation

---

## Step 6 — View Portfolio

Check active loans and aggregate exposure:

```bash
# Active loans
curl -s http://localhost:8080/portfolio/loans | python3 -m json.tool
```

```bash
# Aggregate exposure by corridor, tier, maturity class
curl -s http://localhost:8080/portfolio/exposure | python3 -m json.tool
```

```bash
# Yield metrics
curl -s http://localhost:8080/portfolio/yield | python3 -m json.tool
```

**Point out:** These are real-time views — no cache, no batch job. They read directly from the active loan book in the repayment engine.

---

## Step 7 — Platform Monitoring (Admin)

View platform-wide metrics (BPI operator view):

```bash
# Platform summary
curl -s http://localhost:8080/admin/platform/summary | python3 -m json.tool
```

Expected:
```json
{
    "total_active_loans": 1,
    "total_licensees": 1,
    "total_principal_usd": "1000000.00"
}
```

```bash
# Per-licensee stats
curl -s http://localhost:8080/admin/licensees/DEUTDEDB/stats | python3 -m json.tool
```

---

## Step 8 — Regulatory Export

Pull DORA Art.19 and SR 11-7 reports:

```bash
# DORA events (JSON)
curl -s "http://localhost:8080/admin/regulatory/dora/export?format=json" | python3 -m json.tool

# DORA events (CSV) — for NCA submission
curl -s "http://localhost:8080/admin/regulatory/dora/export?format=csv"

# SR 11-7 model validation (JSON)
curl -s "http://localhost:8080/admin/regulatory/sr117/export?format=json" | python3 -m json.tool

# SR 11-7 model validation (CSV)
curl -s "http://localhost:8080/admin/regulatory/sr117/export?format=csv"
```

**Point out:**
- DORA Art.19 requires financial entities to report major ICT-related incidents to their National Competent Authority. LIP generates the event data; the bank submits it.
- SR 11-7 requires quarterly model validation. LIP pre-generates validation reports for C1 (failure classifier) and C2 (PD model) that the bank's model risk management team can review and submit.

---

## Step 9 — Kill Switch Demo

Demonstrate the emergency halt mechanism:

```bash
# Check readiness — should be 200
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8080/health/ready
```

Engage the kill switch (via Redis or environment variable):

```bash
# If Redis is running:
redis-cli SET lip:kill_switch ACTIVE

# Or restart with environment variable:
# LIP_KILL_SWITCH_ACTIVE=true uvicorn lip.api.app:app ...
```

```bash
# Now readiness returns 503
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8080/health/ready
```

Expected:
```json
{
    "status": "not_ready",
    "checks": {
        "redis": true,
        "kafka": true,
        "kill_switch": false
    }
}
```

**Point out:**
- `kill_switch: false` means "engaged" — the check failed, meaning the switch IS active
- K8s will stop routing traffic to this pod
- No new loans will be funded while the kill switch is engaged
- Existing loans continue their repayment cycle — the kill switch halts new origination only
- This satisfies EU AI Act Art.14 (human oversight) — a human can halt the system at any time

**Recovery:**

```bash
redis-cli DEL lip:kill_switch
curl -s http://localhost:8080/health/ready | python3 -m json.tool
# Should return 200 with all checks: true
```

---

## Step 10 — Cleanup

Remove the known entity registration:

```bash
curl -s -X DELETE http://localhost:8080/known-entities/DEUTDEDB | python3 -m json.tool
```

Stop the environment:

```bash
docker-compose down
```

---

## Summary for Bank Audience

| Capability | What You Saw |
|-----------|-------------|
| Classification | C1 failure detection → C4 dispute check → C6 velocity/sanctions screen |
| Pricing | C2 PD model with known-entity tier override → 300 bps floor |
| Execution | C7 generates offer, funds loan, registers with repayment engine |
| Monitoring | Real-time portfolio views, per-licensee stats, platform summary |
| Regulatory | DORA Art.19 + SR 11-7 exports ready for NCA submission |
| Safety | Kill switch halts origination; readiness probe integrates with K8s |
| Integration | HMAC-authenticated REST API; ISO 20022 native; Kafka event streaming |
