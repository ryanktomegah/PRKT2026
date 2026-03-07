"""
C7 Execution Agent — Bank-side execution orchestration (ELO).
Architecture Spec: Zero outbound from C7 container.
EU AI Act Art.14 human-in-the-loop compliance.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
from .agent import ExecutionAgent
from .decision_log import DecisionLogger
from .degraded_mode import DegradedModeManager
from .human_override import HumanOverrideInterface
from .kill_switch import KillSwitch

__all__ = [
    "ExecutionAgent", "KillSwitch", "DecisionLogger",
    "HumanOverrideInterface", "DegradedModeManager",
]
