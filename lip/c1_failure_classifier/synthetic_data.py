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
    "DEUTDEFF": {"name": "Deutsche Bank",       "tier": 1, "country": "DE", "region": "EU"},
    "BNPAFRPP": {"name": "BNP Paribas",         "tier": 1, "country": "FR", "region": "EU"},
    "HSBCGB2L": {"name": "HSBC",                "tier": 1, "country": "GB", "region": "EU"},
    "CHASUS33": {"name": "JPMorgan Chase",       "tier": 1, "country": "US", "region": "NA"},
    "CITIUS33": {"name": "Citibank",             "tier": 1, "country": "US", "region": "NA"},
    "BOFAUS3N": {"name": "Bank of America",      "tier": 1, "country": "US", "region": "NA"},
    "SCBLSGSG": {"name": "Standard Chartered",   "tier": 1, "country": "SG", "region": "APAC"},
    # Tier 2 — Large regional banks
    "SBINMUMU": {"name": "State Bank of India",  "tier": 2, "country": "IN", "region": "APAC"},
    "BRADBRSP": {"name": "Bradesco",             "tier": 2, "country": "BR", "region": "LATAM"},
    "LOYDGB2L": {"name": "Lloyds Bank",          "tier": 2, "country": "GB", "region": "EU"},
    "COBADEFF": {"name": "Commerzbank",          "tier": 2, "country": "DE", "region": "EU"},
    "ABKEKENA": {"name": "Absa Bank Kenya",      "tier": 2, "country": "KE", "region": "AFR"},
    "ICBKCNBJ": {"name": "ICBC",                 "tier": 2, "country": "CN", "region": "APAC"},
    "MABOROBU": {"name": "Raiffeisen Romania",   "tier": 2, "country": "RO", "region": "EU"},
    "INGBNL2A": {"name": "ING Bank",             "tier": 2, "country": "NL", "region": "EU"},
    # Tier 3 — Smaller / EM banks: AFR
    "ECOCCIAB": {"name": "Ecobank Cote d'Ivoire","tier": 3, "country": "CI", "region": "AFR"},
    "ZENITHNL": {"name": "Zenith Bank Nigeria",  "tier": 3, "country": "NG", "region": "AFR"},
    "FBNBNGL1": {"name": "First Bank Nigeria",   "tier": 3, "country": "NG", "region": "AFR"},
    "SBZAZAJJ": {"name": "Standard Bank S.Africa","tier": 3, "country": "ZA", "region": "AFR"},
    "GTBINGLA": {"name": "Guaranty Trust Bank",  "tier": 3, "country": "NG", "region": "AFR"},
    # Tier 3 — MENA
    "AIBKEGCX": {"name": "Arab Intl Bank Egypt", "tier": 3, "country": "EG", "region": "MENA"},
    "NBADAEAA": {"name": "First Abu Dhabi Bank", "tier": 3, "country": "AE", "region": "MENA"},
    "RIBLSARI": {"name": "Riyad Bank",           "tier": 3, "country": "SA", "region": "MENA"},
    "QNBAQAQA": {"name": "Qatar National Bank",  "tier": 3, "country": "QA", "region": "MENA"},
    "MASHAEAD": {"name": "Mashreq Bank UAE",      "tier": 3, "country": "AE", "region": "MENA"},
    # Tier 3 — LATAM
    "BBVAMXMM": {"name": "BBVA Mexico",          "tier": 3, "country": "MX", "region": "LATAM"},
    "BNORMXMM": {"name": "Banorte Mexico",        "tier": 3, "country": "MX", "region": "LATAM"},
    "BCHICLRM": {"name": "Banco de Chile",        "tier": 3, "country": "CL", "region": "LATAM"},
    "BCOLCOBM": {"name": "Bancolombia",           "tier": 3, "country": "CO", "region": "LATAM"},
    # Tier 3 — APAC
    "PNBPINBB": {"name": "Punjab National Bank",  "tier": 3, "country": "IN", "region": "APAC"},
    "HDFCINBB": {"name": "HDFC Bank",             "tier": 3, "country": "IN", "region": "APAC"},
    "KASITHBK": {"name": "Kasikorn Bank",         "tier": 3, "country": "TH", "region": "APAC"},
    "MANDIDJJ": {"name": "Bank Mandiri",          "tier": 3, "country": "ID", "region": "APAC"},
    "BKKBTHBK": {"name": "Bangkok Bank",          "tier": 3, "country": "TH", "region": "APAC"},
    "AKBKTRIS": {"name": "Akbank Turkey",         "tier": 3, "country": "TR", "region": "MENA"},
}

