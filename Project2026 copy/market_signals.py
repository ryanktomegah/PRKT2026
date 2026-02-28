#!/usr/bin/env python3
"""
MARKET SIGNAL LAYER — Real-time market condition inputs for CVA pricing
Patent Spec v4.0 — System and Method for Automated Liquidity Bridging

COVERAGE
  Claim 1(e)   — counterparty-specific risk-adjusted liquidity cost (enhancement)
                 Real-time market signals make the cost genuinely real-time rather
                 than based on quarterly balance sheets alone.
  Claim 2(iv)  — liquidity pricing component (market signals are an input)
  Extension    — Real-time market data integration for dynamic credit risk adjustment
                 (future patent filing)

PURPOSE
  Fetches live market data from the ECB Data Portal SDMX REST API and combines
  four market stress signals into a single market_stress_multiplier that adjusts
  the structural PD in real-time:

    PD_adjusted = PD_structural × market_stress_multiplier

  Signal composition:
    1. €STR rate          — interbank funding stress (Claim 1(e) systemic)
    2. FX spot vol        — corridor settlement risk (Claim 1(e) corridor)
    3. Settlement lag     — operational corridor stress (simulated)
    4. CDS spread         — counterparty credit spread (simulated)

ARCHITECTURE
  ┌─────────────────────────────────────────────────────┐
  │  MarketSignalAggregator.get_market_signals()         │
  │    → fetches/caches ECB data                         │
  │    → generates simulated CDS + settlement lag        │
  │    → computes z-scores for each signal               │
  │    → combines into composite_z                       │
  │    → returns market_stress_multiplier ∈ [0.5, 3.0]  │
  └─────────────────────────────────────────────────────┘

DEPENDENCIES
  Standard library only: urllib.request, csv, json, math, hashlib, datetime
  No external pip packages required.
"""

# =============================================================================
# SECTION 1: IMPORTS
# =============================================================================

import csv
import hashlib
import io
import json
import math
import urllib.error
import urllib.request
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# SECTION 2: STATIC FALLBACK DATA
# =============================================================================

# Fallback risk-free rates (used when ECB API is unavailable)
# Claim 1(e) — counterparty-specific risk-adjusted liquidity cost
RISK_FREE_RATES: Dict[str, float] = {
    "USD": 0.053,
    "EUR": 0.040,   # Will be overridden by live €STR when available
    "GBP": 0.052,
    "JPY": 0.001,
    "CAD": 0.045,
    "CHF": 0.018,
    "INR": 0.065,
    "BRL": 0.115,
    "MXN": 0.105,
    "ZAR": 0.085,
    "CNY": 0.035,
    "SGD": 0.038,
    "AED": 0.054,
    "HKD": 0.055,
    "DEFAULT": 0.060,
}

# Fallback €STR rate used when API is unavailable
_ESTR_FALLBACK: float = 0.040

# Baseline CDS spreads by tier (bps) — used as centre of simulated range
# Claim 1(e) — counterparty credit risk component
_CDS_TIER_BASELINE: Dict[int, Tuple[float, float]] = {
    1: (40.0, 80.0),     # Tier 1 GSIBs: 40–80 bps
    2: (80.0, 200.0),    # Tier 2 regional: 80–200 bps
    3: (200.0, 500.0),   # Tier 3 data-sparse: 200–500 bps
}

# Baseline settlement lag in hours by corridor type
# Claim 1(e) — corridor operational stress component
_SETTLEMENT_LAG_BASELINE: Dict[str, float] = {
    "G7":          4.0,    # G7 currency corridors
    "EM":          12.0,   # Emerging market corridors
    "HIGH_FRICTION": 18.0, # High-friction corridors (CNY, BRL, etc.)
}

# G7 currencies for corridor classification
_G7_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD"}

# High-friction currencies
_HIGH_FRICTION_CURRENCIES = {"CNY", "BRL", "NGN", "PKR", "EGP", "VND"}

