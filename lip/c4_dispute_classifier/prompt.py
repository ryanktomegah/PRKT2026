"""
prompt.py — Structured prompt construction for LLM dispute classification
C4 Spec Section 5.3
"""

from .taxonomy import DisputeClass

# ---------------------------------------------------------------------------
# System prompt — stable, version-controlled
# ---------------------------------------------------------------------------

SYSTEM_PROMPT: str = (
    "You are a payment dispute classifier for cross-border payments.\n"
    "Classify the following payment rejection into exactly one of these four categories:\n"
    "- NOT_DISPUTE: Normal payment failure with no dispute\n"
    "- DISPUTE_CONFIRMED: Definitive dispute (fraud, unauthorized, contested)\n"
    "- DISPUTE_POSSIBLE: Possible dispute, insufficient information to confirm\n"
    "- NEGOTIATION: Active negotiation or partial settlement underway\n"
    "\n"
    "Respond with ONLY the category name, nothing else."
)


# ---------------------------------------------------------------------------
# Few-shot examples — one canonical example per class
# ---------------------------------------------------------------------------

_FEW_SHOT_EXAMPLES: list = [
    {
        "rejection_code": "AC01",
        "narrative": "Incorrect account number provided by originator. Payment returned.",
        "amount": "1500.00",
        "currency": "EUR",
        "counterparty": "DEUTDEDBFRA",
        "language": "EN",
        "expected_class": DisputeClass.NOT_DISPUTE,
    },
    {
        "rejection_code": "FRAU",
        "narrative": (
            "Customer reports unauthorised transaction. "
            "Card not present fraud suspected. Dispute formally raised."
        ),
        "amount": "4200.00",
        "currency": "GBP",
        "counterparty": "BARCGB22XXX",
        "language": "EN",
        "expected_class": DisputeClass.DISPUTE_CONFIRMED,
    },
    {
        "rejection_code": "MS02",
        "narrative": (
            "Payment returned without clear reason. "
            "Customer has not confirmed whether they authorised the transfer."
        ),
        "amount": "750.00",
        "currency": "USD",
        "counterparty": "CHASUS33XXX",
        "language": "EN",
        "expected_class": DisputeClass.DISPUTE_POSSIBLE,
    },
    {
        "rejection_code": "CUST",
        "narrative": (
            "Payer and payee in active negotiation over partial settlement. "
            "Agreed to revisit outstanding amount of 300 EUR by end of week."
        ),
        "amount": "900.00",
        "currency": "EUR",
        "counterparty": "BNPAFRPPXXX",
        "language": "EN",
        "expected_class": DisputeClass.NEGOTIATION,
    },
]


# ---------------------------------------------------------------------------
# DisputePromptBuilder
# ---------------------------------------------------------------------------

class DisputePromptBuilder:
    """
    Constructs structured prompts for the LLM dispute classifier.

    The builder separates the system instruction from the user-facing
    payment details so that the LLM can be called with a standard
    chat-completion interface (system / user roles).
    """

    def build(
        self,
        rejection_code: str,
        narrative: str,
        amount: str,
        currency: str,
        counterparty: str,
        language: str = "EN",
    ) -> dict:
        """
        Build a complete prompt dict ready for LLM inference.

        Args:
            rejection_code: ISO 20022 / SWIFT rejection code (e.g. "FRAU").
            narrative:       Free-text payment narrative.
            amount:          Transaction amount as a string (e.g. "1500.00").
            currency:        ISO 4217 currency code (e.g. "EUR").
            counterparty:    BIC or counterparty identifier.
            language:        ISO 639-1 language code of the narrative (default "EN").

        Returns:
            dict with keys ``'system'`` (str) and ``'user'`` (str).
        """
        user_prompt = self._format_user_prompt(
            rejection_code, narrative, amount, currency, counterparty, language
        )
        return {
            "system": SYSTEM_PROMPT,
            "user": user_prompt,
        }

    def build_few_shot_examples(self) -> list:
        """
        Return a list of four few-shot example dicts, one per dispute class.

        Each dict has the keys ``'system'``, ``'user'``, and ``'assistant'``
        (the expected model output token).

        Returns:
            List of four example dicts for use in few-shot prompt construction.
        """
        examples = []
        for ex in _FEW_SHOT_EXAMPLES:
            prompt = self.build(
                rejection_code=ex["rejection_code"],
                narrative=ex["narrative"],
                amount=ex["amount"],
                currency=ex["currency"],
                counterparty=ex["counterparty"],
                language=ex["language"],
            )
            examples.append(
                {
                    "system": prompt["system"],
                    "user": prompt["user"],
                    "assistant": ex["expected_class"].value,
                }
            )
        return examples

    def _format_user_prompt(
        self,
        rejection_code: str,
        narrative: str,
        amount: str,
        currency: str,
        counterparty: str,
        language: str,
    ) -> str:
        """
        Format the user-facing section of the prompt.

        Presents the structured payment details in a consistent, parseable
        format that the model has been fine-tuned to expect.
        """
        # Normalise empty / missing fields to 'N/A' for consistent tokenisation.
        rejection_code = rejection_code.strip() if rejection_code else "N/A"
        narrative = narrative.strip() if narrative else "N/A"
        amount = amount.strip() if amount else "N/A"
        currency = currency.strip().upper() if currency else "N/A"
        counterparty = counterparty.strip() if counterparty else "N/A"
        language = language.strip().upper() if language else "EN"

        return (
            f"Payment Rejection Details:\n"
            f"  Rejection Code : {rejection_code}\n"
            f"  Amount         : {amount} {currency}\n"
            f"  Counterparty   : {counterparty}\n"
            f"  Narrative Lang : {language}\n"
            f"  Narrative      : {narrative}\n"
            f"\n"
            f"Classify this rejection:"
        )

    def _translate_prompt_to_language(self, prompt: str, language: str) -> str:
        """
        Placeholder for prompt-level translation.

        Per C4 Spec Section 11, translation is applied at the *input* (narrative)
        level before reaching this layer, not at the prompt level.  This method
        is therefore a no-op and returns the prompt unchanged.

        Args:
            prompt:   The prompt string.
            language: Target language code (ignored in this implementation).

        Returns:
            The original prompt string unmodified.
        """
        return prompt
