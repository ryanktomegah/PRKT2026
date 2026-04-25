# BPI C8 License Manager — Component Specification v1.0

> **Component:** C8 — License Manager
> **Classification:** Security Boundary (CIPHER-owned, REX-compliant)
> **Status:** Production — shipped and wired into C2, C3, C4, C6, C7, and lip-api boot paths
> **Last updated:** 2026-04-23

---

## 1. Purpose and Role in the Platform

C8 is the cross-cutting licensing enforcement layer. It answers two questions at every component startup:

1. **Is this deployment authorized by BPI?** Offline HMAC-SHA256 verification of a BPI-signed license token.
2. **What are the operational limits the licensee agreed to?** Per-licensee TPS caps, AML caps, feature flags, and token expiry.

If the token is missing, malformed, expired, signature-invalid, or not scoped to the booting component, the component's kill switch engages and the service refuses to serve requests. There is **no fallback mode** — a deployment without a valid license cannot generate loan offers.

C8 is the only component with **refusal-grade authority** by design — its job is to say "no." It has no state to serve, no HTTP endpoints in the request path, and no dependencies on Redis, Kafka, or any other service.

---

## 2. Architecture

```
                ┌───────────────────────────────┐
                │  BPI License Signing Authority │
                │  (offline; key never on pod)   │
                └───────────────────────────────┘
                          │  HMAC-SHA256 signing
                          ▼
                ┌───────────────────────────────┐
                │  LicenseToken (JSON payload +  │
                │  hex signature; ~2KB)          │
                └───────────────────────────────┘
                          │  delivered to licensee
                          ▼
 ┌────────────────────────────────────────────────────────────────┐
 │                    Licensee K8s Namespace                      │
 │                                                                │
 │   ┌─────────────┐     ┌───────────────┐     ┌──────────────┐   │
 │   │ K8s Secret  │────►│ lip-api pod   │◄────│ lip-c2 pod   │   │
 │   │ (token+key) │     │ C8 boot       │     │ C8 boot      │   │
 │   └─────────────┘     │ validator     │     │ validator    │   │
 │                       └───────────────┘     └──────────────┘   │
 │                              │                                 │
 │                              ▼                                 │
 │                       ┌──────────────┐                         │
 │                       │ KillSwitch   │ engages on any failure  │
 │                       │ (C7-owned)   │                         │
 │                       └──────────────┘                         │
 └────────────────────────────────────────────────────────────────┘
```

### 2.1 Trust Boundary

C8 enforces the technology-licensor boundary between BPI (the platform licensor) and the licensee bank. The cryptographic boundary is a single symmetric HMAC key pair:

- **BPI-side** — holds `license_signing_key` offline, never on any pod. Used only by the issuance tooling in `lip.c8_license_manager.runtime` to sign new tokens.
- **Licensee-side** — holds `license_verification_key` (same key — HMAC is symmetric) in K8s Secret `lip-license-secret`. Used at every component boot to verify the token.

This is a deliberate choice: asymmetric signing (RSA / EdDSA) would allow BPI to publish a public verification key and keep the signing key fully private. The symmetric design is justified because:

1. The licensee is a regulated bank that we already trust operationally — they have access to their own K8s secrets, and compromise of the verification key is equivalent to compromise of their entire deployment.
2. HMAC-SHA256 is substantially faster than asymmetric verification (~10x at boot), and boot speed matters when a fleet of pods restarts.
3. Key rotation is simpler — one key to rotate, not two.

**Downside acknowledged**: a malicious insider at the licensee could forge tokens. The mitigation is (a) every token embeds `licensee_id` + `contract_id` which are audit-trailed against BPI's contract database, and (b) BPI can revoke via a `revocation_list` pushed to licensees who must install it — see § 5.3.

---

## 3. LicenseToken — Data Model

`lip/c8_license_manager/license_token.py` defines the canonical schema:

```python
@dataclass(frozen=True)
class LicenseToken:
    licensee_id: str              # stable identifier assigned by BPI at contract time
    contract_id: str              # BPI contract reference
    deployment_id: str            # per-cluster UUID; enables per-cluster revocation
    issued_at: date               # token issuance date
    expires_at: date              # HARD expiry; no grace period
    licensed_components: frozenset[str]  # {"C1","C2","C3","C4","C5","C6","C7"}
    max_tps: int                  # per-licensee rate limit (0 = unlimited; negotiated per contract)
    aml_dollar_cap_usd: Decimal   # EPG-16; 0 = unlimited; explicit in every token (EPG-17)
    aml_count_cap: int            # EPG-16; 0 = unlimited; explicit in every token (EPG-17)
    signature: Optional[str]      # hex HMAC-SHA256 digest over canonical_payload()
```

