"""
fx_risk_policy.py — GAP-12: FX risk policy for cross-currency bridge corridors.

Bridge loans are internally denominated in USD (``principal_usd``), but the
borrower's payment corridor may be EUR, GBP, or another currency.  If the
bank's funding is USD but the borrower needs EUR, a silent FX conversion would
create undisclosed risk for both parties — neither has agreed to bear it.

This module defines a ``FXRiskPolicy`` enum and a ``FXRiskConfig`` dataclass
that govern whether C7 should issue a bridge offer for a given payment currency.

Phase 1 (pilot):
    ``SAME_CURRENCY_ONLY`` — the bank only funds in its declared base currency.
    EUR/GBP payments from a USD-funded bank return ``CURRENCY_NOT_SUPPORTED``.
    This is the conservative, audit-safe default for the pilot programme.

Phase 2 (requires QUANT sign-off + bank FX desk API integration):
    ``FX_DECOMPOSITION`` — bridge loan is split into base-currency funding +
    hedged FX leg.  Not implemented; reserved for future extension.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FXRiskPolicy(str, Enum):
    """Enumeration of FX risk policies for cross-currency corridors.

    Attributes:
        SAME_CURRENCY_ONLY: Bank funds only in its declared base currency.
            Payments in other currencies are blocked with ``CURRENCY_NOT_SUPPORTED``.
        BANK_NATIVE_CURRENCY: Bank always funds in its base currency; the
            borrower's FX conversion is the bank's responsibility.  All
            currencies are accepted; settlement is in bank base currency.
    """

    SAME_CURRENCY_ONLY = "SAME_CURRENCY_ONLY"
    BANK_NATIVE_CURRENCY = "BANK_NATIVE_CURRENCY"
    # FX_DECOMPOSITION = "FX_DECOMPOSITION"  # Phase 2 — requires QUANT sign-off


@dataclass(frozen=True)
class FXRiskConfig:
    """Configuration for the FX risk gate applied in C7 before offer generation.

    Args:
        policy: Active FX risk policy.  Defaults to
            :attr:`FXRiskPolicy.SAME_CURRENCY_ONLY` (conservative pilot default).
        bank_base_currency: ISO 4217 code of the bank's native funding currency.
            Defaults to ``"USD"``.  Used as the fallback currency when the
            payment context does not specify a currency.
        g10_currencies: Set of G10 ISO 4217 currency codes.  Used by
            :meth:`is_g10` for eligibility checks; not used by the policy gate
            directly but available for downstream risk scoring.
    """

    policy: FXRiskPolicy = FXRiskPolicy.SAME_CURRENCY_ONLY
    bank_base_currency: str = "USD"
    g10_currencies: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "NZD", "SEK", "NOK"}
        )
    )

    def is_supported(self, payment_currency: str) -> bool:
        """Return ``True`` when the bank can fund a bridge loan for this currency.

        Applies the active :attr:`policy`:

        * ``SAME_CURRENCY_ONLY``: supported iff ``payment_currency`` equals
          :attr:`bank_base_currency` (case-insensitive).
        * ``BANK_NATIVE_CURRENCY``: always supported; bank funds in base
          currency and handles any FX exposure internally.

        Args:
            payment_currency: ISO 4217 currency code of the payment corridor.

        Returns:
            ``True`` when the policy permits bridge funding for this currency.
        """
        if self.policy == FXRiskPolicy.SAME_CURRENCY_ONLY:
            return payment_currency.upper() == self.bank_base_currency.upper()
        if self.policy == FXRiskPolicy.BANK_NATIVE_CURRENCY:
            return True
        return False

    def is_g10(self, currency: str) -> bool:
        """Return ``True`` when ``currency`` is a G10 currency.

        Args:
            currency: ISO 4217 currency code.  Case-insensitive.
        """
        return currency.upper() in self.g10_currencies
