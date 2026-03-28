"""
P5 cascade engine constants.

All thresholds require QUANT sign-off to change (per P5 blueprint §7.6).
"""
from decimal import Decimal

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
