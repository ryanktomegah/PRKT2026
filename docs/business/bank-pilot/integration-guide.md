# LIP Integration Guide

> Technical integration guide for pilot bank engineering teams.

---

## 1. Network Requirements

| Requirement | Detail |
|-------------|--------|
| Protocol | HTTPS (TLS 1.2+) |
| mTLS | Optional for Phase 1; recommended for production |
| Inbound ports | 8080 (API), 9090 (metrics) |
| Outbound | Zero outbound from C7 execution agent container |
| Webhook endpoints | Not required for Phase 1 (polling model) |

LIP runs entirely within the bank's infrastructure perimeter. No data leaves the bank's network. BPI accesses aggregate metrics (admin endpoints) via authenticated API only.

---

## 2. Authentication — HMAC-SHA256

### Key Exchange

1. BPI generates a 256-bit HMAC key
2. Key is exchanged out-of-band (encrypted email or secure file transfer)
3. Bank stores key in their secrets management system (Vault, AWS Secrets Manager, GCP Secret Manager)
4. Key is injected into LIP via `LIP_API_HMAC_KEY` environment variable

### Signing Process

Every authenticated request includes an `Authorization` header:

```
Authorization: HMAC-SHA256 <timestamp>:<hex_digest>
```

**Computation:**

```
message = "{timestamp}|{METHOD}|{path}|" + body_bytes
digest  = HMAC-SHA256(key, message)
header  = "HMAC-SHA256 {timestamp}:{hex(digest)}"
```

- `timestamp`: Unix epoch seconds (integer, as string in the message)
- `METHOD`: HTTP method, uppercased (GET, POST, DELETE)
- `path`: Full request path including leading slash (e.g., `/admin/platform/summary`)
- `body_bytes`: Raw request body (empty bytes for GET/DELETE)
- `key`: HMAC key bytes

### Replay Prevention

Requests with timestamps more than **300 seconds** (5 minutes) from server time are rejected. Ensure NTP synchronisation between client and LIP deployment.

### Example Implementations

**Python:**
```python
import hmac, hashlib, time

def sign_request(method: str, path: str, body: bytes, key: bytes) -> str:
    ts = str(int(time.time()))
    message = f"{ts}|{method.upper()}|{path}|".encode() + body
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"HMAC-SHA256 {ts}:{digest}"

# Usage
headers = {
    "Authorization": sign_request("GET", "/admin/platform/summary", b"", key)
}
```

**Java:**
```java
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

public class LipAuth {
    public static String sign(String method, String path, byte[] body, byte[] key)
            throws Exception {
        long ts = System.currentTimeMillis() / 1000;
        byte[] prefix = String.format("%d|%s|%s|", ts, method.toUpperCase(), path)
                .getBytes(StandardCharsets.UTF_8);
        byte[] message = new byte[prefix.length + body.length];
        System.arraycopy(prefix, 0, message, 0, prefix.length);
        System.arraycopy(body, 0, message, prefix.length, body.length);

        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        byte[] digest = mac.doFinal(message);

        StringBuilder hex = new StringBuilder();
        for (byte b : digest) hex.append(String.format("%02x", b));

        return String.format("HMAC-SHA256 %d:%s", ts, hex);
    }
}
```

**curl (bash):**
```bash
#!/bin/bash
KEY="your-hex-key-here"
TS=$(date +%s)
METHOD="GET"
PATH_="/admin/platform/summary"
BODY=""

MESSAGE="${TS}|${METHOD}|${PATH_}|${BODY}"
DIGEST=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$KEY" | awk '{print $2}')

curl -H "Authorization: HMAC-SHA256 ${TS}:${DIGEST}" \
  "http://localhost:8080${PATH_}"
```

---

## 3. ISO 20022 Message Format

LIP consumes ISO 20022 payment status messages. The primary input is `pacs.002` (FIToFIPaymentStatusReport).

### Field Mapping — pacs.002 to LIP Pipeline