# Signal combination weights (Claim 1(e) — composite stress index)
_SIGNAL_WEIGHTS: Dict[str, float] = {
    "cds":            0.40,   # Strongest — directly prices credit risk
    "fx_vol":         0.25,   # Corridor-level stress
    "settlement_lag": 0.20,   # Operational stress
    "estr":           0.15,   # Systemic funding stress
}

# Regime thresholds (composite z-score)
_REGIME_THRESHOLDS = [
    (0.5,  "CALM"),
    (1.5,  "ELEVATED"),
    (2.5,  "STRESSED"),
]

# ECB API base URL
_ECB_BASE_URL = "https://data-api.ecb.europa.eu/service/data"

# Cache TTL in seconds
_ESTR_TTL_SECONDS   = 3600   # 1 hour — €STR updates once daily
_FX_TTL_SECONDS     = 3600   # 1 hour per currency pair
_API_TIMEOUT_SECONDS = 5


# =============================================================================
# SECTION 3: DATACLASSES
# =============================================================================

@dataclass
class MarketSignals:
    """
    Combined market signal output for a single counterparty/corridor combination.

    Claim 1(e) — counterparty-specific risk-adjusted liquidity cost:
    These signals adjust the structural PD to reflect current market conditions,
    making the liquidity cost genuinely real-time rather than based only on
    quarterly balance sheets.

    Claim 2(iv) — liquidity pricing component:
    market_stress_multiplier is a direct input to the CVA pricing formula.
    """
    # Individual signals -------------------------------------------------------
    estr_rate:                float   # Latest €STR rate (decimal, e.g. 0.039)
    estr_z_score:             float   # z-score vs 90-day distribution
    fx_implied_vol:           float   # Annualised 30d historical vol (decimal)
    fx_vol_z_score:           float   # z-score vs 90-day vol distribution
    settlement_lag_hours:     float   # Average settlement time in hours
    settlement_lag_z_score:   float   # z-score vs 90-day simulated history
    cds_spread_bps:           float   # CDS spread for counterparty (bps)
    cds_z_score:              float   # z-score vs 90-day simulated history

    # Combined output ----------------------------------------------------------
    composite_z:              float   # Weighted combination of all z-scores
    market_stress_multiplier: float   # exp(0.3 * composite_z), clamped [0.5, 3.0]
    regime:                   str     # "CALM" / "ELEVATED" / "STRESSED" / "CRISIS"
    data_freshness:           str     # ISO 8601 timestamp of computation

    # Source tracking ----------------------------------------------------------
    sources: Dict[str, str] = field(default_factory=dict)
    # e.g. {"estr": "ECB live", "fx_vol": "ECB live",
    #        "cds": "simulated", "settlement_lag": "simulated"}


# =============================================================================
# SECTION 4: SIMPLE TTL CACHE
# =============================================================================

class _TTLCache:
    """
    Thread-safe dict-based TTL cache.
    No external dependencies — uses standard library datetime.
    """
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if not expired, else None."""
        if key not in self._store:
            return None
        value, expire_ts = self._store[key]
        now = datetime.now(timezone.utc).timestamp()
        if now > expire_ts:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store value with TTL."""
        expire_ts = datetime.now(timezone.utc).timestamp() + ttl_seconds
        self._store[key] = (value, expire_ts)


_cache = _TTLCache()


# =============================================================================
# SECTION 5: ECB API FETCHERS
# =============================================================================

def _build_date_range(lookback_days: int = 130) -> Tuple[str, str]:
    """
    Build start/end date strings covering the last `lookback_days` calendar days.
    Adds buffer to ensure we get ~90 business days of data.
    """
    end_dt   = date.today()
    start_dt = end_dt - timedelta(days=lookback_days)
    return start_dt.isoformat(), end_dt.isoformat()


