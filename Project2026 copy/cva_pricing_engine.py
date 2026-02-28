#!/usr/bin/env python3
"""
COMPONENT 2: CVA PRICING ENGINE
Patent Spec v4.0 — System and Method for Automated Liquidity Bridging
Triggered by Real-Time Payment Network Failure Detection

COVERAGE
  Independent Claim 1(e) — counterparty-specific risk-adjusted liquidity cost
  Independent Claim 2(iii) — counterparty risk assessment component
  Independent Claim 2(iv)  — liquidity pricing component
  Dependent Claim D4 — Tier 1 PD: Merton/KMV structural model (listed counterparties)
  Dependent Claim D5 — Tier 2 PD: Damodaran sector-vol proxy (private firms)
  Dependent Claim D6 — Tier 3 PD: Altman Z'-score (data-sparse counterparties)
  Dependent Claim D7 — bridge loan secured by receivable assignment
  Dependent Claim D8 — receivable purchase at CVA-derived discount (alternative)

PURPOSE
  For each payment flagged by Component 1 (threshold_exceeded=True), this engine
  computes a risk-adjusted bridge loan APR using a tiered probability-of-default
  framework.  The tiered framework is the core technical contribution that extends
  beyond JPMorgan US7089207B1, which covers ONLY listed companies with observable
  equity market prices.  Tier 2 (Damodaran proxy) and Tier 3 (Altman Z') handle
  private mid-market counterparties — the majority of cross-border trade finance.

CVA FORMULA (Claim 1(e))
  Expected Loss = PD × EAD × LGD × DF
  CVA cost rate = EL / EAD / (bridge_horizon_years)        [annualised]
  Bridge Loan APR = CVA cost rate + Funding Spread + Operational Margin

TIERED PD FRAMEWORK (D4 / D5 / D6)
  Tier 1 — Listed GSIBs:       Merton/KMV structural model (observable equity)
  Tier 2 — Private regionals:  Damodaran sector-median asset volatility proxy
  Tier 3 — Data-sparse:        Altman Z'-score → Moody's historical default table

COMPONENT CHAIN
  [ISO 20022 stream]
    → Component 1: Failure Prediction  (failure_prediction_engine.py)
    → Component 2: CVA Pricing          ← THIS FILE
    → Component 3: Bridge Loan Execution Workflow

DEPENDENCIES
  Standard library only (math, json, dataclasses, uuid).
  Imports Component 1 if present; falls back to embedded mock data if absent.
"""

# =============================================================================
# SECTION 1: IMPORTS
# =============================================================================

import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Market Signal Layer — real-time market condition adjustment (Claim 1(e))
# Import is optional; falls back gracefully if module is absent.
# ---------------------------------------------------------------------------
try:
    from market_signals import MarketSignalAggregator
    _MARKET_SIGNALS_AVAILABLE = True
except ImportError:
    _MARKET_SIGNALS_AVAILABLE = False
    MarketSignalAggregator = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Normal CDF from standard library — no scipy required
