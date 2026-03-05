"""
C3 Repayment Engine — Dual-Signal Settlement Monitoring
Architecture Spec S2.3

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
from .repayment_loop import RepaymentLoop, SettlementMonitor
from .rejection_taxonomy import classify_rejection_code, RejectionClass
from .corridor_buffer import CorridorBuffer

__all__ = [
    "RepaymentLoop",
    "SettlementMonitor",
    "classify_rejection_code",
    "RejectionClass",
    "CorridorBuffer",
]
