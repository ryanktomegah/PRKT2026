"""
test_merton_solver.py — Verification of Merton-KMV iterative solver.
Part of Tier 1 R&D: Algorithmic Pedigree.
"""
import math

import pytest

from lip.c2_pd_model.merton_kmv import MertonKMVSolver, _norm_cdf


def test_merton_solver_convergence():
    """Verify that the solver recovers known V_A and sigma_A from generated V_E and sigma_E."""
    # Known Asset params
    v_a_true = 1500.0
    sigma_a_true = 0.20
    debt = 1000.0
    risk_free = 0.05
    T = 1.0

    # Generate V_E and sigma_E from true asset params (Forward Black-Scholes)
    d1 = (math.log(v_a_true / debt) + (risk_free + 0.5 * sigma_a_true**2) * T) / (sigma_a_true * math.sqrt(T))
    d2 = d1 - sigma_a_true * math.sqrt(T)

    v_e_true = v_a_true * _norm_cdf(d1) - debt * math.exp(-risk_free * T) * _norm_cdf(d2)
    # sigma_E * V_E = N(d1) * sigma_A * V_A
    sigma_e_true = (_norm_cdf(d1) * sigma_a_true * v_a_true) / v_e_true

    # Now try to back out V_A and sigma_A using solver
    solver = MertonKMVSolver(tolerance=1e-8)
    v_a_calc, sigma_a_calc, dd = solver.solve(v_e_true, sigma_e_true, debt, risk_free, T)

    assert v_a_calc == pytest.approx(v_a_true, rel=1e-4)
    assert sigma_a_calc == pytest.approx(sigma_a_true, rel=1e-4)
    assert dd > 0

def test_merton_solver_high_risk():
    """Verify solver handles a high-risk (distressed) scenario."""
    # V_E is very small relative to debt
    v_e = 50.0
    sigma_e = 1.50
    debt = 1000.0
    risk_free = 0.03
    T = 1.0

    solver = MertonKMVSolver()
    v_a, sigma_a, dd = solver.solve(v_e, sigma_e, debt, risk_free, T)

    # Asset value should be slightly above debt or equal if distressed
    assert v_a > 0
    # DD should be very low or negative
    assert dd < 1.0

def test_merton_degenerate_inputs():
    solver = MertonKMVSolver()
    # Zero debt
    v_a, sigma_a, dd = solver.solve(100, 0.2, 0, 0.05, T=1.0)
    assert v_a == 0.0 # Handled by if-statement

def test_short_horizon_t():
    v_e, sigma_e, debt, rf = 120.0, 0.30, 100.0, 0.05
    solver = MertonKMVSolver()
    _, _, dd_annual = solver.solve(v_e, sigma_e, debt, rf, T=1.0)
    _, _, dd_7day  = solver.solve(v_e, sigma_e, debt, rf, T=7/365)
    assert dd_7day > dd_annual

def test_distressed_firm_returns_negative_dd():
    solver = MertonKMVSolver()
    _, _, dd = solver.solve(50.0, 1.50, 1000.0, 0.03, T=1.0)
    assert math.isfinite(dd)
    assert dd < 0
