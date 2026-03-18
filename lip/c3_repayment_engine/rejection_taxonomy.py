"""
rejection_taxonomy.py — SWIFT rejection code taxonomy
Architecture Spec S8: Full code → Class A/B/C/BLOCK mapping

T = f(rejection_code_class):
  Class A → 3 days maturity  (technical/routing errors)
  Class B → 7 days maturity  (systemic/processing errors)
  Class C → 21 days maturity (investigation/complex errors)
  BLOCK   → no bridge offered (compliance, dispute, legal)

BLOCK codes — no bridge ever offered:
  Compliance hold: DNOR, CNOR, RR01, RR02, RR03, RR04, AG01
  Legal/court:     LEGL
  Dispute/fraud:   DISP, FRAU, FRAD, DUPL

EPG references: EPG-01 (RR01-RR03), EPG-02 (DNOR), EPG-03 (CNOR),
                EPG-07 (RR04), EPG-08 (AG01, LEGL)
"""
from enum import Enum


class RejectionClass(str, Enum):
    CLASS_A = "CLASS_A"
    CLASS_B = "CLASS_B"
    CLASS_C = "CLASS_C"
    BLOCK = "BLOCK"


# Full SWIFT rejection code taxonomy — Architecture Spec S8
# Maps ISO 20022 reason codes to their classification tier.
REJECTION_CODE_TAXONOMY: dict[str, RejectionClass] = {
    # ── CLASS A — Temporary / Technical (3-day maturity) ────────────────────
    "AC01": RejectionClass.CLASS_A,  # IncorrectAccountNumber
    "AC04": RejectionClass.CLASS_A,  # ClosedAccountNumber
    "AC06": RejectionClass.CLASS_A,  # BlockedAccount
    "AM01": RejectionClass.CLASS_A,  # ZeroAmount
    "AM02": RejectionClass.CLASS_A,  # NotAllowedAmount
    "AM03": RejectionClass.CLASS_A,  # NotAllowedCurrency
    "AM04": RejectionClass.CLASS_A,  # InsufficientFunds
    "AM05": RejectionClass.CLASS_A,  # Duplication
    "AM06": RejectionClass.CLASS_A,  # TooLowAmount
    "AM09": RejectionClass.CLASS_A,  # WrongAmount
    "AM10": RejectionClass.CLASS_A,  # InvalidControlSum
    "AM12": RejectionClass.CLASS_A,  # InvalidAmount
    "BE01": RejectionClass.CLASS_A,  # InconsistentWithEndCustomer
    "BE05": RejectionClass.CLASS_A,  # UnrecognisedInitiatingParty
    "DT01": RejectionClass.CLASS_A,  # InvalidDate
    "ED01": RejectionClass.CLASS_A,  # CorrespondentBankNotAllowed
    "ED03": RejectionClass.CLASS_A,  # BalanceInfoRequest
    "ED05": RejectionClass.CLASS_A,  # SettlementFailed
    "FF01": RejectionClass.CLASS_A,  # InvalidFileFormat
    "FF03": RejectionClass.CLASS_A,  # InvalidPaymentTypeInfo
    "FF05": RejectionClass.CLASS_A,  # InvalidLocalInstrumentCode
    "MD01": RejectionClass.CLASS_A,  # NoMandate
    "MD02": RejectionClass.CLASS_A,  # MissingMandatoryInfo
    "MD06": RejectionClass.CLASS_A,  # RefundRequestedByEndCustomer
    "RC01": RejectionClass.CLASS_A,  # BankIdentifierIncorrect
    "RR01": RejectionClass.BLOCK,    # MissingDebtorAccountOrIdentification — KYC failure, debtor unidentified (EPG-01)
    "RR02": RejectionClass.BLOCK,    # MissingDebtorNameOrAddress — KYC failure, debtor name/address missing (EPG-01)
    "RR03": RejectionClass.BLOCK,    # MissingCreditorNameOrAddress — KYC failure, creditor unidentified (EPG-01)
    "RR04": RejectionClass.BLOCK,    # RegulatoryReason — regulatory prohibition, defense-in-depth (EPG-07)
    # ── CLASS B — Systemic / Processing (7-day maturity) ────────────────────
    "AG01": RejectionClass.BLOCK,    # TransactionForbidden — bank-level prohibition on this transaction (EPG-08)
    "AG02": RejectionClass.CLASS_B,  # InvalidBankOperationCode
    "CURR": RejectionClass.CLASS_B,  # UnrecognisedCurrency
    "CUST": RejectionClass.CLASS_B,  # RequestedByCustomer
    "DNOR": RejectionClass.BLOCK,    # DebtorNotAllowedToSend — bank's compliance system prohibited this sender (EPG-02)
    "FOCR": RejectionClass.CLASS_B,  # FollowingCancellationRequest
    "MS02": RejectionClass.CLASS_B,  # NotSpecifiedReasonCustomerGenerated
    "MS03": RejectionClass.CLASS_B,  # NotSpecifiedReasonAgentGenerated
    "NARR": RejectionClass.CLASS_B,  # Narrative
    "NOAS": RejectionClass.CLASS_B,  # NoAnswerFromCustomer
    "NOOR": RejectionClass.CLASS_B,  # NoOriginalTransactionReceived
    "PTNA": RejectionClass.CLASS_B,  # PassThroughNotAllowed
    "RCON": RejectionClass.CLASS_B,  # SettlementFailedContinuous
    "SVNR": RejectionClass.CLASS_B,  # ServiceNotRendered
    "TECH": RejectionClass.CLASS_B,  # TechnicalProblem
    "TIMO": RejectionClass.CLASS_B,  # TimeOut
    "UPAY": RejectionClass.CLASS_B,  # UnduePayment
    # ── CLASS C — Investigation / Complex (21-day maturity) ─────────────────
    "AGNT": RejectionClass.CLASS_C,  # IncorrectAgent
    "CVCY": RejectionClass.CLASS_C,  # CurrencyConversionFailed
    "INVB": RejectionClass.CLASS_C,  # InvalidBIC
    "INVR": RejectionClass.CLASS_C,  # InvalidReference
    "LEGL": RejectionClass.BLOCK,    # LegalDecision — court/regulatory authority prevented payment (EPG-08)
    "OPAY": RejectionClass.CLASS_C,  # OtherPayment
    "PCOR": RejectionClass.CLASS_C,  # PartiallyCorrupt
    "QMIS": RejectionClass.CLASS_C,  # QualityMismatch
    "UMKA": RejectionClass.CLASS_C,  # UnmatchedAmount
    # ── BLOCK — Compliance / Dispute / Legal (no bridge offered) ────────────
    "CNOR": RejectionClass.BLOCK,    # CreditorNotAllowedToReceive — bank prohibited receiving entity (EPG-03)
    "DISP": RejectionClass.BLOCK,    # DisputedTransaction
    "FRAU": RejectionClass.BLOCK,    # Fraud
    "FRAD": RejectionClass.BLOCK,    # FraudulentOrigin
    "DUPL": RejectionClass.BLOCK,    # DuplicateDetected
}

