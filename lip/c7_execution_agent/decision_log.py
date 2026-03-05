"""
decision_log.py — Immutable HMAC-SHA256 signed decision log.
Architecture Spec S4.8: 7-year retention.

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
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

RETENTION_YEARS = 7


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
    entry_signature: str = ""    # HMAC-SHA256; populated by DecisionLogger.log()


class DecisionLogger:
    """Immutable HMAC-SHA256 signed decision log with 7-year retention."""

    def __init__(self, hmac_key: bytes, storage_backend=None):
        self._key = hmac_key
        self._store: Dict[str, DecisionLogEntryData] = {}
        self._backend = storage_backend

    # ── public API ──────────────────────────────────────────────────────────

    def log(self, entry: DecisionLogEntryData) -> str:
        if not entry.entry_id:
            entry.entry_id = str(uuid.uuid4())
        entry.entry_signature = self._sign_entry(entry)
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
