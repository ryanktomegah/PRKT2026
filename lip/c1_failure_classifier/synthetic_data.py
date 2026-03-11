"""
synthetic_data.py — Synthetic SWIFT pacs.002 payment data generator
for C1 Failure Prediction Classifier training.

ALL data produced by this module is explicitly synthetic:
    corpus_tag = "SYNTHETIC_CORPUS"

Architecture anchors:
    - BIS CPMI payment statistics for volume/amount distributions
    - 3.5% midpoint failure rate
    - 55% Class A / 30% Class B / 15% Class C among failures
    - BLOCK codes excluded (handled by C4 prefilter)
    - Power-law degree distribution for BIC graph (correspondent banking)
    - Rejection code co-occurrence patterns (AC01/AC04 cluster;
      AM04 with large amounts; CURR with cross-border; AG01 with EM)

SWIFT does not publish pacs.002 transaction-level failure data; synthetic
generation is the industry-standard approach for training payment failure
classifiers.
"""
from __future__ import annotations

import csv
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from lip.c3_repayment_engine.rejection_taxonomy import (
    REJECTION_CODE_TAXONOMY,
    RejectionClass,
    get_all_codes_for_class,
)

# ── Global generation parameters ─────────────────────────────────────────────
FAILURE_RATE = 0.035  # 3.5% midpoint failure rate

CLASS_DISTRIBUTION: dict[str, float] = {
    "A": 0.55,   # 55% of failures — Class A (transient, 3-day maturity)
    "B": 0.30,   # 30% of failures — Class B (procedural, 7-day maturity)
    "C": 0.15,   # 15% of failures — Class C (structural, 21-day maturity)
}
# BLOCK codes (DISP, FRAU, FRAD, DUPL) are excluded from training — C4 domain.

# ── BIC Registry — 35 institutions across tiers and geographies ──────────────
BIC_REGISTRY: dict[str, dict] = {
    # Tier 1 — GSIBs
    # failure_multiplier: individual BIC risk factor within tier (seed-derived, not random)
    "DEUTDEFF": {"name": "Deutsche Bank",        "tier": 1, "country": "DE", "region": "EU",    "failure_multiplier": 0.85},
    "BNPAFRPP": {"name": "BNP Paribas",          "tier": 1, "country": "FR", "region": "EU",    "failure_multiplier": 0.90},
    "HSBCGB2L": {"name": "HSBC",                 "tier": 1, "country": "GB", "region": "EU",    "failure_multiplier": 0.80},
    "CHASUS33": {"name": "JPMorgan Chase",        "tier": 1, "country": "US", "region": "NA",   "failure_multiplier": 0.75},
    "CITIUS33": {"name": "Citibank",              "tier": 1, "country": "US", "region": "NA",   "failure_multiplier": 0.82},
    "BOFAUS3N": {"name": "Bank of America",       "tier": 1, "country": "US", "region": "NA",   "failure_multiplier": 0.88},
    "SCBLSGSG": {"name": "Standard Chartered",    "tier": 1, "country": "SG", "region": "APAC", "failure_multiplier": 1.05},
    # Tier 2 — Large regional banks
    "SBINMUMU": {"name": "State Bank of India",   "tier": 2, "country": "IN", "region": "APAC", "failure_multiplier": 1.20},
    "BRADBRSP": {"name": "Bradesco",              "tier": 2, "country": "BR", "region": "LATAM","failure_multiplier": 1.35},
    "LOYDGB2L": {"name": "Lloyds Bank",           "tier": 2, "country": "GB", "region": "EU",   "failure_multiplier": 0.95},
    "COBADEFF": {"name": "Commerzbank",           "tier": 2, "country": "DE", "region": "EU",   "failure_multiplier": 0.92},
    "ABKEKENA": {"name": "Absa Bank Kenya",       "tier": 2, "country": "KE", "region": "AFR",  "failure_multiplier": 1.45},
    "ICBKCNBJ": {"name": "ICBC",                  "tier": 2, "country": "CN", "region": "APAC", "failure_multiplier": 1.30},
    "MABOROBU": {"name": "Raiffeisen Romania",    "tier": 2, "country": "RO", "region": "EU",   "failure_multiplier": 1.15},
    "INGBNL2A": {"name": "ING Bank",              "tier": 2, "country": "NL", "region": "EU",   "failure_multiplier": 0.88},
    # Tier 3 — Smaller / EM banks: AFR
    "ECOCCIAB": {"name": "Ecobank Cote d'Ivoire", "tier": 3, "country": "CI", "region": "AFR",  "failure_multiplier": 1.70},
    "ZENITHNL": {"name": "Zenith Bank Nigeria",   "tier": 3, "country": "NG", "region": "AFR",  "failure_multiplier": 2.10},
    "FBNBNGL1": {"name": "First Bank Nigeria",    "tier": 3, "country": "NG", "region": "AFR",  "failure_multiplier": 1.90},
    "SBZAZAJJ": {"name": "Standard Bank S.Africa","tier": 3, "country": "ZA", "region": "AFR",  "failure_multiplier": 1.40},
    "GTBINGLA": {"name": "Guaranty Trust Bank",   "tier": 3, "country": "NG", "region": "AFR",  "failure_multiplier": 1.80},
    # Tier 3 — MENA
    "AIBKEGCX": {"name": "Arab Intl Bank Egypt",  "tier": 3, "country": "EG", "region": "MENA", "failure_multiplier": 2.20},
    "NBADAEAA": {"name": "First Abu Dhabi Bank",  "tier": 3, "country": "AE", "region": "MENA", "failure_multiplier": 1.10},
    "RIBLSARI": {"name": "Riyad Bank",            "tier": 3, "country": "SA", "region": "MENA", "failure_multiplier": 1.25},
    "QNBAQAQA": {"name": "Qatar National Bank",   "tier": 3, "country": "QA", "region": "MENA", "failure_multiplier": 1.15},
    "MASHAEAD": {"name": "Mashreq Bank UAE",       "tier": 3, "country": "AE", "region": "MENA", "failure_multiplier": 1.30},
    # Tier 3 — LATAM
    "BBVAMXMM": {"name": "BBVA Mexico",           "tier": 3, "country": "MX", "region": "LATAM","failure_multiplier": 1.55},
    "BNORMXMM": {"name": "Banorte Mexico",         "tier": 3, "country": "MX", "region": "LATAM","failure_multiplier": 1.60},
    "BCHICLRM": {"name": "Banco de Chile",         "tier": 3, "country": "CL", "region": "LATAM","failure_multiplier": 1.35},
    "BCOLCOBM": {"name": "Bancolombia",            "tier": 3, "country": "CO", "region": "LATAM","failure_multiplier": 1.50},
    # Tier 3 — APAC
    "PNBPINBB": {"name": "Punjab National Bank",   "tier": 3, "country": "IN", "region": "APAC", "failure_multiplier": 1.75},
    "HDFCINBB": {"name": "HDFC Bank",              "tier": 3, "country": "IN", "region": "APAC", "failure_multiplier": 1.20},
    "KASITHBK": {"name": "Kasikorn Bank",          "tier": 3, "country": "TH", "region": "APAC", "failure_multiplier": 1.40},
    "MANDIDJJ": {"name": "Bank Mandiri",           "tier": 3, "country": "ID", "region": "APAC", "failure_multiplier": 1.65},
    "BKKBTHBK": {"name": "Bangkok Bank",           "tier": 3, "country": "TH", "region": "APAC", "failure_multiplier": 1.30},
    "AKBKTRIS": {"name": "Akbank Turkey",          "tier": 3, "country": "TR", "region": "MENA", "failure_multiplier": 1.85},
}

