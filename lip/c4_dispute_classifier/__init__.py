"""
C4 Dispute Classifier — LLM-based dispute classification

Pluggable backend: Groq API (qwen/qwen3-32b, validated) for dev/staging,
or future GPTQ local model for bank-side zero-outbound deployment.
Note: zero-outbound applies to C7 (execution agent) today; C4 requires
outbound for Groq API until local GPTQ backend is implemented.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
from .model import DisputeClassifier, classify_dispute
from .prefilter import PreFilter, apply_prefilter
from .taxonomy import DisputeClass

__all__ = [
    "DisputeClass",
    "DisputeClassifier",
    "classify_dispute",
    "PreFilter",
    "apply_prefilter",
]