| ISO 20022 Field | XPath | LIP Field | Description |
|-----------------|-------|-----------|-------------|
| `EndToEndId` | `TxInfAndSts/OrgnlEndToEndId` | `end_to_end_id` | UETR — unique transaction reference |
| `StsRsnInf/Rsn/Cd` | `TxInfAndSts/StsRsnInf/Rsn/Cd` | `rejection_code` | ISO 20022 reason code (e.g., MS03, AC01) |
| `InstdAmt` | `TxInfAndSts/OrgnlTxRef/Amt/InstdAmt` | `amount` | Payment amount |
| `InstdAmt@Ccy` | (attribute) | `currency` | Payment currency (ISO 4217) |
| `DbtrAgt/FinInstnId/BICFI` | `TxInfAndSts/OrgnlTxRef/DbtrAgt/...` | `sending_bic` | Sending bank BIC |
| `CdtrAgt/FinInstnId/BICFI` | `TxInfAndSts/OrgnlTxRef/CdtrAgt/...` | `receiving_bic` | Receiving bank BIC |
| `AddtlInf` | `TxInfAndSts/StsRsnInf/AddtlInf` | `narrative` | Free-text rejection narrative |

### Supported Rejection Codes by Class

**Class A — Technical/Missing Data (3-day maturity):**
AC01, AC04, AC06, AM02, AM03, AM05, AM09, AM10, BE01, BE04, BE06, BE07, DT01, FF01, MS03, RC01, RR06, TM01

**Class B — Procedural Holds (currently blocked):**
B1 subclass requires Bridgeability Certification API. B2 subclass permanently blocked.

**Class C — Systemic/Processing (21-day maturity):**
AG02, CUST, DNOR (non-compliance subset excluded), ED05, FOCR, MD01, MD02, NARR, NOAS, NOOR

**BLOCK — Never Bridged:**
DNOR (compliance), CNOR, RR01, RR02, RR03, RR04, AG01, LEGL

---

## 4. Known Entity Registration

### Purpose

New counterparties with no LIP transaction history default to Tier 3 (thin-file, 900+ bps fee). For investment-grade banks, this is economically incorrect. The known-entity registry allows manual tier assignment.

### Enrollment Flow

1. Bank credit officer identifies counterparties eligible for tier override
2. POST each BIC with assigned tier to `/known-entities`
3. LIP C2 model checks registry before data-availability rule
4. Subsequent loans to registered BICs use the override tier

### API

```bash
# Register
curl -X POST "http://localhost:8080/known-entities?bic=DEUTDEDB&tier=1"

# List all
curl http://localhost:8080/known-entities

# Remove
curl -X DELETE http://localhost:8080/known-entities/DEUTDEDB
```

### Tier Values

| Tier | Meaning | Fee Range |
|------|---------|-----------|
| 1 | Investment-grade, listed | 300–539 bps |
| 2 | Private company, balance-sheet data available | 540–899 bps |
| 3 | Thin file (no history, no public data) | 900–1500 bps |

---

## 5. Borrower Enrollment

Each bank that will use LIP must be enrolled as a borrower. The borrower is the originating bank (B2B interbank structure), not the end customer.

### Process

1. Bank provides their primary BIC
2. BPI registers the BIC in the borrower registry
3. LIP associates all bridge loans with this BIC as the borrower
4. Governing law is derived from BIC country code (chars 4–5)

---

## 6. Event Streaming (Kafka)

LIP uses Kafka (Redpanda-compatible) for real-time event streaming.

### Topic Structure

| Topic | Key | Partitions | Retention | Description |
|-------|-----|-----------|-----------|-------------|
| `lip.payment.events` | `uetr` | 24 | 7 days | Incoming payment failure events |
| `lip.failure.predictions` | `uetr` | 12 | 7 days | C1 classification results |
| `lip.settlement.signals` | `uetr` | 24 | 7 days | Settlement confirmation signals |
| `lip.dispute.results` | `uetr` | 6 | 7 days | C4 dispute classification |
| `lip.velocity.alerts` | `uetr` | 6 | 7 days | C6 velocity/sanctions alerts |
| `lip.loan.offers` | `uetr` | 6 | 7 days | Bridge loan offers generated |
| `lip.repayment.events` | `uetr` | 6 | 7 days | Repayment lifecycle events |
| `lip.decision.log` | `uetr` | 12 | **7 years** | Full audit trail (SR 11-7) |
| `lip.dead.letter` | `uetr` | 6 | 7 days | Failed processing events |
| `lip.stress.regime` | `corridor` | 6 | 7 days | Corridor stress indicators |