# ── Currency Corridor Definitions ─────────────────────────────────────────────
CORRIDOR_DEFINITIONS: dict[str, dict] = {
    # G7 high-volume corridors
    # failure_rate_multiplier: per-corridor risk factor (replaces 3-bucket region_type approach)
    "EUR/USD": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 800,  "failure_rate_multiplier": 0.30},
    "GBP/USD": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 350,  "failure_rate_multiplier": 0.35},
    "USD/JPY": {"region_type": "G7",           "avg_settlement_hours": 6,  "annual_volume_billions": 500,  "failure_rate_multiplier": 0.38},
    "EUR/GBP": {"region_type": "G7",           "avg_settlement_hours": 3,  "annual_volume_billions": 200,  "failure_rate_multiplier": 0.32},
    "EUR/JPY": {"region_type": "G7",           "avg_settlement_hours": 6,  "annual_volume_billions": 150,  "failure_rate_multiplier": 0.42},
    "GBP/JPY": {"region_type": "G7",           "avg_settlement_hours": 6,  "annual_volume_billions": 80,   "failure_rate_multiplier": 0.48},
    "USD/CHF": {"region_type": "G7",           "avg_settlement_hours": 5,  "annual_volume_billions": 70,   "failure_rate_multiplier": 0.36},
    "EUR/CHF": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 80,   "failure_rate_multiplier": 0.35},
    "GBP/CHF": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 60,   "failure_rate_multiplier": 0.40},
    "USD/CAD": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 150,  "failure_rate_multiplier": 0.38},
    "USD/AUD": {"region_type": "G7",           "avg_settlement_hours": 10, "annual_volume_billions": 60,   "failure_rate_multiplier": 0.52},
    # EM corridors
    "USD/INR": {"region_type": "EM",           "avg_settlement_hours": 12, "annual_volume_billions": 80,   "failure_rate_multiplier": 1.20},
    "EUR/INR": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 40,   "failure_rate_multiplier": 1.25},
    "GBP/INR": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 20,   "failure_rate_multiplier": 1.28},
    "USD/KES": {"region_type": "EM",           "avg_settlement_hours": 16, "annual_volume_billions": 5,    "failure_rate_multiplier": 1.60},
    "USD/AED": {"region_type": "EM",           "avg_settlement_hours": 12, "annual_volume_billions": 30,   "failure_rate_multiplier": 1.10},
    "USD/SAR": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 25,   "failure_rate_multiplier": 1.15},
    "EUR/AED": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 15,   "failure_rate_multiplier": 1.12},
    "USD/ZAR": {"region_type": "EM",           "avg_settlement_hours": 16, "annual_volume_billions": 10,   "failure_rate_multiplier": 1.45},
    "USD/PHP": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 15,   "failure_rate_multiplier": 1.30},
    "USD/THB": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 12,   "failure_rate_multiplier": 1.22},
    # High-friction corridors
    "USD/BRL": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 45,  "failure_rate_multiplier": 1.70},
    "USD/CNY": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 120, "failure_rate_multiplier": 2.50},
    "EUR/BRL": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 20, "annual_volume_billions": 15,  "failure_rate_multiplier": 1.80},
    "EUR/CNY": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 20, "annual_volume_billions": 60,  "failure_rate_multiplier": 2.50},
    "USD/NGN": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 24, "annual_volume_billions": 8,   "failure_rate_multiplier": 2.80},
    "USD/EGP": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 12,  "failure_rate_multiplier": 2.80},
    "EUR/ZAR": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 22, "annual_volume_billions": 6,   "failure_rate_multiplier": 2.00},
    "USD/MXN": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 16, "annual_volume_billions": 35,  "failure_rate_multiplier": 1.55},
    "USD/CLP": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 10,  "failure_rate_multiplier": 1.65},
    "EUR/MXN": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 8,   "failure_rate_multiplier": 1.65},
    "GBP/BRL": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 22, "annual_volume_billions": 5,   "failure_rate_multiplier": 1.85},
    "USD/IDR": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 16, "annual_volume_billions": 20,  "failure_rate_multiplier": 1.72},
    "USD/VND": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 8,   "failure_rate_multiplier": 1.80},
}

# ── Log-normal amount parameters per corridor region type ─────────────────────
# (log_mu, log_sigma) anchored to BIS CPMI stats:
#   G7:           median $250K, mean ~$1.2M
#   EM:           median $50K,  mean ~$300K
#   HIGH_FRICTION: median $80K, mean ~$500K
_AMOUNT_PARAMS: dict[str, tuple[float, float]] = {
    "G7":           (float(np.log(250_000)), 1.80),
    "EM":           (float(np.log(50_000)),  1.90),
    "HIGH_FRICTION": (float(np.log(80_000)), 1.90),
}

# ── Country → primary currency mapping ───────────────────────────────────────
_COUNTRY_TO_CURRENCY: dict[str, str] = {
    "DE": "EUR", "FR": "EUR", "NL": "EUR", "IT": "EUR", "ES": "EUR",
    "AT": "EUR", "RO": "EUR", "BE": "EUR", "FI": "EUR", "PT": "EUR",
    "CI": "USD",  # XOF — fall back to USD for corridor matching
    "GB": "GBP",
    "US": "USD",
    "JP": "JPY",
    "CH": "CHF",
    "CA": "CAD",
    "AU": "AUD",
    "SG": "USD",  # Standard Chartered SG frequently deals in USD
    "IN": "INR",
    "BR": "BRL",
    "CN": "CNY",
    "KE": "KES",
    "ZA": "ZAR",
    "NG": "NGN",
    "EG": "EGP",
    "AE": "AED",
    "SA": "SAR",
    "QA": "USD",  # QAR — fall back to USD for corridor matching
    "MX": "MXN",
    "CL": "CLP",
    "CO": "USD",  # COP — fall back to USD
    "TH": "THB",
    "ID": "IDR",
    "TR": "USD",  # TRY — fall back to USD
    "PH": "PHP",
    "VN": "VND",
}

# ── Pre-built lookup structures ────────────────────────────────────────────────

# Non-BLOCK rejection codes, grouped by class label ("A", "B", "C")
_CODES_BY_CLASS: dict[str, list[str]] = {
    "A": get_all_codes_for_class(RejectionClass.CLASS_A),
    "B": get_all_codes_for_class(RejectionClass.CLASS_B),
    "C": get_all_codes_for_class(RejectionClass.CLASS_C),
}
_BLOCK_CODES: set[str] = {
    c for c, rc in REJECTION_CODE_TAXONOMY.items() if rc is RejectionClass.BLOCK
}

# BIC list sorted by tier (Tier 1 first) to assign Zipf ranks
_bic_tier_pairs = sorted(
    ((bic, info["tier"]) for bic, info in BIC_REGISTRY.items()),
    key=lambda x: x[1],
)
_BIC_LIST: list[str] = [bic for bic, _ in _bic_tier_pairs]
_BIC_RANKS: np.ndarray = np.arange(1, len(_BIC_LIST) + 1, dtype=float)
_BIC_WEIGHTS_RAW: np.ndarray = 1.0 / (_BIC_RANKS ** 1.5)
_BIC_WEIGHTS: np.ndarray = _BIC_WEIGHTS_RAW / _BIC_WEIGHTS_RAW.sum()

