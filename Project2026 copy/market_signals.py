#!/usr/bin/env python3
"""
MARKET SIGNAL MODULE
Patent Spec v4.0 — Automated Liquidity Bridging System

Provides live market signals that dynamically adjust the CVA pricing engine
to current market stress conditions.

SIGNALS
  1. Live ECB €STR rate         — Euro short-term rate (OIS proxy)
  2. Live ECB FX spot volatility — Historical vol from ECB reference rates
  3. Simulated CDS spread        — Tier-based with deterministic perturbation
  4. Simulated settlement lag    — Corridor-based with deterministic seed

AGGREGATION
  MarketSignalAggregator combines all four z-scores into a composite
  market_stress_multiplier applied to pd_structural in the CVA formula.

DATA SOURCES
  ECB Data Portal (SDMX REST API, CSV format):
    €STR:  https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT
    FX:    https://data-api.ecb.europa.eu/service/data/EXR/D.{CCY}.EUR.SP00.A

DEPENDENCIES
  Standard library only: urllib.request, csv, io, math, hashlib, json,
  datetime, time, functools, dataclasses, typing.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import csv
import hashlib
import io
import math
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# CONSTANTS
# =============================================================================

# Static fallback risk-free rates (used when live API is unavailable)
_STATIC_RISK_FREE: Dict[str, float] = {
    "USD": 0.053,
    "EUR": 0.040,
    "GBP": 0.052,
    "JPY": 0.001,
    "CAD": 0.045,
    "CHF": 0.018,
    "INR": 0.065,
    "BRL": 0.115,
    "MXN": 0.105,
    "CNY": 0.035,
    "SGD": 0.038,
    "HKD": 0.052,
    "DEFAULT": 0.045,
}

# CDS spread baselines by counterparty tier (bps)
_CDS_TIER_BASELINES: Dict[int, Tuple[float, float]] = {
    1: (40.0, 80.0),     # Tier 1 GSIBs: 40–80 bps
    2: (80.0, 200.0),    # Tier 2 private regionals: 80–200 bps
    3: (200.0, 500.0),   # Tier 3 data-sparse: 200–500 bps
}

# Settlement lag baselines by corridor type (hours)
_LAG_G7_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "CHF"}
_LAG_HIGH_FRICTION = {"CNY", "BRL"}

_CACHE_TTL_SECONDS = 3600  # 1-hour TTL for ECB API responses
_ECB_TIMEOUT_SECONDS = 5
_ECB_LOOKBACK_CALENDAR_DAYS = 130  # ~90 business days

# Composite z-score weights
_WEIGHT_CDS   = 0.40
_WEIGHT_FXVOL = 0.25
_WEIGHT_LAG   = 0.20
_WEIGHT_ESTR  = 0.15

# market_stress_multiplier clamp range
_MULTIPLIER_MIN = 0.5
_MULTIPLIER_MAX = 3.0


# =============================================================================
# SIMPLE IN-PROCESS CACHE
# =============================================================================

_cache: Dict[str, Tuple[float, Any]] = {}   # key → (expiry_epoch, value)


def _cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and time.time() < entry[0]:
        return entry[1]
    return None


def _cache_set(key: str, value: Any, ttl: float = _CACHE_TTL_SECONDS) -> None:
    _cache[key] = (time.time() + ttl, value)


# =============================================================================
# ECB API HELPERS
# =============================================================================

def _ecb_fetch_csv(url: str) -> List[Dict[str, str]]:
    """
    Fetch a CSV from the ECB SDMX REST API and return parsed rows.
    Raises on any network or HTTP error (caller handles fallback).
    """
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=_ECB_TIMEOUT_SECONDS) as resp:
        content = resp.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def _date_range() -> Tuple[str, str]:
    """Return (start_period, end_period) strings for the 90-business-day lookback."""
    today = date.today()
    start = today - timedelta(days=_ECB_LOOKBACK_CALENDAR_DAYS)
    return start.isoformat(), today.isoformat()


# =============================================================================
# STATISTICAL HELPERS
# =============================================================================

def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals)


def _std(vals: List[float]) -> float:
    m = _mean(vals)
    variance = sum((v - m) ** 2 for v in vals) / len(vals)
    return math.sqrt(variance)


def _zscore(value: float, series: List[float]) -> float:
    """Z-score of value vs series.  Returns 0.0 if std == 0."""
    if len(series) < 2:
        return 0.0
    s = _std(series)
    if s == 0.0:
        return 0.0
    return (value - _mean(series)) / s


def _log_returns(prices: List[float]) -> List[float]:
    """Compute log returns from a price series."""
    return [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]


def _rolling_vol(log_rets: List[float], window: int = 30) -> List[float]:
    """30-day rolling historical volatility (annualised)."""
    vols = []
    for i in range(window, len(log_rets) + 1):
        window_rets = log_rets[i - window:i]
        if len(window_rets) < 2:
            continue
        vols.append(_std(window_rets) * math.sqrt(252))
    return vols


# =============================================================================
# 1. LIVE ECB €STR FETCHER
# =============================================================================

def _fetch_estr() -> Dict[str, Any]:
    """
    Fetch the last ~90 business days of ECB €STR rates.

    Returns dict with keys:
      latest_rate (float), zscore (float), series_mean (float),
      series_std (float), obs_date (str), source (str), live (bool)
    """
    cache_key = "estr"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    start, end = _date_range()
    url = (
        "https://data-api.ecb.europa.eu/service/data/EST/"
        f"B.EU000A2X2A25.WT?startPeriod={start}&endPeriod={end}&format=csvdata"
    )

    try:
        rows = _ecb_fetch_csv(url)
        rates = []
        last_date = ""
        for row in rows:
            try:
                rates.append(float(row["OBS_VALUE"]))
                last_date = row["TIME_PERIOD"]
            except (KeyError, ValueError):
                continue

        if not rates:
            raise ValueError("Empty €STR series from ECB API")

        latest = rates[-1]
        z = _zscore(latest, rates)
        result = {
            "latest_rate": latest / 100.0,        # convert pct → decimal
            "zscore": round(z, 4),
            "series_mean": round(_mean(rates) / 100.0, 6),
            "series_std": round(_std(rates) / 100.0, 6),
            "obs_date": last_date,
            "n_obs": len(rates),
            "source": "live — ECB SDMX REST API (€STR)",
            "live": True,
        }
        _cache_set(cache_key, result)
        return result

    except Exception as exc:
        fallback = {
            "latest_rate": _STATIC_RISK_FREE["EUR"],
            "zscore": 0.0,
            "series_mean": _STATIC_RISK_FREE["EUR"],
            "series_std": 0.0,
            "obs_date": date.today().isoformat(),
            "n_obs": 0,
            "source": f"static fallback — ECB API unavailable: {exc}",
            "live": False,
        }
        return fallback


def get_live_risk_free(currency: str) -> float:
    """
    Return the live risk-free rate for a given currency.

    For EUR: uses the latest ECB €STR observation.
    For all others: returns the static RISK_FREE_RATES fallback.
    """
    if currency.upper() == "EUR":
        estr = _fetch_estr()
        return estr["latest_rate"]
    return _STATIC_RISK_FREE.get(currency.upper(), _STATIC_RISK_FREE["DEFAULT"])


# =============================================================================
# 2. LIVE ECB FX SPOT VOLATILITY FETCHER
# =============================================================================

def _fetch_fx_series(ccy: str) -> List[float]:
    """
    Fetch ECB daily FX spot rates for CCY/EUR over the lookback window.
    Returns a list of float spot rates (CCY per EUR), oldest first.
    """
    start, end = _date_range()
    url = (
        "https://data-api.ecb.europa.eu/service/data/EXR/"
        f"D.{ccy}.EUR.SP00.A?startPeriod={start}&endPeriod={end}&format=csvdata"
    )
    rows = _ecb_fetch_csv(url)
    prices = []
    for row in rows:
        try:
            prices.append(float(row["OBS_VALUE"]))
        except (KeyError, ValueError):
            continue
    return prices


def _fetch_fx_volatility(currency_pair: str) -> Dict[str, Any]:
    """
    Compute 30-day rolling historical FX volatility for a currency pair.

    For EUR/X pairs, fetches X/EUR directly.
    For non-EUR pairs (USD/GBP), fetches both legs vs EUR and computes cross rate.

    Returns dict with keys:
      latest_vol (float), zscore (float), n_obs (int), source (str), live (bool)
    """
    parts = currency_pair.upper().split("/")
    if len(parts) != 2:
        return {"latest_vol": 0.10, "zscore": 0.0, "n_obs": 0,
                "source": "static fallback — invalid pair", "live": False}

    ccy1, ccy2 = parts[0], parts[1]
    cache_key = f"fxvol:{currency_pair.upper()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        # Determine which series to fetch
        if ccy2 == "EUR":
            # e.g. USD/EUR — fetch USD/EUR directly
            prices = _fetch_fx_series(ccy1)
        elif ccy1 == "EUR":
            # e.g. EUR/USD — fetch USD/EUR, then invert
            raw = _fetch_fx_series(ccy2)
            prices = [1.0 / p for p in raw if abs(p) > 1e-10]
        else:
            # Cross rate: ccy1/ccy2 = (ccy1/EUR) / (ccy2/EUR)
            series1 = _fetch_fx_series(ccy1)
            series2 = _fetch_fx_series(ccy2)
            n = min(len(series1), len(series2))
            prices = [series1[i] / series2[i] for i in range(n) if abs(series2[i]) > 1e-10]

        if len(prices) < 32:
            raise ValueError(f"Insufficient FX data: {len(prices)} obs for {currency_pair}")

        log_rets = _log_returns(prices)
        rolling = _rolling_vol(log_rets, window=30)

        if not rolling:
            raise ValueError("No rolling vol computed")

        latest_vol = rolling[-1]
        z = _zscore(latest_vol, rolling)

        result = {
            "latest_vol": round(latest_vol, 6),
            "zscore": round(z, 4),
            "n_obs": len(prices),
            "vol_series_mean": round(_mean(rolling), 6),
            "vol_series_std": round(_std(rolling), 6),
            "source": f"live — ECB SDMX REST API (FX: {currency_pair})",
            "live": True,
        }
        _cache_set(cache_key, result)
        return result

    except Exception as exc:
        return {
            "latest_vol": 0.10,
            "zscore": 0.0,
            "n_obs": 0,
            "source": f"static fallback — ECB FX API unavailable: {exc}",
            "live": False,
        }


# =============================================================================
# 3. SIMULATED CDS SPREAD SIGNAL
# =============================================================================

def _deterministic_float(seed_str: str) -> float:
    """
    Return a deterministic float in [0, 1) derived from SHA-256(seed_str).
    Reproducible across runs for the same date + BIC combination.
    """
    digest = hashlib.sha256(seed_str.encode()).hexdigest()
    return int(digest[:8], 16) / 0x100000000


def _simulate_cds_series(bic: str, tier: int, n_days: int = 90) -> List[float]:
    """
    Generate a deterministic 90-day CDS spread history (bps) for a given BIC.
    Each day's value is seeded by SHA-256(date + BIC) for reproducibility.
    """
    lo, hi = _CDS_TIER_BASELINES.get(tier, _CDS_TIER_BASELINES[3])
    midpoint = (lo + hi) / 2.0
    spread = hi - lo

    today = date.today()
    series = []
    for i in range(n_days, 0, -1):
        d = today - timedelta(days=i)
        seed = f"{d.isoformat()}:{bic}"
        noise = (_deterministic_float(seed) - 0.5) * spread
        series.append(midpoint + noise)
    return series


def get_cds_signal(bic: str, tier: int) -> Dict[str, Any]:
    """
    Return a simulated CDS spread signal for a given BIC and tier.

    Returns dict with keys:
      latest_spread_bps (float), zscore (float), tier (int), source (str)
    """
    cache_key = f"cds:{bic}:{tier}:{date.today().isoformat()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    series = _simulate_cds_series(bic, tier)
    latest = series[-1]
    z = _zscore(latest, series)

    result = {
        "latest_spread_bps": round(latest, 2),
        "zscore": round(z, 4),
        "tier": tier,
        "series_mean_bps": round(_mean(series), 2),
        "series_std_bps": round(_std(series), 2),
        "source": "simulated — production uses Bloomberg/Refinitiv CDS feed",
    }
    _cache_set(cache_key, result, ttl=86400)  # 24h TTL (daily signal)
    return result


# =============================================================================
# 4. SIMULATED SETTLEMENT LAG SIGNAL
# =============================================================================

def _corridor_baseline_hours(currency_pair: str) -> float:
    """Return baseline settlement lag (hours) for a corridor."""
    parts = currency_pair.upper().split("/")
    currencies = set(parts)
    if currencies & _LAG_HIGH_FRICTION:
        return 18.0
    if currencies <= _LAG_G7_CURRENCIES:
        return 4.0
    return 12.0  # EM corridors


def _simulate_lag_series(currency_pair: str, n_days: int = 90) -> List[float]:
    """
    Generate a deterministic 90-day settlement lag history (hours).
    """
    baseline = _corridor_baseline_hours(currency_pair)
    today = date.today()
    series = []
    for i in range(n_days, 0, -1):
        d = today - timedelta(days=i)
        seed = f"{d.isoformat()}:{currency_pair}"
        noise = (_deterministic_float(seed) - 0.5) * baseline * 0.4
        series.append(baseline + noise)
    return series


def get_lag_signal(currency_pair: str) -> Dict[str, Any]:
    """
    Return a simulated settlement lag signal for a currency corridor.

    Returns dict with keys:
      latest_lag_hours (float), zscore (float), baseline_hours (float), source (str)
    """
    cache_key = f"lag:{currency_pair}:{date.today().isoformat()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    series = _simulate_lag_series(currency_pair)
    latest = series[-1]
    z = _zscore(latest, series)

    result = {
        "latest_lag_hours": round(latest, 2),
        "zscore": round(z, 4),
        "baseline_hours": _corridor_baseline_hours(currency_pair),
        "series_mean_hours": round(_mean(series), 2),
        "series_std_hours": round(_std(series), 2),
        "source": "simulated — production uses SWIFT gpi settlement analytics",
    }
    _cache_set(cache_key, result, ttl=86400)
    return result


# =============================================================================
# 5. MARKET SIGNAL RESULT DATACLASS
# =============================================================================

@dataclass
class MarketSignalResult:
    """
    Aggregated market signal snapshot returned by MarketSignalAggregator.
    """
    # Composite output
    market_stress_multiplier: float
    composite_zscore:         float
    regime:                   str    # CALM / ELEVATED / STRESSED / CRISIS

    # Individual signals
    estr:     Dict[str, Any]
    fx_vol:   Dict[str, Any]
    cds:      Dict[str, Any]
    lag:      Dict[str, Any]

    # Component z-scores and weights
    zscore_cds:   float
    zscore_fxvol: float
    zscore_lag:   float
    zscore_estr:  float

    # Metadata
    currency_pair:  str
    receiving_bic:  str
    tier:           int
    computed_at:    str


# =============================================================================
# 6. MARKET SIGNAL AGGREGATOR
# =============================================================================

class MarketSignalAggregator:
    """
    Combines live ECB €STR, live ECB FX volatility, simulated CDS spreads,
    and simulated settlement lags into a single market_stress_multiplier.

    multiplier = exp(0.3 × composite_z), clamped to [0.5, 3.0]

    Composite z = 0.40 × z_cds + 0.25 × z_fxvol + 0.20 × z_lag + 0.15 × z_estr
    """

    @staticmethod
    def _regime(composite_z: float) -> str:
        if composite_z <= 0.8:
            return "CALM"
        if composite_z <= 1.2:
            return "ELEVATED"
        if composite_z <= 2.0:
            return "STRESSED"
        return "CRISIS"

    @staticmethod
    def _regime_badge(regime: str) -> str:
        return {"CALM": "🟢", "ELEVATED": "🟡", "STRESSED": "🟠", "CRISIS": "🔴"}.get(regime, "⚪")

    def get_market_signals(
        self,
        currency_pair: str,
        receiving_bic: str,
        tier: int,
    ) -> MarketSignalResult:
        """
        Fetch and aggregate all market signals.

        Parameters
        ----------
        currency_pair : str
            e.g. "EUR/USD"
        receiving_bic : str
            BIC of the counterparty (receiving bank), e.g. "CHASUS33"
        tier : int
            Counterparty tier (1, 2, or 3) from the CVA engine
        """
        estr_data   = _fetch_estr()
        fxvol_data  = _fetch_fx_volatility(currency_pair)
        cds_data    = get_cds_signal(receiving_bic, tier)
        lag_data    = get_lag_signal(currency_pair)

        z_estr   = estr_data.get("zscore", 0.0)
        z_fxvol  = fxvol_data.get("zscore", 0.0)
        z_cds    = cds_data.get("zscore", 0.0)
        z_lag    = lag_data.get("zscore", 0.0)

        composite_z = (
            _WEIGHT_CDS   * z_cds
            + _WEIGHT_FXVOL * z_fxvol
            + _WEIGHT_LAG   * z_lag
            + _WEIGHT_ESTR  * z_estr
        )

        raw_multiplier = math.exp(0.3 * composite_z)
        multiplier = max(_MULTIPLIER_MIN, min(_MULTIPLIER_MAX, raw_multiplier))
        regime = self._regime(abs(composite_z))

        return MarketSignalResult(
            market_stress_multiplier = round(multiplier, 6),
            composite_zscore         = round(composite_z, 4),
            regime                   = regime,
            estr                     = estr_data,
            fx_vol                   = fxvol_data,
            cds                      = cds_data,
            lag                      = lag_data,
            zscore_cds               = round(z_cds, 4),
            zscore_fxvol             = round(z_fxvol, 4),
            zscore_lag               = round(z_lag, 4),
            zscore_estr              = round(z_estr, 4),
            currency_pair            = currency_pair,
            receiving_bic            = receiving_bic,
            tier                     = tier,
            computed_at              = datetime.now(timezone.utc).isoformat(),
        )

    def get_signal_snapshot(
        self,
        currency_pair: str = "EUR/USD",
        receiving_bic: str = "CHASUS33",
        tier: int = 1,
    ) -> Dict[str, Any]:
        """Return the signal as a plain dict (for API responses)."""
        result = self.get_market_signals(currency_pair, receiving_bic, tier)
        return {
            "market_stress_multiplier": result.market_stress_multiplier,
            "composite_zscore":         result.composite_zscore,
            "regime":                   result.regime,
            "regime_badge":             self._regime_badge(result.regime),
            "currency_pair":            result.currency_pair,
            "receiving_bic":            result.receiving_bic,
            "tier":                     result.tier,
            "computed_at":              result.computed_at,
            "signals": {
                "estr":   result.estr,
                "fx_vol": result.fx_vol,
                "cds":    result.cds,
                "lag":    result.lag,
            },
            "zscores": {
                "cds":   result.zscore_cds,
                "fx_vol": result.zscore_fxvol,
                "lag":   result.zscore_lag,
                "estr":  result.zscore_estr,
            },
            "weights": {
                "cds":   _WEIGHT_CDS,
                "fx_vol": _WEIGHT_FXVOL,
                "lag":   _WEIGHT_LAG,
                "estr":  _WEIGHT_ESTR,
            },
        }


# =============================================================================
# STANDALONE TEST / DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MARKET SIGNAL MODULE — Live Integration Test")
    print("=" * 60)

    # Test €STR
    print("\n[1] ECB €STR Rate:")
    estr = _fetch_estr()
    print(f"  Latest rate : {estr['latest_rate']:.4%}  ({estr['obs_date']})")
    print(f"  Z-score     : {estr['zscore']:.4f}")
    print(f"  N obs       : {estr['n_obs']}")
    print(f"  Source      : {estr['source']}")
    if not estr["live"]:
        print("  WARNING: Using static fallback — ECB API unavailable!")

    # Test FX vol
    print("\n[2] ECB FX Volatility (EUR/USD):")
    fxvol = _fetch_fx_volatility("EUR/USD")
    print(f"  30d ann vol : {fxvol['latest_vol']:.4f}")
    print(f"  Z-score     : {fxvol['zscore']:.4f}")
    print(f"  N obs       : {fxvol['n_obs']}")
    print(f"  Source      : {fxvol['source']}")

    # Test live risk-free
    print("\n[3] Live risk-free rates:")
    for ccy in ["EUR", "USD", "GBP"]:
        rf = get_live_risk_free(ccy)
        print(f"  {ccy}: {rf:.4%}")

    # Test full aggregation
    print("\n[4] MarketSignalAggregator:")
    agg = MarketSignalAggregator()
    sigs = agg.get_market_signals("EUR/USD", "CHASUS33", 1)
    print(f"  multiplier  : {sigs.market_stress_multiplier}")
    print(f"  composite_z : {sigs.composite_zscore}")
    print(f"  regime      : {sigs.regime}  {MarketSignalAggregator._regime_badge(sigs.regime)}")
    print(f"  z_cds={sigs.zscore_cds}  z_fxvol={sigs.zscore_fxvol}  "
          f"z_lag={sigs.zscore_lag}  z_estr={sigs.zscore_estr}")

    print("\n✓ Market signal module test complete.")
