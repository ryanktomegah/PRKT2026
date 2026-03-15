"""
borrower_registry.py — GAP-03: Enrolled Borrower Registry.

Before LIP can offer a bridge loan, the sending BIC (the borrower) must have
explicitly enrolled in the service by signing a Master Receivables Finance
Agreement (MRFA).

The ``BorrowerRegistry`` is the authoritative source of truth for these
enrollments. C7 (Execution Agent) checks this registry as the very first gate
in the decision pipeline. If a sender is not enrolled, the pipeline returns
``BORROWER_NOT_ENROLLED`` and halts.
"""
from __future__ import annotations

from typing import Optional, Set


class BorrowerRegistry:
    """Manages the set of BICs authorized to receive bridge loan offers.

    Thread-safety: NOT thread-safe. Callers responsible for external locking.
    """

    def __init__(self, enrolled_bics: Optional[Set[str]] = None) -> None:
        """
        Args:
            enrolled_bics: Optional initial set of enrolled BIC codes.
        """
        self._enrolled: Set[str] = set()
        if enrolled_bics:
            for bic in enrolled_bics:
                self._enrolled.add(bic.upper())

    def enroll(self, bic: str) -> None:
        """Add a BIC to the registry.

        Args:
            bic: SWIFT BIC code to enroll.
        """
        self._enrolled.add(bic.upper())

    def unenroll(self, bic: str) -> None:
        """Remove a BIC from the registry.

        Args:
            bic: SWIFT BIC code to remove.
        """
        self._enrolled.discard(bic.upper())

    def is_enrolled(self, bic: str) -> bool:
        """Return True if the BIC is enrolled.

        Args:
            bic: SWIFT BIC code to check.
        """
        return bic.upper() in self._enrolled

    def list_enrolled(self) -> Set[str]:
        """Return a copy of the enrolled BICs set."""
        return set(self._enrolled)
