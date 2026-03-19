"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

graph_builder.py — BIC-pair directed multigraph construction
C1 Spec Section 3: Payment corridor graph
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── P5 Bayesian smoothing constants ───────────────────────────────────────────
# QUANT sign-off required to change these values.
# k=5 mirrors the standard Laplace pseudo-count for Beta-Binomial inference.
# Prior default = 10% average corridor dependency (conservative; update after
# accumulating 30 days of pilot data under QUANT review).
_SMOOTHING_K: int = 5          # pseudo-count; higher = more prior weight
_DEPENDENCY_PRIOR_DEFAULT: float = 0.10  # prior when no history exists


@dataclass
class PaymentEdge:
    """Represents a single directed payment between two BIC nodes.

    Attributes
    ----------
    uetr:
        Unique End-to-End Transaction Reference (ISO 20022).
    sending_bic:
        BIC code of the originating financial institution.
    receiving_bic:
        BIC code of the destination financial institution.
    amount_usd:
        Transaction amount normalised to USD.
    currency_pair:
        Original currency pair string, e.g. ``"USD_EUR"``.
    timestamp:
        Unix epoch timestamp (seconds) at payment submission.
    features:
        Arbitrary key-value store for pre-computed edge features.
    """

    uetr: str
    sending_bic: str
    receiving_bic: str
    amount_usd: float
    currency_pair: str
    timestamp: float
    # P5 Bayesian smoothing: smoothed concentration score (see BICGraphBuilder.add_payment).
    # Raw formula: amount / cumulative_incoming_volume (=1.0 on first payment — inflated).
    # Smoothed: (n × raw + k × prior) / (n + k), k=5. Reduces first-payment bias.
    dependency_score: float = 0.0
    # Number of prior payments to the same receiving BIC when this edge was added.
    # Low observation_count signals low confidence in dependency_score.
    observation_count: int = 0
    features: dict = field(default_factory=dict)


@dataclass
class CorridorGraph:
    """Snapshot of the BIC-pair directed multigraph.

    Attributes
    ----------
    nodes:
        Sorted list of unique BIC codes observed in the graph.
    edges:
        All :class:`PaymentEdge` instances added to the graph.
    adjacency:
        Nested mapping ``{sending_bic: {receiving_bic: [PaymentEdge, ...]}}``
        enabling O(1) corridor lookup.
    """

    nodes: List[str] = field(default_factory=list)
    edges: List[PaymentEdge] = field(default_factory=list)
    adjacency: Dict[str, Dict[str, List[PaymentEdge]]] = field(default_factory=dict)


@dataclass(frozen=True)
class CascadeConfidence:
    """Confidence metadata attached to a :meth:`BICGraphBuilder.get_cascade_risk` result.

    Attributes
    ----------
    mean_observation_count:
        Mean number of prior payments per at-risk corridor. Higher values
        indicate well-observed corridors where ``dependency_score`` is reliable.
    min_observation_count:
        Minimum observation count across all at-risk corridors. A value below
        ``_SMOOTHING_K`` (=5) means at least one corridor's score is still
        pulled significantly toward the prior.
    is_high_confidence:
        ``True`` when all at-risk corridors have at least ``_SMOOTHING_K``
        prior observations — at that point smoothing contribution is < 50%.
    at_risk_count:
        Number of BICs flagged as at risk (length of the returned list).
    """

    mean_observation_count: float
    min_observation_count: int
    is_high_confidence: bool
    at_risk_count: int