# math.erf is available since Python 3.2 and is exact to machine precision.
# N(x) = Φ(x) = ½ · (1 + erf(x / √2))
# ---------------------------------------------------------------------------
def _N(x: float) -> float:
    """Cumulative distribution function of the standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ---------------------------------------------------------------------------
# Optional Component 1 import
# ---------------------------------------------------------------------------
try:
    from failure_prediction_engine import (
        BANK_PROFILES,
        package_predictions,
        run_pipeline,
        PaymentFailurePrediction,
    )
    _COMPONENT1_AVAILABLE = True
except ImportError:
    _COMPONENT1_AVAILABLE = False
    BANK_PROFILES: Dict[str, Tuple] = {}


# =============================================================================
# SECTION 2: CONSTANTS
# =============================================================================

# ---------------------------------------------------------------------------
# 2.1  Risk-free rates by settlement currency (2026 approximate)
# In production these come from live OIS swap rate feeds.
# Convention: receiving currency (CCY2 of the pair) determines the rate.
# ---------------------------------------------------------------------------
RISK_FREE_RATES: Dict[str, float] = {
    "USD": 0.053,   # SOFR-based OIS ~ 5.30 %
    "EUR": 0.040,   # ESTR-based OIS ~ 4.00 %
    "GBP": 0.052,   # SONIA-based OIS ~ 5.20 %
    "JPY": 0.001,   # BOJ policy rate  ~ 0.10 %
    "CAD": 0.045,   # BOC overnight   ~ 4.50 %
    "CHF": 0.018,   # SNB policy rate  ~ 1.80 %
    "INR": 0.065,   # RBI repo         ~ 6.50 %
    "BRL": 0.115,   # SELIC            ~ 11.50 %
    "MXN": 0.105,   # Banxico          ~ 10.50 %
    "ZAR": 0.085,   # SARB             ~ 8.50 %
    "CNY": 0.035,   # PBOC 1-yr LPR   ~ 3.50 %
    "SGD": 0.038,   # MAS SORA         ~ 3.80 %
    "AED": 0.054,   # Follows USD peg  ~ 5.40 %
    "HKD": 0.055,   # HKMA follows Fed ~ 5.50 %
    "DEFAULT": 0.060,
}

# ---------------------------------------------------------------------------
# 2.2  Funding spread by sender bank tier (bps over risk-free)
# This is the lender's own wholesale funding cost, NOT the borrower's spread.
# Tier 1 (GSIB): repo / covered bond market — tightest spreads.
# Tier 3 (EM bank): subordinated funding — significant premium.
# ---------------------------------------------------------------------------
FUNDING_SPREAD_BPS: Dict[int, float] = {
    1: 25.0,    # GSIB: ~25 bps over OIS
    2: 75.0,    # Regional: ~75 bps over OIS
    3: 150.0,   # Emerging market: ~150 bps over OIS
}

# ---------------------------------------------------------------------------
# 2.3  LGD corridor friction (added to base LGD)
# Cross-border receivable recovery is jurisdiction-dependent.
# Base secured LGD = 30 % (receivable assignment, Claim D7).
# Friction = incremental LGD from enforcement risk, FX freezes, legal lag.
# ---------------------------------------------------------------------------
CORRIDOR_LGD_FRICTION: Dict[str, float] = {
    "EUR/USD": 0.00,  "USD/EUR": 0.00,   # G7 bilateral enforcement — nil friction
    "GBP/USD": 0.02,  "USD/GBP": 0.02,
    "USD/JPY": 0.05,  "JPY/USD": 0.05,   # Japanese enforcement lag
    "EUR/GBP": 0.02,  "GBP/EUR": 0.02,
    "USD/CHF": 0.03,  "CHF/USD": 0.03,
    "USD/CAD": 0.00,  "CAD/USD": 0.00,   # CUSMA framework
    "USD/SGD": 0.08,  "SGD/USD": 0.08,
    "USD/HKD": 0.05,  "HKD/USD": 0.05,
    "USD/CNY": 0.20,  "CNY/USD": 0.20,   # Capital controls — highest friction
    "EUR/INR": 0.18,  "INR/EUR": 0.18,
    "USD/INR": 0.16,  "INR/USD": 0.16,
    "USD/BRL": 0.22,  "BRL/USD": 0.22,   # Political/FX risk
    "USD/MXN": 0.15,  "MXN/USD": 0.15,
    "USD/ZAR": 0.20,  "ZAR/USD": 0.20,
    "USD/AED": 0.08,  "AED/USD": 0.08,
    "DEFAULT": 0.12,
}

# ---------------------------------------------------------------------------
# 2.4  Damodaran sector-median ASSET volatilities (D5 — Tier 2 PD)
# Source: Aswath Damodaran "Volatility — Implied and Actual" annual update.
# These are firm ASSET volatilities (not equity vols) inferred from listed-
# firm leverage and equity vol data within each sector.  Published at
# pages.stern.nyu.edu/~adamodar/.  The trade secret version uses proprietary
# calibrations from live bridge loan portfolio defaults (Section 5 of spec).
# ---------------------------------------------------------------------------
DAMODARAN_SECTOR_ASSET_VOL: Dict[str, float] = {
    "financial_services":   0.080,   # Banks/insurance — low leverage-adj vol
    "manufacturing":        0.120,
    "retail":               0.150,
    "technology":           0.220,
    "healthcare":           0.180,
    "energy":               0.200,
    "real_estate":          0.100,
    "commodities_trading":  0.250,
    "logistics_shipping":   0.160,
    "agriculture":          0.200,
    "construction":         0.180,
    "telecom":              0.120,
    "hospitality":          0.220,
    "emerging_market_trade":0.280,   # High-vol proxy for EM trade finance
    "DEFAULT":              0.180,
}

# ---------------------------------------------------------------------------
# 2.5  Altman Z'-score → Moody's 1-year PD table (D6 — Tier 3 PD)
# Z' model (Altman 1995) is calibrated for PRIVATE companies (uses book
# equity in X4, not market cap).  PD values are from Moody's "Annual Default
# Study 1920-2025" cohort data, mapped to Z'-implied rating equivalents.
#
# Table: (z_lower_inclusive, z_upper_exclusive, annual_pd)
# Ordered from safe → distress.
# ---------------------------------------------------------------------------
ALTMAN_PD_TABLE: List[Tuple[float, float, float]] = [
    (5.00,  math.inf,  0.0005),   # Extremely safe  ≈ AAA/Aaa
    (3.50,  5.00,      0.0010),   # Very safe       ≈ AA
    (2.90,  3.50,      0.0030),   # Safe border     ≈ A
    (2.30,  2.90,      0.0080),   # Grey upper      ≈ BBB
    (1.70,  2.30,      0.0180),   # Grey mid        ≈ BB
    (1.23,  1.70,      0.0400),   # Grey lower      ≈ B
    (0.80,  1.23,      0.0800),   # Distress upper  ≈ CCC
    (0.30,  0.80,      0.1400),   # Distress mid    ≈ CC
    (-math.inf, 0.30,  0.2500),   # Deep distress   ≈ C/D
]

# ---------------------------------------------------------------------------
# 2.6  Bridge loan operating parameters
# ---------------------------------------------------------------------------
OPERATIONAL_MARGIN_BPS:   float = 50.0    # Fixed profit margin above CVA cost
MINIMUM_RATE_BPS:         float = 150.0   # Floor — never price below 1.50 % APR
MAXIMUM_RATE_BPS:         float = 800.0   # Cap  — never price above 8.00 % APR
OFFER_VALIDITY_SECONDS:   int   = 300     # 5-minute acceptance window (D9 latency)
ADVANCE_DURATION_BUFFER:  int   = 7       # Days added for dispute resolution
LGD_BASE_SECURED:         float = 0.30    # Base LGD, receivable assignment (D7)
MERTON_HORIZON_YEARS:     float = 1.0     # Structural model always computes 1-yr PD


# =============================================================================
# SECTION 3: COUNTERPARTY PROFILES
# =============================================================================

@dataclass
class CounterpartyProfile:
    """
    Financial characteristics of a counterparty, keyed by BIC.

    In production this record is retrieved from a live counterparty risk
    database populated from Bloomberg/Refinitiv (Tier 1), BvD Orbis
    (Tier 2), and KYC/credit bureau data (Tier 3).

    The 'tier' field drives which PD model is selected (D4/D5/D6):
      Tier 1 — GSIB listed: observable equity market data available
      Tier 2 — Private regional: balance-sheet data, no equity prices
      Tier 3 — Data-sparse: only basic financial ratios available
    """
    bic:         str
    institution: str
    tier:        int       # 1 / 2 / 3
    sector:      str
    country:     str

    # Tier 1 inputs — Merton/KMV (D4) ----------------------------------------
    equity_market_cap_bn: Optional[float] = None   # USD billions
    equity_volatility:    Optional[float] = None   # Annualised equity vol σ_E
    total_debt_bn:        Optional[float] = None   # USD billions (book value)

    # Tier 2 inputs — proxy structural (D5) -----------------------------------
    total_assets_bn: Optional[float] = None        # USD billions

    # Tier 3 inputs — Altman Z' (D6) -----------------------------------------
    # All X-ratios expressed as fractions (0.12 = 12 %)
    x1_wc_to_assets:     Optional[float] = None   # Working capital / Total assets
    x2_re_to_assets:     Optional[float] = None   # Retained earnings / Total assets
    x3_ebit_to_assets:   Optional[float] = None   # EBIT / Total assets
    x4_equity_to_debt:   Optional[float] = None   # Book equity / Total liabilities
    x5_sales_to_assets:  Optional[float] = None   # Sales / Total assets


# ---------------------------------------------------------------------------
# Synthetic counterparty database keyed by BIC.
# In production: live-queried from the proprietary counterparty risk DB
# (a critical trade secret per Section 5 of the patent specification).
# ---------------------------------------------------------------------------
_COUNTERPARTY_DB: Dict[str, CounterpartyProfile] = {

    # ── TIER 1 — Global SIFIs (Merton/KMV, D4) ────────────────────────────
    "CHASUS33": CounterpartyProfile(
        "CHASUS33", "JPMorgan Chase", 1, "financial_services", "US",
        equity_market_cap_bn=490.0, equity_volatility=0.22, total_debt_bn=310.0,
    ),
    "BNPAFRPP": CounterpartyProfile(
        "BNPAFRPP", "BNP Paribas", 1, "financial_services", "FR",
        equity_market_cap_bn=75.0, equity_volatility=0.28, total_debt_bn=1_200.0,
    ),
    "HSBCHKHH": CounterpartyProfile(
        "HSBCHKHH", "HSBC Holdings", 1, "financial_services", "HK",
        equity_market_cap_bn=135.0, equity_volatility=0.25, total_debt_bn=890.0,
    ),
    "DEUTDEDB": CounterpartyProfile(
        "DEUTDEDB", "Deutsche Bank", 1, "financial_services", "DE",
        equity_market_cap_bn=22.0, equity_volatility=0.38, total_debt_bn=480.0,
    ),
    "ROYCCAT2": CounterpartyProfile(
        "ROYCCAT2", "Royal Bank of Canada", 1, "financial_services", "CA",
        equity_market_cap_bn=175.0, equity_volatility=0.19, total_debt_bn=920.0,
    ),
    "ANZBAU3M": CounterpartyProfile(
        "ANZBAU3M", "ANZ Bank Australia", 1, "financial_services", "AU",
        equity_market_cap_bn=55.0, equity_volatility=0.22, total_debt_bn=520.0,
    ),
    "ICBKCNBJ": CounterpartyProfile(
        "ICBKCNBJ", "ICBC China", 1, "financial_services", "CN",
        equity_market_cap_bn=215.0, equity_volatility=0.20, total_debt_bn=4_500.0,
    ),
    "SMBCJPJT": CounterpartyProfile(
        "SMBCJPJT", "Sumitomo Mitsui", 1, "financial_services", "JP",
        equity_market_cap_bn=65.0, equity_volatility=0.18, total_debt_bn=1_400.0,
    ),
    "UOVBSGSG": CounterpartyProfile(
        "UOVBSGSG", "UOB Singapore", 1, "financial_services", "SG",
        equity_market_cap_bn=33.0, equity_volatility=0.17, total_debt_bn=280.0,
    ),
    "CITIGB2L": CounterpartyProfile(
        "CITIGB2L", "Citi London Branch", 1, "financial_services", "GB",
        equity_market_cap_bn=95.0, equity_volatility=0.28, total_debt_bn=620.0,
    ),

    # ── TIER 2 — Private / regional banks (Damodaran proxy, D5) ──────────
    "ABNANL2A": CounterpartyProfile(
        "ABNANL2A", "ABN AMRO", 2, "financial_services", "NL",
        total_assets_bn=395.0,
    ),
    "INGSTLNX": CounterpartyProfile(
        "INGSTLNX", "ING Belgium", 2, "financial_services", "BE",
        total_assets_bn=840.0,
    ),
    "SCBLSGSG": CounterpartyProfile(
        "SCBLSGSG", "Standard Chartered SG", 2, "financial_services", "SG",
        total_assets_bn=280.0,
    ),
    "BARCGB22": CounterpartyProfile(
        "BARCGB22", "Barclays Correspondent", 2, "financial_services", "GB",
        total_assets_bn=1_500.0,
    ),
    "SBINMUMU": CounterpartyProfile(
        "SBINMUMU", "State Bank of India Mumbai", 2, "financial_services", "IN",
        total_assets_bn=620.0,
    ),
    "NEDSZAJJ": CounterpartyProfile(
        "NEDSZAJJ", "Nedbank South Africa", 2, "financial_services", "ZA",
        total_assets_bn=85.0,
    ),
    "BRADBRSP": CounterpartyProfile(
        "BRADBRSP", "Bradesco Brazil", 2, "financial_services", "BR",
        total_assets_bn=390.0,
    ),
    "BKCHZAJJ": CounterpartyProfile(
        "BKCHZAJJ", "Bank of China Johannesburg", 2, "financial_services", "ZA",
        total_assets_bn=42.0,
    ),
    "MGTCBEEB": CounterpartyProfile(
        "MGTCBEEB", "Euroclear Bank", 2, "financial_services", "BE",
        total_assets_bn=300.0,
    ),
    "COBADEFF": CounterpartyProfile(
        "COBADEFF", "Commerzbank", 2, "financial_services", "DE",
        total_assets_bn=480.0,
    ),

    # ── TIER 3 — Data-sparse / EM intermediaries (Altman Z', D6) ─────────
    "ABNAEGCX": CounterpartyProfile(
        "ABNAEGCX", "Egyptian Correspondent Bank", 3, "emerging_market_trade", "EG",
        x1_wc_to_assets=0.06, x2_re_to_assets=0.04, x3_ebit_to_assets=0.020,
        x4_equity_to_debt=0.18, x5_sales_to_assets=0.55,
    ),
    "IDIBPKKA": CounterpartyProfile(
        "IDIBPKKA", "Pakistan SME Finance Bank", 3, "emerging_market_trade", "PK",
        x1_wc_to_assets=0.04, x2_re_to_assets=0.02, x3_ebit_to_assets=0.015,
        x4_equity_to_debt=0.12, x5_sales_to_assets=0.40,
    ),
    "BKCHNGBX": CounterpartyProfile(
        "BKCHNGBX", "First Bank Nigeria", 3, "emerging_market_trade", "NG",
        x1_wc_to_assets=0.03, x2_re_to_assets=0.01, x3_ebit_to_assets=0.010,
        x4_equity_to_debt=0.10, x5_sales_to_assets=0.35,
    ),
}


def _get_counterparty_profile(bic: str) -> CounterpartyProfile:
    """
    Retrieve a counterparty profile by BIC.

    For unknown BICs (not in the proprietary database), construct a
    conservative Tier 3 synthetic profile.  The resulting Z'-score
    lands in the grey-zone lower region (PD ~ 4 % annualised), which
    is the prudent assumption when KYC data is absent.
    """
    if bic in _COUNTERPARTY_DB:
        return _COUNTERPARTY_DB[bic]

    # Unknown BIC — conservative Tier 3 fallback
    country = bic[4:6] if len(bic) >= 6 else "XX"
    return CounterpartyProfile(
        bic=bic,
        institution=f"Unknown Correspondent [{bic}]",
        tier=3,
        sector="emerging_market_trade",
        country=country,
        # Conservative Z' ratios → grey-zone lower border → PD ~ 4 %
        x1_wc_to_assets=0.05,
        x2_re_to_assets=0.03,
        x3_ebit_to_assets=0.020,
        x4_equity_to_debt=0.15,
        x5_sales_to_assets=0.45,
    )


# =============================================================================
# SECTION 4: TIERED PD ESTIMATION ENGINE  (Claims D4 / D5 / D6)
# =============================================================================

class TieredPDEngine:
    """
    Implements the three-tier probability-of-default framework from the patent.

    WHY THREE TIERS?
    JPMorgan US7089207B1 (prior art) requires observable equity market prices —
    it works only for listed public companies.  The majority of mid-market
    cross-border trade finance counterparties are PRIVATE.  The tiered framework
    closes this gap:

      D4 — Tier 1: Merton/KMV structural model — listed GSIBs
      D5 — Tier 2: Damodaran sector-vol proxy   — private regional banks
      D6 — Tier 3: Altman Z'-score              — data-sparse counterparties

    All three produce an annualised PD that is then scaled to the bridge
    loan horizon: PD_T = 1 - (1 - PD_annual)^(T/365).
    """

    _MAX_ITER:   int   = 60
    _TOLERANCE:  float = 1e-5     # Convergence: |ΔV_A| < $10 (scaled internally)

    # -------------------------------------------------------------------------
    # D4 — Merton / KMV structural model
    # -------------------------------------------------------------------------
    def _pd_tier1_merton(
        self,
        profile:        CounterpartyProfile,
        risk_free:      float,
        horizon_days:   int,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Dependent Claim D4 — Merton (1974) / KMV structural model.

        The model treats firm equity as a call option on firm assets:
          E = V_A · N(d₁) - D · e^{-rT} · N(d₂)         [BSM equity formula]
          σ_E · E = V_A · N(d₁) · σ_A                    [volatility constraint]

        We solve iteratively for (V_A, σ_A) given observable (E, σ_E, D, r, T).
        Distance-to-default: DD = (ln(V_A/D) + (μ - ½σ_A²)T) / (σ_A√T)
        PD = N(-d₂) under risk-neutral measure.

        PATENT RELEVANCE: This tier covers the same methodology as JPMorgan
        US7089207B1 for listed counterparties.  The novelty of the invention
        lies in tiers 2 and 3, which this engine dispatches to automatically
        when equity prices are absent.
        """
        E       = (profile.equity_market_cap_bn or 0.0) * 1e9
        sigma_E = profile.equity_volatility or 0.25
        D       = (profile.total_debt_bn or 0.0) * 1e9
        r       = risk_free
        T       = MERTON_HORIZON_YEARS

        if D <= 0 or E <= 0:
            # Degenerate input — use fallback PD
            return 0.005, {"model": "Merton/KMV (D4) — degenerate inputs, fallback 0.50%"}

        # Initialise: asset value ≈ equity + debt, asset vol from equity vol
        V_A     = E + D
        sigma_A = sigma_E * E / max(V_A, 1.0)

        for _ in range(self._MAX_ITER):
            d1      = (math.log(max(V_A, 1e-9) / D) + (r + 0.5 * sigma_A**2) * T) \
                      / max(sigma_A * math.sqrt(T), 1e-10)
            d2      = d1 - sigma_A * math.sqrt(T)
            Nd1, Nd2 = _N(d1), _N(d2)

            # Update asset value: solve E = V_A·N(d1) - D·e^{-rT}·N(d2) for V_A
            V_A_new = (E + D * math.exp(-r * T) * Nd2) / max(Nd1, 1e-10)
            # Update asset volatility from the volatility constraint
            sigma_A_new = sigma_E * E / max(V_A_new * Nd1, 1e-10)

            if abs(V_A_new - V_A) / max(abs(V_A), 1.0) < self._TOLERANCE:
                V_A, sigma_A = V_A_new, sigma_A_new
                break
            V_A, sigma_A = V_A_new, sigma_A_new

        # Final d2 with converged parameters
        d1_f = (math.log(max(V_A, 1e-9) / D) + (r + 0.5 * sigma_A**2) * T) \
               / max(sigma_A * math.sqrt(T), 1e-10)
        d2_f = d1_f - sigma_A * math.sqrt(T)
        # KMV distance-to-default (drift-adjusted)
        dd   = (math.log(max(V_A, 1e-9) / D) + (r - 0.5 * sigma_A**2) * T) \
               / max(sigma_A * math.sqrt(T), 1e-10)

        pd_annual  = float(_N(-d2_f))
        pd_horizon = 1.0 - (1.0 - pd_annual) ** (horizon_days / 365.0)

        return pd_horizon, {
            "model":               "Merton/KMV structural (D4)",
            "asset_value_bn":      round(V_A / 1e9, 3),
            "asset_volatility":    round(sigma_A, 5),
            "distance_to_default": round(dd, 3),
            "pd_annual":           round(pd_annual, 7),
            "pd_horizon":          round(pd_horizon, 7),
            "horizon_days":        horizon_days,
        }

    # -------------------------------------------------------------------------
    # D5 — Damodaran sector-median asset volatility proxy
    # -------------------------------------------------------------------------
    def _pd_tier2_damodaran(
        self,
        profile:      CounterpartyProfile,
        risk_free:    float,
        horizon_days: int,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Dependent Claim D5 — proxy structural model for private counterparties.

        When equity market prices are unavailable:
          V_A → total_assets  (book-value proxy)
          σ_A → sector-median asset volatility from Damodaran database

        Implied debt:
          Financial services firms: D = V_A × (1 - 0.08)   [Basel III Tier-1 floor]
          All other sectors:        D = V_A × (1 - 0.30)

        This is a single-step calculation — no iteration required since σ_A is
        taken directly from the Damodaran table rather than inferred from equity.

        PATENT RELEVANCE: This is the primary D5 embodiment.  It enables PD
        estimation for the ~90 % of mid-market trade finance counterparties
        that are private companies — the exact gap JPMorgan US7089207B1 leaves.
        """
        V_A     = (profile.total_assets_bn or 50.0) * 1e9
        sector  = profile.sector
        sigma_A = DAMODARAN_SECTOR_ASSET_VOL.get(sector, DAMODARAN_SECTOR_ASSET_VOL["DEFAULT"])
        r       = risk_free
        T       = MERTON_HORIZON_YEARS

        # Implied debt from sector leverage assumption
        equity_ratio = 0.08 if sector == "financial_services" else 0.30
        D = V_A * (1.0 - equity_ratio)

        if D <= 0 or V_A <= 0:
            return 0.01, {"model": "Damodaran proxy (D5) — degenerate, fallback 1.0%"}

        d2 = (math.log(V_A / D) + (r - 0.5 * sigma_A**2) * T) \
             / max(sigma_A * math.sqrt(T), 1e-10)

        pd_annual = float(_N(-d2))
        # Clip: proxy method is less precise than Tier 1
        pd_annual  = max(0.0001, min(pd_annual, 0.25))
        pd_horizon = 1.0 - (1.0 - pd_annual) ** (horizon_days / 365.0)

        return pd_horizon, {
            "model":             "Damodaran proxy structural (D5)",
            "sector":            sector,
            "total_assets_bn":   round(V_A / 1e9, 2),
            "implied_debt_bn":   round(D / 1e9, 2),
            "sigma_A_sector":    round(sigma_A, 5),
            "equity_ratio":      equity_ratio,
            "pd_annual":         round(pd_annual, 7),
            "pd_horizon":        round(pd_horizon, 7),
            "horizon_days":      horizon_days,
        }

    # -------------------------------------------------------------------------
    # D6 — Altman Z'-score
    # -------------------------------------------------------------------------
    def _pd_tier3_altman(
        self,
        profile:      CounterpartyProfile,
        horizon_days: int,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Dependent Claim D6 — Altman Z'-score for data-sparse counterparties.

        The Z' model (Altman 1995) was specifically designed for PRIVATE firms.
        Unlike the original Z-score (1968), Z' uses BOOK VALUE of equity in X4
        (not market cap), making it viable when equity prices are unobservable.

        Z' = 0.717·X1 + 0.847·X2 + 3.107·X3 + 0.420·X4 + 0.998·X5

          X1 = Working Capital / Total Assets       (short-term liquidity)
          X2 = Retained Earnings / Total Assets     (cumulative profitability)
          X3 = EBIT / Total Assets                  (operating efficiency)
          X4 = Book Equity / Total Liabilities      (financial leverage)
          X5 = Sales / Total Assets                 (asset efficiency)

        Zone mapping (Altman 1995):
          Z' > 2.90  → Safe zone       (approximate investment grade)
          1.23 < Z' < 2.90 → Grey zone (speculative grade)
          Z' < 1.23  → Distress zone   (high default probability)

        PD is then read from ALTMAN_PD_TABLE, which maps Z' to Moody's
        historical 1-year default rates for the equivalent rating category.
        """
        x1 = profile.x1_wc_to_assets    or 0.05
        x2 = profile.x2_re_to_assets    or 0.03
        x3 = profile.x3_ebit_to_assets  or 0.02
        x4 = profile.x4_equity_to_debt  or 0.15
        x5 = profile.x5_sales_to_assets or 0.45

        z_prime = (0.717 * x1 + 0.847 * x2 + 3.107 * x3
                   + 0.420 * x4 + 0.998 * x5)

        # Map Z' to annual PD via Moody's historical default table
        pd_annual = 0.05   # fallback (grey zone mid)
        zone      = "grey"
        for lb, ub, pd in ALTMAN_PD_TABLE:
            if lb <= z_prime < ub:
                pd_annual = pd
                if lb >= 2.90:
                    zone = "safe"
                elif ub <= 1.23:
                    zone = "distress"
                break

        pd_horizon = 1.0 - (1.0 - pd_annual) ** (horizon_days / 365.0)

        return pd_horizon, {
            "model":      "Altman Z'-score (D6)",
            "z_prime":    round(z_prime, 3),
            "zone":       zone,
            "ratios": {
                "X1_wc_to_assets":    round(x1, 4),
                "X2_re_to_assets":    round(x2, 4),
                "X3_ebit_to_assets":  round(x3, 4),
                "X4_equity_to_debt":  round(x4, 4),
                "X5_sales_to_assets": round(x5, 4),
            },
            "pd_annual":  round(pd_annual, 7),
            "pd_horizon": round(pd_horizon, 7),
            "horizon_days": horizon_days,
        }

    # -------------------------------------------------------------------------
    # Dispatcher — selects tier based on available data
    # -------------------------------------------------------------------------
    def estimate_pd(
        self,
        profile:      CounterpartyProfile,
        horizon_days: int,
        risk_free:    float = 0.05,
    ) -> Tuple[float, int, Dict[str, Any]]:
        """
        Select the appropriate PD model based on counterparty data availability.

        Returns: (pd_estimate, tier_used, diagnostics)

        Tier 1 requires: equity_market_cap_bn, equity_volatility, total_debt_bn
        Tier 2 requires: total_assets_bn
        Tier 3: always available (falls back to conservative defaults if ratios missing)
        """
        tier1_ready = (
            profile.tier <= 1
            and profile.equity_market_cap_bn is not None
            and profile.equity_volatility is not None
            and profile.total_debt_bn is not None
        )
        tier2_ready = (
            profile.tier <= 2
            and profile.total_assets_bn is not None
        )

        if tier1_ready:
            pd, diag = self._pd_tier1_merton(profile, risk_free, horizon_days)
            return pd, 1, diag
        elif tier2_ready:
            pd, diag = self._pd_tier2_damodaran(profile, risk_free, horizon_days)
            return pd, 2, diag
        else:
            pd, diag = self._pd_tier3_altman(profile, horizon_days)
            return pd, 3, diag


# =============================================================================
# SECTION 5: LGD ESTIMATOR
# =============================================================================

class LGDEstimator:
    """
    Estimates Loss-Given-Default for the bridge loan advance.

    The bridge loan is secured by legal assignment of the delayed payment
    receivable (Dependent Claim D7).  LGD therefore reflects:
      1. Base recovery on secured assignment in the receiving jurisdiction
      2. Corridor-specific enforcement friction (capital controls, FX freezes)
      3. Payment status adjustment — partial settlement reduces net exposure
      4. Size premium — large payments attract competing creditor claims

    BCBS 248 (intraday liquidity risk) baseline: 45 % unsecured LGD.
    Secured by receivable assignment: base reduced to 30 % (D7).
    """

    def estimate_lgd(
        self,
        currency_pair:  str,
        payment_status: str,
        amount_usd:     float,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compute LGD for a specific payment advance.

        Adjustments applied (all additive on top of secured base):
          + corridor friction   : jurisdiction-specific enforcement lag
          - partial status adj  : PART status means partial settlement occurred
          + large payment adj   : >$5M triggers competing creditor complexity
        """
        base    = LGD_BASE_SECURED
        friction = CORRIDOR_LGD_FRICTION.get(currency_pair, CORRIDOR_LGD_FRICTION["DEFAULT"])

        # Partial settlement: receiver already received some funds → lower net risk
        status_adj = -0.05 if payment_status in ("PART", "ACSP") else 0.0

        # Very large payments: more creditors, longer freeze orders, more complex
        size_adj = 0.05 if amount_usd > 5_000_000 else 0.0

        lgd = min(base + friction + status_adj + size_adj, 0.90)
        lgd = max(lgd, 0.05)

        return lgd, {
            "base_lgd_secured":   base,
            "corridor_friction":  round(friction, 4),
            "status_adjustment":  status_adj,
            "size_adjustment":    size_adj,
            "lgd_final":          round(lgd, 4),
            "security_type":      "payment_receivable_assignment (Claim D7)",
        }


# =============================================================================
# SECTION 6: CVA COMPUTATION
# =============================================================================

class CVAPricer:
    """
    Orchestrates tiered PD, LGD, and discount factor into the CVA formula
    and derives the bridge loan annual percentage rate.

    CVA Formula (Claim 1(e)):
      EL   = PD_blended × EAD × LGD × DF
      Rate = (EL / EAD) / T_years                  [annualised CVA cost rate]
      APR  = Rate + Funding_Spread + Operational_Margin

    PD Blending:
      The tiered structural PD captures long-run creditworthiness.
      The Component 1 ML failure_probability captures short-run operational risk.
      Blended PD = 0.60 × PD_structural + 0.40 × PD_ml
      This prevents double-counting while preserving both signals.

    Rates are expressed in basis points (bps). 1 bps = 0.01 %.
    """

    def __init__(self) -> None:
        self._pd_engine  = TieredPDEngine()
        self._lgd_engine = LGDEstimator()
        # Market signal aggregator — real-time adjustment (Claim 1(e) enhancement)
        self._market_signals = MarketSignalAggregator() if _MARKET_SIGNALS_AVAILABLE else None

    def _risk_free_for_pair(self, currency_pair: str) -> float:
        """Extract the receiving (CCY2) settlement currency and look up the OIS rate."""
        ccy = currency_pair.split("/")[1] if "/" in currency_pair else currency_pair[:3]
        return RISK_FREE_RATES.get(ccy, RISK_FREE_RATES["DEFAULT"])

    def _funding_spread_for_bic(self, sending_bic: str) -> float:
        """
        Lender's short-term funding cost above the risk-free rate.
        Sourced from the sender bank's tier (from Component 1's BANK_PROFILES).
        """
        tier = BANK_PROFILES.get(sending_bic, ("XX", 0.10, 3))[2]
        return FUNDING_SPREAD_BPS.get(int(tier), FUNDING_SPREAD_BPS[3]) / 10_000.0

    @staticmethod
    def _discount_factor(risk_free: float, horizon_days: int) -> float:
        """DF = exp(-r × T)  where T = (settlement_lag + buffer) / 365."""
        T = (horizon_days + ADVANCE_DURATION_BUFFER) / 365.0
        return math.exp(-risk_free * T)

    def price(self, cva_input: Dict[str, Any]) -> "CVAAssessment":
        """
        Main pricing method.

        Accepts the dict produced by PaymentFailurePrediction.to_cva_input()
        from Component 1.  Returns a fully-populated CVAAssessment ready for
        Component 3 (Bridge Loan Execution Workflow).
        """
        uetr           = cva_input["uetr"]
        ead            = float(cva_input["ead"])
        currency_pair  = cva_input["currency_pair"]
        sending_bic    = cva_input["sending_bic"]
        receiving_bic  = cva_input["receiving_bic"]
        lag_days       = int(cva_input["settlement_lag_days"])
        payment_status = cva_input["payment_status"]
        ml_pd          = float(cva_input["pd"])            # Component 1 output
        threshold_exc  = bool(cva_input["threshold_exceeded"])
        top_factors    = cva_input.get("top_risk_factors", [])

        # -- Step 1: Counterparty profile & risk-free rate --------------------
        profile   = _get_counterparty_profile(receiving_bic)
        risk_free = self._risk_free_for_pair(currency_pair)

        # -- Step 2: Tiered PD (D4/D5/D6) ------------------------------------
        horizon_days = lag_days + ADVANCE_DURATION_BUFFER
        pd_structural, tier_used, pd_diag = self._pd_engine.estimate_pd(
            profile, horizon_days, risk_free
        )

        # CVA uses the structural PD — the probability that the counterparty
        # FAILS TO REPAY the bridge advance (credit default risk).
        #
        # The ML failure_probability from Component 1 is the probability that
        # the ORIGINAL PAYMENT fails to settle (operational risk).  These are
        # fundamentally different risk dimensions:
        #   - ml_pd   → "Will this wire transfer fail?"    (Component 1's job)
        #   - pd_structural → "Will borrower repay us?"    (Component 2's job)
        #
        # Conflating them by blending would produce nonsense APRs because
        # ml_pd values of 20-40% (reasonable for a flagged payment) annualize
        # over a 7-day horizon into > 10,000 bps CVA rates.  The ML signal
        # already did its job by triggering the bridge offer; it does not
        # enter the credit pricing formula.
        #
        # We record both signals for transparency but price on pd_structural.
        pd_blended = pd_structural     # Credit risk only — no operational blend

        # -- Step 2b: Market signal adjustment (Claim 1(e) enhancement) ------
        # Real-time market signals adjust the structural PD to reflect current
        # market conditions.  The structural PD captures long-run creditworthiness;
        # the market multiplier captures short-run stress.
        #
        # Patent relevance: Claim 1(e) specifies "counterparty-specific
        # risk-adjusted liquidity cost". Market signals make the cost genuinely
        # real-time rather than based on quarterly balance sheets alone.
        #
        # Extension (future filing): Real-time market data integration for
        # dynamic credit risk adjustment.
        market_stress_multiplier = 1.0
        market_signals_dict: Dict[str, Any] = {}
        if self._market_signals is not None:
            market_sigs = self._market_signals.get_market_signals(
                currency_pair, receiving_bic, tier_used
            )
            pd_market_adjusted = min(
                pd_structural * market_sigs.market_stress_multiplier, 0.99
            )
            pd_blended = pd_market_adjusted
            market_stress_multiplier = market_sigs.market_stress_multiplier
            market_signals_dict = {
                "estr_rate":              market_sigs.estr_rate,
                "estr_z_score":           round(market_sigs.estr_z_score, 3),
                "fx_implied_vol":         round(market_sigs.fx_implied_vol, 4),
                "fx_vol_z_score":         round(market_sigs.fx_vol_z_score, 3),
                "settlement_lag_hours":   round(market_sigs.settlement_lag_hours, 1),
                "settlement_lag_z_score": round(market_sigs.settlement_lag_z_score, 3),
                "cds_spread_bps":         round(market_sigs.cds_spread_bps, 1),
                "cds_z_score":            round(market_sigs.cds_z_score, 3),
                "composite_z":            round(market_sigs.composite_z, 3),
                "regime":                 market_sigs.regime,
                "data_freshness":         market_sigs.data_freshness,
                "sources":                market_sigs.sources,
            }

        # -- Step 3: LGD ------------------------------------------------------
        lgd, lgd_diag = self._lgd_engine.estimate_lgd(
            currency_pair, payment_status, ead
        )

        # -- Step 4: Discount factor ------------------------------------------
        df = self._discount_factor(risk_free, lag_days)

        # -- Step 5: Expected Loss (CVA formula) ------------------------------
        expected_loss = pd_blended * ead * lgd * df

        # -- Step 6: Annualised CVA cost rate ---------------------------------
        T_years = max(horizon_days / 365.0, 1 / 365.0)
        cva_rate_annual = (expected_loss / ead) / T_years

        # -- Step 7: Bridge Loan APR ------------------------------------------
        funding_spread      = self._funding_spread_for_bic(sending_bic)
        operational_margin  = OPERATIONAL_MARGIN_BPS / 10_000.0
        apr_decimal         = cva_rate_annual + funding_spread + operational_margin
        apr_bps             = apr_decimal * 10_000.0
        apr_bps             = max(MINIMUM_RATE_BPS, min(apr_bps, MAXIMUM_RATE_BPS))
        apr_decimal         = apr_bps / 10_000.0

        # -- Step 8: Expected profit ------------------------------------------
        expected_profit = ead * operational_margin * T_years

        return CVAAssessment(
            uetr                  = uetr,
            currency_pair         = currency_pair,
            sending_bic           = sending_bic,
            receiving_bic         = receiving_bic,
            counterparty_name     = profile.institution,
            counterparty_tier     = tier_used,
            bridge_loan_amount    = ead,
            bridge_horizon_days   = horizon_days,
            annualized_rate_bps   = round(apr_bps, 1),
            apr_decimal           = round(apr_decimal, 6),
            cva_cost_rate_annual  = round(cva_rate_annual, 6),
            funding_spread_bps    = round(funding_spread * 10_000, 1),
            net_margin_bps        = round(operational_margin * 10_000, 1),
            expected_profit_usd   = round(expected_profit, 2),
            offer_valid_seconds   = OFFER_VALIDITY_SECONDS,
            pd_tier_used          = tier_used,
            pd_structural         = round(pd_structural, 7),
            pd_ml_signal          = round(ml_pd, 7),
            pd_blended            = round(pd_blended, 7),
            lgd_estimate          = round(lgd, 4),
            ead_usd               = round(ead, 2),
            expected_loss_usd     = round(expected_loss, 2),
            discount_factor       = round(df, 6),
            risk_free_rate        = round(risk_free, 4),
            pd_model_diagnostics  = pd_diag,
            lgd_model_diagnostics = lgd_diag,
            top_risk_factors      = top_factors,
            threshold_exceeded    = threshold_exc,
            market_stress_multiplier = market_stress_multiplier,
            market_signals        = market_signals_dict,
        )


# =============================================================================
# SECTION 7: CVAAssessment DATACLASS  —  Interface to Component 3
# =============================================================================

@dataclass
class CVAAssessment:
    """
    Complete CVA pricing result.

    This dataclass is the structured interface between:
      Component 2 (CVA Pricing Engine)           ← produced here
      Component 3 (Bridge Loan Execution Workflow) ← consumed there

    Component 3 uses:
      - annualized_rate_bps / bridge_loan_amount  → generate offer letter
      - ead_usd / uetr                            → execute disbursement
      - counterparty details                      → record security interest
      - bridge_horizon_days                       → set repayment trigger
      - pd_blended / lgd_estimate / expected_loss → risk reporting
    """
    # Identity -----------------------------------------------------------------
    uetr:              str
    currency_pair:     str
    sending_bic:       str
    receiving_bic:     str
    counterparty_name: str
    counterparty_tier: int

    # Loan economics -----------------------------------------------------------
    bridge_loan_amount:   float
    bridge_horizon_days:  int
    annualized_rate_bps:  float    # Total APR in bps
    apr_decimal:          float    # Total APR as decimal (0.0250 = 2.50 %)
    cva_cost_rate_annual: float    # CVA component only (annualised)
    funding_spread_bps:   float
    net_margin_bps:       float
    expected_profit_usd:  float
    offer_valid_seconds:  int

    # CVA components -----------------------------------------------------------
    pd_tier_used:     int
    pd_structural:    float        # Tiered model output (credit default risk)
    pd_ml_signal:     float        # Component 1 failure_probability (operational risk — NOT in CVA formula)
    pd_blended:       float        # = pd_structural (credit risk only; ML signal kept separate for audit)
    lgd_estimate:     float
    ead_usd:          float
    expected_loss_usd: float
    discount_factor:  float
    risk_free_rate:   float

    # Model diagnostics --------------------------------------------------------
    pd_model_diagnostics:  Dict[str, Any]
    lgd_model_diagnostics: Dict[str, Any]
    top_risk_factors:      List[Dict[str, Any]]
    threshold_exceeded:    bool

    # Market signals (Claim 1(e) — real-time market adjustment) ---------------
    market_stress_multiplier: float = 1.0
    market_signals: Dict[str, Any] = field(default_factory=dict)

    def to_execution_input(self) -> Dict[str, Any]:
        """
        Serialise to the structured input format for Component 3.

        Component 3 (Bridge Loan Execution Workflow) uses this to:
          1. Generate and transmit the bridge loan offer
          2. Execute disbursement upon acceptance
          3. Establish security interest — receivable assignment (Claim D7)
          4. Configure settlement monitoring for auto-repayment (Claim 5)
          5. Report expected loss to portfolio risk systems
        """
        total_cost = (self.bridge_loan_amount * self.apr_decimal
                      * self.bridge_horizon_days / 365.0)
        return {
            "uetr": self.uetr,
            "offer": {
                "bridge_loan_amount_usd": self.bridge_loan_amount,
                "annualized_rate_bps":    self.annualized_rate_bps,
                "apr_decimal":            self.apr_decimal,
                "bridge_horizon_days":    self.bridge_horizon_days,
                "offer_valid_seconds":    self.offer_valid_seconds,
                "total_cost_usd":         round(total_cost, 2),
            },
            "counterparty": {
                "receiving_bic":  self.receiving_bic,
                "institution":    self.counterparty_name,
                "pd_tier_used":   self.pd_tier_used,
                "pd_blended":     self.pd_blended,
                "lgd":            self.lgd_estimate,
            },
            "security_interest": {
                "collateral_type":     "payment_receivable_assignment",
                "collateral_uetr":     self.uetr,
                "security_amount_usd": self.bridge_loan_amount,
                "legal_basis":         "Claim D7 — assignment of delayed payment receivable",
            },
            "settlement_monitoring": {
                "repayment_trigger":  "swift_gpi_settlement_confirmation",
                "monitor_uetr":       self.uetr,
                "max_repayment_days": self.bridge_horizon_days + 14,
                "legal_basis":        "Claim 5 — auto-repayment loop",
            },
            "risk_metrics": {
                "expected_loss_usd":    self.expected_loss_usd,
                "expected_profit_usd":  self.expected_profit_usd,
                "pd_blended":           self.pd_blended,
                "lgd":                  self.lgd_estimate,
            },
        }


# =============================================================================
# SECTION 8: BRIDGE LOAN OFFER FORMATTER
# =============================================================================

_TIER_LABELS = {
    1: "Tier 1 — Merton/KMV Structural (D4)",
    2: "Tier 2 — Damodaran Proxy Structural (D5)",
    3: "Tier 3 — Altman Z'-Score (D6)",
}


def _fmt_pd_detail(assessment: CVAAssessment) -> str:
    """Format the tier-specific PD diagnostic lines for the offer sheet."""
    d = assessment.pd_model_diagnostics
    t = assessment.pd_tier_used
    if t == 1:
        return (
            f"    DD = {d.get('distance_to_default', '?'):>7}   "
            f"Asset value: ${d.get('asset_value_bn', '?')}B   "
            f"Asset vol: {d.get('asset_volatility', 0):.2%}"
        )
    elif t == 2:
        return (
            f"    Sector: {d.get('sector', '?'):20s}   "
            f"Assets: ${d.get('total_assets_bn', '?')}B   "
            f"σ_A: {d.get('sigma_A_sector', 0):.2%}"
        )
    else:
        z   = d.get("z_prime", "?")
        zon = d.get("zone", "?").upper()
        return f"    Altman Z' = {z}   Zone: {zon}"


def format_offer_sheet(assessment: CVAAssessment, rank: int) -> str:
    """
    Produce a banker-readable bridge loan offer sheet for one payment.

    Format matches the style of a term sheet telex — designed to be
    readable by a treasury operations officer without quantitative
    background.
    """
    W = 70
    total_cost = (assessment.bridge_loan_amount * assessment.apr_decimal
                  * assessment.bridge_horizon_days / 365.0)
    lgd_d = assessment.lgd_model_diagnostics

    lines: List[str] = [
        "",
        "─" * W,
        f"  BRIDGE LOAN OFFER  #{rank:02d}",
        f"  UETR : {assessment.uetr}",
        "─" * W,
        f"  Corridor          {assessment.currency_pair}",
        f"  Advance amount    ${assessment.bridge_loan_amount:>14,.2f}",
        f"  Bridge horizon    {assessment.bridge_horizon_days} days"
        f"  ({assessment.bridge_horizon_days/365:.2f} yrs)",
        f"  Offer valid       {assessment.offer_valid_seconds}s from transmission",
        "",
        "  ── PRICING ──────────────────────────────────────────────────",
        f"  APR (total)       {assessment.annualized_rate_bps:>6.1f} bps"
        f"  ({assessment.apr_decimal:.4%})",
        f"    CVA cost rate:  {assessment.cva_cost_rate_annual*10_000:>6.1f} bps",
        f"    Funding spread: {assessment.funding_spread_bps:>6.1f} bps",
        f"    Operational:    {assessment.net_margin_bps:>6.1f} bps",
        f"  Total cost (borrower)  ${total_cost:>12,.2f}",
        f"  Expected profit        ${assessment.expected_profit_usd:>12,.2f}",
        "",
    ]

    # ── MARKET SIGNALS (Claim 1(e) — real-time adjustment) ──────────────
    msigs = assessment.market_signals
    if msigs:
        _REGIME_EMOJI = {"CALM": "🟢", "ELEVATED": "🟡", "STRESSED": "🟠", "CRISIS": "🔴"}
        regime     = msigs.get("regime", "CALM")
        emoji      = _REGIME_EMOJI.get(regime, "⚪")
        multiplier = assessment.market_stress_multiplier
        estr_src   = msigs.get("sources", {}).get("estr", "")
        fx_src     = msigs.get("sources", {}).get("fx_vol", "")
        lag_src    = msigs.get("sources", {}).get("settlement_lag", "")
        cds_src    = msigs.get("sources", {}).get("cds", "")
        lines += [
            "  ── MARKET SIGNALS (Claim 1(e) — real-time adjustment) ───────────",
            f"  Regime:           {regime} {emoji}",
            f"  Stress multiplier: {multiplier:.2f}×  "
            f"(PD adjusted from {assessment.pd_structural:.4%} → {assessment.pd_blended:.4%})",
            f"  €STR rate:        {msigs.get('estr_rate', 0):.2%}"
            f"     (z: {msigs.get('estr_z_score', 0):+.1f})  [{estr_src}]",
            f"  FX vol (30d ann): {msigs.get('fx_implied_vol', 0):.1%}"
            f"     (z: {msigs.get('fx_vol_z_score', 0):+.1f})  [{fx_src}]",
            f"  Settlement lag:   {msigs.get('settlement_lag_hours', 0):.1f} hrs"
            f"   (z: {msigs.get('settlement_lag_z_score', 0):+.1f})  [{lag_src}]",
            f"  CDS spread:       {msigs.get('cds_spread_bps', 0):.1f} bps"
            f"  (z: {msigs.get('cds_z_score', 0):+.1f})  [{cds_src}]",
            "",
        ]

    lines += [
        "  ── CVA COMPONENTS ───────────────────────────────────────────",
        f"  Counterparty      {assessment.counterparty_name}  [{assessment.receiving_bic}]",
        _fmt_pd_detail(assessment),
        f"  PD structural     {assessment.pd_structural:.5%}  [{assessment.bridge_horizon_days}d]",
        f"  PD ML signal      {assessment.pd_ml_signal:.5%}  [Component 1 failure_prob]",
        f"  PD (credit risk)  {assessment.pd_blended:.5%}  [structural only — ML signal shown above, not in CVA formula]",
        f"  EAD               ${assessment.ead_usd:>14,.2f}",
        (f"  LGD               {assessment.lgd_estimate:.2%}"
         f"  [base {lgd_d.get('base_lgd_secured',0):.0%}"
         f" + corridor {lgd_d.get('corridor_friction',0):.0%}]"),
        f"  Discount factor   {assessment.discount_factor:.6f}  [r = {assessment.risk_free_rate:.2%}]",
        f"  Expected Loss     ${assessment.expected_loss_usd:>12,.2f}",
        "",
        "  ── SECURITY & REPAYMENT (CLAIMS D7 + 5) ────────────────────",
        f"  Collateral        Assignment of receivable UETR {assessment.uetr[:8]}…",
        f"  Repayment trigger SWIFT gpi settlement confirmation (Claim 5)",
        "─" * W,
    ]
    return "\n".join(lines)


# =============================================================================
# SECTION 9: FULL PIPELINE + DEMO
# =============================================================================

def _mock_cva_inputs() -> List[Dict[str, Any]]:
    """
    Minimal mock CVA inputs for standalone execution when
    failure_prediction_engine.py is not on the Python path.
    Three payments exercise all three PD tiers.
    """
    return [
        {   # Tier 1 counterparty (BNP Paribas — listed GSIB)
            "uetr": str(uuid.uuid4()), "pd": 0.68, "ead": 3_200_000.0,
            "currency_pair": "EUR/INR",  "sending_bic": "BNPAFRPP",
            "receiving_bic": "SBINMUMU", "settlement_lag_days": 2,
            "payment_status": "RJCT",    "threshold_exceeded": True,
            "top_risk_factors": [], "forward_risk_horizon": 14,
        },
        {   # Tier 2 counterparty (Bradesco — private regional)
            "uetr": str(uuid.uuid4()), "pd": 0.55, "ead": 8_750_000.0,
            "currency_pair": "USD/BRL",  "sending_bic": "CHASUS33",
            "receiving_bic": "BRADBRSP", "settlement_lag_days": 1,
            "payment_status": "PDNG",    "threshold_exceeded": True,
            "top_risk_factors": [], "forward_risk_horizon": 7,
        },
        {   # Tier 3 counterparty (Egyptian correspondent — data-sparse)
            "uetr": str(uuid.uuid4()), "pd": 0.31, "ead": 650_000.0,
            "currency_pair": "GBP/USD",  "sending_bic": "BARCGB22",
            "receiving_bic": "ABNAEGCX", "settlement_lag_days": 0,
            "payment_status": "PDNG",    "threshold_exceeded": True,
            "top_risk_factors": [], "forward_risk_horizon": 3,
        },
    ]


def run_cva_pipeline(
    flagged_payments: Optional[List[Dict[str, Any]]] = None,
    n_demo_payments: int = 500,
) -> Dict[str, Any]:
    """
    End-to-end CVA pricing pipeline.

    If flagged_payments is None and Component 1 is importable, runs the
    full failure prediction pipeline and prices every threshold_exceeded
    payment.  Otherwise uses embedded mock data for standalone demo.
    """
    pricer = CVAPricer()

    if flagged_payments is None:
        if _COMPONENT1_AVAILABLE:
            print("  Importing Component 1 (failure_prediction_engine)…", flush=True)
            c1_results   = run_pipeline(n_demo_payments, seed=42)
            predictions  = package_predictions(c1_results)
            flagged_payments = [
                p.to_cva_input()
                for p in predictions
                if p.threshold_exceeded
            ]
            n_total = len(predictions)
            n_flagged = len(flagged_payments)
            print(
                f"  Component 1: {n_total} payments scored, "
                f"{n_flagged} flagged (threshold_exceeded=True)",
                flush=True,
            )
        else:
            print(
                "  [Component 1 not importable — using embedded mock CVA inputs]",
                flush=True,
            )
            flagged_payments = _mock_cva_inputs()

    assessments: List[CVAAssessment] = []
    for cva_input in flagged_payments:
        try:
            assessments.append(pricer.price(cva_input))
        except Exception as exc:
            uid = cva_input.get("uetr", "?")[:8]
            print(f"  [CVA WARN] UETR {uid}…: {exc}", flush=True)

    tier_counts = {1: 0, 2: 0, 3: 0}
    for a in assessments:
        tier_counts[a.pd_tier_used] = tier_counts.get(a.pd_tier_used, 0) + 1

    n = len(assessments)
    return {
        "assessments":           assessments,
        "n_priced":              n,
        "total_advance_usd":     sum(a.bridge_loan_amount for a in assessments),
        "total_expected_loss":   sum(a.expected_loss_usd  for a in assessments),
        "total_expected_profit": sum(a.expected_profit_usd for a in assessments),
        "avg_apr_bps":           sum(a.annualized_rate_bps for a in assessments) / max(n, 1),
        "tier_distribution":     tier_counts,
    }


def print_cva_demonstration(results: Dict[str, Any], n_top: int = 5) -> None:
    """Print the formatted CVA pricing demonstration."""
    assessments = results["assessments"]
    W = 70

    print()
    print("=" * W)
    print("  COMPONENT 2: CVA PRICING ENGINE — DEMONSTRATION OUTPUT")
    print("  Patent Spec v4.0 — Claims 1(e), 2(iii/iv), D4, D5, D6, D7")
    print("=" * W)

    # Portfolio summary
    td = results["tier_distribution"]
    print()
    print("  PORTFOLIO SUMMARY")
    print(f"  {'─' * 48}")
    print(f"  Payments priced:       {results['n_priced']}")
    print(f"  Total advance pool:    ${results['total_advance_usd']:>14,.2f}")
    print(f"  Total expected loss:   ${results['total_expected_loss']:>14,.2f}")
    print(f"  Total expected profit: ${results['total_expected_profit']:>14,.2f}")
    print(f"  Average APR:           {results['avg_apr_bps']:.1f} bps")
    print(
        f"  PD tier usage:  "
        f"Tier 1 (Merton): {td.get(1,0)}   "
        f"Tier 2 (Damodaran): {td.get(2,0)}   "
        f"Tier 3 (Altman Z'): {td.get(3,0)}"
    )

    print()
    print("  TIERED PD FRAMEWORK — KEY PATENT DISTINCTION FROM PRIOR ART")
    print(f"  {'─' * 48}")
    print("  Tier 1 (D4)  Merton/KMV structural  — listed GSIBs with observable equity")
    print("  Tier 2 (D5)  Damodaran proxy         — private firms, sector-median asset vol")
    print("  Tier 3 (D6)  Altman Z'-score         — data-sparse counterparties")
    print("  JPMorgan US7089207B1 covers Tier 1 ONLY.")
    print("  Tiers 2 & 3 are the novel extension disclosed in this specification.")

    # ── Banker summary table — top 10 by failure probability ─────────────
    top10 = sorted(assessments, key=lambda a: a.pd_ml_signal, reverse=True)[:10]
    print()
    print("  TOP 10 HIGHEST-RISK PAYMENTS (sorted by failure probability)")
    print(f"  {'─' * 64}")
    hdr = (
        f"  {'#':>2}  {'Corridor':<10}  {'Amount (USD)':>14}  "
        f"{'Fail%':>6}  {'PD Tier':<8}  {'Exp.Loss':>11}  {'APR (bps)':>9}"
    )
    print(hdr)
    print(f"  {'─' * 64}")
    for i, a in enumerate(top10, 1):
        print(
            f"  {i:>2}  {a.currency_pair:<10}  ${a.bridge_loan_amount:>13,.0f}  "
            f"{a.pd_ml_signal:>5.1%}  "
            f"T{a.pd_tier_used} ({('Merton','Damodr','Altman')[a.pd_tier_used-1]})  "
            f"${a.expected_loss_usd:>10,.0f}  {a.annualized_rate_bps:>9.1f}"
        )
    print(f"  {'─' * 64}")

    # ── Detailed offer sheets — top N by advance amount ───────────────────
    top = sorted(assessments, key=lambda a: a.bridge_loan_amount, reverse=True)[:n_top]
    print(f"\n  TOP {len(top)} BRIDGE LOAN OFFERS (sorted by advance amount)")
    for rank, a in enumerate(top, 1):
        print(format_offer_sheet(a, rank))

    # Component 3 handoff preview
    if top:
        print()
        print("  COMPONENT 3 EXECUTION INPUT — first offer (JSON)")
        print(f"  {'─' * 48}")
        exec_input = top[0].to_execution_input()
        print(json.dumps(exec_input, indent=4))

    print()
    print("=" * W)
    print("  COMPONENT 2 COMPLETE")
    print("  Hand-off: CVAAssessment.to_execution_input() → Component 3")
    print("=" * W)


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    print()
    print("Running CVA Pricing Engine — Component 2 of 3")
    print("Patent Spec v4.0 — Automated Liquidity Bridging System")
    print("─" * 70)

    results = run_cva_pipeline(n_demo_payments=500)
    print_cva_demonstration(results, n_top=5)
