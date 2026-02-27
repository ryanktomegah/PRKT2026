#!/usr/bin/env python3
"""
=============================================================================
COMPONENT 4: STREAMLIT DEMO DASHBOARD
Automated Liquidity Bridging System — Patent Spec v4.0
=============================================================================

PURPOSE
  This is the meeting-room demo interface.  A banker at a laptop can:
    1. Select any payment corridor from the dropdowns
    2. Press "Analyse Payment"
    3. See the failure probability, CVA pricing, and bridge loan offer terms
       appear in under one second — each labelled with the patent claim that
       produced it.

ARCHITECTURE
  The dashboard calls the FastAPI backend (api.py) via HTTP.  It imports
  nothing from the engine files directly — every number on screen traces
  back through the API to a live computation in Components 1, 2, or 3.

  Session statistics accumulate in st.session_state across button presses,
  so the portfolio summary updates live during the demo.

DESIGN PRINCIPLES
  ─ Patent claim labels on every output field (the demo's "secret weapon").
  ─ Color-coded risk panel (green = monitor, red = bridge loan recommended).
  ─ All numeric inputs are sliders — no typing needed for a smooth demo.
  ─ Clear error messages if the API is not running.

=============================================================================
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# =============================================================================
# SECTION 1: Configuration
# =============================================================================

API_BASE    = "http://localhost:8000"
API_TIMEOUT = 10   # seconds per request

# BIC list — matches BANK_PROFILES in failure_prediction_engine.py
# Format: (BIC, display_label)
_BICS = [
    ("DEUTDEDB", "DEUTDEDB — Deutsche Bank (EU, Tier 1)"),
    ("BNPAFRPP", "BNPAFRPP — BNP Paribas (EU, Tier 1)"),
    ("HSBCGB2L", "HSBCGB2L — HSBC (GB, Tier 1)"),
    ("BARCGB22", "BARCGB22 — Barclays (GB, Tier 1)"),
    ("CHASUSU3", "CHASUSU3 — JPMorgan Chase (US, Tier 1)"),
    ("CITIUS33", "CITIUS33 — Citibank (US, Tier 1)"),
    ("BOFAUS3N", "BOFAUS3N — Bank of America (US, Tier 1)"),
    ("UBSWCHZH", "UBSWCHZH — UBS (CH, Tier 1)"),
    ("ABNANL2A", "ABNANL2A — ABN AMRO (EU, Tier 2)"),
    ("INGBNL2A", "INGBNL2A — ING (EU, Tier 2)"),
    ("MHCBJPJT", "MHCBJPJT — Mizuho (JP, Tier 2)"),
    ("BOTKJPJT", "BOTKJPJT — MUFG (JP, Tier 2)"),
    ("SMBCJPJT", "SMBCJPJT — SMBC (JP, Tier 2)"),
    ("BCITITMM", "BCITITMM — Intesa Sanpaolo (EU, Tier 2)"),
    ("RBOSGB2L", "RBOSGB2L — NatWest (GB, Tier 2)"),
    ("CMCIFRPP", "CMCIFRPP — Crédit Mutuel (EU, Tier 2)"),
    ("PARBFRPP", "PARBFRPP — BNP Subsidiary (EU, Tier 2)"),
    ("ICICINBB", "ICICINBB — ICICI Bank India (IN, Tier 3)"),
    ("HDFCINBB", "HDFCINBB — HDFC Bank India (IN, Tier 3)"),
    ("ITAUBRSP", "ITAUBRSP — Itaú Unibanco Brazil (BR, Tier 3)"),
]
_BIC_OPTIONS   = [b[0] for b in _BICS]
_BIC_LABELS    = {b[0]: b[1] for b in _BICS}

_CORRIDORS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "EUR/GBP", "USD/CHF",
    "AUD/USD", "USD/CAD", "EUR/JPY", "GBP/JPY", "EUR/CHF",
    "USD/INR", "EUR/INR", "USD/BRL", "EUR/BRL", "GBP/INR",
]

_STATUSES = ["PDNG", "RJCT", "ACSP", "PART"]
_STATUS_DESC = {
    "PDNG": "PDNG — Pending settlement",
    "RJCT": "RJCT — Rejected by network",
    "ACSP": "ACSP — Accepted",
    "PART": "PART — Partial acceptance (liquidity stress)",
}


# =============================================================================
# SECTION 2: Page setup
# =============================================================================

st.set_page_config(
    page_title="Automated Liquidity Bridging System",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS — minimal styling for a clean demo look
st.markdown("""
<style>
  .risk-high   { background:#fff0f0; border-left:4px solid #d62728; padding:12px; border-radius:4px; }
  .risk-low    { background:#f0fff4; border-left:4px solid #2ca02c; padding:12px; border-radius:4px; }
  .claim-tag   { font-size:0.72em; color:#5a5a8a; font-style:italic; }
  .panel-title { font-size:1.1em; font-weight:700; color:#1a1a2e; margin-bottom:8px; }
  .metric-val  { font-size:1.6em; font-weight:800; }
  .apr-high    { color:#d62728; }
  .apr-low     { color:#2ca02c; }
  div[data-testid="stHorizontalBlock"] { gap: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SECTION 3: Session state initialisation
# =============================================================================
#
# Portfolio statistics accumulate across button presses in the session.
# Recall rate = (number flagged for bridging) / (total analysed).

def _init_session():
    defaults = {
        "total_analysed":   0,
        "total_flagged":    0,
        "total_advance_usd": 0.0,
        "apr_sum":          0.0,
        "apr_count":        0,
        # last results
        "last_score":    None,
        "last_price":    None,
        "last_execute":  None,
        "last_error":    None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()


# =============================================================================
# SECTION 4: API helpers
# =============================================================================

def _api_health() -> Optional[Dict]:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.json() if r.ok else None
    except Exception:
        return None


def _api_score(payload: Dict) -> Optional[Dict]:
    try:
        r = requests.post(f"{API_BASE}/score", json=payload, timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.session_state["last_error"] = f"/score HTTP {e.response.status_code}: {e.response.text[:300]}"
        return None
    except Exception as e:
        st.session_state["last_error"] = f"/score error: {str(e)}"
        return None


def _api_price(payload: Dict) -> Optional[Dict]:
    try:
        r = requests.post(f"{API_BASE}/price", json=payload, timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.session_state["last_error"] = f"/price HTTP {e.response.status_code}: {e.response.text[:300]}"
        return None
    except Exception as e:
        st.session_state["last_error"] = f"/price error: {str(e)}"
        return None


def _api_execute(payload: Dict) -> Optional[Dict]:
    try:
        r = requests.post(f"{API_BASE}/execute", json=payload, timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.session_state["last_error"] = f"/execute HTTP {e.response.status_code}: {e.response.text[:300]}"
        return None
    except Exception as e:
        st.session_state["last_error"] = f"/execute error: {str(e)}"
        return None


# =============================================================================
# SECTION 5: Page header
# =============================================================================

st.markdown("## 🏦 Automated Liquidity Bridging System")
st.markdown(
    "**Patent-backed proof-of-concept** · Three-component pipeline: "
    "failure prediction → CVA pricing → bridge loan execution. "
    "Every output labelled with the patent claim that produced it."
)

# Health status banner
health = _api_health()
if health and health.get("model_ready"):
    st.success(
        f"✅ API ready — model AUC {health.get('model_auc', '?'):.3f} | "
        f"Threshold {health.get('threshold', '?'):.3f} | "
        f"Recall {health.get('model_recall', '?'):.3f}"
    )
else:
    st.error(
        "⚠️ API not reachable. Start the backend first: "
        "`uvicorn api:app --host 0.0.0.0 --port 8000`"
    )

st.divider()

# =============================================================================
# SECTION 6: Layout — two columns
# =============================================================================

col_input, col_results = st.columns([1, 2], gap="large")

# =============================================================================
# SECTION 7: LEFT PANEL — Payment input controls
# =============================================================================

with col_input:
    st.markdown("### Payment Input")
    st.caption("Configure a payment and press Analyse to run the full three-component pipeline.")

    # Sender / receiver BIC dropdowns
    sending_idx  = st.selectbox(
        "Sending BIC",
        options=range(len(_BIC_OPTIONS)),
        format_func=lambda i: _BICS[i][1],
        index=0,
        help="Sending institution — Claim 1(b): counterparty performance history",
    )
    sending_bic = _BIC_OPTIONS[sending_idx]

    receiving_idx = st.selectbox(
        "Receiving BIC",
        options=range(len(_BIC_OPTIONS)),
        format_func=lambda i: _BICS[i][1],
        index=13,   # default: ICICINBB (India, Tier 3) — higher risk for demo
        help="Receiving institution — determines CVA tier and LGD corridor",
    )
    receiving_bic = _BIC_OPTIONS[receiving_idx]

    # Currency pair
    corridor_idx = st.selectbox(
        "Currency Pair",
        options=range(len(_CORRIDORS)),
        format_func=lambda i: _CORRIDORS[i],
        index=11,  # default: EUR/INR — exotic, high corridor risk
        help="Claim 1(b)(iv): routing characteristics",
    )
    currency_pair = _CORRIDORS[corridor_idx]

    # Amount
    amount_usd = st.slider(
        "Payment Amount (USD)",
        min_value=10_000,
        max_value=5_000_000,
        value=250_000,
        step=10_000,
        format="$%d",
        help="Exposure at Default (EAD) for CVA calculation",
    )

    # Submission hour
    hour_of_day = st.slider(
        "Submission Hour (UTC)",
        min_value=0,
        max_value=23,
        value=15,
        help="Claim 1(b)(v): temporal risk factor — 15:00–17:00 is end-of-day stress window",
    )

    # Payment status
    status_idx = st.selectbox(
        "Payment Status (pacs.002)",
        options=range(len(_STATUSES)),
        format_func=lambda i: _STATUS_DESC[_STATUSES[i]],
        index=0,
        help="Claim 1(b)(i): payment processing status — Dep. D1: ISO 20022 codes",
    )
    payment_status = _STATUSES[status_idx]

    # Advanced options (collapsed by default — don't distract in a demo)
    with st.expander("Advanced options", expanded=False):
        settlement_lag   = st.slider("Settlement Lag (days)", 0, 5, 1)
        prior_rejections = st.slider("Prior Rejections (last 30d)", 0, 10, 0)
        data_quality     = st.slider("Data Quality Score", 0.3, 1.0, 0.92, step=0.01)
        correspondent_d  = st.slider("Correspondent Depth", 1, 5, 2)
        message_priority = st.selectbox("Message Priority", ["NORM", "HIGH", "URGP"])

    st.divider()

    # The main button
    analyse_clicked = st.button(
        "🔍 Analyse Payment",
        type="primary",
        use_container_width=True,
    )

    # Quick preset buttons for demo convenience
    st.caption("Quick presets:")
    col_p1, col_p2, col_p3 = st.columns(3)
    preset_low  = col_p1.button("Low Risk",  use_container_width=True)
    preset_high = col_p2.button("High Risk", use_container_width=True)
    preset_rjct = col_p3.button("Rejected",  use_container_width=True)


# =============================================================================
# SECTION 8: Preset handling
# =============================================================================
#
# These presets let the demo operator quickly jump to interesting scenarios
# without fumbling with sliders in front of a banker.

_preset_payloads = {
    "low": {
        "sending_bic": "DEUTDEDB", "receiving_bic": "BNPAFRPP",
        "currency_pair": "EUR/USD", "amount_usd": 100_000,
        "hour_of_day": 10, "payment_status": "ACSP",
        "settlement_lag_days": 1, "prior_rejections_30d": 0,
        "data_quality_score": 0.97, "correspondent_depth": 1,
        "message_priority": "NORM",
    },
    "high": {
        "sending_bic": "ICICINBB", "receiving_bic": "ITAUBRSP",
        "currency_pair": "USD/BRL", "amount_usd": 750_000,
        "hour_of_day": 16, "payment_status": "PDNG",
        "settlement_lag_days": 0, "prior_rejections_30d": 3,
        "data_quality_score": 0.62, "correspondent_depth": 4,
        "message_priority": "URGP",
    },
    "rjct": {
        "sending_bic": "HDFCINBB", "receiving_bic": "ITAUBRSP",
        "currency_pair": "USD/INR", "amount_usd": 1_500_000,
        "hour_of_day": 17, "payment_status": "RJCT",
        "settlement_lag_days": 0, "prior_rejections_30d": 5,
        "data_quality_score": 0.55, "correspondent_depth": 5,
        "message_priority": "NORM",
    },
}

_active_payload = None
if preset_low:
    _active_payload = _preset_payloads["low"]
elif preset_high:
    _active_payload = _preset_payloads["high"]
elif preset_rjct:
    _active_payload = _preset_payloads["rjct"]
elif analyse_clicked:
    _active_payload = {
        "sending_bic":         sending_bic,
        "receiving_bic":       receiving_bic,
        "currency_pair":       currency_pair,
        "amount_usd":          float(amount_usd),
        "hour_of_day":         int(hour_of_day),
        "payment_status":      payment_status,
        "settlement_lag_days": settlement_lag,
        "prior_rejections_30d": prior_rejections,
        "data_quality_score":  data_quality,
        "correspondent_depth": correspondent_d,
        "message_priority":    message_priority,
    }


# =============================================================================
# SECTION 9: Run the three-component pipeline on button press
# =============================================================================

if _active_payload is not None:
    st.session_state["last_error"] = None

    with st.spinner("Running three-component pipeline …"):
        t_total = time.perf_counter()

        # ── Component 1: /score ────────────────────────────────────────────
        score_result = _api_score(_active_payload)

        if score_result:
            # Build the /price request from the score output
            price_payload = {
                "uetr":               score_result["uetr"],
                "pd":                 score_result["failure_probability"],
                "ead":                score_result["amount_usd"],
                "currency_pair":      score_result["currency_pair"],
                "sending_bic":        score_result["sending_bic"],
                "receiving_bic":      score_result["receiving_bic"],
                "settlement_lag_days": score_result["settlement_lag_days"],
                "payment_status":     score_result["payment_status"],
                "top_risk_factors":   score_result["top_risk_factors"],
                "threshold_exceeded": score_result["threshold_exceeded"],
                "forward_risk_horizon": "reactive",
            }

            # ── Component 2: /price ────────────────────────────────────────
            price_result = _api_price(price_payload)

            if price_result:
                # Build the /execute request from the price output
                execute_payload = {
                    "uetr":                  price_result["uetr"],
                    "currency_pair":         price_result["currency_pair"],
                    "sending_bic":           price_result["sending_bic"],
                    "receiving_bic":         price_result["receiving_bic"],
                    "counterparty_name":     price_result["counterparty_name"],
                    "counterparty_tier":     price_result["counterparty_tier"],
                    "ead_usd":               price_result["ead_usd"],
                    "bridge_horizon_days":   price_result["bridge_horizon_days"],
                    "annualized_rate_bps":   price_result["annualized_rate_bps"],
                    "apr_decimal":           price_result["apr_decimal"],
                    "cva_cost_rate_annual":  price_result["cva_cost_rate_annual"],
                    "funding_spread_bps":    price_result["funding_spread_bps"],
                    "net_margin_bps":        price_result["net_margin_bps"],
                    "expected_profit_usd":   price_result["expected_profit_usd"],
                    "offer_valid_seconds":   price_result["offer_valid_seconds"],
                    "pd_tier_used":          price_result["counterparty_tier"],
                    "pd_structural":         price_result["pd_structural"],
                    "pd_ml_signal":          price_result["pd_ml_signal"],
                    "pd_blended":            price_result["pd_blended"],
                    "lgd_estimate":          price_result["lgd_estimate"],
                    "expected_loss_usd":     price_result["expected_loss_usd"],
                    "discount_factor":       price_result["discount_factor"],
                    "risk_free_rate":        price_result["risk_free_rate"],
                    "pd_model_diagnostics":  price_result["pd_model_diagnostics"],
                    "lgd_model_diagnostics": price_result["lgd_model_diagnostics"],
                    "top_risk_factors":      price_result["top_risk_factors"],
                    "threshold_exceeded":    price_result["threshold_exceeded"],
                }

                # ── Component 3: /execute ──────────────────────────────────
                execute_result = _api_execute(execute_payload)

                if execute_result:
                    # Store results and update portfolio stats
                    st.session_state["last_score"]   = score_result
                    st.session_state["last_price"]   = price_result
                    st.session_state["last_execute"] = execute_result

                    st.session_state["total_analysed"] += 1
                    if score_result["threshold_exceeded"]:
                        st.session_state["total_flagged"]     += 1
                        st.session_state["total_advance_usd"] += score_result["amount_usd"]
                        st.session_state["apr_sum"]           += price_result["annualized_rate_bps"]
                        st.session_state["apr_count"]         += 1

        elapsed_ms = (time.perf_counter() - t_total) * 1000

    if st.session_state.get("last_error"):
        with col_results:
            st.error(f"Pipeline error: {st.session_state['last_error']}")


# =============================================================================
# SECTION 10: RIGHT PANEL — Results
# =============================================================================

with col_results:
    score_r   = st.session_state.get("last_score")
    price_r   = st.session_state.get("last_price")
    execute_r = st.session_state.get("last_execute")

    if not score_r:
        st.info("Press **Analyse Payment** to run the pipeline. Results will appear here.")
    else:
        # ─────────────────────────────────────────────────────────────────
        # PANEL 1: Risk assessment (Component 1)
        # ─────────────────────────────────────────────────────────────────
        prob       = score_r["failure_probability"]
        threshold  = score_r["decision_threshold"]
        exceeded   = score_r["threshold_exceeded"]
        rec        = score_r["bridge_recommendation"]
        conf_label = "High confidence" if score_r["is_high_confidence"] else "Low confidence"

        panel_class = "risk-high" if exceeded else "risk-low"
        panel_icon  = "🔴" if exceeded else "🟢"

        st.markdown(f"""
<div class="{panel_class}">
<div class="panel-title">{panel_icon} PANEL 1 — Failure Risk Assessment</div>
</div>
""", unsafe_allow_html=True)

        r1c1, r1c2, r1c3 = st.columns(3)
        r1c1.metric(
            "Failure Probability",
            f"{prob:.1%}",
            delta=f"{prob - threshold:+.1%} vs threshold",
            delta_color="inverse",
        )
        r1c2.metric("Decision Threshold", f"{threshold:.1%}")
        r1c3.metric("Recommendation", rec, delta=conf_label)

        st.caption(
            "**Claim 1(c)** — LightGBM gradient-boosting + isotonic calibration  ·  "
            f"**Dep. D3** — F-beta (β=2) threshold = {threshold:.3f}, recall-weighted  ·  "
            "**Dep. D1** — ISO 20022 pacs.002 field names"
        )

        # SHAP explanations
        st.markdown("**Top 3 Risk Factors** (SHAP attribution — Claim 1(b) feature set)")
        for i, rf in enumerate(score_r.get("top_risk_factors", [])[:3], 1):
            direction_icon = "⬆" if rf["direction"] == "raises" else "⬇"
            shap_val = rf["shap_value"]
            st.markdown(
                f"**{i}.** `{rf['feature']}` {direction_icon} "
                f"— {rf['description']}  "
                f"*(SHAP={shap_val:+.4f}, value={rf['value']:.3f})*"
            )

        st.caption(f"UETR: `{score_r['uetr']}`  ·  Inference: {score_r['inference_latency_ms']:.1f}ms")
        st.divider()

        # ─────────────────────────────────────────────────────────────────
        # PANEL 2: CVA Pricing (Component 2)
        # ─────────────────────────────────────────────────────────────────
        if price_r:
            apr_bps  = price_r["annualized_rate_bps"]
            apr_col  = "apr-high" if apr_bps > 400 else "apr-low"

            st.markdown("""
<div style="background:#f5f5ff; border-left:4px solid #2255cc; padding:12px; border-radius:4px;">
<div class="panel-title">🔷 PANEL 2 — CVA Pricing</div>
</div>
""", unsafe_allow_html=True)

            r2c1, r2c2, r2c3 = st.columns(3)
            r2c1.metric("Counterparty",   price_r["counterparty_name"])
            r2c2.metric("PD Model",       price_r["pd_tier_label"].split(" — ")[0])
            r2c3.metric(
                "Bridge Loan APR",
                f"{apr_bps:.1f} bps",
                delta=f"({price_r['apr_decimal']:.2%})",
            )

            r2c1b, r2c2b, r2c3b = st.columns(3)
            r2c1b.metric(
                "Structural PD",
                f"{price_r['pd_structural']:.5%}",
                help="Credit risk PD — used in CVA formula",
            )
            r2c2b.metric(
                "ML Signal (operational)",
                f"{price_r['pd_ml_signal']:.2%}",
                help="Payment failure probability from Component 1 — NOT in CVA formula",
            )
            r2c3b.metric("LGD", f"{price_r['lgd_estimate']:.1%}")

            r2c1c, r2c2c, r2c3c = st.columns(3)
            r2c1c.metric("Expected Loss",    f"${price_r['expected_loss_usd']:,.2f}")
            r2c2c.metric("EAD (Loan Size)",  f"${price_r['ead_usd']:,.0f}")
            r2c3c.metric("Discount Factor",  f"{price_r['discount_factor']:.6f}")

            st.caption(
                f"**Claim 1(e)** — EL = PD × EAD × LGD × DF; APR = (EL/EAD)/T + spread + margin  ·  "
                f"**{price_r['pd_tier_label']}**  ·  "
                "**Dep. D7** — LGD floor 0.30 (receivable assignment)"
            )

            # APR breakdown table
            with st.expander("APR component breakdown", expanded=False):
                st.markdown(f"""
| Component | Value |
|-----------|-------|
| CVA cost rate (annualised) | {price_r['cva_cost_rate_annual']:.4%} |
| Funding spread | {price_r['funding_spread_bps']:.1f} bps |
| Operational margin | {price_r['net_margin_bps']:.1f} bps |
| **Total APR** | **{apr_bps:.1f} bps** |
| Risk-free rate | {price_r['risk_free_rate']:.2%} |
| Horizon | {price_r['bridge_horizon_days']} days |
""")
            st.divider()

        # ─────────────────────────────────────────────────────────────────
        # PANEL 3: Bridge Loan Offer (Component 3)
        # ─────────────────────────────────────────────────────────────────
        if execute_r:
            offer_status = execute_r["offer_status"]
            status_icons = {"ACCEPTED": "✅", "REJECTED": "❌", "EXPIRED": "⏱"}
            s_icon = status_icons.get(offer_status, "?")

            bg_col = (
                "#f0fff4" if offer_status == "ACCEPTED"
                else "#fff0f0" if offer_status == "REJECTED"
                else "#fffbf0"
            )
            border_col = (
                "#2ca02c" if offer_status == "ACCEPTED"
                else "#d62728" if offer_status == "REJECTED"
                else "#ff7f0e"
            )

            st.markdown(f"""
<div style="background:{bg_col}; border-left:4px solid {border_col}; padding:12px; border-radius:4px;">
<div class="panel-title">{s_icon} PANEL 3 — Bridge Loan Offer (Claim 5)</div>
</div>
""", unsafe_allow_html=True)

            r3c1, r3c2 = st.columns(2)
            r3c1.metric("Offer Status",    f"{s_icon} {offer_status}")
            r3c2.metric("Loan ID",         execute_r["loan_id"])

            r3c1b, r3c2b, r3c3b = st.columns(3)
            r3c1b.metric("Advance Amount",  f"${execute_r['advance_amount_usd']:,.0f}")
            r3c2b.metric("Total Cost",      f"${execute_r['total_cost_usd']:,.2f}")
            r3c3b.metric("APR",             f"{execute_r['apr_bps']:.1f} bps")

            st.markdown(f"""
| Field | Value | Claim |
|-------|-------|-------|
| UETR | `{execute_r['uetr']}` | Claim 3(k) — SWIFT gpi token binding |
| Collateral | {execute_r['collateral_type']} | Dep. D7 — receivable assignment |
| Repayment trigger | {execute_r['repayment_trigger']} | Claim 5(v) |
| Settlement source | {execute_r['settlement_source']} | Dep. D11 |
| Settlement status | `{execute_r['settlement_status']}` | Claim 5(x) — audit record |
| Horizon | {execute_r['offer_horizon_days']} days | Claim 1(f) |
""")

            if execute_r.get("security_assignment"):
                st.info(f"🔒 **Security Interest (Claim 3(m)):** {execute_r['security_assignment']}")

            st.caption(
                "**Claim 1(f)** — offer generated  ·  "
                "**Claim 1(h)** — auto-repayment on settlement  ·  "
                "**Claim 5(t–x)** — full settlement-confirmation loop"
            )


# =============================================================================
# SECTION 11: Portfolio summary (updates live)
# =============================================================================

st.divider()
st.markdown("### Session Portfolio Summary")
st.caption(
    "Aggregate statistics across all payments analysed in this session. "
    "Updates each time Analyse Payment is pressed."
)

total   = st.session_state["total_analysed"]
flagged = st.session_state["total_flagged"]
advance = st.session_state["total_advance_usd"]
apr_avg = (
    st.session_state["apr_sum"] / st.session_state["apr_count"]
    if st.session_state["apr_count"] > 0 else 0.0
)
recall_rate = flagged / total if total > 0 else 0.0

pcol1, pcol2, pcol3, pcol4, pcol5 = st.columns(5)
pcol1.metric("Payments Analysed",   total)
pcol2.metric("Flagged for Bridge",  flagged,  delta=f"{recall_rate:.1%} rate")
pcol3.metric("Total Advance Pool",  f"${advance:,.0f}")
pcol4.metric("Average APR",         f"{apr_avg:.1f} bps" if apr_avg > 0 else "—")
pcol5.metric("Recall Rate",         f"{recall_rate:.1%}" if total > 0 else "—",
             help="Payments recommended for bridge / total analysed")

st.caption(
    "**Claim 2(vi)** — settlement monitoring component tracks all active loans  ·  "
    "**Dep. D9** — sub-100ms inference enables real-time stream processing"
)

# Small reset button
if st.button("Reset session stats", type="secondary"):
    for key in ["total_analysed","total_flagged","total_advance_usd",
                "apr_sum","apr_count","last_score","last_price","last_execute","last_error"]:
        st.session_state[key] = 0 if isinstance(st.session_state[key], (int, float)) else None
    st.rerun()