_MATURITY_MAP: dict[RejectionClass, int] = {
    RejectionClass.CLASS_A: 3,
    RejectionClass.CLASS_B: 7,
    RejectionClass.CLASS_C: 21,
    RejectionClass.BLOCK: 0,
}


def classify_rejection_code(code: str) -> RejectionClass:
    """Return the RejectionClass for a given ISO 20022 rejection code.

    Raises:
        ValueError: If the code is not present in the taxonomy.
    """
    normalised = code.strip().upper()
    try:
        return REJECTION_CODE_TAXONOMY[normalised]
    except KeyError:
        raise ValueError(
            f"Unknown rejection code '{code}'. "
            "Add it to REJECTION_CODE_TAXONOMY before use."
        )


def maturity_days(rejection_class: RejectionClass) -> int:
    """Return the maturity window in days for a given RejectionClass.

    BLOCK codes return 0 — no bridge is offered and no maturity window applies.
    """
    return _MATURITY_MAP[rejection_class]


def is_dispute_block(code: str) -> bool:
    """Return True if the rejection code maps to the BLOCK class."""
    try:
        return classify_rejection_code(code) is RejectionClass.BLOCK
    except ValueError:
        return False


def get_all_codes_for_class(cls: RejectionClass) -> list[str]:
    """Return all rejection codes that belong to the given RejectionClass."""
    return [code for code, rc in REJECTION_CODE_TAXONOMY.items() if rc is cls]
