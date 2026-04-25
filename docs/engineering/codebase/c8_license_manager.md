# `lip/c8_license_manager/` — License Enforcement and Metering

> **The security-boundary component.** C8 answers one question at every service's boot: "is this deployment authorized by BPI?" If the answer is no, the kill switch engages and nothing serves traffic. CIPHER has final authority over this code; REX has final authority over its metering outputs.

**Source:** `lip/c8_license_manager/`
**Module count:** 7 Python files, 1,504 LoC
**Test files:** 2 (`test_c8_{license,processor}.py`)
**Spec:** [`../specs/BPI_C8_Component_Spec_v1.0.md`](../specs/BPI_C8_Component_Spec_v1.0.md)

---

## Purpose

C8 is a **cross-cutting enforcement layer**, not a request-path service. Its code is imported into every other component's process and called at boot via `enforce_component_license(component_name)`. If validation fails, the kill switch engages.

Three operational surfaces:

1. **Boot validation** — offline HMAC-SHA256 verification that the deployed component is entitled to run
2. **Query metering** — per-licensee count of decisions, feeding the TPS rate limiter and monthly BPI billing
3. **Regulator subscriptions** — DORA Art.19 streaming audit surface

No HTTP endpoints in the request path. No Kafka subscriptions. No Redis writes except for metering counters and kill-switch state.

---

## The token model (`license_token.py`)

`LicenseToken` is the canonical schema. Every field is explicit (no silent defaults):

```python
@dataclass(frozen=True)
class LicenseToken:
    licensee_id: str              # stable identifier from BPI contract
    contract_id: str              # BPI contract reference
    deployment_id: str            # per-cluster UUID; enables per-cluster revocation
    issued_at: date
    expires_at: date              # HARD expiry; no grace period
    licensed_components: frozenset[str]  # {"C1","C2","C3","C4","C5","C6","C7"}
    max_tps: int                  # per-licensee rate limit (0 = unlimited)
    aml_dollar_cap_usd: Decimal   # EPG-16; 0 = unlimited; explicit (EPG-17)
    aml_count_cap: int            # EPG-16; 0 = unlimited; explicit (EPG-17)
    signature: Optional[str]      # hex HMAC-SHA256 over canonical_payload()
```

### Canonical payload

`canonical_payload()` returns the bytes BPI signs. **Lexicographic field ordering** to ensure deterministic serialization across Python versions:

```
"{aml_count_cap}|{aml_dollar_cap_usd}|{contract_id}|{deployment_id}|"
"{expires_at ISO}|{issued_at ISO}|{licensed_components sorted comma-joined}|"
"{licensee_id}|{max_tps}".encode("utf-8")
```

The `signature` field is excluded from the canonical payload.

### EPG-17 explicit fields

Every token **must** set `aml_dollar_cap_usd` and `aml_count_cap` explicitly, even when zero (unlimited). `from_dict()` raises `ValueError` if either is absent. The rationale: a token parser that silently defaults missing fields to "unlimited" could accidentally process sanction-adjacent payments without AML caps. Making the field explicit fails loudly on misconfiguration.

---

## Boot validation (`boot_validator.py`)

`LicenseBootValidator.validate()` — the 6-step flow:

```
1. LOAD   — token JSON from LIP_LICENSE_TOKEN_JSON env var or file
            HMAC key from LIP_LICENSE_KEY_HEX env var or file
2. PARSE  — LicenseToken.from_dict(json.loads(token_str))
            (raises on missing aml_* fields — EPG-17)
3. VERIFY — verify_token(token, signing_key)
            constant-time HMAC comparison via hmac.compare_digest
4. EXPIRY — token.is_expired(as_of=date.today())
5. SCOPE  — required_component in token.licensed_components
6. CTX    — build LicenseeContext (or ProcessorLicenseeContext)
```

Any failure engages the KillSwitch. Kill-switch state persists in Redis so a crashed-and-restarted pod stays dead until a valid token is provided.

### "Why kill switch, not raise?"

1. Kill switch state persists across process restarts (Redis-backed) — a transient bad token stays rejected until manually cleared.
2. Observability — engagement emits a Prometheus metric and a decision log entry. Raising an exception is only visible in pod logs.
3. Uniform stop semantics with other fatal conditions (KMS unreachable, decision log HMAC failure).

