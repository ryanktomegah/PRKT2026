# LIP API Reference

> Version 1.0.0 — Lending Intelligence Platform
> Base URL: `https://<deployment-host>:8080`

---

## Authentication

All endpoints except `/health/*` require HMAC-SHA256 authentication.

**Header format:**
```
Authorization: HMAC-SHA256 <timestamp>:<hex_digest>
```

**Signing algorithm:**
```
message = "{timestamp}|{METHOD}|{path}|{body}"
digest  = HMAC-SHA256(key, message)
header  = "HMAC-SHA256 {timestamp}:{hex(digest)}"
```

- `timestamp`: Unix epoch seconds (integer)
- `METHOD`: HTTP method, uppercase (GET, POST, DELETE)
- `path`: Request path (e.g., `/admin/platform/summary`)
- `body`: Raw request body bytes (empty string for GET/DELETE)
- `key`: Shared HMAC key (exchanged out-of-band during onboarding)

**Replay window:** 5 minutes. Requests with timestamps older than 300 seconds are rejected.

**Example signing (Python):**
```python
import hmac, hashlib, time

def sign(method: str, path: str, body: bytes, key: bytes) -> str:
    ts = str(int(time.time()))
    message = f"{ts}|{method.upper()}|{path}|".encode() + body
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"HMAC-SHA256 {ts}:{digest}"
```

**Error responses:**
| Status | Body | Cause |
|--------|------|-------|
| 401 | `{"detail": "Missing Authorization header"}` | No `Authorization` header |
| 401 | `{"detail": "Invalid HMAC signature"}` | Bad signature or expired timestamp |

---

## Health Router — `/health`

Health endpoints are **unauthenticated** (no HMAC required). Used by K8s probes.

### GET /health/live

Liveness probe. Always returns 200.

**Response** `200 OK`:
```json
{
  "status": "alive"
}
```

**curl:**
```bash
curl http://localhost:8080/health/live
```

---

### GET /health/ready

Readiness probe. Returns 200 when all subsystems are healthy, 503 otherwise.

**Checks performed:**
- `redis`: Redis connection reachable (or in-memory mode)
- `kafka`: Kafka producer can list topics (or not configured)
- `kill_switch`: Kill switch is not engaged

**Response** `200 OK` (all checks pass):
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

**Response** `503 Service Unavailable` (one or more checks fail):
```json
{
  "status": "not_ready",
  "checks": {
    "redis": true,
    "kafka": false,
    "kill_switch": true
  }
}
```

**curl:**
```bash
curl -w "\n%{http_code}" http://localhost:8080/health/ready
```

---

## Admin Router — `/admin`

Platform-wide monitoring and regulatory export endpoints for BPI operators.

### GET /admin/platform/summary

Platform-wide aggregate snapshot across all licensees.

**Response** `200 OK`:
```json
{
  "total_active_loans": 47,
  "total_licensees": 3,
  "total_principal_usd": "14250000.00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_active_loans` | int | Number of live bridge loans across all licensees |
| `total_licensees` | int | Count of distinct licensees with active loans |
| `total_principal_usd` | string | Sum of principal across all active loans (decimal-serialised) |

**curl:**
```bash
curl -H "Authorization: $(python3 -c "
from lip.api.auth import sign_request
print(sign_request('GET', '/admin/platform/summary', b'', KEY))
")" http://localhost:8080/admin/platform/summary
```

---

### GET /admin/licensees

List all active licensee IDs (licensees with at least one live loan).

**Response** `200 OK`:
```json
{
  "licensees": ["DEUTDEDB", "BNPAFRPP", "COBADEFF"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `licensees` | string[] | Sorted list of licensee IDs with active loans |

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/admin/licensees
```

---

### GET /admin/licensees/{licensee_id}/stats

Per-licensee active loan count and total principal.

**Path parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `licensee_id` | string | Opaque licensee identifier (hashed BIC or license ID) |

