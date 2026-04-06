"""Integrity Shield — structural prevention of Delve-class failure modes.

This module enforces evidence-before-assertion across BPI's external claims,
compliance reports, breach disclosures, OSS attribution, and vendor onboarding.
Every external integrity artifact must carry a cryptographic proof chain back
to the underlying data; uncorroborated assertions are structurally rejected.
"""