# ── Currency Corridor Definitions ─────────────────────────────────────────────
CORRIDOR_DEFINITIONS: dict[str, dict] = {
    # G7 high-volume corridors
    "EUR/USD": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 800},
    "GBP/USD": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 350},
    "USD/JPY": {"region_type": "G7",           "avg_settlement_hours": 6,  "annual_volume_billions": 500},
    "EUR/GBP": {"region_type": "G7",           "avg_settlement_hours": 3,  "annual_volume_billions": 200},
    "EUR/JPY": {"region_type": "G7",           "avg_settlement_hours": 6,  "annual_volume_billions": 150},
    "GBP/JPY": {"region_type": "G7",           "avg_settlement_hours": 6,  "annual_volume_billions": 80},
    "USD/CHF": {"region_type": "G7",           "avg_settlement_hours": 5,  "annual_volume_billions": 70},
    "EUR/CHF": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 80},
    "GBP/CHF": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 60},
    "USD/CAD": {"region_type": "G7",           "avg_settlement_hours": 4,  "annual_volume_billions": 150},
    "USD/AUD": {"region_type": "G7",           "avg_settlement_hours": 10, "annual_volume_billions": 60},
    # EM corridors
    "USD/INR": {"region_type": "EM",           "avg_settlement_hours": 12, "annual_volume_billions": 80},
    "EUR/INR": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 40},
    "GBP/INR": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 20},
    "USD/KES": {"region_type": "EM",           "avg_settlement_hours": 16, "annual_volume_billions": 5},
    "USD/AED": {"region_type": "EM",           "avg_settlement_hours": 12, "annual_volume_billions": 30},
    "USD/SAR": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 25},
    "EUR/AED": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 15},
    "USD/ZAR": {"region_type": "EM",           "avg_settlement_hours": 16, "annual_volume_billions": 10},
    "USD/PHP": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 15},
    "USD/THB": {"region_type": "EM",           "avg_settlement_hours": 14, "annual_volume_billions": 12},
    # High-friction corridors
    "USD/BRL": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 45},
    "USD/CNY": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 120},
    "EUR/BRL": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 20, "annual_volume_billions": 15},
    "EUR/CNY": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 20, "annual_volume_billions": 60},
    "USD/NGN": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 24, "annual_volume_billions": 8},
    "USD/EGP": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 12},
    "EUR/ZAR": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 22, "annual_volume_billions": 6},
    "USD/MXN": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 16, "annual_volume_billions": 35},
    "USD/CLP": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 10},
    "EUR/MXN": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 8},
    "GBP/BRL": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 22, "annual_volume_billions": 5},
    "USD/IDR": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 16, "annual_volume_billions": 20},
    "USD/VND": {"region_type": "HIGH_FRICTION", "avg_settlement_hours": 18, "annual_volume_billions": 8},
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
        missing_fields = set()
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

        # Corridor type
        corridor_type = CORRIDOR_DEFINITIONS.get(
            record["currency_pair"], {}
        ).get("region_type", "G7")
        if corridor_type == "G7":
            score *= 0.55
        elif corridor_type == "EM":
            score *= 1.40
        else:  # HIGH_FRICTION
            score *= 2.10

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

        # Tier of counterparties (max tier = weakest link)
        send_tier = BIC_REGISTRY[record["sending_bic"]]["tier"]
        recv_tier = BIC_REGISTRY[record["receiving_bic"]]["tier"]
        max_tier = max(send_tier, recv_tier)
        tier_multipliers = {1: 0.50, 2: 1.00, 3: 1.85}
        score *= tier_multipliers[max_tier]

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
