"""
cbdc_normalizer.py — CBDC-to-ISO 20022 payment event normalization.

Patent Family 5 (P5): Normalizes CBDC payment failure events from e-CNY (PBoC),
e-EUR (ECB experimental), and Sand Dollar (CBB) into canonical ISO 20022
pacs.008/pacs.002 format for the existing C5 pipeline.

Architecture:
  - Input: CBDC-specific failure event dicts from central bank APIs/webhooks.
  - Output: NormalizedEvent with rail set to CBDC_ECNY / CBDC_EEUR / CBDC_SAND_DOLLAR.
  - Failure codes: CBDC-specific codes mapped to ISO 20022 equivalents so
    downstream components (C7 compliance gate, rejection taxonomy, C1 classifier)
    operate on a uniform code space without CBDC-specific branching logic.

NOVA sign-off required for protocol-level changes.
REX sign-off required for regulatory disclosure of CBDC handling.
"""
from __future__ import annotations

import logging

from lip.c5_streaming.event_normalizer import (
    NormalizedEvent,
    _compute_telemetry_eligibility,
    _safe_datetime,
    _safe_decimal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CBDC failure code → ISO 20022 mapping
# ---------------------------------------------------------------------------
# Patent Family 5, Dependent Claim 3: CBDC-specific failure codes translated
# to ISO 20022 equivalents. Downstream pipeline components process these
# uniformly without CBDC-specific branching.
#
# EPG-20/21: No AML/SAR/OFAC/PEP language in this mapping. CBDC-KYC01 maps
# to RR01 (MissingDebtorAccountOrIdentification) — the generic KYC failure
# code, not a compliance-investigation indicator.

CBDC_FAILURE_CODE_MAP: dict[str, str] = {
    # Smart contract / account errors
    "CBDC-SC01": "AC01",   # smart contract execution failure → ClosedAccountNumber
    "CBDC-SC02": "AC04",   # smart contract timeout → ClosedAccountNumber (account unavailable)
    "CBDC-SC03": "ED05",   # contract validation failure → SettlementFailed
    # KYC / identity errors
    "CBDC-KYC01": "RR01",  # KYC identity verification failure → MissingDebtorAccountOrIdentification
    "CBDC-KYC02": "RR02",  # KYC address verification failure → MissingDebtorNameOrAddress
    # Liquidity errors
    "CBDC-LIQ01": "AM04",  # liquidity pool insufficient → InsufficientFunds
    "CBDC-LIQ02": "AM02",  # amount exceeds CBDC wallet limit → NotAllowedAmount
    # Finality / timing errors
    "CBDC-FIN01": "TM01",  # finality timeout → InvalidCutOffTime
    "CBDC-FIN02": "DT01",  # settlement date mismatch → InvalidDate
    # Cross-chain interoperability errors
    "CBDC-INT01": "FF01",  # interoperability bridge failure → InvalidFileFormat (closest analog)
    "CBDC-INT02": "NARR",  # cross-chain protocol error → Narrative (no direct ISO equivalent)
    # Cryptographic errors
    "CBDC-CRY01": "DS02",  # signature validation failure → OrderRejected
    "CBDC-CRY02": "DS02",  # certificate chain error → OrderRejected
    # Network congestion
    "CBDC-NET01": "MS03",  # network congestion delay → NotSpecifiedReasonAgentGenerated
}


def normalize_cbdc_failure_code(cbdc_code: str | None) -> str | None:
    """Map a CBDC-specific failure code to its ISO 20022 equivalent.

    Unknown CBDC codes are passed through with a warning so the downstream
    taxonomy applies its safe default (BLOCK for unknown = fail-closed).
    """
    if not cbdc_code:
        return None
    upper = cbdc_code.strip().upper()
    mapped = CBDC_FAILURE_CODE_MAP.get(upper)
    if mapped:
        return mapped
    logger.warning(
        "Unknown CBDC failure code %r — passing through for fail-closed handling.",
        cbdc_code,
    )
    return cbdc_code


class CBDCNormalizer:
    """Normalizes CBDC payment failure events to the canonical NormalizedEvent format.

    Supports three CBDC rails:
      - e-CNY (PBoC): ``normalize_ecny()``
      - e-EUR (ECB experimental): ``normalize_eeur()``
      - Sand Dollar (CBB): ``normalize_sand_dollar()``

    Each rail produces a NormalizedEvent with the rail field set to the
    CBDC-specific identifier (CBDC_ECNY, CBDC_EEUR, CBDC_SAND_DOLLAR) so
    downstream components can apply differential maturity logic via
    RAIL_MATURITY_HOURS in constants.py.
    """

    SUPPORTED_RAILS: frozenset[str] = frozenset({
        "CBDC_ECNY",
        "CBDC_EEUR",
        "CBDC_SAND_DOLLAR",
    })

    def normalize_ecny(self, msg: dict) -> NormalizedEvent:
        """Parse a PBoC e-CNY payment failure event.

        Expected e-CNY event schema (PBoC Digital Currency Electronic Payment):
          - transaction_id: unique transaction identifier
          - wallet_id_sender: sender digital wallet ID
          - wallet_id_receiver: receiver digital wallet ID
          - amount: transaction amount in CNY
          - currency: always "CNY"
          - timestamp: ISO 8601 event timestamp
          - failure_code: CBDC-specific failure code
          - failure_description: human-readable description
          - institution_bic_sender: BIC of sender's servicing institution
          - institution_bic_receiver: BIC of receiver's servicing institution
        """
        amount = _safe_decimal(msg.get("amount", "0"))
        currency = msg.get("currency", "CNY")

        sttlm = msg.get("settlement_amount")
        original_amount = _safe_decimal(sttlm) if sttlm else None

        event = NormalizedEvent(
            uetr=msg.get("transaction_id", ""),
            individual_payment_id=msg.get("payment_reference", msg.get("transaction_id", "")),
            sending_bic=msg.get("institution_bic_sender", msg.get("wallet_id_sender", "")),
            receiving_bic=msg.get("institution_bic_receiver", msg.get("wallet_id_receiver", "")),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get("timestamp")),
            rail="CBDC_ECNY",
            rejection_code=normalize_cbdc_failure_code(msg.get("failure_code")),
            narrative=msg.get("failure_description"),
            raw_source=msg,
            original_payment_amount_usd=original_amount,
        )
        event.telemetry_eligible = _compute_telemetry_eligibility(event)
        return event

    def normalize_eeur(self, msg: dict) -> NormalizedEvent:
        """Parse an ECB experimental e-EUR payment failure event.

        Expected e-EUR event schema (ECB DLT pilot):
          - tx_hash: DLT transaction hash (used as UETR equivalent)
          - sender_iban: sender's IBAN or DLT address
          - receiver_iban: receiver's IBAN or DLT address
          - amount: transaction amount
          - currency: always "EUR"
          - created_at: ISO 8601 event timestamp
          - error_code: CBDC-specific failure code
          - error_message: human-readable error description
          - sender_bic: BIC of sender's servicing institution
          - receiver_bic: BIC of receiver's servicing institution
        """
        amount = _safe_decimal(msg.get("amount", "0"))
        currency = msg.get("currency", "EUR")

        sttlm = msg.get("settlement_amount")
        original_amount = _safe_decimal(sttlm) if sttlm else None

        event = NormalizedEvent(
            uetr=msg.get("tx_hash", ""),
            individual_payment_id=msg.get("end_to_end_id", msg.get("tx_hash", "")),
            sending_bic=msg.get("sender_bic", msg.get("sender_iban", "")),
            receiving_bic=msg.get("receiver_bic", msg.get("receiver_iban", "")),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get("created_at")),
            rail="CBDC_EEUR",
            rejection_code=normalize_cbdc_failure_code(msg.get("error_code")),
            narrative=msg.get("error_message"),
            raw_source=msg,
            original_payment_amount_usd=original_amount,
        )
        event.telemetry_eligible = _compute_telemetry_eligibility(event)
        return event

    def normalize_sand_dollar(self, msg: dict) -> NormalizedEvent:
        """Parse a Central Bank of the Bahamas Sand Dollar payment failure event.

        Expected Sand Dollar event schema (CBB):
          - reference_id: unique transaction reference
          - sender_wallet: sender wallet identifier
          - receiver_wallet: receiver wallet identifier
          - amount: transaction amount in BSD
          - currency: always "BSD"
          - event_time: ISO 8601 event timestamp
          - status_code: CBDC-specific failure code
          - status_message: human-readable status description
          - sender_institution_bic: BIC of sender's servicing institution
          - receiver_institution_bic: BIC of receiver's servicing institution
        """
        amount = _safe_decimal(msg.get("amount", "0"))
        currency = msg.get("currency", "BSD")

        sttlm = msg.get("settlement_amount")
        original_amount = _safe_decimal(sttlm) if sttlm else None

        event = NormalizedEvent(
            uetr=msg.get("reference_id", ""),
            individual_payment_id=msg.get("payment_id", msg.get("reference_id", "")),
            sending_bic=msg.get(
                "sender_institution_bic", msg.get("sender_wallet", ""),
            ),
            receiving_bic=msg.get(
                "receiver_institution_bic", msg.get("receiver_wallet", ""),
            ),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get("event_time")),
            rail="CBDC_SAND_DOLLAR",
            rejection_code=normalize_cbdc_failure_code(msg.get("status_code")),
            narrative=msg.get("status_message"),
            raw_source=msg,
            original_payment_amount_usd=original_amount,
        )
        event.telemetry_eligible = _compute_telemetry_eligibility(event)
        return event

    def normalize(self, rail: str, msg: dict) -> NormalizedEvent:
        """Dispatch to the correct CBDC normalizer based on rail string.

        Raises ValueError for unrecognised CBDC rails.
        """
        handlers = {
            "CBDC_ECNY": self.normalize_ecny,
            "CBDC_EEUR": self.normalize_eeur,
            "CBDC_SAND_DOLLAR": self.normalize_sand_dollar,
        }
        handler = handlers.get(rail.upper())
        if handler is None:
            raise ValueError(
                f"Unknown CBDC rail: {rail!r}. "
                f"Supported: {sorted(handlers)}"
            )
        return handler(msg)


def get_rail_maturity_hours(rail: str) -> float:
    """Return the maturity buffer in hours for a given settlement rail.

    CBDC rails use a 4-hour buffer (programmatic finality).
    Legacy rails use the UETR TTL (45 days = 1080 hours) or 24 hours for
    domestic instant rails.

    Raises ValueError for unrecognised rails — never silently defaults.
    """
    from lip.common.constants import RAIL_MATURITY_HOURS
    upper = rail.strip().upper()
    if upper not in RAIL_MATURITY_HOURS:
        raise ValueError(
            f"Unknown rail {rail!r} — no maturity configured. "
            f"Known rails: {sorted(RAIL_MATURITY_HOURS)}"
        )
    return RAIL_MATURITY_HOURS[upper]