### Consumer Group Setup

Bank systems that need to subscribe to LIP events should create a dedicated consumer group:

```
group.id: {bank-bic}-lip-consumer
auto.offset.reset: earliest
enable.auto.commit: false
```

Recommended: consume from `lip.loan.offers` (new bridge loan notifications) and `lip.repayment.events` (settlement lifecycle updates).

---

## 7. Monitoring Integration

### Prometheus Metrics

LIP exposes Prometheus-compatible metrics on port 9090.

**Key metrics:**
| Metric | Type | Description |
|--------|------|-------------|
| `lip_pipeline_duration_seconds` | histogram | End-to-end pipeline latency |
| `lip_loans_funded_total` | counter | Total bridge loans funded |
| `lip_loans_active` | gauge | Currently active bridge loans |
| `lip_c1_predictions_total` | counter | C1 classification count |
| `lip_c6_velocity_blocks_total` | counter | C6 velocity/sanctions blocks |
| `lip_kill_switch_active` | gauge | 1 if kill switch engaged, 0 otherwise |

### Grafana Dashboard

Import the provided dashboard template from `lip/infrastructure/monitoring/grafana-dashboard.json` (if available) or build custom dashboards using the metrics above.

### Alerting Recommendations

| Alert | Condition | Severity |
|-------|-----------|----------|
| Pipeline latency | p99 > 94ms for 5 minutes | Warning |
| Kill switch engaged | `lip_kill_switch_active == 1` | Critical |
| Readiness down | `/health/ready` returns 503 for 2 minutes | Critical |
| Loan default | Default rate > 2% rolling 30 days | Warning |

---

## 8. Kill Switch — Emergency Halt

### What It Does

The kill switch immediately halts all new bridge loan origination. Existing loans continue their repayment cycle.

### How to Activate

**Option 1 — Redis (instant):**
```bash
redis-cli SET lip:kill_switch ACTIVE
```

**Option 2 — K8s restart with env var:**
```bash
kubectl set env deployment/lip-c7-execution \
  LIP_KILL_SWITCH_ACTIVE=true -n lip
```

### How to Verify

```bash
curl http://localhost:8080/health/ready
# Returns 503 with kill_switch: false (check failed = switch is active)
```

### How to Recover

```bash
redis-cli DEL lip:kill_switch
# Or remove the environment variable and restart
```

### Who Can Activate

Designate the following roles with kill switch authority:
- Bank's Head of Operations
- Bank's Chief Risk Officer (or delegate)
- BPI Platform Operations (via admin API)

Document the activation authority in the operational runbook before go-live.

---

## 9. Testing

### Sandbox Environment

LIP can run in full in-memory mode (no Redis, no Kafka) for integration testing:

```bash
REDIS_URL="" LIP_API_HMAC_KEY="" \
  uvicorn lip.api.app:app --host 0.0.0.0 --port 8080
```

### Test BICs

Use these BICs for integration testing (they are not real SWIFT BICs):

| BIC | Purpose |
|-----|---------|
| `TESTBANK01` | Generic test counterparty |
| `TESTTIER1X` | Pre-registered as Tier 1 (if configured) |
| `TESTTIER3X` | Thin-file test entity |
| `TESTBLOCKX` | Entity that triggers C6 velocity block |

### End-to-End Validation Checklist

- [ ] Health endpoints return 200 (live) and 200 (ready)
- [ ] Known entity registration: POST, GET, DELETE cycle
- [ ] Pipeline processes a Class A event → FUNDED outcome
- [ ] Pipeline blocks a BLOCK-class event → short-circuit
- [ ] Portfolio endpoints return active loan after funding
- [ ] Admin summary reflects correct counts
- [ ] DORA export returns valid JSON/CSV
- [ ] SR 11-7 export returns valid JSON/CSV
- [ ] Kill switch engagement → readiness returns 503
- [ ] Kill switch disengagement → readiness returns 200
- [ ] HMAC authentication rejects unsigned requests (when key configured)
- [ ] HMAC authentication rejects expired timestamps
- [ ] Pipeline latency < 94ms p99 under load