---

## Runtime context (`license_token.py`)

### LicenseeContext (standard)

Exposed to all licensed components at boot:

```python
# context.licensee_id       — AML salt namespace (C6 EPG-16)
# context.max_tps           — API rate limiter
# context.aml_dollar_cap_usd — C6 per-licensee override
# context.aml_count_cap      — C6 per-licensee override
```

### ProcessorLicenseeContext (extended, BPI cloud multi-tenant)

```python
# context.tenant_id         — per-tenant namespace for velocity counters
# context.tenant_salt       — derived salt (HMAC over base salt); tenants cryptographically separated
# context.royalty_rate      — BPI's royalty share for this tenant (default 0.30 per canonical constants)
```

The distinction is tested via `isinstance()` at `build_runtime_pipeline()` in `runtime_pipeline.py`. When C8 returns a `ProcessorLicenseeContext`, the pipeline runs in multi-tenant mode and passes the tenant ID into every decision log entry.

### Revocation (`LIP_LICENSE_REVOCATION_LIST`)

A licensee-side file / env var listing `(licensee_id, deployment_id)` pairs revoked by BPI. `verify_token()` checks the revocation list **after** HMAC verification. A revoked deployment engages the kill switch on next boot.

Licensees are contractually obligated (license agreement § 7.3) to apply revocation list updates within 24 hours. BPI pushes updates via the standard ConfigMap update channel.

---

## Query metering (`query_metering.py`)

Records every decision log entry in per-licensee counters:

- Redis key: `lip:c8:query_count:<licensee_id>:<component>`
- Increment: `INCR` (atomic)
- TTL: 40 days (retention for monthly billing reconciliation + 10-day buffer)

Two consumers:

| Consumer | Purpose |
|----------|---------|
| `lip.api.rate_limiter.RateLimiter` | Instantaneous sliding-window TPS per licensee — enforces `max_tps` from the license token |
| BPI monthly billing reconciliation | Reads counters via admin API; writes invoice line items |

Tests: `test_c8_license.py::test_query_metering_increment`, `test_query_metering_redis_backend.py` (end-to-end with real Redis).

---

## Revenue metering (`revenue_metering.py`)

For processor-mode deployments (BPI cloud), records per-loan revenue with phase classification:

| Phase | BPI share | Bank share | Income type |
|-------|-----------|------------|-------------|
| Phase 1 (Licensor) | 30% (royalty) | 70% | ROYALTY |
| Phase 2 (Hybrid) | 55% | 30% capital return + 15% distribution premium | LENDING_REVENUE |
| Phase 3 (Full MLO) | 80% | 0% capital return + 20% distribution premium | LENDING_REVENUE |

The phase distinction is load-bearing for tax + contract reasons. The same dollar of fee is categorised differently for revenue recognition — "royalty" (passive, tax-advantaged) vs "lending revenue" (active, different accounting treatment).

Bank fee shares MUST decompose into **capital return + distribution premium** (user QUANT rule; see feedback memory). Any code path that reports bank share as a single monolithic percentage creates a Phase 3 negotiation trap.

---

## Regulator subscription (`regulator_subscription.py`)

DORA Art.19 requires licensees subject to the regulation to expose an incident-reporting endpoint. C8 hosts the subscription surface:

```
POST /admin/regulator/subscribe     → register a regulator for tenant scope
GET  /admin/regulator/stream/<id>   → SSE stream of filtered decision log entries
DELETE /admin/regulator/<id>        → unsubscribe
```

Scope enforcement is CIPHER-audited — a regulator subscribed to tenant A CANNOT observe tenant B's decisions. The `tenant_id` field in every decision log entry is the scope boundary.

