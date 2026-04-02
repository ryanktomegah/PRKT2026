"""
lip/c3/__init__.py — C3 Repayment Engine Rust State Machine Package

Exposes the StateMachineBridge and PaymentWatchdog from the Python bridge layer.
"""
from lip.c3.state_machine_bridge import (
    PaymentWatchdog,
    StateMachineBridge,
)

__all__ = [
    "StateMachineBridge",
    "PaymentWatchdog",
]
