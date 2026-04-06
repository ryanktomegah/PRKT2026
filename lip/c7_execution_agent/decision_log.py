"""
decision_log.py — Immutable HMAC-SHA256 signed decision log.
Architecture Spec S4.8: 7-year retention.

Regulatory obligations covered by this module:
  EU AI Act Art.13(2)(b) — Transparency: every automated credit decision must be
    logged with its inputs, outputs, and decision type.
  EU AI Act Art.17     — Quality management: audit trail for model governance.
  EU AI Act Art.61     — Post-market monitoring: decision logs feed monitoring pipeline.
  SR 11-7 (Fed/OCC)    — Model risk management: model decisions must be auditable.
  FINTRAC / FinCEN     — AML record retention: AML-blocked decisions (BLOCK type with
    aml_passed=False) must be retained for ≥ 5 years (RETENTION_YEARS=7 exceeds this).
  DORA Art.30          — ICT incident reporting: kill-switch activations and KMS
    unavailability gaps are captured in kms_unavailable_gap field.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import hashlib
import hmac
import json
import logging
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

RETENTION_YEARS = 7

# Schema version hash — first 16 hex chars of the canonical schema digest.
# Used to detect log format drift across deployments without full re-parse.
_SCHEMA_VALIDATION_HASH: str = "e47fc6d4b19465c9"


@dataclass
class DecisionLogEntryData:
    """Immutable decision log entry. entry_signature is set after all other fields are populated."""
    entry_id: str
    uetr: str
    individual_payment_id: str
    decision_type: str           # OFFER | FUND | REPAY | BLOCK | DECLINE | OVERRIDE
    decision_timestamp: str      # ISO-8601
    failure_probability: float
    pd_score: float
    fee_bps: int
    loan_amount: str             # Decimal serialised as string
    dispute_class: str
    aml_passed: bool
    human_override: bool = False
    degraded_mode: bool = False
    gpu_fallback: bool = False
    kms_unavailable_gap: Optional[float] = None  # seconds
    operator_id: Optional[str] = None
    licensee_id: str = ""        # C8 license: identifies which BPI licensee generated this entry
    tenant_id: str = ""             # P3: processor tenant for per-tenant audit partitioning
    entry_signature: str = ""    # HMAC-SHA256; populated by DecisionLogger.log()


class DecisionLogger:
    """Immutable HMAC-SHA256 signed decision log with 7-year retention.

    The in-memory ``_store`` is a bounded LRU cache (default 10 000 entries).
    When ``_store_maxsize`` is reached the oldest entry is evicted.  Permanent
    retention is the responsibility of ``storage_backend`` (e.g. PostgreSQL).
    The in-memory store is only a short-term lookup cache for the current
    process lifetime.
    """

    _DEFAULT_STORE_MAXSIZE = 10_000

    def __init__(self, hmac_key: bytes, storage_backend=None, *, store_maxsize: int = _DEFAULT_STORE_MAXSIZE):
        # Security invariant: HMAC key must be ≥ 32 bytes (256-bit minimum).
        # Keys shorter than this weaken the MAC against brute-force attacks on the audit log.
        if len(hmac_key) < 32:
            raise ValueError(
                f"HMAC key must be ≥ 32 bytes for HMAC-SHA256 integrity. "
                f"Got {len(hmac_key)} bytes. Source key from a secrets manager."
            )
        self._key = hmac_key
        self._store_maxsize = max(1, store_maxsize)
        # OrderedDict used as a bounded LRU: oldest entry evicted when maxsize reached.
        self._store: OrderedDict[str, DecisionLogEntryData] = OrderedDict()
        self._backend = storage_backend

    # ── public API ──────────────────────────────────────────────────────────

    def log(self, entry: DecisionLogEntryData) -> str:
        if not entry.entry_id:
            entry.entry_id = str(uuid.uuid4())
        entry.entry_signature = self._sign_entry(entry)
        # Evict oldest entry when the store is at capacity (LRU eviction).
        if len(self._store) >= self._store_maxsize and entry.entry_id not in self._store:
            self._store.popitem(last=False)
        self._store[entry.entry_id] = entry
        if self._backend:
            self._backend.save(entry)
        logger.info("Decision logged: %s type=%s uetr=%s",
                    entry.entry_id, entry.decision_type, entry.uetr)
        return entry.entry_id

    def verify(self, entry_id: str) -> bool:
        entry = self.get(entry_id)
        if entry is None:
            return False
        expected = self._sign_entry(entry)
        return hmac.compare_digest(entry.entry_signature, expected)

    def get(self, entry_id: str) -> Optional[DecisionLogEntryData]:
        return self._store.get(entry_id)

    def get_by_uetr(self, uetr: str) -> List[DecisionLogEntryData]:
        return [e for e in self._store.values() if e.uetr == uetr]

    # ── internal helpers ─────────────────────────────────────────────────────

    def _sign_entry(self, entry: DecisionLogEntryData) -> str:
        canonical = self._entry_to_canonical_json(entry)
        return hmac.new(self._key, canonical, hashlib.sha256).hexdigest()

    def _entry_to_canonical_json(self, entry: DecisionLogEntryData) -> bytes:
        d = asdict(entry)
        d.pop("entry_signature", None)
        return json.dumps(d, sort_keys=True, default=str).encode()