Tests: `test_p10_regulator_subscription.py` (integration with P10's regulatory service).

---

## Component enforcement (`runtime.py`)

`enforce_component_license(component_name: str)` is the boot-time gate every other component calls:

| Component | Call site |
|-----------|-----------|
| C1 | `lip/c1_failure_classifier/api.py::create_app()` (when standalone) |
| C2 | `lip/c2_pd_model/api.py::create_app()` |
| C3 | `lip/c3_repayment_engine/api.py::create_app()` |
| C4 | `lip/c4_dispute_classifier/api.py::create_app()` |
| C6 | `lip/c6_aml_velocity/api.py::create_app()` |
| C7 (lip-api) | `lip/api/app.py::create_app()` |
| C9 (batch job) | `lip/c9_settlement_predictor/job.py::main()` |

C5 (streaming) validates via the Kafka consumer group — the Go consumer refuses to subscribe to a LIP topic without a valid service-account license.

---

## Token lifecycle

### Issuance (BPI operations, offline)

```bash
# Operator on an air-gapped machine with the signing key
python -m lip.c8_license_manager.runtime issue \
    --licensee-id BANK_ABC \
    --contract-id CON-2026-0012 \
    --deployment-id $(uuidgen) \
    --expires-at 2027-04-23 \
    --licensed-components C1,C2,C3,C4,C5,C6,C7 \
    --max-tps 500 \
    --aml-dollar-cap-usd 10000000 \
    --aml-count-cap 1000 \
    --signing-key-file .secrets/bpi_signing_key \
    --output LICENCE_BANK_ABC_DEPLOY_$(date +%Y%m%d).json
```

### Deployment (licensee K8s operator)

```bash
kubectl -n lip-staging create secret generic lip-license-secret \
    --from-file=token_json=LICENCE_BANK_ABC_DEPLOY_20260423.json \
    --from-file=key_hex=.secrets/lip_license_key_hex
```

### Rotation (on contract renewal)

Rotate on the old token's expiry day. Overlap window: 24 hours — both tokens valid simultaneously, pods read secret at boot, rolling restart picks up the new token without downtime.

---

## Image deployment

`Dockerfile.c8` exists (`lip/infrastructure/docker/Dockerfile.c8`) but is **not deployed to licensee clusters**. It is a BPI-operator-only image for:

1. Offline token issuance / rotation
2. Query metering + revenue metering reconciliation CLIs
3. Regulator subscription admin

Labelled `deployment-scope="bpi-only"`. The image contains no plaintext keys; all sign/verify requires the HMAC key mounted via `LIP_LICENSE_SIGNING_KEY_FILE` at runtime.

Banks running LIP never see this image. They receive only signed tokens and the verification key.

---

## Consumers

| Consumer | How it uses C8 |
|----------|---------------|
| Every C* service at boot | `enforce_component_license` — engages kill switch on failure |
| `lip/api/runtime_pipeline.py` | Reads `LicenseeContext` / `ProcessorLicenseeContext` for pipeline construction |
| `lip/c6_aml_velocity/aml_checker.py` | Reads `aml_dollar_cap_usd`, `aml_count_cap` for EPG-16 enforcement |
| `lip/api/rate_limiter.py` | Reads `max_tps` for sliding-window rate limit |
| `lip/p10_regulatory_data/` | Reads tenant scope for regulator export filtering |

---

## What C8 does NOT do

- **Does not make network calls** to BPI at runtime — validation is offline HMAC. The only network egress is Redis (metering) and Kafka (decision log).
- **Does not mint tokens** at runtime — issuance is offline, done by the BPI-operator image only.
- **Does not auto-renew** expired tokens — expiry is hard; requires BPI to issue a new token.
- **Does not talk to regulators directly** — the subscription surface is plumbing; filtering and reporting live in P10.

---

## Cross-references

- **Spec** — [`../specs/BPI_C8_Component_Spec_v1.0.md`](../specs/BPI_C8_Component_Spec_v1.0.md) (the canonical reference)
- **Pipeline** — [`pipeline.md`](pipeline.md) § Construction — LicenseeContext injection
- **EPG-16 / EPG-17** — [`../../legal/decisions/EPG-16-18_aml_caps_human_review.md`](../../legal/decisions/EPG-16-18_aml_caps_human_review.md)
- **Constants** — `lip/common/constants.py` § License / Revenue (PLATFORM_ROYALTY_RATE, SALT_ROTATION_DAYS)
- **Integrity gate** — [`integrity.md`](integrity.md)