**Response** `200 OK`:
```json
{
  "licensee_id": "DEUTDEDB",
  "active_loan_count": 12,
  "total_principal_usd": "3600000.00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `licensee_id` | string | Echo of the requested licensee ID |
| `active_loan_count` | int | Number of live bridge loans for this licensee |
| `total_principal_usd` | string | Sum of principal across this licensee's active loans |

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/admin/licensees/DEUTDEDB/stats
```

---

### GET /admin/regulatory/dora/export

Export DORA Art.19 ICT-related incident events for NCA submission.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | `json` | Export format: `csv` or `json` |

**Response** `200 OK` (JSON):
```json
[
  {
    "event_id": "dora-2026-001",
    "event_type": "ICT_INCIDENT",
    "severity": "HIGH",
    "timestamp": "2026-03-15T10:22:01Z",
    "description": "Kill switch activated — pipeline halt",
    "resolution_ts": "2026-03-15T10:45:00Z"
  }
]
```

**Response** `200 OK` (CSV):
```
event_id,event_type,severity,timestamp,description,resolution_ts
dora-2026-001,ICT_INCIDENT,HIGH,2026-03-15T10:22:01Z,"Kill switch activated — pipeline halt",2026-03-15T10:45:00Z
```

**curl:**
```bash
# JSON
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  "http://localhost:8080/admin/regulatory/dora/export?format=json"

# CSV
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  "http://localhost:8080/admin/regulatory/dora/export?format=csv"
```

---

### GET /admin/regulatory/sr117/export

Export SR 11-7 model validation reports for regulatory submission.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | `json` | Export format: `csv` or `json` |

