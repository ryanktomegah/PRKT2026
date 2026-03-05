"""
Liquidity Intelligence Platform (LIP) — Production System
Architecture Specification v1.2

Three-entity role mapping:
  MLO  — Money Lending Organisation (offers bridge loan)
  MIPLO — Money In / Payment Lending Organisation (receives settlement)
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
__version__ = "1.0.0"
__all__ = ["common", "c1_failure_classifier", "c2_pd_model", "c3_repayment_engine",
           "c4_dispute_classifier", "c5_streaming", "c6_aml_velocity", "c7_execution_agent"]