class BICGraphBuilder:
    """Incrementally builds a directed multigraph of BIC-pair corridors.

    Each call to :meth:`add_payment` registers a :class:`PaymentEdge` and
    updates all internal indices.  The graph can be snapshotted at any time
    via :meth:`build_graph`.

    C1 Spec Section 3 compliance:
    - Directed edges represent payment flows (sending → receiving).
    - Multi-edges allowed: many UETRs may share the same corridor.
    - Node features are computed on-the-fly from observed history.
    """

    _SECONDS_PER_DAY: float = 86_400.0
    _SECONDS_24H: float = 24 * 3600.0
    _SECONDS_30D: float = 30 * 86_400.0
    _SECONDS_7D: float = 7 * 86_400.0

    def __init__(self) -> None:
        # {bic -> list[PaymentEdge]} for outgoing edges
        self._out_edges: Dict[str, List[PaymentEdge]] = {}
        # {bic -> list[PaymentEdge]} for incoming edges
        self._in_edges: Dict[str, List[PaymentEdge]] = {}
        # nested: {sending -> {receiving -> [edges]}}
        self._adjacency: Dict[str, Dict[str, List[PaymentEdge]]] = {}
        # {bic -> earliest timestamp} for corridor age
        self._bic_first_seen: Dict[str, float] = {}
        # latest timestamp seen across all edges — used as reference point in
        # get_node_features() so that time-window features (24h, 30d) are
        # computed relative to the data, not wall-clock time.  This makes
        # training on historical/synthetic data produce the same features as
        # production inference on live data.
        self._max_timestamp: float = time.time()
        # {bic -> total incoming USD volume} for dependency calculation (P5)
        self._in_volumes: Dict[str, float] = {}
        self._all_edges: List[PaymentEdge] = []
        # Running totals for global prior (used in Bayesian smoothing)
        self._dep_score_sum: float = 0.0
        self._dep_score_count: int = 0
        logger.debug("BICGraphBuilder initialised")

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_payment(self, edge: PaymentEdge) -> None:
        """Register a payment edge in the multigraph.

        Parameters
        ----------
        edge:
            A fully-populated :class:`PaymentEdge`.  Both BICs are created
            as nodes if not already present.
        """
        s, r = edge.sending_bic, edge.receiving_bic

        if edge.timestamp > self._max_timestamp:
            self._max_timestamp = edge.timestamp

        for bic in (s, r):
            if bic not in self._bic_first_seen:
                self._bic_first_seen[bic] = edge.timestamp
            else:
                self._bic_first_seen[bic] = min(self._bic_first_seen[bic], edge.timestamp)

        self._out_edges.setdefault(s, []).append(edge)

        # Capture observation count BEFORE appending to incoming edges
        n = len(self._in_edges.get(r, []))
        self._in_edges.setdefault(r, []).append(edge)
        self._adjacency.setdefault(s, {}).setdefault(r, []).append(edge)

        # Update incoming volume
        self._in_volumes[r] = self._in_volumes.get(r, 0.0) + edge.amount_usd

        # ── P5 Bayesian smoothing ────────────────────────────────────────────
        # Raw dependency = fraction of total receivables this payment represents.
        # Without smoothing: first payment → score = 1.0 (trivially inflated).
        # With smoothing (Laplace / Beta-Binomial): pull toward the global prior
        # until the corridor is well-observed (n ≥ k).
        raw = edge.amount_usd / self._in_volumes[r]
        prior = self._compute_corridor_prior_dependency()
        smoothed = (n * raw + _SMOOTHING_K * prior) / (n + _SMOOTHING_K)

        edge.dependency_score = smoothed
        edge.observation_count = n

        # Update running totals for future prior calculations
        self._dep_score_sum += smoothed
        self._dep_score_count += 1

        self._all_edges.append(edge)

    def _compute_corridor_prior_dependency(self) -> float:
        """Return the global mean dependency score across all observed edges.

        Used as the Bayesian prior in :meth:`add_payment`. Returns
        ``_DEPENDENCY_PRIOR_DEFAULT`` (0.10) when no history exists yet.
        """
        if self._dep_score_count == 0:
            return _DEPENDENCY_PRIOR_DEFAULT
        return self._dep_score_sum / self._dep_score_count

    # ------------------------------------------------------------------
    # Neighbourhood queries
    # ------------------------------------------------------------------

    def get_neighbors(self, bic: str, k: int = 5) -> List[str]:
        """Return top-*k* neighbours by total outbound transaction volume.

        Parameters
        ----------
        bic:
            Source BIC whose outbound corridors are ranked.
        k:
            Maximum number of neighbours to return.

        Returns
        -------
        List[str]
            Up to *k* receiving-BIC codes, sorted descending by USD volume.
        """
        if bic not in self._adjacency:
            return []

        corridor_volume: Dict[str, float] = {}
        for receiving_bic, edges in self._adjacency[bic].items():
            corridor_volume[receiving_bic] = sum(e.amount_usd for e in edges)

        sorted_neighbors = sorted(
            corridor_volume.items(), key=lambda kv: kv[1], reverse=True
        )
        return [nbr for nbr, _ in sorted_neighbors[:k]]

    def get_cascade_risk(
        self, bic: str, dependency_threshold: float = 0.2
    ) -> Tuple[List[str], CascadeConfidence]:
        """Identify downstream BICs highly dependent on payments from this BIC.

        Implements core logic for Supply Chain Cascade Detection (P5).

        Parameters
        ----------
        bic:
            Source BIC whose failure might cascade.
        dependency_threshold:
            Minimum ratio of payment-to-receivables to trigger a risk flag.

        Returns
        -------
        List[str]
            BICs at risk of cascade failure.

        Returns a ``(at_risk_bics, confidence)`` tuple. Low
        :attr:`CascadeConfidence.min_observation_count` values (< ``_SMOOTHING_K``
        = 5) indicate that at least one corridor score is still pulled toward the
        prior and should be treated with caution. The known first-payment
        over-inflation bug is resolved by Bayesian smoothing in
        :meth:`add_payment`.
        """
        if bic not in self._adjacency:
            _empty_conf = CascadeConfidence(
                mean_observation_count=0.0,
                min_observation_count=0,
                is_high_confidence=False,
                at_risk_count=0,
            )
            return [], _empty_conf

        at_risk = []
        obs_counts: List[int] = []

        for receiving_bic, edges in self._adjacency[bic].items():
            if not edges:
                continue
            latest = max(edges, key=lambda e: e.timestamp)
            if latest.dependency_score >= dependency_threshold:
                at_risk.append(receiving_bic)
                obs_counts.append(latest.observation_count)

        if not at_risk:
            conf = CascadeConfidence(
                mean_observation_count=0.0,
                min_observation_count=0,
                is_high_confidence=True,   # no risk corridors = no concern
                at_risk_count=0,
            )
            return [], conf

        mean_obs = sum(obs_counts) / len(obs_counts)
        min_obs = min(obs_counts)
        conf = CascadeConfidence(
            mean_observation_count=mean_obs,
            min_observation_count=min_obs,
            is_high_confidence=(min_obs >= _SMOOTHING_K),
            at_risk_count=len(at_risk),
        )
        return at_risk, conf

    # ------------------------------------------------------------------
    # Feature computation
    # ------------------------------------------------------------------

    def get_node_features(self, bic: str) -> np.ndarray:
        """Compute the 8-dimensional node feature vector for a BIC.

        Feature layout (NODE_FEATURE_DIM = 8):

        0. ``out_degree``           — number of distinct outbound corridors
        1. ``in_degree``            — number of distinct inbound corridors
        2. ``volume_24h``           — total USD sent in last 24 h (log1p)
        3. ``failure_rate_30d``     — fraction of payments flagged failed in 30 d
        4. ``avg_amount``           — mean outbound USD (log1p)
        5. ``std_amount``           — std of outbound USD (log1p)
        6. ``corridor_age_days``    — days since first observed edge
        7. ``currency_concentration`` — Herfindahl–Hirschman index of currency pairs

        Parameters
        ----------
        bic:
            Target BIC code.

        Returns
        -------
        np.ndarray
            Shape ``(8,)``, dtype ``float64``.
        """
        now = self._max_timestamp  # data-relative reference; correct for both training and production
        out_edges = self._out_edges.get(bic, [])
        _in_edges = self._in_edges.get(bic, [])

        out_degree = float(len(self._adjacency.get(bic, {})))
        in_degree = float(
            sum(1 for edges_dict in self._adjacency.values() if bic in edges_dict)
        )

        cutoff_24h = now - self._SECONDS_24H
        volume_24h = math.log1p(
            sum(e.amount_usd for e in out_edges if e.timestamp >= cutoff_24h)
        )

        cutoff_30d = now - self._SECONDS_30D
        recent_out = [e for e in out_edges if e.timestamp >= cutoff_30d]
        failure_rate_30d = 0.0
        if recent_out:
            failed = sum(1 for e in recent_out if e.features.get("failed", False))
            failure_rate_30d = failed / len(recent_out)

        amounts = [e.amount_usd for e in out_edges]
        avg_amount = math.log1p(float(np.mean(amounts))) if amounts else 0.0
        std_amount = math.log1p(float(np.std(amounts))) if len(amounts) > 1 else 0.0

        first_seen = self._bic_first_seen.get(bic, now)  # now = _max_timestamp
        corridor_age_days = (now - first_seen) / self._SECONDS_PER_DAY

        # Herfindahl-Hirschman index over currency pairs
        pair_counts: Dict[str, int] = {}
        for e in out_edges:
            pair_counts[e.currency_pair] = pair_counts.get(e.currency_pair, 0) + 1
        total_tx = len(out_edges) or 1
        currency_concentration = float(
            sum((cnt / total_tx) ** 2 for cnt in pair_counts.values())
        )

        return np.array(
            [
                out_degree,
                in_degree,
                volume_24h,
                failure_rate_30d,
                avg_amount,
                std_amount,
                corridor_age_days,
                currency_concentration,
            ],
            dtype=np.float64,
        )

    def get_edge_features(self, sending_bic: str, receiving_bic: str) -> np.ndarray:
        """Compute the 6-dimensional edge feature vector for a corridor.

        Feature layout (EDGE_FEATURE_DIM = 6):

        0. ``amount``                — most-recent payment amount (log1p USD)
        1. ``hour_of_day``           — hour extracted from the most-recent timestamp
        2. ``day_of_week``           — weekday (0=Mon … 6=Sun) of most-recent tx
        3. ``corridor_failure_rate`` — fraction of failed payments on this corridor
        4. ``corridor_volume_7d``    — total USD on corridor in last 7 d (log1p)
        5. ``amount_zscore``         — z-score of latest amount vs corridor history

        Parameters
        ----------
        sending_bic:
            Originating BIC.
        receiving_bic:
            Receiving BIC.

        Returns
        -------
        np.ndarray
            Shape ``(6,)``, dtype ``float64``.  Returns zeros if the corridor
            has no recorded history.
        """
        corridor_edges = (
            self._adjacency.get(sending_bic, {}).get(receiving_bic, [])
        )
        if not corridor_edges:
            return np.zeros(6, dtype=np.float64)

        latest = max(corridor_edges, key=lambda e: e.timestamp)
        import datetime

        dt = datetime.datetime.fromtimestamp(latest.timestamp, tz=datetime.timezone.utc)
        hour_of_day = float(dt.hour)
        day_of_week = float(dt.weekday())

        failed_count = sum(
            1 for e in corridor_edges if e.features.get("failed", False)
        )
        corridor_failure_rate = failed_count / len(corridor_edges)

        now = self._max_timestamp  # data-relative reference (same fix as get_node_features)
        cutoff_7d = now - self._SECONDS_7D
        corridor_volume_7d = math.log1p(
            sum(e.amount_usd for e in corridor_edges if e.timestamp >= cutoff_7d)
        )

        amounts = np.array([e.amount_usd for e in corridor_edges], dtype=np.float64)
        latest_amount = latest.amount_usd
        log_amount = math.log1p(latest_amount)
        amount_mean = float(np.mean(amounts))
        amount_std = float(np.std(amounts)) + 1e-9
        amount_zscore = (latest_amount - amount_mean) / amount_std

        return np.array(
            [
                log_amount,
                hour_of_day,
                day_of_week,
                corridor_failure_rate,
                corridor_volume_7d,
                amount_zscore,
            ],
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def build_graph(self) -> CorridorGraph:
        """Produce an immutable snapshot of the current multigraph.

        Returns
        -------
        CorridorGraph
            Contains all nodes, edges, and the adjacency mapping at the
            time of the call.
        """
        nodes = sorted(self._bic_first_seen.keys())
        adjacency_copy: Dict[str, Dict[str, List[PaymentEdge]]] = {
            s: {r: list(edges) for r, edges in receivers.items()}
            for s, receivers in self._adjacency.items()
        }
        graph = CorridorGraph(
            nodes=nodes,
            edges=list(self._all_edges),
            adjacency=adjacency_copy,
        )
        logger.info(
            "build_graph: %d nodes, %d edges", len(nodes), len(self._all_edges)
        )
        return graph