**Response** `200 OK` (JSON):
```json
[
  {
    "model_id": "c1-failure-classifier",
    "validation_date": "2026-03-01",
    "dataset": "out_of_time_2026Q1",
    "auc_roc": 0.94,
    "f_beta_score": 0.87,
    "threshold": 0.110,
    "status": "PASS"
  },
  {
    "model_id": "c2-pd-model",
    "validation_date": "2026-03-01",
    "dataset": "out_of_time_2026Q1",
    "gini_coefficient": 0.82,
    "ks_statistic": 0.61,
    "status": "PASS"
  }
]
```

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  "http://localhost:8080/admin/regulatory/sr117/export?format=json"
```

---

## Portfolio Router — `/portfolio`

Real-time portfolio visibility for capital providers and licensee operators.

### GET /portfolio/loans

All active bridge loans with full position detail.

**Response** `200 OK`:
```json
[
  {
    "loan_id": "LN-2026-00142",
    "uetr": "550e8400-e29b-41d4-a716-446655440000",
    "principal_usd": "1000000.00",
    "fee_bps": 300,
    "tier": 1,
    "maturity_date": "2026-03-24T00:00:00+00:00",
    "rejection_class": "CLASS_A",
    "corridor": "EUR-USD",
    "funded_at": "2026-03-21T14:00:00+00:00",
    "days_to_maturity": 3,
    "licensee_id": "DEUTDEDB"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `loan_id` | string | Unique loan identifier |
| `uetr` | string | ISO 20022 Unique End-to-End Transaction Reference |
| `principal_usd` | string | Loan principal (decimal-serialised) |
| `fee_bps` | int | Annualised fee in basis points (floor: 300 bps) |
| `tier` | int | Credit tier (1=investment-grade, 2=private, 3=thin-file) |
| `maturity_date` | string | ISO 8601 loan maturity datetime |
| `rejection_class` | string | Payment failure classification (CLASS_A, CLASS_B, CLASS_C) |
| `corridor` | string | Currency corridor (e.g., EUR-USD, GBP-JPY) |
| `funded_at` | string | ISO 8601 datetime when loan was funded |
| `days_to_maturity` | int | Days remaining until maturity (negative = overdue) |
| `licensee_id` | string | Licensee that originated this loan |

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/portfolio/loans
```

---

### GET /portfolio/exposure

Aggregate exposure broken down by corridor, tier, and maturity class.

**Response** `200 OK`:
```json
{
  "total_exposure_usd": "14250000.00",
  "loan_count": 47,
  "by_corridor": {
    "EUR-USD": { "principal_usd": "8500000.00", "loan_count": 28 },
    "GBP-JPY": { "principal_usd": "5750000.00", "loan_count": 19 }
  },
  "by_tier": {
    "1": { "principal_usd": "10000000.00", "loan_count": 33 },
    "2": { "principal_usd": "3250000.00", "loan_count": 11 },
    "3": { "principal_usd": "1000000.00", "loan_count": 3 }
  },
  "by_maturity_class": {
    "CLASS_A": { "principal_usd": "9000000.00", "loan_count": 30 },
    "CLASS_C": { "principal_usd": "5250000.00", "loan_count": 17 }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_exposure_usd` | string | Sum of all active loan principal |
| `loan_count` | int | Total active loan count |
| `by_corridor` | object | Exposure grouped by currency corridor |
| `by_tier` | object | Exposure grouped by credit tier (1, 2, 3) |
| `by_maturity_class` | object | Exposure grouped by rejection class (CLASS_A/B/C) |

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/portfolio/exposure
```

---

### GET /portfolio/yield

Cumulative and estimated annualised yield on the active book.

**Response** `200 OK`:
```json
{
  "book_principal_usd": "14250000.00",
  "accrued_fee_usd": "23456.78",
  "realised_royalty_usd": "15000.00",
  "estimated_annualised_yield_bps": 342
}
```

| Field | Type | Description |
|-------|------|-------------|
| `book_principal_usd` | string | Total active loan principal |
| `accrued_fee_usd` | string | Estimated fee accrued on active book since funding |
| `realised_royalty_usd` | string | BPI royalty collected via settlement (YTD) |
| `estimated_annualised_yield_bps` | int | Weighted average fee rate across active book |

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/portfolio/yield
```

---

## Known Entities Router — `/known-entities`

Tier-override administration for known, investment-grade counterparties.

### GET /known-entities

List all registered BIC-to-tier overrides.

**Response** `200 OK`:
```json
[
  { "bic": "DEUTDEDB", "tier": 1 },
  { "bic": "BNPAFRPP", "tier": 1 },
  { "bic": "COBADEFF", "tier": 2 }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `bic` | string | SWIFT BIC code (uppercased) |
| `tier` | int | Manual tier override (1, 2, or 3) |

**curl:**
```bash
curl -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/known-entities
```

---

### POST /known-entities

Register a BIC with a manual tier override.

**Query parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bic` | string | Yes | SWIFT BIC code |
| `tier` | int | Yes | Tier value: 1, 2, or 3 |

**Response** `200 OK`:
```json
{
  "bic": "JPMORGAN",
  "tier": 1,
  "status": "registered"
}
```

**curl:**
```bash
curl -X POST \
  -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  "http://localhost:8080/known-entities?bic=JPMORGAN&tier=1"
```

---

### DELETE /known-entities/{bic}

Remove a BIC's tier override.

**Path parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `bic` | string | SWIFT BIC code to remove |

**Response** `200 OK`:
```json
{
  "bic": "JPMORGAN",
  "status": "unregistered"
}
```

**curl:**
```bash
curl -X DELETE \
  -H "Authorization: HMAC-SHA256 <ts>:<hex>" \
  http://localhost:8080/known-entities/JPMORGAN
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `REDIS_URL` | Yes for pilot/prod | Redis/Valkey connection URL. When unset, LIP can run in-memory for single-process demos only. |
| `LIP_REQUIRE_DURABLE_OFFER_STORE` | Yes for pilot/prod | Set to `1` so startup fails closed if `REDIS_URL` is missing or unreachable. |
| `LIP_API_HMAC_KEY` | No | HMAC signing key (hex-encoded or raw string). When unset, auth is disabled (dev mode only). |
| `LIP_KILL_SWITCH_ACTIVE` | No | Set to `true` to start with kill switch engaged. |

## Error Codes Summary

| Status | Meaning | When |
|--------|---------|------|
| 200 | Success | Normal response |
| 401 | Unauthorized | Missing or invalid HMAC signature |
| 503 | Service Unavailable | Readiness check failed (Redis down, kill switch engaged) |
