# `lip/api/` — FastAPI Surface

> **The HTTP boundary of LIP.** Every external caller — bank pilot integrations, BPI admin tooling, regulator-facing exports, the cascade-engine consumers — enters through this directory. K8s expects HTTP on port 8080; this is what serves it.

**Source:** `lip/api/`
**Module count:** 14 routers and services
**Entrypoint:** `lip/api/app.py` → `uvicorn lip.api.app:app --host 0.0.0.0 --port 8080`
**Closes:** GAP-22 (K8s HTTP-on-8080 requirement)

---

## Purpose

`lip/api/` assembles all FastAPI routers into a single application with graceful shutdown, HMAC authentication, rate limiting, and a health-check endpoint. It is intentionally **thin** — routers delegate to service classes, and service classes delegate to the actual component code in `lip/c{N}_*/` and `lip/common/`.

The HTTP layer exists for three audiences:
1. **Pilot bank integrations** that cannot embed the LIP package directly and need an HTTP API
2. **BPI admin tooling** for multi-tenant monitoring and licensee management (closes GAP-15)
3. **Regulators** consuming SR 11-7 / DORA / EU AI Act exports (closes GAP-14, with `regulatory_router.py`)

---

## Application assembly

`app.py` provides:

- `create_app()` — factory for testing / programmatic use
- A module-level `app` for `uvicorn lip.api.app:app`
- An `asynccontextmanager` lifespan that wires up shared resources at startup and tears them down on shutdown

The factory composes all routers (admin, MIPLO, portfolio, regulatory, cascade, health) and applies the HMAC authentication dependency from `auth.py`.

---

## Routers and services

| Router | Service | Purpose | Lines |
|--------|---------|---------|-------|
| `admin_router.py` | `BPIAdminService` | Multi-tenant administration: licensee management, configuration, audit queries (closes GAP-15) | — |
| `miplo_router.py` | `miplo_service.py` | MIPLO (Money In / Payment Lending Organisation) endpoints — the bank-side bridge-loan acceptance and execution surface | 159 / 151 |
| `portfolio_router.py` | (inline) | Portfolio reporting API for MLO (closes GAP-07) — outstanding loans, exposures, settlement progress | 392 |
| `regulatory_router.py` | `regulatory_service.py` + `regulatory_models.py` | Regulator-facing exports — DORA Art. 19 incidents, SR 11-7 model validation reports, EU AI Act Art. 61 logging (closes GAP-14) | 537 / 298 / 167 |
| `cascade_router.py` | `cascade_service.py` | P5 cascade engine HTTP surface — coordinated intervention API and supply-chain cascade alerts (Sprint 3d). See [`p5_cascade_engine.md`](p5_cascade_engine.md). | — |
| `health_router.py` | `DefaultReadinessChecker` | K8s liveness + readiness probes; health checks include downstream Redis / Kafka availability | — |

## Cross-cutting middleware

| File | Purpose |
|------|---------|
| `auth.py` | `make_hmac_dependency` — HMAC-SHA256 request authentication. Tied to the C8 license token, so the same key material that authorises a licensee's pipeline use also authorises their HTTP calls. |
| `rate_limiter.py` | Per-licensee request rate limiting (default to license-token bucket sizes) | 83 |

## Boundary rule

`lip/api/` modules are allowed to import from `lip/c{N}_*/`, `lip/common/`, `lip/p5_cascade_engine/`, `lip/p10_regulatory_data/`, and `lip/risk/`. They must **not** contain business logic — every router function is either a thin adapter (parse request → call service → format response) or a permission check. Logic that does not fit that shape belongs in a service class or, more often, in the relevant component module.

## Authentication & security

- **HMAC-SHA256** request signing tied to C8 license token material
- **Per-licensee rate limiting** with bucket sizes from the license token
- **Network policies** at the K8s layer (see `lip/infrastructure/`) — `regulatory_router` is reachable only from internal mTLS namespaces; `miplo_router` is reachable only from the pilot bank's mTLS peer
- **Graceful shutdown** flushes in-flight pipeline executions and refuses new requests with 503 once the lifespan teardown begins

## Cross-references

- **Three-layer enrollment requirement** (License Agreement → MRFA → Borrower Registry) — every `miplo_router` endpoint enforces all three before issuing offers. See `PROGRESS.md` § Three-Layer Enrollment Requirement.
- **DORA / SR 11-7 export shape**: `regulatory_models.py` defines the canonical Pydantic models; the underlying data comes from `lip/common/regulatory_reporter.py`
- **Portfolio reporting**: backed by `lip/risk/portfolio_risk.py` (see [`risk.md`](risk.md)) and `lip/c3_repayment_engine/`
- **Cascade endpoints**: backed by `lip/p5_cascade_engine/` (see [`p5_cascade_engine.md`](p5_cascade_engine.md))
- **Operative compliance**: see [`../decisions/EPG-19_compliance_hold_bridging.md`](../decisions/EPG-19_compliance_hold_bridging.md) — there is no API endpoint that can override the compliance-hold block