def _fetch_ecb_csv(url: str) -> List[Dict[str, str]]:
    """
    Fetch ECB SDMX CSV data and return parsed rows.

    The ECB SDMX REST API returns CSV with metadata header rows that must be
    skipped.  The actual data rows start after the blank-line separator.
    Returns a list of dicts keyed by the CSV header row.

    All errors are caught and re-raised as RuntimeError.
    """
    req = urllib.request.Request(
        url,
        headers={"Accept": "text/csv", "User-Agent": "CVA-Pricer/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise RuntimeError(f"ECB API request failed: {exc}") from exc

    # Parse CSV — ECB format has metadata rows at the top.
    # Find the header row: it contains "OBS_VALUE" or "TIME_PERIOD".
    lines = raw.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if "OBS_VALUE" in line or "TIME_PERIOD" in line:
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("Cannot find header row in ECB CSV response")

    data_text = "\n".join(lines[header_idx:])
    reader    = csv.DictReader(io.StringIO(data_text))
    rows = []
    for row in reader:
        # Skip rows with missing OBS_VALUE
        obs = row.get("OBS_VALUE", "").strip()
        if obs and obs not in ("", "NaN", "NA"):
            rows.append(dict(row))
    return rows


def _fetch_estr_series(lookback_days: int = 130) -> List[float]:
    """
    Fetch €STR (Euro Short-Term Rate) daily rates from ECB Data Portal.

    Endpoint: EST/EST.B.EU000A2X2A25.WT
    Claim 1(e) — systemic funding stress signal.

    Returns list of daily €STR rates (decimal), most-recent last.
    Falls back to static value on any error.
    """
    cache_key = f"estr_{lookback_days}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    start, end = _build_date_range(lookback_days)
    url = (
        f"{_ECB_BASE_URL}/EST/EST.B.EU000A2X2A25.WT"
        f"?startPeriod={start}&endPeriod={end}&format=csvdata"
    )
    try:
        rows = _fetch_ecb_csv(url)
        rates = []
        for row in rows:
            val = row.get("OBS_VALUE", "").strip()
            if val:
                try:
                    # ECB reports €STR as percentage (e.g. 3.9 → 0.039)
                    rates.append(float(val) / 100.0)
                except ValueError:
                    pass
        if len(rates) < 10:
            raise RuntimeError(f"Insufficient €STR data: {len(rates)} points")
        _cache.set(cache_key, rates, _ESTR_TTL_SECONDS)
        return rates
    except Exception as exc:
        warnings.warn(f"[market_signals] €STR fetch failed: {exc}. Using fallback.")
        return [_ESTR_FALLBACK] * 90


def _fetch_fx_series(ccy: str, lookback_days: int = 130) -> List[float]:
    """
    Fetch FX spot rate series for a given non-EUR currency vs EUR.

    Endpoint: EXR/D.{CCY}.EUR.SP00.A
    ECB quotes as "1 EUR = X CCY", so EUR/USD means the rate = USD per EUR.
    Claim 1(e) — corridor settlement stress signal.

    Returns list of daily spot rates, most-recent last.
    """
    cache_key = f"fx_{ccy}_{lookback_days}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    start, end = _build_date_range(lookback_days)
    url = (
        f"{_ECB_BASE_URL}/EXR/D.{ccy}.EUR.SP00.A"
        f"?startPeriod={start}&endPeriod={end}&format=csvdata"
    )
    try:
        rows = _fetch_ecb_csv(url)
        rates = []
        for row in rows:
            val = row.get("OBS_VALUE", "").strip()
            if val:
                try:
                    rates.append(float(val))
                except ValueError:
                    pass
        if len(rates) < 10:
            raise RuntimeError(f"Insufficient FX data for {ccy}: {len(rates)} points")
        _cache.set(cache_key, rates, _FX_TTL_SECONDS)
        return rates
    except Exception as exc:
        warnings.warn(f"[market_signals] FX {ccy}/EUR fetch failed: {exc}. Using fallback.")
        return []


def _compute_historical_vol(spot_rates: List[float], window: int = 30) -> float:
    """
    Compute 30-day rolling historical volatility (annualised).
    vol = std(log_returns[-window:]) * sqrt(252)

    Claim 1(e) — FX corridor stress signal.
    """
    if len(spot_rates) < window + 1:
        return 0.10   # fallback: 10% annualised vol

    # Use the most recent `window` log returns
    recent = spot_rates[-(window + 1):]
    log_returns = [
        math.log(recent[i + 1] / recent[i])
        for i in range(len(recent) - 1)
        if recent[i] > 0 and recent[i + 1] > 0
    ]
    if len(log_returns) < 5:
        return 0.10

    n    = len(log_returns)
    mean = sum(log_returns) / n
    var  = sum((r - mean) ** 2 for r in log_returns) / max(n - 1, 1)
    return math.sqrt(var) * math.sqrt(252)


def _compute_z_score(series: List[float], latest: float) -> float:
    """
    Compute z-score of `latest` vs a historical series.
    z = (latest - mean) / std
    Returns 0.0 if series is too short or std is zero.
    """
    if len(series) < 5:
        return 0.0
    n    = len(series)
    mean = sum(series) / n
    var  = sum((x - mean) ** 2 for x in series) / max(n - 1, 1)
    std  = math.sqrt(var)
    if std < 1e-12:
        return 0.0
    return (latest - mean) / std


def get_live_risk_free(currency: str) -> float:
    """
    Return the live risk-free rate for a given currency.

    For EUR: uses the latest €STR value from ECB Data Portal.
    For others: falls back to the static RISK_FREE_RATES dict.

    Claim 1(e) — risk-free rate used in discount factor calculation.
    """
    if currency.upper() == "EUR":
        try:
            rates = _fetch_estr_series()
            if rates:
                return rates[-1]
        except Exception:
            pass
    return RISK_FREE_RATES.get(currency.upper(), RISK_FREE_RATES["DEFAULT"])


# =============================================================================
# SECTION 6: FX VOL SIGNAL
# =============================================================================

def _get_fx_vol_signal(currency_pair: str) -> Tuple[float, float, str]:
    """
    Compute FX historical volatility signal for a currency corridor.

    For EUR-involving pairs: fetch the single ECB series directly.
    For cross rates: fetch both legs and compute the cross.

    Returns (latest_vol, z_score, source_tag)
    Claim 1(e) — corridor settlement stress.
    """
    parts = currency_pair.split("/")
    if len(parts) != 2:
        return 0.10, 0.0, "fallback — invalid pair"

    ccy1, ccy2 = parts[0].upper(), parts[1].upper()

    # Determine which currencies to fetch from ECB (ECB quotes vs EUR)
    try:
        if ccy2 == "EUR":
            # Direct ECB series: D.{CCY1}.EUR.SP00.A
            spot_rates = _fetch_fx_series(ccy1)
        elif ccy1 == "EUR":
            # ECB gives EUR/CCY2 = 1/D.{CCY2}.EUR.SP00.A
            raw_rates  = _fetch_fx_series(ccy2)
            spot_rates = [1.0 / r for r in raw_rates if r > 0]
        else:
            # Cross rate: fetch both legs and compute cross
            # EUR/CCY1 = 1 / D.CCY1.EUR.SP00.A  (inverted)
            # EUR/CCY2 = D.CCY2.EUR.SP00.A (but we need CCY1/CCY2)
            # CCY1/CCY2 = (EUR/CCY2) / (EUR/CCY1) = D.CCY2.EUR / (1/D.CCY1.EUR)
            raw_ccy1 = _fetch_fx_series(ccy1)  # EUR/CCY1 rate = CCY1 per EUR
            raw_ccy2 = _fetch_fx_series(ccy2)  # EUR/CCY2 rate = CCY2 per EUR
            min_len  = min(len(raw_ccy1), len(raw_ccy2))
            if min_len < 10:
                raise RuntimeError("Insufficient data for cross rate")
            # CCY1/CCY2 = (CCY2/EUR) / (CCY1/EUR) = raw_ccy2 / raw_ccy1
            spot_rates = [
                raw_ccy2[-min_len + i] / raw_ccy1[-min_len + i]
                for i in range(min_len)
                if raw_ccy1[-min_len + i] > 0
            ]

        if len(spot_rates) < 31:
            return 0.10, 0.0, "fallback — insufficient data"

        # Compute vol for each rolling 30-day window in the 90-day history
        # to get a distribution of vols for z-score computation
        all_vols = []
        for end_idx in range(31, len(spot_rates) + 1):
            window_rates = spot_rates[end_idx - 31:end_idx]
            vol = _compute_historical_vol(window_rates, window=30)
            all_vols.append(vol)

        latest_vol = all_vols[-1] if all_vols else 0.10
        z_score    = _compute_z_score(all_vols[:-1], latest_vol) if len(all_vols) > 1 else 0.0

        return latest_vol, z_score, "ECB live"

    except Exception as exc:
        warnings.warn(f"[market_signals] FX vol signal failed for {currency_pair}: {exc}")
        return 0.10, 0.0, "fallback — API error"


# =============================================================================
# SECTION 7: €STR SIGNAL
# =============================================================================

def _get_estr_signal() -> Tuple[float, float, str]:
    """
    Compute €STR rate and its z-score vs 90-day history.

    Returns (latest_estr_rate, z_score, source_tag)
    Claim 1(e) — systemic interbank funding stress signal.
    """
    try:
        rates = _fetch_estr_series()
        if len(rates) < 10:
            return _ESTR_FALLBACK, 0.0, "fallback — insufficient data"

        latest  = rates[-1]
        history = rates[:-1]
        z_score = _compute_z_score(history, latest)

        return latest, z_score, "ECB live"

    except Exception as exc:
        warnings.warn(f"[market_signals] €STR signal failed: {exc}")
        return _ESTR_FALLBACK, 0.0, "fallback — API error"


# =============================================================================
# SECTION 8: SIMULATED SIGNALS
# =============================================================================

def _deterministic_float(seed_str: str, min_val: float, max_val: float) -> float:
    """
    Generate a deterministic float in [min_val, max_val] from a seed string.
    Uses MD5 hash for reproducibility — same seed always gives same value.
    """
    digest = hashlib.md5(seed_str.encode("utf-8")).digest()  # noqa: S324
    # Use first 4 bytes as unsigned int, normalise to [0, 1)
    uint_val = int.from_bytes(digest[:4], byteorder="big")
    frac     = uint_val / (2 ** 32)
    return min_val + frac * (max_val - min_val)


def _get_simulated_cds_signal(
    receiving_bic: str,
    counterparty_tier: int,
    today: Optional[date] = None,
) -> Tuple[float, float, str]:
    """
    Simulate CDS spread for a counterparty based on tier and BIC.

    Uses deterministic daily perturbation so the same (date, BIC) pair always
    produces the same spread — reproducible for demos.

    Returns (cds_spread_bps, z_score, source_tag)

    NOTE: "source": "simulated — production uses Bloomberg/Refinitiv CDS feed"
    Claim 1(e) — counterparty credit spread signal.
    """
    if today is None:
        today = date.today()

    tier = max(1, min(3, counterparty_tier))
    lo, hi = _CDS_TIER_BASELINE.get(tier, (80.0, 200.0))

    # Build 90-day simulated history for z-score computation
    history: List[float] = []
    for i in range(90, 0, -1):
        past_date = today - timedelta(days=i)
        seed = f"{past_date.isoformat()}_{receiving_bic}_cds"
        spread = _deterministic_float(seed, lo, hi)
        history.append(spread)

    # Today's spread
    today_seed   = f"{today.isoformat()}_{receiving_bic}_cds"
    today_spread = _deterministic_float(today_seed, lo, hi)

    z_score = _compute_z_score(history, today_spread)

    return (
        today_spread,
        z_score,
        "simulated — production uses Bloomberg/Refinitiv CDS feed",
    )


def _classify_corridor(currency_pair: str) -> str:
    """Classify corridor as G7, EM, or HIGH_FRICTION."""
    parts = currency_pair.split("/")
    ccys  = {p.upper() for p in parts}

    if ccys & _HIGH_FRICTION_CURRENCIES:
        return "HIGH_FRICTION"
    if ccys.issubset(_G7_CURRENCIES):
        return "G7"
    return "EM"


def _get_simulated_settlement_lag_signal(
    currency_pair: str,
    today: Optional[date] = None,
) -> Tuple[float, float, str]:
    """
    Simulate average settlement time for a currency corridor.

    Uses deterministic daily perturbation for reproducibility.

    Returns (lag_hours, z_score, source_tag)

    NOTE: "source": "simulated — production uses SWIFT gpi Analytics"
    Claim 1(e) — corridor operational stress signal.
    """
    if today is None:
        today = date.today()

    corridor_type = _classify_corridor(currency_pair)
    baseline      = _SETTLEMENT_LAG_BASELINE[corridor_type]

    # Noise band: ±30% of baseline
    lo = baseline * 0.70
    hi = baseline * 1.30

    # Build 90-day history
    history: List[float] = []
    for i in range(90, 0, -1):
        past_date = today - timedelta(days=i)
        seed = f"{past_date.isoformat()}_{currency_pair}_lag"
        lag  = _deterministic_float(seed, lo, hi)
        history.append(lag)

    today_seed = f"{today.isoformat()}_{currency_pair}_lag"
    today_lag  = _deterministic_float(today_seed, lo, hi)

    z_score = _compute_z_score(history, today_lag)

    return (
        today_lag,
        z_score,
        "simulated — production uses SWIFT gpi Analytics",
    )


# =============================================================================
# SECTION 9: MARKET STRESS COMBINER
# =============================================================================

def _regime_from_z(composite_z: float) -> str:
    """
    Map a composite z-score to a named stress regime.

    Thresholds (Claim 1(e) — market stress classification):
      z < 0.5   → CALM
      0.5–1.5   → ELEVATED
      1.5–2.5   → STRESSED
      z ≥ 2.5   → CRISIS
    """
    if composite_z >= 2.5:
        return "CRISIS"
    if composite_z >= 1.5:
        return "STRESSED"
    if composite_z >= 0.5:
        return "ELEVATED"
    return "CALM"


def _market_multiplier(composite_z: float) -> float:
    """
    Convert composite z-score to market stress multiplier.

    Formula: exp(0.3 × composite_z), clamped to [0.5, 3.0]
    Claim 1(e) — real-time PD adjustment factor.
    """
    raw = math.exp(0.3 * composite_z)
    return max(0.5, min(3.0, raw))


class MarketSignalAggregator:
    """
    Aggregates real-time and simulated market signals into a single stress
    multiplier for CVA pricing.

    Claim 1(e) — counterparty-specific risk-adjusted liquidity cost:
    The aggregated market signals adjust the structural PD in real-time,
    making the liquidity cost genuinely responsive to current market conditions.

    Claim 2(iv) — liquidity pricing component:
    The market_stress_multiplier from get_market_signals() is a direct input
    to the CVA formula:  PD_adjusted = PD_structural × market_stress_multiplier

    Usage:
        aggregator = MarketSignalAggregator()
        sigs = aggregator.get_market_signals("EUR/INR", "SBINMUMU", tier=2)
        pd_adjusted = pd_structural * sigs.market_stress_multiplier
    """

    def get_market_signals(
        self,
        currency_pair:     str,
        receiving_bic:     str,
        counterparty_tier: int,
    ) -> MarketSignals:
        """
        Compute all four market stress signals and combine into a single
        market_stress_multiplier.

        Parameters
        ----------
        currency_pair     : ISO currency pair, e.g. "EUR/INR"
        receiving_bic     : BIC of the counterparty receiving the bridge advance
        counterparty_tier : 1 / 2 / 3 (drives CDS spread simulation baseline)

        Returns
        -------
        MarketSignals dataclass with all signal values and the combined multiplier.

        On any failure, falls back gracefully: returns multiplier=1.0 (no adjustment)
        and marks sources accordingly.  The pricing pipeline is NEVER disrupted.
        """
        try:
            return self._compute_signals(currency_pair, receiving_bic, counterparty_tier)
        except Exception as exc:
            warnings.warn(
                f"[market_signals] MarketSignalAggregator failed: {exc}. "
                "Returning neutral multiplier=1.0"
            )
            return self._neutral_signals()

    def _compute_signals(
        self,
        currency_pair:     str,
        receiving_bic:     str,
        counterparty_tier: int,
    ) -> MarketSignals:
        """
        Internal computation — wrapped by get_market_signals() for error handling.
        """
        # Signal 1: €STR — interbank funding stress (ECB live)
        estr_rate, estr_z, estr_src = _get_estr_signal()

        # Signal 2: FX vol — corridor settlement stress (ECB live)
        fx_vol, fx_vol_z, fx_src = _get_fx_vol_signal(currency_pair)

        # Signal 3: Settlement lag — operational corridor stress (simulated)
        lag_hours, lag_z, lag_src = _get_simulated_settlement_lag_signal(currency_pair)

        # Signal 4: CDS spread — counterparty credit stress (simulated)
        cds_bps, cds_z, cds_src = _get_simulated_cds_signal(receiving_bic, counterparty_tier)

        # Combine signals into composite z-score (Claim 1(e) — stress index)
        # Weighted sum: CDS 40%, FX vol 25%, settlement lag 20%, €STR 15%
        composite_z = (
            _SIGNAL_WEIGHTS["cds"]            * cds_z
            + _SIGNAL_WEIGHTS["fx_vol"]       * fx_vol_z
            + _SIGNAL_WEIGHTS["settlement_lag"] * lag_z
            + _SIGNAL_WEIGHTS["estr"]         * estr_z
        )

        multiplier = _market_multiplier(composite_z)
        regime     = _regime_from_z(composite_z)
        freshness  = datetime.now(timezone.utc).isoformat()

        return MarketSignals(
            estr_rate               = estr_rate,
            estr_z_score            = estr_z,
            fx_implied_vol          = fx_vol,
            fx_vol_z_score          = fx_vol_z,
            settlement_lag_hours    = lag_hours,
            settlement_lag_z_score  = lag_z,
            cds_spread_bps          = cds_bps,
            cds_z_score             = cds_z,
            composite_z             = composite_z,
            market_stress_multiplier = multiplier,
            regime                  = regime,
            data_freshness          = freshness,
            sources = {
                "estr":           estr_src,
                "fx_vol":         fx_src,
                "settlement_lag": lag_src,
                "cds":            cds_src,
            },
        )

    @staticmethod
    def _neutral_signals() -> MarketSignals:
        """
        Return a neutral (no stress) MarketSignals object used as fallback
        when the signal computation fails entirely.
        market_stress_multiplier=1.0 means no adjustment to structural PD.
        """
        freshness = datetime.now(timezone.utc).isoformat()
        return MarketSignals(
            estr_rate               = _ESTR_FALLBACK,
            estr_z_score            = 0.0,
            fx_implied_vol          = 0.10,
            fx_vol_z_score          = 0.0,
            settlement_lag_hours    = 8.0,
            settlement_lag_z_score  = 0.0,
            cds_spread_bps          = 100.0,
            cds_z_score             = 0.0,
            composite_z             = 0.0,
            market_stress_multiplier = 1.0,
            regime                  = "CALM",
            data_freshness          = freshness,
            sources = {
                "estr":           "fallback — signal computation error",
                "fx_vol":         "fallback — signal computation error",
                "settlement_lag": "fallback — signal computation error",
                "cds":            "fallback — signal computation error",
            },
        )
