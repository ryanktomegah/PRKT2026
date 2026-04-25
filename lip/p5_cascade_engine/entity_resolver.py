"""
entity_resolver.py — Elevate BIC-level payment graphs to corporate-level cascade graphs.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Set

from lip.c1_failure_classifier.graph_builder import CorridorGraph, PaymentEdge
from lip.p5_cascade_engine.constants import CORPORATE_EDGE_MIN_PAYMENTS_30D
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)

logger = logging.getLogger(__name__)


class CorporateEntityResolver:
    """Resolves BIC-level payment edges to corporate-level supply chain edges."""

    def __init__(
        self,
        bic_to_corporate: Dict[str, str],
        corporate_metadata: Optional[Dict[str, Dict]] = None,
    ) -> None:
        self._mapping = dict(bic_to_corporate)
        self._metadata = corporate_metadata or {}

    def resolve(self, bic_graph: CorridorGraph) -> CascadeGraph:
        """Elevate a BIC-level graph to a corporate-level cascade graph."""
        # Phase 1: Aggregate BIC edges to corporate pairs
        pair_edges: Dict[tuple, List[PaymentEdge]] = defaultdict(list)
        corp_bics: Dict[str, Set[str]] = defaultdict(set)
        corridor_corps: Dict[str, Set[str]] = defaultdict(set)

        for edge in bic_graph.edges:
            src_corp = self._mapping.get(edge.sending_bic)
            tgt_corp = self._mapping.get(edge.receiving_bic)

            if src_corp is None or tgt_corp is None:
                continue
            if src_corp == tgt_corp:
                continue
            if edge.amount_usd <= 0:
                continue

            pair_edges[(src_corp, tgt_corp)].append(edge)
            corp_bics[src_corp].add(edge.sending_bic)
            corp_bics[tgt_corp].add(edge.receiving_bic)

            # Track corridor membership from currency_pair field
            if edge.currency_pair:
                corridor_corps[edge.currency_pair].add(src_corp)
                corridor_corps[edge.currency_pair].add(tgt_corp)

        # Phase 2: Build CorporateEdge from aggregated edges
        corporate_edges: List[CorporateEdge] = []

        for (src_corp, tgt_corp), edges in pair_edges.items():
            if len(edges) < CORPORATE_EDGE_MIN_PAYMENTS_30D:
                continue

            total_volume = sum(e.amount_usd for e in edges)
            payment_count = len(edges)
            # Use Decimal arithmetic to avoid float division precision loss (B9-07)
            d_total = Decimal(str(total_volume))
            d_numerator = sum(
                Decimal(str(e.amount_usd)) * Decimal(str(e.dependency_score))
                for e in edges
            )
            dep_score = float(
                (d_numerator / d_total).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            )
            failed_count = sum(1 for e in edges if e.features.get("failed", False))
            failure_rate = failed_count / payment_count
            max_ts = max(e.timestamp for e in edges)

            corporate_edges.append(CorporateEdge(
                source_corporate_id=src_corp,
                target_corporate_id=tgt_corp,
                total_volume_30d=total_volume,
                payment_count_30d=payment_count,
                dependency_score=dep_score,
                failure_rate_30d=failure_rate,
                avg_settlement_hours=0.0,
                last_payment_timestamp=max_ts,
            ))

        # Phase 3: Build adjacency structures
        adjacency: Dict[str, Dict[str, CorporateEdge]] = defaultdict(dict)
        reverse_adjacency: Dict[str, Dict[str, CorporateEdge]] = defaultdict(dict)

        for ce in corporate_edges:
            adjacency[ce.source_corporate_id][ce.target_corporate_id] = ce
            reverse_adjacency[ce.target_corporate_id][ce.source_corporate_id] = ce

        # Phase 4: Build CorporateNode for each corporate in edges
        all_corp_ids: Set[str] = set()
        for ce in corporate_edges:
            all_corp_ids.add(ce.source_corporate_id)
            all_corp_ids.add(ce.target_corporate_id)

        nodes: Dict[str, CorporateNode] = {}
        for corp_id in all_corp_ids:
            meta = self._metadata.get(corp_id, {})

            jurisdiction = meta.get("jurisdiction", "")
            if not jurisdiction:
                bics = corp_bics.get(corp_id, set())
                if bics:
                    primary_bic = sorted(bics)[0]
                    jurisdiction = primary_bic[4:6] if len(primary_bic) >= 6 else "XX"
                else:
                    jurisdiction = "XX"

            incoming = sum(
                e.total_volume_30d for e in reverse_adjacency.get(corp_id, {}).values()
            )
            outgoing = sum(
                e.total_volume_30d for e in adjacency.get(corp_id, {}).values()
            )

            dep_scores = {
                src: e.dependency_score
                for src, e in reverse_adjacency.get(corp_id, {}).items()
            }

            nodes[corp_id] = CorporateNode(
                corporate_id=corp_id,
                name_hash=meta.get("name_hash", ""),
                bics=frozenset(corp_bics.get(corp_id, set())),
                sector=meta.get("sector", "UNKNOWN"),
                jurisdiction=jurisdiction,
                total_incoming_volume_30d=incoming,
                total_outgoing_volume_30d=outgoing,
                dependency_scores=dep_scores,
            )

        # Phase 5: Compute summary statistics
        avg_dep = 0.0
        if corporate_edges:
            avg_dep = sum(e.dependency_score for e in corporate_edges) / len(corporate_edges)

        cascade = CascadeGraph(
            nodes=nodes,
            edges=corporate_edges,
            adjacency=dict(adjacency),
            reverse_adjacency=dict(reverse_adjacency),
            build_timestamp=time.time(),
            node_count=len(nodes),
            edge_count=len(corporate_edges),
            avg_dependency_score=avg_dep,
            corridor_to_corporates={k: sorted(v) for k, v in corridor_corps.items()},
        )

        logger.info(
            "resolve: %d BIC edges → %d corporate nodes, %d corporate edges (avg dep=%.3f)",
            len(bic_graph.edges), cascade.node_count, cascade.edge_count, avg_dep,
        )

        return cascade
