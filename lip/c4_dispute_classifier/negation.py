"""
negation.py — Negation test suite: 500 cases across 5 categories
C4 Spec Section 10
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from .taxonomy import DisputeClass

# ---------------------------------------------------------------------------
# NegationCategory
# ---------------------------------------------------------------------------

class NegationCategory(str, Enum):
    STANDARD_NEGATION = "standard_negation"         # "not disputed", "no dispute"
    DOUBLE_NEGATION = "double_negation"              # "cannot not dispute" → dispute
    IMPLICIT_NEGATION = "implicit_negation"          # "resolved", "settled" → not dispute
    CONDITIONAL_NEGATION = "conditional_negation"    # "unless disputed"
    MULTILINGUAL_NEGATION = "multilingual_negation"  # DE/FR/ES negations


# ---------------------------------------------------------------------------
# NegationTestCase
# ---------------------------------------------------------------------------

@dataclass
class NegationTestCase:
    case_id: int
    narrative: str
    rejection_code: Optional[str]
    category: NegationCategory
    expected_class: DisputeClass
    language: str = "EN"
    description: str = ""


# ---------------------------------------------------------------------------
# Test case templates
# ---------------------------------------------------------------------------

# Each entry: (narrative, rejection_code, expected_class, language, description)
_STANDARD_NEGATION_TEMPLATES: List[Tuple] = [
    ("Payment is not a dispute.", None, DisputeClass.NOT_DISPUTE, "EN", "Explicit not-dispute"),
    ("No dispute raised by payer.", None, DisputeClass.NOT_DISPUTE, "EN", "No dispute raised"),
    ("Payment not disputed by customer.", None, DisputeClass.NOT_DISPUTE, "EN", "Not disputed"),
    ("No fraud detected on this transaction.", None, DisputeClass.NOT_DISPUTE, "EN", "No fraud"),
    ("Customer confirmed no dispute.", None, DisputeClass.NOT_DISPUTE, "EN", "Confirmed no dispute"),
    ("Not a fraudulent transaction.", None, DisputeClass.NOT_DISPUTE, "EN", "Not fraudulent"),
    ("Payer does not contest this payment.", None, DisputeClass.NOT_DISPUTE, "EN", "Payer not contesting"),
    ("No unauthorized activity reported.", None, DisputeClass.NOT_DISPUTE, "EN", "No unauthorized activity"),
    ("Transaction is not contested.", None, DisputeClass.NOT_DISPUTE, "EN", "Not contested"),
    ("No chargeback requested.", None, DisputeClass.NOT_DISPUTE, "EN", "No chargeback"),
    ("Customer accepts the charge; no dispute.", None, DisputeClass.NOT_DISPUTE, "EN", "Accepts charge"),
    ("Payment rejected due to incorrect IBAN, not a dispute.", "AC01", DisputeClass.NOT_DISPUTE, "EN", "Technical rejection"),
    ("Insufficient funds; no dispute raised.", "AM04", DisputeClass.NOT_DISPUTE, "EN", "Insufficient funds"),
    ("Beneficiary account closed; no dispute.", "AC04", DisputeClass.NOT_DISPUTE, "EN", "Account closed"),
    ("Duplicate detected but not disputed.", None, DisputeClass.NOT_DISPUTE, "EN", "Duplicate not disputed"),
    ("Payer has not raised any dispute.", None, DisputeClass.NOT_DISPUTE, "EN", "No dispute raised (alt)"),
    ("No legal action pending.", None, DisputeClass.NOT_DISPUTE, "EN", "No legal action"),
    ("Transaction declined; dispute not raised.", None, DisputeClass.NOT_DISPUTE, "EN", "Declined no dispute"),
    ("Card expired; not fraudulent.", None, DisputeClass.NOT_DISPUTE, "EN", "Card expired"),
    ("Wrong sort code; not disputed.", None, DisputeClass.NOT_DISPUTE, "EN", "Wrong sort code"),
]

_DOUBLE_NEGATION_TEMPLATES: List[Tuple] = [
    ("Payment cannot not be disputed.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Double negation → possible"),
    ("Customer does not deny disputing this.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not denying dispute"),
    ("Not without dispute; see attached.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not without dispute"),
    ("Payer did not say it was not fraud.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Did not say not fraud"),
    ("Cannot rule out dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Cannot rule out"),
    ("Not impossible that this is fraudulent.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not impossible fraud"),
    ("Dispute is not absent from this case.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Dispute not absent"),
    ("Customer has not confirmed non-dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Has not confirmed non-dispute"),
    ("Not refusing to dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not refusing dispute"),
    ("Transaction not confirmed as non-fraudulent.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not confirmed non-fraud"),
    ("Cannot not raise a dispute on this.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Cannot not raise"),
    ("Payer hasn't said it was unauthorised but hasn't denied it either.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Ambiguous authorisation"),
    ("No confirmation of no dispute received.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "No confirmation of no dispute"),
    ("Not a confirmed non-dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not confirmed non-dispute"),
    ("Unable to confirm no fraud.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Unable to confirm no fraud"),
    ("Neither disputed nor clearly not disputed.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Ambiguous neither/nor"),
    ("Payer not declaring no dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not declaring no dispute"),
    ("Cannot exclude the possibility of dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Cannot exclude possibility"),
    ("Not an undisputed payment.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Not undisputed"),
    ("No absence of dispute indicators.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "No absence of indicators"),
]

_IMPLICIT_NEGATION_TEMPLATES: List[Tuple] = [
    ("Payment has been settled.", None, DisputeClass.NOT_DISPUTE, "EN", "Settled"),
    ("Transaction resolved successfully.", None, DisputeClass.NOT_DISPUTE, "EN", "Resolved"),
    ("Funds received by beneficiary.", None, DisputeClass.NOT_DISPUTE, "EN", "Funds received"),
    ("Matter closed; no further action.", None, DisputeClass.NOT_DISPUTE, "EN", "Matter closed"),
    ("Payer has withdrawn their complaint.", None, DisputeClass.NOT_DISPUTE, "EN", "Complaint withdrawn"),
    ("Issue resolved to customer satisfaction.", None, DisputeClass.NOT_DISPUTE, "EN", "Resolved to satisfaction"),
    ("Payment completed without incident.", None, DisputeClass.NOT_DISPUTE, "EN", "Completed without incident"),
    ("Reconciliation confirmed; no outstanding issues.", None, DisputeClass.NOT_DISPUTE, "EN", "Reconciliation confirmed"),
    ("Case withdrawn by claimant.", None, DisputeClass.NOT_DISPUTE, "EN", "Case withdrawn"),
    ("Beneficiary confirmed receipt.", None, DisputeClass.NOT_DISPUTE, "EN", "Beneficiary confirmed"),
    ("All parties satisfied; payment finalised.", None, DisputeClass.NOT_DISPUTE, "EN", "All parties satisfied"),
    ("Account credited; transaction complete.", None, DisputeClass.NOT_DISPUTE, "EN", "Transaction complete"),
    ("Dispute dropped after investigation.", None, DisputeClass.NOT_DISPUTE, "EN", "Dispute dropped"),
    ("Refund processed; case closed.", None, DisputeClass.NOT_DISPUTE, "EN", "Refund processed closed"),
    ("Agreement reached; payment released.", None, DisputeClass.NOT_DISPUTE, "EN", "Agreement reached"),
    ("Both parties confirmed acceptance.", None, DisputeClass.NOT_DISPUTE, "EN", "Both parties accept"),
    ("Technical error corrected; payment successful.", "AC01", DisputeClass.NOT_DISPUTE, "EN", "Error corrected"),
    ("Payer acknowledged receipt of funds.", None, DisputeClass.NOT_DISPUTE, "EN", "Acknowledged receipt"),
    ("Payment processed; customer notified.", None, DisputeClass.NOT_DISPUTE, "EN", "Payment processed"),
    ("Investigation concluded; no issue found.", None, DisputeClass.NOT_DISPUTE, "EN", "Investigation concluded"),
]

_CONDITIONAL_NEGATION_TEMPLATES: List[Tuple] = [
    ("Unless fraud is detected, approve payment.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Unless fraud"),
    ("Payment proceeds unless disputed by payer.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Unless disputed"),
    ("Release funds if no dispute is raised within 5 days.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "If no dispute 5 days"),
    ("Approve only if customer confirms no dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Approve if no dispute"),
    ("Process unless unauthorized transaction confirmed.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Unless unauthorized"),
    ("Hold pending dispute check.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Hold pending check"),
    ("Conditional release pending fraud review.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Conditional release"),
    ("Await dispute resolution before processing.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Await resolution"),
    ("Block if dispute raised within 48 hours.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Block if dispute 48h"),
    ("Customer may dispute within 30 days.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "May dispute 30 days"),
    ("Payment subject to dispute window.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Subject to window"),
    ("Possible dispute pending customer confirmation.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Pending confirmation"),
    ("Hold funds until dispute period expires.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Hold until expires"),
    ("Proceed unless legal hold applied.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Unless legal hold"),
    ("Payment contingent on no fraud claim.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Contingent no fraud"),
    ("If dispute confirmed, block immediately.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "If dispute confirmed"),
    ("Waiting for payer acknowledgement; possible dispute.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Waiting acknowledgement"),
    ("Release when dispute window closed.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Release when closed"),
    ("Fraud check pending; payment on hold.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Fraud check pending"),
    ("Dispute possible; awaiting further documentation.", None, DisputeClass.DISPUTE_POSSIBLE, "EN", "Awaiting documentation"),
]

_MULTILINGUAL_NEGATION_TEMPLATES: List[Tuple] = [
    # German — NOT_DISPUTE
    ("Zahlung nicht bestritten.", None, DisputeClass.NOT_DISPUTE, "DE", "DE: not disputed"),
    ("Kein Streit gemeldet.", None, DisputeClass.NOT_DISPUTE, "DE", "DE: no dispute reported"),
    ("Transaktion erfolgreich abgeschlossen.", None, DisputeClass.NOT_DISPUTE, "DE", "DE: transaction completed"),
    ("Kein Betrug festgestellt.", None, DisputeClass.NOT_DISPUTE, "DE", "DE: no fraud detected"),
    ("Zahlung vom Kunden akzeptiert.", None, DisputeClass.NOT_DISPUTE, "DE", "DE: accepted by customer"),
    # German — DISPUTE_CONFIRMED
    ("Betrug gemeldet; Rückbuchung angefordert.", "FRAU", DisputeClass.DISPUTE_CONFIRMED, "DE", "DE: fraud reported"),
    ("Nicht genehmigter Betrag bestritten.", None, DisputeClass.DISPUTE_CONFIRMED, "DE", "DE: unauthorized disputed"),
    ("Streit formal eingereicht.", "DISP", DisputeClass.DISPUTE_CONFIRMED, "DE", "DE: dispute submitted"),
    ("Betrügerische Überweisung gemeldet.", None, DisputeClass.DISPUTE_CONFIRMED, "DE", "DE: fraudulent transfer"),
    ("Klage angekündigt.", None, DisputeClass.DISPUTE_CONFIRMED, "DE", "DE: legal action announced"),
    # French — NOT_DISPUTE
    ("Paiement non contesté.", None, DisputeClass.NOT_DISPUTE, "FR", "FR: not contested"),
    ("Aucun litige signalé.", None, DisputeClass.NOT_DISPUTE, "FR", "FR: no dispute reported"),
    ("Transaction résolue avec succès.", None, DisputeClass.NOT_DISPUTE, "FR", "FR: resolved"),
    ("Aucune fraude détectée.", None, DisputeClass.NOT_DISPUTE, "FR", "FR: no fraud"),
    ("Paiement accepté par le client.", None, DisputeClass.NOT_DISPUTE, "FR", "FR: accepted"),
    # French — DISPUTE_CONFIRMED
    ("Fraude signalée; litige ouvert.", "FRAU", DisputeClass.DISPUTE_CONFIRMED, "FR", "FR: fraud reported"),
    ("Montant non autorisé contesté.", None, DisputeClass.DISPUTE_CONFIRMED, "FR", "FR: unauthorized contested"),
    ("Virement frauduleux signalé.", None, DisputeClass.DISPUTE_CONFIRMED, "FR", "FR: fraudulent transfer"),
    ("Litige formel soumis.", "DISP", DisputeClass.DISPUTE_CONFIRMED, "FR", "FR: dispute submitted"),
    ("Action en justice annoncée.", None, DisputeClass.DISPUTE_CONFIRMED, "FR", "FR: legal action"),
    # Spanish — NOT_DISPUTE
    ("Pago no disputado.", None, DisputeClass.NOT_DISPUTE, "ES", "ES: not disputed"),
    ("Sin disputa reportada.", None, DisputeClass.NOT_DISPUTE, "ES", "ES: no dispute reported"),
    ("Transacción resuelta correctamente.", None, DisputeClass.NOT_DISPUTE, "ES", "ES: resolved"),
    ("Sin fraude detectado.", None, DisputeClass.NOT_DISPUTE, "ES", "ES: no fraud"),
    ("Pago aceptado por el cliente.", None, DisputeClass.NOT_DISPUTE, "ES", "ES: accepted"),
    # Spanish — DISPUTE_CONFIRMED
    ("Fraude reportado; disputa abierta.", "FRAU", DisputeClass.DISPUTE_CONFIRMED, "ES", "ES: fraud reported"),
    ("Monto no autorizado disputado.", None, DisputeClass.DISPUTE_CONFIRMED, "ES", "ES: unauthorized disputed"),
    ("Transferencia fraudulenta reportada.", None, DisputeClass.DISPUTE_CONFIRMED, "ES", "ES: fraudulent transfer"),
    ("Disputa formal presentada.", "DISP", DisputeClass.DISPUTE_CONFIRMED, "ES", "ES: dispute submitted"),
    ("Acción legal anunciada.", None, DisputeClass.DISPUTE_CONFIRMED, "ES", "ES: legal action"),
]

# Map category → template list
_TEMPLATE_MAP: dict = {
    NegationCategory.STANDARD_NEGATION: _STANDARD_NEGATION_TEMPLATES,
    NegationCategory.DOUBLE_NEGATION: _DOUBLE_NEGATION_TEMPLATES,
    NegationCategory.IMPLICIT_NEGATION: _IMPLICIT_NEGATION_TEMPLATES,
    NegationCategory.CONDITIONAL_NEGATION: _CONDITIONAL_NEGATION_TEMPLATES,
    NegationCategory.MULTILINGUAL_NEGATION: _MULTILINGUAL_NEGATION_TEMPLATES,
}


# ---------------------------------------------------------------------------
# generate_negation_test_suite
# ---------------------------------------------------------------------------

def generate_negation_test_suite(n_per_category: int = 100) -> List[NegationTestCase]:
    """
    Generate a suite of negation test cases for the dispute classifier.

    Produces exactly ``n_per_category`` cases per category by cycling through
    the template list as many times as required, yielding a total of
    ``n_per_category * 5`` test cases.

    Args:
        n_per_category: Number of test cases to generate per
                        :class:`NegationCategory` (default 100, giving 500
                        total).

    Returns:
        A flat list of :class:`NegationTestCase` objects.
    """
    suite: List[NegationTestCase] = []
    case_id = 1

    for category, templates in _TEMPLATE_MAP.items():
        generated = 0
        template_count = len(templates)
        while generated < n_per_category:
            tpl = templates[generated % template_count]
            narrative, rejection_code, expected_class, language, description = tpl
            # Add a numeric suffix when cycling to keep narratives unique
            cycle = generated // template_count
            if cycle > 0:
                narrative = f"{narrative} (variant {cycle})"

            suite.append(
                NegationTestCase(
                    case_id=case_id,
                    narrative=narrative,
                    rejection_code=rejection_code,
                    category=category,
                    expected_class=expected_class,
                    language=language,
                    description=description,
                )
            )
            case_id += 1
            generated += 1

    return suite


# ---------------------------------------------------------------------------
# NegationTestRunner
# ---------------------------------------------------------------------------

class NegationTestRunner:
    """
    Runs the negation test suite against a :class:`~model.DisputeClassifier`
    and collects pass/fail metrics broken down by :class:`NegationCategory`.
    """

    def __init__(self, classifier) -> None:
        """
        Args:
            classifier: A :class:`~model.DisputeClassifier` instance.
        """
        self._classifier = classifier

    def run_suite(self, test_cases: List[NegationTestCase]) -> dict:
        """
        Execute all *test_cases* and return an aggregated results dict.

        Args:
            test_cases: List of :class:`NegationTestCase` objects (typically
                        produced by :func:`generate_negation_test_suite`).

        Returns:
            dict with keys:

            - ``total``          (int): total cases run
            - ``passed``         (int): cases where predicted == expected
            - ``failed``         (int): cases where predicted != expected
            - ``accuracy``       (float): overall accuracy 0.0–1.0
            - ``by_category``    (dict): per-category breakdown
              ``{category_value: {passed, failed, accuracy}}``
            - ``false_negatives`` (list): cases where dispute was expected but
              NOT_DISPUTE was returned (dangerous misclassification)
            - ``failed_cases``   (list): all failed :class:`NegationTestCase`
        """
        total = len(test_cases)
        passed = 0
        failed = 0
        false_negatives: list = []
        failed_cases: list = []

        by_category: dict = {
            cat.value: {"passed": 0, "failed": 0, "accuracy": 0.0}
            for cat in NegationCategory
        }

        for case in test_cases:
            result = self._classifier.classify(
                rejection_code=case.rejection_code,
                narrative=case.narrative,
            )
            predicted: DisputeClass = result["dispute_class"]
            cat_key = case.category.value

            if predicted == case.expected_class:
                passed += 1
                by_category[cat_key]["passed"] += 1
            else:
                failed += 1
                by_category[cat_key]["failed"] += 1
                failed_cases.append(case)

                # False negative: dispute expected but NOT_DISPUTE returned
                dispute_expected = case.expected_class in (
                    DisputeClass.DISPUTE_CONFIRMED,
                    DisputeClass.DISPUTE_POSSIBLE,
                )
                if dispute_expected and predicted == DisputeClass.NOT_DISPUTE:
                    false_negatives.append(case)

        # Compute per-category accuracy
        for cat_key, counts in by_category.items():
            cat_total = counts["passed"] + counts["failed"]
            counts["accuracy"] = (
                counts["passed"] / cat_total if cat_total > 0 else 0.0
            )

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "accuracy": passed / total if total > 0 else 0.0,
            "by_category": by_category,
            "false_negatives": false_negatives,
            "failed_cases": failed_cases,
        }