### 3.1 Canonical Payload

`canonical_payload()` returns the deterministic byte sequence signed by BPI. The ordering is **lexicographic over the field names** to ensure BPI and the licensee compute identical bytes regardless of dict-insertion-order differences across Python versions.

```
"{aml_count_cap}|{aml_dollar_cap_usd}|{contract_id}|{deployment_id}|"
"{expires_at ISO}|{issued_at ISO}|{licensed_components comma-joined sorted}|"
"{licensee_id}|{max_tps}".encode("utf-8")
```

The `signature` field is excluded from the canonical payload (it is the output, not the input).

### 3.2 EPG-17 Explicit Field Requirement

Every token MUST set `aml_dollar_cap_usd` and `aml_count_cap` explicitly (even when `0` meaning unlimited). `from_dict()` raises if either field is absent — this prevents a parser from silently treating missing keys as "unlimited" when the contract intent was "default = conservative cap."

The rationale (CIPHER + REX joint decision, 2026-03-18):
- Defaulting to unlimited on missing fields is the correct security failure mode for the *compliance code path* (we want AML enforcement to be loud when misconfigured)
- BUT the operational consequence of "silent unlimited" is that a deployment with a broken token parser could process sanction-adjacent payments without AML caps. Making the field explicit ensures the parser fails loudly if the token is malformed.

---

## 4. Boot Validation Flow

`lip/c8_license_manager/boot_validator.py::LicenseBootValidator.validate()` runs at every service's process start. The flow:

```
1. LOAD: token from env var LIP_LICENSE_TOKEN_JSON or file
   LIP_LICENSE_TOKEN_JSON_FILE. Load signing key from env var
   LIP_LICENSE_KEY_HEX or file LIP_LICENSE_KEY_FILE.
   → on any load failure: log CRITICAL, engage kill switch, return None

2. PARSE: LicenseToken.from_dict(json.loads(token_str))
   → on parse error (missing explicit aml_* fields, bad date format):
     log CRITICAL, engage kill switch, return None

3. VERIFY: verify_token(token, signing_key)
   → recomputes HMAC over canonical_payload, compares hex digests with
     hmac.compare_digest (constant-time)
   → on mismatch: log CRITICAL with licensee_id (NEVER the signature
     itself), engage kill switch, return None

4. EXPIRY: token.is_expired(as_of=date.today())
   → on expired: log CRITICAL, engage kill switch, return None

5. SCOPE: required_component in token.licensed_components
   → on out-of-scope: log CRITICAL, engage kill switch, return None

6. CONTEXT: build LicenseeContext from validated token; for processor-mode
   deployments, build ProcessorLicenseeContext
   → return context (never None if we reach this point)
```

### 4.1 Behavior on Validation Failure

The kill switch is a **hard stop**:
- No HTTP server starts (uvicorn never binds)
- No Kafka consumer begins reading
- No background scheduler starts
- The process exits non-zero after 30 seconds (enough to flush logs to stdout)

A licensee running an unlicensed image will see repeated pod crashes in `kubectl get pods` with status `CrashLoopBackOff` and logs showing `C8 license validation failed: <reason>`.

### 4.2 The "Why Kill Switch, Not Raise?" Question

`LicenseBootValidator._engage(reason)` calls `KillSwitch.engage()` rather than raising a Python exception. Three reasons:

1. **C7 kill switch state persists across process restarts** (Redis-backed). A crashed-and-restarted pod stays killed until a valid token is provided, even if the bad token is briefly cached.
2. **Observability** — kill switch engagement emits a Prometheus metric and a decision log entry. A raised exception would be visible only in pod logs.
3. **Uniform stop semantics** — other components that hit fatal errors (KMS unreachable, decision log HMAC failure) also engage the kill switch. C8 uses the same mechanism, so operators have one thing to check.

---

## 5. Runtime Context

### 5.1 LicenseeContext (standard)

Exposed to all licensed components at boot. Downstream code reads it as a dependency injection:

```python
context = boot_validator.validate()
assert context is not None  # would have been None only if kill switch engaged
# context.licensee_id            — used as AML salt namespace (C6 EPG-16)
# context.max_tps                — used by the API rate limiter
# context.aml_dollar_cap_usd     — per-licensee override of canonical cap (C6)
# context.aml_count_cap          — per-licensee override of count cap (C6)
```

### 5.2 ProcessorLicenseeContext (extended)

When the licensee is operating in **processor mode** (BPI's cloud multi-tenant deployment rather than a bank-owned deployment), the context extends to include:

- `tenant_id` — per-tenant namespace for velocity counters
- `tenant_salt` — derived salt (per-tenant HMAC over the base salt) so tenant velocity counters are cryptographically separated
- `royalty_rate` — BPI's royalty share for this tenant (default 30% per canonical constants, tenant-negotiable down to 25%)

`lip.c8_license_manager.license_token.ProcessorLicenseeContext` is the subclass. The distinction is tested via `isinstance()` at `build_runtime_pipeline()` in `lip/api/runtime_pipeline.py`.

### 5.3 Revocation

A licensee-side `LIP_LICENSE_REVOCATION_LIST` env var (or file) can include a set of `(licensee_id, deployment_id)` pairs that BPI has revoked. `verify_token()` checks the revocation list **after** HMAC verification; a revoked deployment_id engages the kill switch just like an invalid signature.

Revocation is pushed to licensees via the standard BPI update channel (license agreement § 7.3 requires licensees to install revocation list updates within 24h of release). A revoked deployment cannot be unrevoked locally — only a new token with a new `deployment_id` re-enables the cluster.

---

## 6. Query Metering and Revenue Metering

### 6.1 Query Metering (`query_metering.py`)

Records every decision log entry with per-licensee counts. Backed by Redis for multi-replica consistency (HINCRBYFLOAT on atomic counter keys per `(licensee_id, component)` pair). The counters feed two surfaces:

1. **TPS rate limiter** in `lip.api.rate_limiter.RateLimiter` — instantaneous sliding-window TPS per licensee
2. **BPI billing reconciliation** — monthly cron that reads the counter, writes an invoice line item

### 6.2 Revenue Metering (`revenue_metering.py`)

For processor-mode deployments (BPI's cloud), records `(licensee_id, tenant_id, fee_collected_usd, phase)` per funded loan. Phase ∈ {`Phase1_Licensor`, `Phase2_Hybrid`, `Phase3_MLO`} determines BPI's royalty share:

| Phase | BPI share | Bank share | Income type |
|-------|-----------|------------|-------------|
| Phase 1 | 30% (royalty) | 70% | ROYALTY |
| Phase 2 | 55% | 30% capital return + 15% distribution premium | LENDING_REVENUE |
| Phase 3 | 80% | 0% capital return + 20% distribution premium | LENDING_REVENUE |

The phase distinction is load-bearing for tax + contract reasons (QUANT rule, see feedback memory) — the same dollar of fee is categorised differently for revenue-recognition purposes.

### 6.3 Regulator Subscription (`regulator_subscription.py`)

For tenants subject to DORA Art.19 incident-reporting obligations, exposes a subscription endpoint that streams decision log entries filtered by tenant scope to the regulator's reporting pipeline. C8 enforces the subscription's scope — a regulator subscribed to tenant A cannot observe tenant B's decisions.

---

## 7. Component Enforcement (`runtime.py`)

`enforce_component_license(component_name: str)` is the boot-time gate every other component calls:

```python
# lip/c2_pd_model/api.py
def create_app() -> FastAPI:
    enforce_component_license("C2")   # raises / engages kill switch on failure
    ...
```

Components MUST call this before any request-handling code runs. The pattern:

| Component | Call site |
|-----------|-----------|
| C1 | `lip/c1_failure_classifier/api.py::create_app()` |
| C2 | `lip/c2_pd_model/api.py::create_app()` |
| C3 | `lip/c3_repayment_engine/api.py::create_app()` |
| C4 | `lip/c4_dispute_classifier/api.py::create_app()` |
| C6 | `lip/c6_aml_velocity/api.py::create_app()` |
| C7 (lip-api) | `lip/api/app.py::create_app()` |
| C9 (batch job) | `lip/c9_settlement_predictor/job.py::main()` |

C5 (streaming) does not go through this gate — its license check is done at the Kafka consumer group level by the Go consumer, which refuses to subscribe to a LIP topic without a valid service-account license.

---

## 8. Security Properties and Threat Model

### 8.1 Properties Claimed

| Property | How enforced |
|----------|-------------|
| **No deployment runs without a valid, current, scoped, and non-revoked license** | Boot validator — every component. |
| **License compromise is detected on first expiry or revocation** | Hard expiry check; revocation list. |
| **An attacker who compromises the licensee's K8s secret cannot forge a new token** | HMAC-SHA256 with 32+ byte key; requires the BPI signing key. |
| **Token replay across deployments is prevented** | `deployment_id` field binds a token to a specific cluster. BPI issues different `deployment_id` per cluster. |
| **Temporal tampering (clock skew attack)** | `is_expired` uses `date.today()` — clock-skew of hours is tolerable, clock-skew of days would require malicious admin access to the K8s node which is a higher-order compromise. |

### 8.2 Threats Out of Scope

- **Compromise of the BPI signing key** — mitigated by offline key storage + hardware-key rotation procedure (see CIPHER runbook). Not a C8 runtime concern.
- **Malicious code in the licensee's own image** — if an attacker controls the image itself, they could remove the `enforce_component_license` call. Mitigation is image integrity (OSS attribution gate, signed container images) — not C8's scope.
- **Side-channel extraction of the verification key from pod memory** — would require kernel-level compromise of the licensee's node. Not in C8's threat model.

---

## 9. Token Lifecycle Operations

### 9.1 Issuance (BPI operations, offline)

```bash
# BPI operator, offline machine, with the signing key in .secrets/bpi_signing_key
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

### 9.2 Deployment (licensee K8s operator)

```bash
# Licensee-side, with the token file received from BPI + the symmetric key
kubectl -n lip-staging create secret generic lip-license-secret \
    --from-file=token_json=LICENCE_BANK_ABC_DEPLOY_20260423.json \
    --from-file=key_hex=.secrets/lip_license_key_hex
```

### 9.3 Rotation (every contract renewal)

Rotate on the same day as the old token's expiry. Overlap window: 24 hours — both the old and new tokens are simultaneously valid, and pods read the secret at boot, so a rolling restart in the 24h window picks up the new token without downtime.

### 9.4 Revocation (BPI → licensee, incident response)

BPI pushes an updated `LIP_LICENSE_REVOCATION_LIST` to all licensees as a K8s ConfigMap update. Licensees are contractually obligated to apply within 24h. Revoked clusters engage kill switch on next boot.

---

## 10. Testing

| Test file | Scope | Count |
|-----------|-------|-------|
| `test_c8_license.py` | Token sign/verify, parse, canonical payload, EPG-17 explicit fields, expiry | ~20 |
| `test_c8_processor.py` | ProcessorLicenseeContext derivation, tenant salt, royalty rate | ~10 |

Boot-validator failure modes are tested in `test_api_runtime_pipeline.py` (integration) — any of the six failure categories in § 4 triggers kill switch engagement in the test harness.

---

## 11. Deployment

C8 does NOT run as a long-lived service in the request path. Its code is imported into every other component's process via `enforce_component_license`. A standalone `Dockerfile.c8` exists (`lip/infrastructure/docker/Dockerfile.c8`) exclusively for BPI-operator tooling — token issuance, metering reconciliation, regulator subscription admin. This image is **never** deployed to licensee clusters.

See `docs/operations/deployment.md` for the full K8s topology and how `lip-license-secret` is provisioned in each licensee namespace.

---

## 12. Approval Record

| Role | Name | Date | Status |
|------|------|------|--------|
| Component Author | CIPHER | 2026-03-18 | Shipped |
| Security Review | CIPHER | 2026-03-18 | Final authority on C8 design |
| Regulatory Review | REX | 2026-04-23 | Spec issued; DORA Art.19 subscription surface approved |
| Financial Math | QUANT | 2026-03-18 | Phase-share table signed off (§ 6.2) |
| Bank MRM | Pending | — | Pre-pilot; awaiting bank engagement |

---

*BPI C8 Component Spec v1.0 — Bridgepoint Intelligence Inc.*
*CIPHER-owned security boundary. REX-compliant regulator-scoped audit surface.*
*Generated 2026-04-23. Internal use only. Stealth mode active.*
