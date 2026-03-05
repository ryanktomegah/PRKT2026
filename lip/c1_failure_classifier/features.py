"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

features.py — Feature engineering for C1 Failure Classifier
C1 Spec Section 4: Node features, edge features, tabular features
"""

from __future__ import annotations

import datetime
import logging
import math
from typing import Dict, List, Optional

import numpy as np

from .graph_builder import BICGraphBuilder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension constants (consumed by model modules)
# ---------------------------------------------------------------------------

NODE_FEATURE_DIM: int = 8
"""Dimensionality of the per-BIC node feature vector (C1 Spec §4.1)."""

EDGE_FEATURE_DIM: int = 6
"""Dimensionality of the per-corridor edge feature vector (C1 Spec §4.2)."""

TABULAR_FEATURE_DIM: int = 88
"""Input dimensionality of the TabTransformer (C1 Spec §4.3)."""


# ---------------------------------------------------------------------------
# Tabular feature names
# ---------------------------------------------------------------------------

def _build_feature_names() -> List[str]:
    """Return the canonical list of 88 tabular feature names."""
    names: List[str] = []

    # --- Amount features (indices 0-9) ---
    names += [
        "amount_usd_raw",
        "amount_usd_log1p",
        "amount_usd_sqrt",
        "amount_usd_bin_micro",      # < 1 000
        "amount_usd_bin_small",      # 1 000 – 10 000
        "amount_usd_bin_medium",     # 10 000 – 100 000
        "amount_usd_bin_large",      # 100 000 – 1 000 000
        "amount_usd_bin_xlarge",     # > 1 000 000
        "amount_vs_sender_mean",     # z-score vs sender historical mean
        "amount_vs_corridor_mean",   # z-score vs corridor historical mean
    ]

    # --- Time features (indices 10-24) ---
    names += [
        "hour_of_day_sin",
        "hour_of_day_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "day_of_month_sin",
        "day_of_month_cos",
        "month_of_year_sin",
        "month_of_year_cos",
        "is_weekend",
        "is_business_hours",        # 09:00-17:00 UTC
        "is_end_of_month",
        "is_start_of_month",
        "quarter_of_year",
        "week_of_year_norm",
        "time_since_midnight_norm",
    ]

    # --- Corridor / BIC-pair features (indices 25-41) ---
    names += [
        "corridor_tx_count_log1p",
        "corridor_volume_7d_log1p",
        "corridor_volume_30d_log1p",
        "corridor_failure_rate_7d",
        "corridor_failure_rate_30d",
        "corridor_avg_amount_log1p",
        "corridor_std_amount_log1p",
        "corridor_age_days_log1p",
        "corridor_unique_currencies",
        "corridor_tx_per_day_log1p",
        "corridor_max_amount_log1p",
        "corridor_min_amount_log1p",
        "corridor_amount_range_log1p",
        "corridor_p50_amount_log1p",
        "corridor_p95_amount_log1p",
        "corridor_velocity_1h",      # tx count in last 1 h
        "corridor_velocity_24h",     # tx count in last 24 h
    ]

    # --- Sender BIC features (indices 42-52) ---
    names += [
        "sender_out_degree",
        "sender_in_degree",
        "sender_volume_24h_log1p",
        "sender_failure_rate_30d",
        "sender_avg_amount_log1p",
        "sender_std_amount_log1p",
        "sender_age_days_log1p",
        "sender_currency_concentration",
        "sender_tx_count_log1p",
        "sender_unique_receivers",
        "sender_pct_large_tx",       # fraction of tx > $100 000
    ]

    # --- Receiver BIC features (indices 53-63) ---
    names += [
        "receiver_out_degree",
        "receiver_in_degree",
        "receiver_volume_24h_log1p",
        "receiver_failure_rate_30d",
        "receiver_avg_amount_log1p",
        "receiver_std_amount_log1p",
        "receiver_age_days_log1p",
        "receiver_currency_concentration",
        "receiver_tx_count_log1p",
        "receiver_unique_senders",
        "receiver_pct_large_tx",
    ]

    # --- Historical failure features (indices 64-73) ---
    names += [
        "sender_hist_failure_rate_1d",
        "sender_hist_failure_rate_7d",
        "sender_hist_failure_rate_30d",
        "receiver_hist_failure_rate_1d",
        "receiver_hist_failure_rate_7d",
        "receiver_hist_failure_rate_30d",
        "sender_consecutive_failures",
        "receiver_consecutive_failures",
        "corridor_consecutive_failures",
        "global_failure_rate_24h",
    ]

    # --- Currency features (indices 74-82) ---
    names += [
        "is_usd_pair",
        "is_eur_pair",
        "is_gbp_pair",
        "is_exotic_pair",
        "fx_volatility_proxy",       # abs(amount_zscore) as proxy
        "currency_pair_hash_mod8_0",
        "currency_pair_hash_mod8_1",
        "currency_pair_hash_mod8_2",
        "currency_pair_hash_mod8_3",
    ]

    # --- SWIFT / message features (indices 83-87) ---
    names += [
        "is_gpi_payment",
        "message_type_103",          # MT103 flag
        "message_type_202",          # MT202 flag
        "has_beneficiary_info",
        "charge_type_sha",           # SHA charges flag
    ]

    assert len(names) == TABULAR_FEATURE_DIM, (
        f"Expected {TABULAR_FEATURE_DIM} feature names, got {len(names)}"
    )
    return names


_FEATURE_NAMES: List[str] = _build_feature_names()


# ---------------------------------------------------------------------------
# TabularFeatureEngineer
# ---------------------------------------------------------------------------

class TabularFeatureEngineer:
    """Transforms a raw payment dictionary into an 88-dimensional feature vector.

    All features are deterministically computed from the payment dict and
    optional corridor/node statistics passed as nested dicts under the keys
    ``sender_stats``, ``receiver_stats``, and ``corridor_stats``.

    C1 Spec Section 4.3 defines the feature set.
    """

    def extract(self, payment: dict) -> np.ndarray:
        """Extract a fixed-length 88-dim feature vector from a payment dict.

        Parameters
        ----------
        payment:
            Dictionary with at minimum:
            - ``amount_usd`` (float)
            - ``timestamp`` (float, Unix epoch)
            - ``currency_pair`` (str, e.g. ``"USD_EUR"``)
            - ``sending_bic`` (str)
            - ``receiving_bic`` (str)
            Optional sub-dicts for richer features:
            - ``sender_stats`` / ``receiver_stats`` / ``corridor_stats``

        Returns
        -------
        np.ndarray
            Shape ``(88,)``, dtype ``float64``.
        """
        vec = np.zeros(TABULAR_FEATURE_DIM, dtype=np.float64)

        amount_usd: float = float(payment.get("amount_usd", 0.0))
        timestamp: float = float(payment.get("timestamp", 0.0))
        currency_pair: str = str(payment.get("currency_pair", "UNKNOWN"))
        s_stats: dict = payment.get("sender_stats", {})
        r_stats: dict = payment.get("receiver_stats", {})
        c_stats: dict = payment.get("corridor_stats", {})

        dt = datetime.datetime.utcfromtimestamp(timestamp)
        hour = dt.hour
        dow = dt.weekday()
        dom = dt.day
        month = dt.month
        week = dt.isocalendar()[1]

        # ---- Amount features (0-9) ----
        sender_mean = float(s_stats.get("avg_amount", amount_usd + 1e-9))
        corridor_mean = float(c_stats.get("avg_amount", amount_usd + 1e-9))
        sender_std = float(s_stats.get("std_amount", 1.0)) + 1e-9
        corridor_std = float(c_stats.get("std_amount", 1.0)) + 1e-9

        vec[0] = math.log1p(amount_usd)                          # log1p raw
        vec[1] = math.log1p(amount_usd)                          # log1p (alias kept for naming)
        vec[2] = math.sqrt(amount_usd) if amount_usd >= 0 else 0.0
        vec[3] = float(amount_usd < 1_000)
        vec[4] = float(1_000 <= amount_usd < 10_000)
        vec[5] = float(10_000 <= amount_usd < 100_000)
        vec[6] = float(100_000 <= amount_usd < 1_000_000)
        vec[7] = float(amount_usd >= 1_000_000)
        vec[8] = (amount_usd - sender_mean) / sender_std
        vec[9] = (amount_usd - corridor_mean) / corridor_std

        # ---- Time features (10-24) ----
        vec[10] = math.sin(2 * math.pi * hour / 24)
        vec[11] = math.cos(2 * math.pi * hour / 24)
        vec[12] = math.sin(2 * math.pi * dow / 7)
        vec[13] = math.cos(2 * math.pi * dow / 7)
        vec[14] = math.sin(2 * math.pi * dom / 31)
        vec[15] = math.cos(2 * math.pi * dom / 31)
        vec[16] = math.sin(2 * math.pi * month / 12)
        vec[17] = math.cos(2 * math.pi * month / 12)
        vec[18] = float(dow >= 5)
        vec[19] = float(9 <= hour < 17)
        vec[20] = float(dom >= 28)
        vec[21] = float(dom == 1)
        vec[22] = float((month - 1) // 3 + 1) / 4.0  # quarter normalised
        vec[23] = week / 52.0
        vec[24] = (hour * 3600 + dt.minute * 60 + dt.second) / 86_400.0

        # ---- Corridor features (25-41) ----
        vec[25] = math.log1p(float(c_stats.get("tx_count", 0)))
        vec[26] = math.log1p(float(c_stats.get("volume_7d", 0)))
        vec[27] = math.log1p(float(c_stats.get("volume_30d", 0)))
        vec[28] = float(c_stats.get("failure_rate_7d", 0.0))
        vec[29] = float(c_stats.get("failure_rate_30d", 0.0))
        vec[30] = math.log1p(float(c_stats.get("avg_amount", 0)))
        vec[31] = math.log1p(float(c_stats.get("std_amount", 0)))
        vec[32] = math.log1p(float(c_stats.get("age_days", 0)))
        vec[33] = float(c_stats.get("unique_currencies", 1))
        vec[34] = math.log1p(float(c_stats.get("tx_per_day", 0)))
        vec[35] = math.log1p(float(c_stats.get("max_amount", 0)))
        vec[36] = math.log1p(float(c_stats.get("min_amount", 0)))
        vec[37] = math.log1p(
            max(0.0, float(c_stats.get("max_amount", 0)) - float(c_stats.get("min_amount", 0)))
        )
        vec[38] = math.log1p(float(c_stats.get("p50_amount", 0)))
        vec[39] = math.log1p(float(c_stats.get("p95_amount", 0)))
        vec[40] = float(c_stats.get("velocity_1h", 0))
        vec[41] = float(c_stats.get("velocity_24h", 0))

        # ---- Sender features (42-52) ----
        vec[42] = float(s_stats.get("out_degree", 0))
        vec[43] = float(s_stats.get("in_degree", 0))
        vec[44] = math.log1p(float(s_stats.get("volume_24h", 0)))
        vec[45] = float(s_stats.get("failure_rate_30d", 0.0))
        vec[46] = math.log1p(float(s_stats.get("avg_amount", 0)))
        vec[47] = math.log1p(float(s_stats.get("std_amount", 0)))
        vec[48] = math.log1p(float(s_stats.get("age_days", 0)))
        vec[49] = float(s_stats.get("currency_concentration", 0.0))
        vec[50] = math.log1p(float(s_stats.get("tx_count", 0)))
        vec[51] = float(s_stats.get("unique_receivers", 0))
        vec[52] = float(s_stats.get("pct_large_tx", 0.0))

        # ---- Receiver features (53-63) ----
        vec[53] = float(r_stats.get("out_degree", 0))
        vec[54] = float(r_stats.get("in_degree", 0))
        vec[55] = math.log1p(float(r_stats.get("volume_24h", 0)))
        vec[56] = float(r_stats.get("failure_rate_30d", 0.0))
        vec[57] = math.log1p(float(r_stats.get("avg_amount", 0)))
        vec[58] = math.log1p(float(r_stats.get("std_amount", 0)))
        vec[59] = math.log1p(float(r_stats.get("age_days", 0)))
        vec[60] = float(r_stats.get("currency_concentration", 0.0))
        vec[61] = math.log1p(float(r_stats.get("tx_count", 0)))
        vec[62] = float(r_stats.get("unique_senders", 0))
        vec[63] = float(r_stats.get("pct_large_tx", 0.0))

        # ---- Historical failure features (64-73) ----
        vec[64] = float(s_stats.get("failure_rate_1d", 0.0))
        vec[65] = float(s_stats.get("failure_rate_7d", 0.0))
        vec[66] = float(s_stats.get("failure_rate_30d", 0.0))
        vec[67] = float(r_stats.get("failure_rate_1d", 0.0))
        vec[68] = float(r_stats.get("failure_rate_7d", 0.0))
        vec[69] = float(r_stats.get("failure_rate_30d", 0.0))
        vec[70] = float(s_stats.get("consecutive_failures", 0))
        vec[71] = float(r_stats.get("consecutive_failures", 0))
        vec[72] = float(c_stats.get("consecutive_failures", 0))
        vec[73] = float(payment.get("global_failure_rate_24h", 0.0))

        # ---- Currency features (74-82) ----
        cp_upper = currency_pair.upper()
        vec[74] = float("USD" in cp_upper)
        vec[75] = float("EUR" in cp_upper)
        vec[76] = float("GBP" in cp_upper)
        _major = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
        parts = cp_upper.replace("/", "_").split("_")
        vec[77] = float(not all(p in _major for p in parts if len(p) == 3))
        vec[78] = abs(float(payment.get("amount_zscore", 0.0)))  # FX volatility proxy
        # 4-bit hash embedding of the currency pair
        cp_hash = hash(currency_pair) & 0xFF
        for bit_idx in range(4):
            vec[79 + bit_idx] = float((cp_hash >> bit_idx) & 1)

        # ---- SWIFT / message features (83-87) ----
        vec[83] = float(payment.get("is_gpi", False))
        vec[84] = float(str(payment.get("message_type", "")).startswith("103"))
        vec[85] = float(str(payment.get("message_type", "")).startswith("202"))
        vec[86] = float(bool(payment.get("beneficiary_name") or payment.get("beneficiary_account")))
        vec[87] = float(str(payment.get("charge_type", "")).upper() == "SHA")

        return vec

    def feature_names(self) -> List[str]:
        """Return the ordered list of 88 feature names.

        Returns
        -------
        List[str]
            Exactly 88 strings corresponding to positions in the vector
            returned by :meth:`extract`.
        """
        return list(_FEATURE_NAMES)


# ---------------------------------------------------------------------------
# FeaturePipeline
# ---------------------------------------------------------------------------

class FeaturePipeline:
    """Unified pipeline that produces node, edge, and tabular feature arrays.

    This class ties together :class:`BICGraphBuilder` and
    :class:`TabularFeatureEngineer` so that callers can obtain all three
    feature types from a single method call.

    Parameters
    ----------
    graph_builder:
        A populated :class:`BICGraphBuilder` instance used to look up
        graph-structural features for sending/receiving BICs.
    """

    def __init__(self, graph_builder: BICGraphBuilder) -> None:
        self._graph = graph_builder
        self._tab_eng = TabularFeatureEngineer()

    def extract_all(self, payment: dict) -> Dict[str, np.ndarray]:
        """Extract node, edge, and tabular feature vectors for a payment.

        Parameters
        ----------
        payment:
            Raw payment dictionary (same schema as
            :meth:`TabularFeatureEngineer.extract`).

        Returns
        -------
        dict
            Keys:

            - ``"node"``    → ``np.ndarray`` of shape ``(8,)``
            - ``"edge"``    → ``np.ndarray`` of shape ``(6,)``
            - ``"tabular"`` → ``np.ndarray`` of shape ``(88,)``
        """
        sending_bic: str = str(payment.get("sending_bic", ""))
        receiving_bic: str = str(payment.get("receiving_bic", ""))

        node_feat = self._graph.get_node_features(sending_bic)
        edge_feat = self._graph.get_edge_features(sending_bic, receiving_bic)
        tabular_feat = self._tab_eng.extract(payment)

        return {
            "node": node_feat,
            "edge": edge_feat,
            "tabular": tabular_feat,
        }
