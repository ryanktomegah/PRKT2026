"""
C4 Dispute Classifier — LLM-based dispute classification
Bank-side container (zero outbound network) with GPTQ quantized model

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation  
  ELO  — Execution Lending Organisation (bank-side agent, C7)

Architecture Spec: Zero outbound for C4 container
"""
from .taxonomy import DisputeClass
from .model import DisputeClassifier, classify_dispute
from .prefilter import PreFilter, apply_prefilter

__all__ = [
    "DisputeClass",
    "DisputeClassifier",
    "classify_dispute",
    "PreFilter",
    "apply_prefilter",
]
