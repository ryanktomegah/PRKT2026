"""
P5 cascade engine constants.

All thresholds require QUANT sign-off to change (per P5 blueprint §7.6).
"""
from decimal import Decimal

from lip.common.constants import FEE_FLOOR_BPS

# ── Cascade propagation thresholds (QUANT sign-off required) ─────────────────
CASCADE_INTERVENTION_THRESHOLD = 0.70
"""Minimum cascade probability to include a node in intervention plan."""

CASCADE_ALERT_THRESHOLD_USD = Decimal("1000000")
"""$1M — minimum cascade value at risk to trigger bank alert."""

CASCADE_ALERT_DEPENDENCY_THRESHOLD = 0.50
"""Minimum dependency_score for C3 to trigger cascade re-evaluation."""

CASCADE_MAX_HOPS = 5
"""Maximum BFS depth. Academic evidence: >95% of cascade value within 3 hops."""

CASCADE_DISCOUNT_CAP = Decimal("0.30")
"""Maximum PD reduction from cascade discount (prevents gaming)."""

INTERVENTION_BUDGET_SHARE = Decimal("0.25")
"""Maximum fraction of bank bridge lending capacity for cascade interventions."""

# ── Entity resolution ────────────────────────────────────────────────────────
CORPORATE_EDGE_MIN_PAYMENTS_30D = 2
"""Minimum payment count to form a corporate edge (filters noise)."""

CORPORATE_CENTRALITY_BATCH_INTERVAL_HOURS = 4
"""Hours between betweenness centrality recomputation."""

# ── Corporate feature vector ─────────────────────────────────────────────────
CORPORATE_NODE_FEATURE_DIM = 8
"""8-dimensional corporate node feature vector."""

# ── Intervention optimizer ──────────────────────────────────────────────────
INTERVENTION_FEE_RATE_BPS = FEE_FLOOR_BPS
"""Default bridge loan fee (bps annualised) for cost estimation.

Bound to the canonical ``FEE_FLOOR_BPS`` (300 bps). The intervention
optimiser must never estimate costs below the fee floor — doing so would
make bridge loans appear cheaper than they can ever actually be priced,
overstating cost-efficiency and biasing the greedy selection.

QUANT sign-off is required to decouple this from ``FEE_FLOOR_BPS``.
"""

# ── Cascade alert severity thresholds ───────────────────────────────────────
CASCADE_ALERT_EXCLUSIVITY_HOURS = 4
"""Bank exclusivity window (hours) to act on intervention recommendation."""

CASCADE_ALERT_SEVERITY_HIGH_USD = Decimal("10000000")
"""CVaR >= $10M triggers HIGH severity alert."""

CASCADE_ALERT_SEVERITY_MEDIUM_USD = Decimal("1000000")
"""CVaR >= $1M triggers MEDIUM severity alert (same as alert threshold)."""
