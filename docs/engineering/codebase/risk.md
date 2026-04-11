# `lip/risk/` — Portfolio-Level Risk

> **Portfolio-level risk modules.** Where C2 prices a single bridge loan's PD, `lip/risk/` measures the risk of the entire outstanding LIP portfolio: VaR via Monte Carlo, concentration metrics, stress tests, and aggregate portfolio statistics. Used by the BPI admin dashboard and the portfolio reporting API (GAP-07, GAP-15).

**Source:** `lip/risk/`
**Module count:** 4 modules + empty `__init__.py`

---

## Purpose

C2 (PD model) prices the credit risk of an individual bridge loan at offer time. That is necessary but not sufficient: a portfolio of 10,000 loans, each priced correctly in isolation, can still have unacceptable portfolio-level risk if it is concentrated in a single corridor, a single counterparty, or a single failure mode.

`lip/risk/` provides the portfolio-level view. It is consumed by:

- `lip/api/portfolio_router.py` — the MLO-facing portfolio reporting API (closes GAP-07)
- `lip/api/admin_router.py` — the BPI admin dashboard (closes GAP-15)
- The DORA / SR 11-7 reports emitted via `lip/common/regulatory_reporter.py` (closes GAP-14)

It is **not** consumed by the base pipeline — `lip/pipeline.py` does not call into `lip/risk/`. Portfolio-level risk is a reporting concern, not a per-payment decision concern. A pilot bank's MLO uses these numbers to set their risk appetite (which then becomes per-licensee caps in the C8 license token); the per-payment gate is handled by C2 and C6 against those caps, not by `lip/risk/`.

---

## Modules

| File | Lines | Purpose |
|------|-------|---------|
| `var_monte_carlo.py` | 327 | Monte Carlo Value-at-Risk simulation over the outstanding loan book. Samples PD draws per loan, aggregates to portfolio losses, computes VaR at configurable confidence levels (typically 95% / 99% / 99.5%). The Monte Carlo path is used (rather than analytical VaR) because LIP loans have heavy correlation through corridor and counterparty channels that closed-form VaR cannot capture cleanly. |
| `concentration.py` | 147 | Portfolio concentration metrics — Herfindahl–Hirschman Index over corridors, counterparties, and rejection-code classes; single-name exposure flags; corridor-level exposure thresholds. **Distinct from `lip/p10_regulatory_data/concentration.py`**: that one is privacy-preserving and regulator-facing; this one is internal portfolio management against the live book. |
| `portfolio_risk.py` | 320 | The top-level portfolio aggregator. Composes `var_monte_carlo`, `concentration`, and `stress_testing` into the single object consumed by `portfolio_router` and the BPI admin dashboard. |
| `stress_testing.py` | 172 | Scenario-based stress tests — corridor stress (USD/EUR liquidity dries up), single-name stress (a top-10 counterparty defaults), correlated cascade stress (multi-corridor failure cluster). Outputs are scenario-loss tables, not single VaR numbers, because the stress-testing audience is the MLO's risk committee, not a real-time gate. |

---

## Why `__init__.py` is empty

There is no convenience facade and no `__all__`. Every caller imports the specific class it needs: `from lip.risk.var_monte_carlo import VaRMonteCarlo`, `from lip.risk.portfolio_risk import PortfolioRiskAggregator`. This is intentional — the four modules are independent enough that a facade would obscure which one a caller actually depends on, and the dependency clarity matters when SR 11-7 model governance asks "what feeds into this number?"

---

## Distinction from `lip/p5_cascade_engine/` and `lip/p10_regulatory_data/`

| Layer | Audience | Time horizon | Privacy |
|-------|----------|--------------|---------|
| `lip/c2_pd_model/` | C2 (per-payment, real-time) | Per-payment | N/A |
| `lip/risk/` | MLO + BPI admin (internal portfolio reporting) | Daily / on-demand | Internal — full identity preserved |
| `lip/p5_cascade_engine/` | C7 + cascade_router (operational intervention) | Real-time | Internal |
| `lip/p10_regulatory_data/` | External regulators | Periodic batch | k-anonymous + differentially private |

A single change to the loan book ripples through all four layers, but they answer different questions for different audiences. Do not collapse them.

## Cross-references

- **HTTP consumers**: `lip/api/portfolio_router.py`, `lip/api/admin_router.py` (see [`api.md`](api.md))
- **Per-payment risk**: `lip/c2_pd_model/` and the canonical spec at `consolidation files/BPI_C2_Component_Spec_v1.0.md`
- **Privacy-preserving regulatory analytics**: `lip/p10_regulatory_data/` (see [`p10_regulatory_data.md`](p10_regulatory_data.md))
- **Cascade-aware portfolio view**: `lip/p5_cascade_engine/` (see [`p5_cascade_engine.md`](p5_cascade_engine.md))
- **DORA reporting**: `lip/common/regulatory_reporter.py` (see [`common.md`](common.md))