# Corridor volume-weighted probability array for fallback sampling
_CORRIDOR_KEYS: list[str] = list(CORRIDOR_DEFINITIONS.keys())
_CORRIDOR_VOLUMES: np.ndarray = np.array(
    [CORRIDOR_DEFINITIONS[c]["annual_volume_billions"] for c in _CORRIDOR_KEYS],
    dtype=float,
)
_CORRIDOR_PROBS: np.ndarray = _CORRIDOR_VOLUMES / _CORRIDOR_VOLUMES.sum()

# Required fields on every generated record
_REQUIRED_FIELDS = frozenset({
    "uetr", "sending_bic", "receiving_bic", "currency_pair", "amount_usd",
    "hour_of_day", "day_of_week", "settlement_lag_days", "prior_rejections_30d",
    "rejection_code", "rejection_class", "payment_status", "correspondent_depth",
    "data_quality_score", "message_priority", "is_failure", "corpus_tag",
    "generation_timestamp", "generation_seed",
})


# ── Main Generator ────────────────────────────────────────────────────────────

class SyntheticPaymentGenerator:
    """
    Generates realistic synthetic SWIFT pacs.002-style payment records
    for training the C1 Failure Prediction Classifier.

    Architecture anchors:
    - BIS CPMI payment statistics for volume/amount distributions
    - 3.5% midpoint failure rate
    - 55% Class A / 30% Class B / 15% Class C distribution among failures
    - BLOCK codes excluded (handled by C4 prefilter)
    - Power-law degree distribution for BIC graph (correspondent banking)
    - Rejection code co-occurrence patterns (AC01/AC04 cluster;
      AM04 clusters with large amounts; CURR with cross-border;
      AG01 clusters with EM corridors)

    All outputs are explicitly labelled: SYNTHETIC_CORPUS
    """

    def __init__(self, seed: int = 42, failure_rate: float = FAILURE_RATE) -> None:
        self._seed = seed
        self._failure_rate = failure_rate
        self._rng = np.random.default_rng(seed)
        self._gen_ts = datetime.now(timezone.utc).isoformat()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_dataset(self, n_transactions: int = 100_000) -> list[dict]:
        """
        Generate n_transactions synthetic payment records.

        Each record contains:
        - uetr: str (UUID v4)
        - sending_bic: str
        - receiving_bic: str
        - currency_pair: str
        - amount_usd: float
        - hour_of_day: int (0-23)
        - day_of_week: int (0-6)
        - settlement_lag_days: int (0-5)
        - prior_rejections_30d: int
        - rejection_code: str ("NONE" for successful, actual code for failures)
        - rejection_class: str ("NONE", "A", "B", "C")
        - payment_status: str ("ACCC" for success, "RJCT" for failure)
        - correspondent_depth: int (1-5)
        - data_quality_score: float (0.0-1.0)
        - message_priority: str ("NORM", "HIGH", "URGP")
        - is_failure: int (0 or 1) — the label
        - corpus_tag: str = "SYNTHETIC_CORPUS"
        - generation_timestamp: str (ISO 8601)
        - generation_seed: int
        """
        records: list[dict] = []
        for _ in range(n_transactions):
            records.append(self._generate_base_record())

        # Two-pass failure assignment: compute risk scores, normalise, then sample.
        scores = np.array([self._compute_risk_score(r) for r in records], dtype=float)
        mean_score = scores.mean()
        if mean_score > 0:
            norm_probs = self._failure_rate * (scores / mean_score)
        else:
            norm_probs = np.full(n_transactions, self._failure_rate)

        # Assign failure labels and rejection details
        failure_flags = self._rng.random(n_transactions) < norm_probs
        for i, (record, is_fail) in enumerate(zip(records, failure_flags)):
            if is_fail:
                record = self._assign_failure(record)
            else:
                record["rejection_code"] = "NONE"
                record["rejection_class"] = "NONE"
                record["payment_status"] = "ACCC"
                record["is_failure"] = 0
            records[i] = record

        return records

    def generate_graph_data(self, transactions: list[dict]) -> dict:
        """
        From generated transactions, build the BIC-pair graph structure
        needed by C1's GraphSAGE.

        Returns:
        - nodes: list of dicts with BIC identifier and node features
        - edges: list of dicts with (sender, receiver) and edge features
        - adjacency: dict mapping each BIC to its neighbours
        - degree_distribution: dict with degree stats confirming power-law shape
        """
        edge_counts: dict[tuple[str, str], int] = defaultdict(int)
        edge_amounts: dict[tuple[str, str], list[float]] = defaultdict(list)
        edge_failures: dict[tuple[str, str], int] = defaultdict(int)
        node_out_degree: dict[str, int] = defaultdict(int)
        node_in_degree: dict[str, int] = defaultdict(int)
        node_amounts: dict[str, list[float]] = defaultdict(list)
        node_failures: dict[str, int] = defaultdict(int)

        for tx in transactions:
            s, r = tx["sending_bic"], tx["receiving_bic"]
            pair = (s, r)
            edge_counts[pair] += 1
            edge_amounts[pair].append(tx["amount_usd"])
            edge_failures[pair] += tx["is_failure"]
            node_out_degree[s] += 1
            node_in_degree[r] += 1
            node_amounts[s].append(tx["amount_usd"])
            node_amounts[r].append(tx["amount_usd"])
            node_failures[s] += tx["is_failure"]
            node_failures[r] += tx["is_failure"]

        active_bics = set(node_out_degree.keys()) | set(node_in_degree.keys())

        # Node records
        nodes = []
        for bic in active_bics:
            info = BIC_REGISTRY.get(bic, {})
            out_deg = node_out_degree[bic]
            in_deg = node_in_degree[bic]
            total_deg = out_deg + in_deg
            amt_list = node_amounts[bic]
            avg_amt = float(np.mean(amt_list)) if amt_list else 0.0
            fail_ct = node_failures[bic]
            fail_rate = fail_ct / total_deg if total_deg > 0 else 0.0
            nodes.append({
                "bic": bic,
                "tier": info.get("tier", 3),
                "region": info.get("region", "UNKNOWN"),
                "out_degree": out_deg,
                "in_degree": in_deg,
                "total_degree": total_deg,
                "avg_amount_usd": avg_amt,
                "failure_rate": fail_rate,
            })

        # Edge records
        edges = []
        for (s, r), count in edge_counts.items():
            amt_list = edge_amounts[(s, r)]
            edges.append({
                "sender": s,
                "receiver": r,
                "transaction_count": count,
                "avg_amount_usd": float(np.mean(amt_list)),
                "failure_rate": edge_failures[(s, r)] / count,
            })

        # Adjacency dict
        adjacency: dict[str, list[str]] = defaultdict(list)
        for s, r in edge_counts:
            adjacency[s].append(r)

        # Degree distribution stats
        degrees = np.array([n["total_degree"] for n in nodes], dtype=float)
        sorted_degrees = np.sort(degrees)[::-1]
        total_edges = int(sorted_degrees.sum())
        top_10pct = max(1, len(sorted_degrees) // 10)
        top_edge_share = float(sorted_degrees[:top_10pct].sum() / total_edges) if total_edges > 0 else 0.0

        degree_distribution = {
            "min": int(degrees.min()) if len(degrees) > 0 else 0,
            "max": int(degrees.max()) if len(degrees) > 0 else 0,
            "mean": float(degrees.mean()) if len(degrees) > 0 else 0.0,
            "top_10pct_edge_share": top_edge_share,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "adjacency": dict(adjacency),
            "degree_distribution": degree_distribution,
        }

    def generate_to_dataframe(self, n_transactions: int = 100_000):
        """
        Generate dataset and return as pandas DataFrame.
        Convenience wrapper for generate_dataset(). Lazy-imports pandas.
        """
        import pandas as pd  # noqa: PLC0415 — lazy import, pandas is optional
        transactions = self.generate_dataset(n_transactions)
        return pd.DataFrame(transactions)

    def generate_to_csv(self, path: str, n_transactions: int = 100_000) -> None:
        """
        Generate dataset and write to CSV with corpus_tag header.
        First line comment: # SYNTHETIC_CORPUS — generated by
        lip.c1_failure_classifier.synthetic_data
        """
        transactions = self.generate_dataset(n_transactions)
        if not transactions:
            return
        fieldnames = list(transactions[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fh.write(
                "# SYNTHETIC_CORPUS — generated by "
                "lip.c1_failure_classifier.synthetic_data\n"
            )
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(transactions)

    def validate_dataset(self, transactions: list[dict]) -> dict:
        """
        Validate generated dataset against Architecture Spec invariants.

        Checks:
        - Failure rate within [3.0%, 4.0%]
        - Class distribution within 5% of targets (55/30/15)
        - No BLOCK codes present
        - All rejection codes exist in REJECTION_CODE_TAXONOMY
        - All BICs are from BIC_REGISTRY
        - No sender == receiver
        - All required fields present

        Returns dict with pass/fail for each check and summary stats.
        """
        n = len(transactions)
        results: dict = {}

        if n == 0:
            return {"all_pass": False, "error": "empty_dataset"}

        # Required fields check
        missing_fields: set[str] = set()
        for tx in transactions:
            missing_fields |= _REQUIRED_FIELDS - tx.keys()
        results["required_fields_check"] = {
            "pass": len(missing_fields) == 0,
            "missing": list(missing_fields),
        }

        # Self-loop check
        self_loops = [(tx["sending_bic"], tx["receiving_bic"])
                      for tx in transactions
                      if tx["sending_bic"] == tx["receiving_bic"]]
        results["no_self_loops_check"] = {
            "pass": len(self_loops) == 0,
            "self_loop_count": len(self_loops),
        }

        # BIC validity check
        invalid_bics = {
            bic for tx in transactions
            for bic in (tx["sending_bic"], tx["receiving_bic"])
            if bic not in BIC_REGISTRY
        }
        results["all_bics_valid_check"] = {
            "pass": len(invalid_bics) == 0,
            "invalid_bics": list(invalid_bics),
        }

        # Rejection code checks
        block_codes_found = {
            tx["rejection_code"] for tx in transactions
            if tx["rejection_code"] in _BLOCK_CODES
        }
        results["no_block_codes_check"] = {
            "pass": len(block_codes_found) == 0,
            "block_codes_found": list(block_codes_found),
        }

        invalid_codes = {
            tx["rejection_code"] for tx in transactions
            if tx["rejection_code"] != "NONE" and tx["rejection_code"] not in REJECTION_CODE_TAXONOMY
        }
        results["all_codes_valid_check"] = {
            "pass": len(invalid_codes) == 0,
            "invalid_codes": list(invalid_codes),
        }

        # Failure rate check
        failures = [tx for tx in transactions if tx["is_failure"] == 1]
        failure_rate = len(failures) / n
        results["failure_rate_check"] = {
            "pass": 0.03 <= failure_rate <= 0.04,
            "value": failure_rate,
            "expected_range": [0.03, 0.04],
        }

        # Class distribution check
        class_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0}
        for tx in failures:
            rc = tx.get("rejection_class", "NONE")
            if rc in class_counts:
                class_counts[rc] += 1
        n_fail = len(failures)
        class_pass = True
        class_stats = {}
        if n_fail > 0:
            for cls, target in CLASS_DISTRIBUTION.items():
                actual = class_counts[cls] / n_fail
                deviation = abs(actual - target)
                class_stats[cls] = {"actual": actual, "target": target, "deviation": deviation}
                if deviation > 0.05:
                    class_pass = False
        results["class_distribution_check"] = {"pass": class_pass, "stats": class_stats}

        # Amount range check
        bad_amounts = [tx for tx in transactions
                       if not (1_000.0 <= tx["amount_usd"] <= 50_000_000.0)]
        results["amount_range_check"] = {
            "pass": len(bad_amounts) == 0,
            "out_of_range_count": len(bad_amounts),
        }

        # Summary
        all_pass = all(v.get("pass", False) for v in results.values() if isinstance(v, dict))
        results["all_pass"] = all_pass
        results["summary"] = {
            "n_transactions": n,
            "n_failures": n_fail,
            "failure_rate": failure_rate,
        }
        return results

    def summary_statistics(self, transactions: list[dict]) -> dict:
        """
        Compute and return comprehensive summary stats:
        - Total transactions, failure count, failure rate
        - Class A/B/C counts and percentages
        - Top 10 rejection codes
        - Corridor volume distribution
        - Amount percentiles (p25, p50, p75, p95)
        - BIC degree distribution stats
        - Temporal distribution (hour histogram, day-of-week histogram)
        """
        n = len(transactions)
        if n == 0:
            return {}

        failures = [tx for tx in transactions if tx["is_failure"] == 1]
        n_fail = len(failures)
        failure_rate = n_fail / n

        # Class counts
        class_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0}
        for tx in failures:
            rc = tx.get("rejection_class", "NONE")
            if rc in class_counts:
                class_counts[rc] += 1

        # Top rejection codes
        code_counts: dict[str, int] = defaultdict(int)
        for tx in failures:
            code = tx.get("rejection_code", "NONE")
            if code != "NONE":
                code_counts[code] += 1
        top_codes = sorted(code_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Corridor distribution
        corridor_counts: dict[str, int] = defaultdict(int)
        for tx in transactions:
            corridor_counts[tx["currency_pair"]] += 1

        # Amount percentiles
        amounts = np.array([tx["amount_usd"] for tx in transactions], dtype=float)
        percentiles = {
            "p25": float(np.percentile(amounts, 25)),
            "p50": float(np.percentile(amounts, 50)),
            "p75": float(np.percentile(amounts, 75)),
            "p95": float(np.percentile(amounts, 95)),
            "mean": float(amounts.mean()),
        }

        # BIC degree distribution
        bic_counts: dict[str, int] = defaultdict(int)
        for tx in transactions:
            bic_counts[tx["sending_bic"]] += 1
            bic_counts[tx["receiving_bic"]] += 1
        degrees = np.array(list(bic_counts.values()), dtype=float)

        # Temporal distributions
        hour_hist = np.zeros(24, dtype=int)
        dow_hist = np.zeros(7, dtype=int)
        for tx in transactions:
            hour_hist[tx["hour_of_day"]] += 1
            dow_hist[tx["day_of_week"]] += 1

        return {
            "n_transactions": n,
            "n_failures": n_fail,
            "failure_rate": failure_rate,
            "class_counts": dict(class_counts),
            "class_percentages": {
                cls: (count / n_fail if n_fail > 0 else 0.0)
                for cls, count in class_counts.items()
            },
            "top_rejection_codes": top_codes,
            "corridor_distribution": dict(corridor_counts),
            "amount_percentiles": percentiles,
            "bic_degree_stats": {
                "min": int(degrees.min()) if len(degrees) > 0 else 0,
                "max": int(degrees.max()) if len(degrees) > 0 else 0,
                "mean": float(degrees.mean()) if len(degrees) > 0 else 0.0,
            },
            "hour_histogram": hour_hist.tolist(),
            "dow_histogram": dow_hist.tolist(),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _random_uuid(self) -> str:
        """Generate a UUID4-format string using numpy's seeded RNG for determinism."""
        raw = self._rng.integers(0, 256, size=16, dtype=np.uint8)
        raw[6] = (raw[6] & 0x0F) | 0x40  # version 4
        raw[8] = (raw[8] & 0x3F) | 0x80  # variant bits
        hex_str = raw.tobytes().hex()
        return f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"

    def _generate_base_record(self) -> dict:
        """Generate a single transaction record without failure label."""
        sending_bic, receiving_bic = self._sample_bic_pair()
        currency_pair = self._sample_corridor(sending_bic, receiving_bic)
        amount_usd = self._sample_amount(currency_pair)
        hour_of_day, day_of_week = self._sample_temporal()

        corridor_info = CORRIDOR_DEFINITIONS.get(currency_pair, {})
        region_type = corridor_info.get("region_type", "G7")
        _avg_lag = corridor_info.get("avg_settlement_hours", 4)

        # Settlement lag: 0-5 days based on corridor type
        if region_type == "G7":
            lag_choices, lag_probs = [0, 1, 2], [0.60, 0.30, 0.10]
        elif region_type == "EM":
            lag_choices, lag_probs = [1, 2, 3, 4], [0.35, 0.35, 0.20, 0.10]
        else:  # HIGH_FRICTION
            lag_choices, lag_probs = [2, 3, 4, 5], [0.30, 0.35, 0.25, 0.10]
        settlement_lag_days = int(self._rng.choice(lag_choices, p=lag_probs))

        # Prior rejections: most are 0, Poisson-ish tail
        prior_rejection_choices = [0, 1, 2, 3, 4, 5]
        prior_rejection_probs = [0.78, 0.12, 0.05, 0.03, 0.01, 0.01]
        prior_rejections_30d = int(self._rng.choice(prior_rejection_choices, p=prior_rejection_probs))

        # Correspondent depth
        depth_choices = [1, 2, 3, 4, 5]
        depth_probs = [0.40, 0.35, 0.15, 0.07, 0.03]
        correspondent_depth = int(self._rng.choice(depth_choices, p=depth_probs))

        # Data quality score: beta distribution skewed toward 1.0
        raw_dq = float(self._rng.beta(8.0, 1.5))
        data_quality_score = float(np.clip(raw_dq, 0.0, 1.0))

        # Message priority
        priority_choices = ["NORM", "HIGH", "URGP"]
        priority_probs = [0.85, 0.12, 0.03]
        message_priority = str(self._rng.choice(priority_choices, p=priority_probs))

        return {
            "uetr": self._random_uuid(),
            "sending_bic": sending_bic,
            "receiving_bic": receiving_bic,
            "currency_pair": currency_pair,
            "amount_usd": amount_usd,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "settlement_lag_days": settlement_lag_days,
            "prior_rejections_30d": prior_rejections_30d,
            "correspondent_depth": correspondent_depth,
            "data_quality_score": data_quality_score,
            "message_priority": message_priority,
            "corpus_tag": "SYNTHETIC_CORPUS",
            "generation_timestamp": self._gen_ts,
            "generation_seed": self._seed,
            # Failure fields — populated later
            "rejection_code": "NONE",
            "rejection_class": "NONE",
            "payment_status": "ACCC",
            "is_failure": 0,
        }

    def _sample_bic_pair(self) -> tuple[str, str]:
        """
        Sample sender/receiver BIC pair using power-law degree distribution.
        Tier 1 banks appear as correspondents more frequently.
        Sender != Receiver is enforced.
        """
        n_bics = len(_BIC_LIST)
        sender_idx = int(self._rng.choice(n_bics, p=_BIC_WEIGHTS))

        # Remove sender from receiver distribution
        recv_weights = _BIC_WEIGHTS_RAW.copy()
        recv_weights[sender_idx] = 0.0
        recv_weights = recv_weights / recv_weights.sum()
        receiver_idx = int(self._rng.choice(n_bics, p=recv_weights))

        return _BIC_LIST[sender_idx], _BIC_LIST[receiver_idx]

    def _sample_corridor(self, sending_bic: str, receiving_bic: str) -> str:
        """
        Derive currency pair from BIC country codes.
        Cross-border pairs weighted by annual volume.
        """
        send_ccy = _COUNTRY_TO_CURRENCY.get(BIC_REGISTRY[sending_bic]["country"], "USD")
        recv_ccy = _COUNTRY_TO_CURRENCY.get(BIC_REGISTRY[receiving_bic]["country"], "USD")

        if send_ccy != recv_ccy:
            # Try to find a corridor that involves both currencies
            for corridor in (f"{send_ccy}/{recv_ccy}", f"{recv_ccy}/{send_ccy}"):
                if corridor in CORRIDOR_DEFINITIONS:
                    return corridor

            # Try any corridor that includes either currency
            candidates = []
            candidate_vols = []
            for corridor, info in CORRIDOR_DEFINITIONS.items():
                c1, c2 = corridor.split("/")
                if send_ccy in (c1, c2) or recv_ccy in (c1, c2):
                    candidates.append(corridor)
                    candidate_vols.append(info["annual_volume_billions"])
            if candidates:
                vols = np.array(candidate_vols, dtype=float)
                probs = vols / vols.sum()
                idx = int(self._rng.choice(len(candidates), p=probs))
                return candidates[idx]

        # Fallback: volume-weighted random corridor
        return str(_CORRIDOR_KEYS[int(self._rng.choice(len(_CORRIDOR_KEYS), p=_CORRIDOR_PROBS))])

    def _sample_amount(self, corridor: str) -> float:
        """
        Log-normal amount distribution anchored to BIS CPMI stats.
        G7 corridors: median $250K, mean $1.2M (heavy right tail)
        EM corridors: median $50K, mean $300K
        High-friction: median $80K, mean $500K
        """
        region_type = CORRIDOR_DEFINITIONS.get(corridor, {}).get("region_type", "G7")
        log_mu, log_sigma = _AMOUNT_PARAMS[region_type]
        amount = float(np.exp(self._rng.normal(log_mu, log_sigma)))
        return float(np.clip(amount, 1_000.0, 50_000_000.0))

    def _sample_temporal(self) -> tuple[int, int]:
        """
        Hour and day-of-week with realistic patterns:
        - Peak hours: 8-16 UTC (European/US business hours)
        - Monday-Friday 85%, weekend 15%
        """
        # Weekday vs weekend
        is_weekend = self._rng.random() < 0.15
        if is_weekend:
            day_of_week = int(self._rng.choice([5, 6]))
        else:
            day_of_week = int(self._rng.integers(0, 5))

        # Hour of day: Gaussian centred at noon UTC, clipped to 0-23
        if is_weekend:
            # Flat distribution on weekends
            hour_of_day = int(self._rng.integers(0, 24))
        else:
            # Bell curve peaking around 10:00 UTC (EU morning / US overlap)
            raw_hour = self._rng.normal(10.0, 4.0)
            hour_of_day = int(np.clip(round(raw_hour), 0, 23))

        return hour_of_day, day_of_week

    def _compute_risk_score(self, record: dict) -> float:
        """
        Compute unnormalized risk score for conditioning failure probability.
        Returns a positive float; 1.0 represents average risk.
        """
        score = 1.0

        # Per-corridor failure rate multiplier (individual corridor risk, not just 3-bucket)
        corridor_info = CORRIDOR_DEFINITIONS.get(record["currency_pair"], {})
        score *= corridor_info.get("failure_rate_multiplier", 1.0)

        # Time of day
        hour = record["hour_of_day"]
        if 8 <= hour <= 16:
            score *= 0.75
        else:
            score *= 1.35

        # Day of week
        if record["day_of_week"] >= 5:  # Weekend
            score *= 1.55

        # Amount
        amount = record["amount_usd"]
        if amount > 1_000_000:
            score *= 1.45
        elif amount < 10_000:
            score *= 1.20

        # Tier of counterparties (max tier = weakest link), plus per-BIC multiplier
        send_bic_info = BIC_REGISTRY[record["sending_bic"]]
        recv_bic_info = BIC_REGISTRY[record["receiving_bic"]]
        max_tier = max(send_bic_info["tier"], recv_bic_info["tier"])
        tier_multipliers = {1: 0.50, 2: 1.00, 3: 1.85}
        send_fm = send_bic_info.get("failure_multiplier", 1.0)
        recv_fm = recv_bic_info.get("failure_multiplier", 1.0)
        score *= tier_multipliers[max_tier] * max(send_fm, recv_fm)

        # Prior rejections history
        prior = record["prior_rejections_30d"]
        if prior >= 3:
            score *= 2.60
        elif prior > 0:
            score *= 1.55

        return max(score, 1e-4)

    def _assign_failure(self, record: dict) -> dict:
        """
        Assign rejection class and rejection code to a known-failure record.
        Samples rejection class (A/B/C) per CLASS_DISTRIBUTION, then
        samples a code respecting co-occurrence patterns.
        """
        # Sample rejection class
        cls_keys = list(CLASS_DISTRIBUTION.keys())
        cls_probs = np.array([CLASS_DISTRIBUTION[k] for k in cls_keys])
        rejection_class = str(cls_keys[int(self._rng.choice(len(cls_keys), p=cls_probs))])

        rejection_code = self._sample_rejection_code(rejection_class, record)

        record["rejection_code"] = rejection_code
        record["rejection_class"] = rejection_class
        record["payment_status"] = "RJCT"
        record["is_failure"] = 1
        return record

    def _sample_rejection_code(self, rejection_class: str, record: dict) -> str:
        """
        Sample a specific rejection code within the assigned class,
        conditioned on transaction features.

        Uses rejection codes from REJECTION_CODE_TAXONOMY only.
        BLOCK codes (DISP, FRAU, FRAD, DUPL) are never sampled.
        """
        codes = _CODES_BY_CLASS.get(rejection_class, [])
        if not codes:
            return "NONE"

        weights = np.ones(len(codes), dtype=float)
        corridor_type = CORRIDOR_DEFINITIONS.get(
            record.get("currency_pair", "EUR/USD"), {}
        ).get("region_type", "G7")
        amount = record.get("amount_usd", 0.0)

        for i, code in enumerate(codes):
            if rejection_class == "A":
                # AM04 (InsufficientFunds) clusters with large amounts
                if code == "AM04" and amount > 500_000:
                    weights[i] *= 4.0
                # AC01 / AC04 (account errors) are the most common Class A codes
                if code in ("AC01", "AC04"):
                    weights[i] *= 2.5
                # ED05 (SettlementFailed) clusters with EM/HIGH_FRICTION
                if code == "ED05" and corridor_type in ("EM", "HIGH_FRICTION"):
                    weights[i] *= 2.0
            elif rejection_class == "B":
                # CURR (UnrecognisedCurrency) clusters with EM/HIGH_FRICTION (cross-border)
                if code == "CURR" and corridor_type in ("EM", "HIGH_FRICTION"):
                    weights[i] *= 5.0
                # AG01 (TransactionForbidden) clusters with EM corridors
                if code == "AG01" and corridor_type == "EM":
                    weights[i] *= 3.5
                # TECH and TIMO are general codes
                if code in ("TECH", "TIMO"):
                    weights[i] *= 1.5
            elif rejection_class == "C":
                # INVB (InvalidBIC) and AGNT (IncorrectAgent) are most common
                if code in ("INVB", "AGNT"):
                    weights[i] *= 2.0

        probs = weights / weights.sum()
        chosen_code = str(codes[int(self._rng.choice(len(codes), p=probs))])
        return chosen_code


# ── SMOTE Integration ─────────────────────────────────────────────────────────

def apply_smote(
    transactions: list[dict],
    target_minority_ratio: float = 0.15,
    seed: int = 42,
) -> list[dict]:
    """
    Apply SMOTE oversampling to balance the failure class.

    Default 3.5% failure rate → oversample to 15% for training.
    Uses numeric features only for SMOTE interpolation.
    Categorical features (BIC, corridor, rejection_code) are assigned
    from the nearest real failure neighbour.

    Returns augmented transaction list with new synthetic failures
    tagged corpus_tag="SYNTHETIC_CORPUS_SMOTE".

    Falls back to simple random oversampling if imblearn is not installed.
    """
    failures = [tx for tx in transactions if tx["is_failure"] == 1]
    successes = [tx for tx in transactions if tx["is_failure"] == 0]
    n_success = len(successes)
    n_fail = len(failures)

    if n_fail == 0 or n_success == 0:
        return list(transactions)

    # Compute how many synthetic failures we need
    n_target_fail = int(round(n_success * target_minority_ratio / (1.0 - target_minority_ratio)))
    n_new = n_target_fail - n_fail
    if n_new <= 0:
        return list(transactions)

    numeric_cols = [
        "amount_usd", "hour_of_day", "day_of_week", "settlement_lag_days",
        "prior_rejections_30d", "correspondent_depth", "data_quality_score",
    ]

    def _to_feature_matrix(txs: list[dict]) -> np.ndarray:
        return np.array([[tx[c] for c in numeric_cols] for tx in txs], dtype=float)

    try:
        from imblearn.over_sampling import SMOTE  # noqa: PLC0415 — lazy import

        X_fail = _to_feature_matrix(failures)
        X_all = _to_feature_matrix(transactions)
        y_all = np.array([tx["is_failure"] for tx in transactions], dtype=int)

        # SMOTE needs at least k_neighbors+1 minority samples
        k_neighbors = min(5, n_fail - 1)
        if k_neighbors < 1:
            raise ValueError("Not enough failure samples for SMOTE")

        sm = SMOTE(
            sampling_strategy=target_minority_ratio / (1.0 - target_minority_ratio),
            k_neighbors=k_neighbors,
            random_state=seed,
        )
        X_res, y_res = sm.fit_resample(X_all, y_all)

        # Extract only the new synthetic failure records
        n_orig = len(transactions)
        new_numeric_rows = X_res[n_orig:]
        new_labels = y_res[n_orig:]

        new_records: list[dict] = []
        rng = np.random.default_rng(seed)
        for row in new_numeric_rows[new_labels == 1]:
            # Find nearest real failure neighbour for categorical fields
            dists = np.sum((X_fail - row) ** 2, axis=1)
            nearest_idx = int(np.argmin(dists))
            src = failures[nearest_idx]

            new_tx = src.copy()
            for j, col in enumerate(numeric_cols):
                new_tx[col] = float(row[j])
            # Clip after SMOTE interpolation
            new_tx["hour_of_day"] = int(np.clip(round(new_tx["hour_of_day"]), 0, 23))
            new_tx["day_of_week"] = int(np.clip(round(new_tx["day_of_week"]), 0, 6))
            new_tx["settlement_lag_days"] = int(np.clip(round(new_tx["settlement_lag_days"]), 0, 5))
            new_tx["prior_rejections_30d"] = int(max(0, round(new_tx["prior_rejections_30d"])))
            new_tx["correspondent_depth"] = int(np.clip(round(new_tx["correspondent_depth"]), 1, 5))
            new_tx["data_quality_score"] = float(np.clip(new_tx["data_quality_score"], 0.0, 1.0))
            new_tx["amount_usd"] = float(np.clip(new_tx["amount_usd"], 1_000.0, 50_000_000.0))
            new_tx["uetr"] = str(uuid.uuid4())
            new_tx["corpus_tag"] = "SYNTHETIC_CORPUS_SMOTE"
            new_records.append(new_tx)

        return list(transactions) + new_records

    except (ImportError, Exception):
        # Graceful fallback: random oversampling with numeric perturbation
        rng = np.random.default_rng(seed)
        new_records = []
        X_fail = _to_feature_matrix(failures)
        for _ in range(n_new):
            src_idx = int(rng.integers(0, n_fail))
            src = failures[src_idx]
            new_tx = src.copy()
            # Add small noise to numeric fields (5% std)
            for j, col in enumerate(numeric_cols):
                noise = float(rng.normal(0, abs(X_fail[src_idx, j]) * 0.05 + 1e-6))
                new_tx[col] = float(X_fail[src_idx, j]) + noise
            # Clip
            new_tx["hour_of_day"] = int(np.clip(round(new_tx["hour_of_day"]), 0, 23))
            new_tx["day_of_week"] = int(np.clip(round(new_tx["day_of_week"]), 0, 6))
            new_tx["settlement_lag_days"] = int(np.clip(round(new_tx["settlement_lag_days"]), 0, 5))
            new_tx["prior_rejections_30d"] = int(max(0, round(new_tx["prior_rejections_30d"])))
            new_tx["correspondent_depth"] = int(np.clip(round(new_tx["correspondent_depth"]), 1, 5))
            new_tx["data_quality_score"] = float(np.clip(new_tx["data_quality_score"], 0.0, 1.0))
            new_tx["amount_usd"] = float(np.clip(new_tx["amount_usd"], 1_000.0, 50_000_000.0))
            new_tx["uetr"] = str(uuid.uuid4())
            new_tx["corpus_tag"] = "SYNTHETIC_CORPUS_SMOTE"
            new_records.append(new_tx)

        return list(transactions) + new_records


# ── Dataset Split Utility ─────────────────────────────────────────────────────

def train_val_test_split(
    transactions: list[dict],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    stratify_by: str = "is_failure",
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Stratified split preserving failure rate across splits.
    Returns (train, val, test) lists.
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-9:
        raise ValueError("train_ratio + val_ratio + test_ratio must equal 1.0")

    rng = np.random.default_rng(seed)

    # Separate by stratum
    strata: dict[int, list[int]] = defaultdict(list)
    for i, tx in enumerate(transactions):
        strata[tx[stratify_by]].append(i)

    train_idx: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []

    for stratum_indices in strata.values():
        arr = np.array(stratum_indices, dtype=int)
        arr = rng.permutation(arr)
        n = len(arr)
        n_train = max(1, int(n * train_ratio))
        n_val = max(0, int(n * val_ratio))
        train_idx.extend(arr[:n_train].tolist())
        val_idx.extend(arr[n_train: n_train + n_val].tolist())
        test_idx.extend(arr[n_train + n_val:].tolist())

    # Shuffle each split
    train_idx = rng.permutation(train_idx).tolist()
    val_idx = rng.permutation(val_idx).tolist()
    test_idx = rng.permutation(test_idx).tolist()

    train = [transactions[i] for i in train_idx]
    val = [transactions[i] for i in val_idx]
    test = [transactions[i] for i in test_idx]

    return train, val, test


# ---------------------------------------------------------------------------
# Stats enrichment helper (leave-one-out failure rates to prevent leakage)
# ---------------------------------------------------------------------------

def _compute_bic_corridor_stats(
    records: list[dict],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """Aggregate per-BIC sender/receiver stats and per-corridor stats.

    Returns three baseline dicts keyed by BIC or corridor string.  Each dict
    stores *global* aggregates plus internal keys ``_total_tx`` and
    ``_total_fail`` used by the caller to apply leave-one-out (LOO) failure
    rates per record (excluding each record's own label from the denominator).

    LOO formula for record i (BIC/corridor key k):
        loo_rate = (base[k]["_total_fail"] - records[i]["is_failure"])
                   / (base[k]["_total_tx"] - 1)
    """
    LARGE_TX = 1_000_000.0

    # ── Accumulate ─────────────────────────────────────────────────────────
    s_tx: dict[str, list] = defaultdict(list)       # sender_bic -> list[amount]
    s_fail: dict[str, int] = defaultdict(int)
    s_receivers: dict[str, set] = defaultdict(set)
    s_corridors: dict[str, set] = defaultdict(set)

    r_tx: dict[str, list] = defaultdict(list)       # receiver_bic -> list[amount]
    r_fail: dict[str, int] = defaultdict(int)
    r_senders: dict[str, set] = defaultdict(set)
    r_corridors: dict[str, set] = defaultdict(set)

    c_tx: dict[str, list] = defaultdict(list)       # corridor -> list[amount]
    c_fail: dict[str, int] = defaultdict(int)
    c_vol: dict[str, float] = defaultdict(float)

    # Track how often each BIC appears in either role (for in/out degree)
    node_as_sender: dict[str, int] = defaultdict(int)
    node_as_receiver: dict[str, int] = defaultdict(int)

    for rec in records:
        s = rec["sending_bic"]
        r = rec["receiving_bic"]
        cp = rec["currency_pair"]
        amt = float(rec["amount_usd"])
        fail = int(rec["is_failure"])

        s_tx[s].append(amt)
        s_fail[s] += fail
        s_receivers[s].add(r)
        s_corridors[s].add(cp)

        r_tx[r].append(amt)
        r_fail[r] += fail
        r_senders[r].add(s)
        r_corridors[r].add(cp)

        c_tx[cp].append(amt)
        c_fail[cp] += fail
        c_vol[cp] += amt

        node_as_sender[s] += 1
        node_as_receiver[r] += 1

    _SYNTHETIC_DAYS = 30.0  # treat dataset as 30-day window

    def _bic_age(bic: str) -> float:
        """Synthetic institution age: older tiers are more established."""
        tier = BIC_REGISTRY.get(bic, {}).get("tier", 3)
        return {1: 5000.0, 2: 2000.0, 3: 500.0}.get(tier, 500.0)

    # ── Sender stats ────────────────────────────────────────────────────────
    sender_base: dict[str, dict] = {}
    for bic, amts_list in s_tx.items():
        amts = np.array(amts_list, dtype=float)
        tx_ct = len(amts_list)
        fail_ct = s_fail[bic]
        global_fr = fail_ct / tx_ct if tx_ct > 0 else 0.0
        avg_amt = float(amts.mean())
        std_amt = float(amts.std()) + 1e-9
        pct_large = float((amts >= LARGE_TX).mean())
        n_corridors = max(len(s_corridors[bic]), 1)
        sender_base[bic] = {
            "out_degree": len(s_receivers[bic]),
            "in_degree": node_as_receiver.get(bic, 0),
            "tx_count": tx_ct,
            "avg_amount": avg_amt,
            "std_amount": std_amt,
            "pct_large_tx": pct_large,
            "volume_24h": float(amts.sum()) / _SYNTHETIC_DAYS,
            "age_days": _bic_age(bic),
            "currency_concentration": 1.0 / n_corridors,
            "unique_receivers": len(s_receivers[bic]),
            # failure rates populated via LOO in caller
            "failure_rate_30d": global_fr,
            "failure_rate_7d": global_fr * 0.90,
            "failure_rate_1d": global_fr * 0.80,
            "consecutive_failures": min(fail_ct, 3),
            "_total_tx": tx_ct,
            "_total_fail": fail_ct,
        }

    # ── Receiver stats ──────────────────────────────────────────────────────
    receiver_base: dict[str, dict] = {}
    for bic, amts_list in r_tx.items():
        amts = np.array(amts_list, dtype=float)
        tx_ct = len(amts_list)
        fail_ct = r_fail[bic]
        global_fr = fail_ct / tx_ct if tx_ct > 0 else 0.0
        avg_amt = float(amts.mean())
        std_amt = float(amts.std()) + 1e-9
        pct_large = float((amts >= LARGE_TX).mean())
        n_corridors = max(len(r_corridors[bic]), 1)
        receiver_base[bic] = {
            "out_degree": node_as_sender.get(bic, 0),
            "in_degree": len(r_senders[bic]),
            "tx_count": tx_ct,
            "avg_amount": avg_amt,
            "std_amount": std_amt,
            "pct_large_tx": pct_large,
            "volume_24h": float(amts.sum()) / _SYNTHETIC_DAYS,
            "age_days": _bic_age(bic),
            "currency_concentration": 1.0 / n_corridors,
            "unique_senders": len(r_senders[bic]),
            "failure_rate_30d": global_fr,
            "failure_rate_7d": global_fr * 0.90,
            "failure_rate_1d": global_fr * 0.80,
            "consecutive_failures": min(fail_ct, 3),
            "_total_tx": tx_ct,
            "_total_fail": fail_ct,
        }

    # ── Corridor stats ──────────────────────────────────────────────────────
    corridor_base: dict[str, dict] = {}
    for cp, amts_list in c_tx.items():
        amts = np.array(amts_list, dtype=float)
        tx_ct = len(amts_list)
        fail_ct = c_fail[cp]
        global_fr = fail_ct / tx_ct if tx_ct > 0 else 0.0
        vol_30d = float(c_vol[cp])
        tx_per_day = tx_ct / _SYNTHETIC_DAYS
        corridor_base[cp] = {
            "tx_count": tx_ct,
            "avg_amount": float(amts.mean()),
            "std_amount": float(amts.std()) + 1e-9,
            "max_amount": float(amts.max()),
            "min_amount": float(amts.min()),
            "p50_amount": float(np.percentile(amts, 50)),
            "p95_amount": float(np.percentile(amts, 95)),
            "volume_30d": vol_30d,
            "volume_7d": vol_30d / 4.0,
            "tx_per_day": tx_per_day,
            "velocity_24h": tx_per_day,
            "velocity_1h": tx_per_day / 24.0,
            "age_days": 5000.0,
            "unique_currencies": 2,
            "failure_rate_30d": global_fr,
            "failure_rate_7d": global_fr * 0.90,
            "consecutive_failures": min(fail_ct, 3),
            "_total_tx": tx_ct,
            "_total_fail": fail_ct,
        }

    return sender_base, receiver_base, corridor_base


# ---------------------------------------------------------------------------
# Module-level convenience function (used by tests and scripts)
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n_samples: int = 1000, seed: int = 42) -> list:
    """Generate a list of C1-format payment records ready for TrainingPipeline.run().

    Thin wrapper around :class:`SWIFTPaymentDataGenerator` that adds the
    ``label`` and ``timestamp`` fields required by
    :meth:`TrainingPipeline.stage1_data_validation`.

    Parameters
    ----------
    n_samples:
        Number of synthetic payment records to generate.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    list of dict
        Each record contains all :class:`SWIFTPaymentDataGenerator` fields plus:
        * ``label``     — int, same as ``is_failure``
        * ``timestamp`` — float Unix timestamp reconstructed from ``hour_of_day``
          and ``day_of_week`` relative to a fixed reference epoch
    """

    generator = SyntheticPaymentGenerator(seed=seed)
    raw = generator.generate_dataset(n_transactions=n_samples)

    # ── Stats enrichment pass (Improvements 1-3) ──────────────────────────
    # Populate sender_stats, receiver_stats, corridor_stats so that
    # TabularFeatureEngineer.extract() can use all 55 previously-zero features.
    # Leave-one-out failure rates: each record excludes its own label from the
    # denominator to prevent label leakage into the training features.
    sender_base, receiver_base, corridor_base = _compute_bic_corridor_stats(raw)

    for rec in raw:
        s = rec["sending_bic"]
        r = rec["receiving_bic"]
        cp = rec["currency_pair"]
        fail = int(rec["is_failure"])

        # LOO failure rate helper: (total_fail - this_fail) / (total_tx - 1)
        def _loo(base: dict, key: str, own_fail: int) -> float:
            b = base.get(key, {})
            total_tx = b.get("_total_tx", 0)
            if total_tx <= 1:
                return 0.0
            return (b.get("_total_fail", 0) - own_fail) / (total_tx - 1)

        s_loo = _loo(sender_base, s, fail)
        r_loo = _loo(receiver_base, r, fail)
        c_loo = _loo(corridor_base, cp, fail)

        # Build sender_stats (copy global baseline, override with LOO rates)
        s_stats = {k: v for k, v in sender_base.get(s, {}).items()
                   if not k.startswith("_")}
        s_stats["failure_rate_30d"] = s_loo
        s_stats["failure_rate_7d"] = s_loo * 0.90
        s_stats["failure_rate_1d"] = s_loo * 0.80

        # Build receiver_stats
        r_stats = {k: v for k, v in receiver_base.get(r, {}).items()
                   if not k.startswith("_")}
        r_stats["failure_rate_30d"] = r_loo
        r_stats["failure_rate_7d"] = r_loo * 0.90
        r_stats["failure_rate_1d"] = r_loo * 0.80

        # Build corridor_stats
        c_stats = {k: v for k, v in corridor_base.get(cp, {}).items()
                   if not k.startswith("_")}
        c_stats["failure_rate_30d"] = c_loo
        c_stats["failure_rate_7d"] = c_loo * 0.90

        rec["sender_stats"] = s_stats
        rec["receiver_stats"] = r_stats
        rec["corridor_stats"] = c_stats

    # Reference epoch: Monday 00:00 UTC — synthetic timestamps are offsets from it.
    _EPOCH_MONDAY = 1_700_000_000.0  # 2023-11-14 22:13:20 UTC, a Tuesday — close enough

    records = []
    for i, rec in enumerate(raw):
        # Reconstruct a plausible Unix timestamp from temporal fields
        ts = (
            _EPOCH_MONDAY
            + rec.get("day_of_week", 0) * 86400
            + rec.get("hour_of_day", 0) * 3600
            + i  # unique second offset so no two records share the same timestamp
        )
        rec["timestamp"] = ts
        rec["label"] = int(rec["is_failure"])
        records.append(rec)

    return records
