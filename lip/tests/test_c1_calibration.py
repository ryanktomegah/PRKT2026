"""
test_c1_calibration.py — Verification of C1 probability calibration.
Part of Tier 1 R&D: Algorithmic Pedigree.
"""
from unittest.mock import MagicMock

import numpy as np
import pytest

from lip.c1_failure_classifier.calibration import IsotonicCalibrator, compute_ece
from lip.c1_failure_classifier.model import ClassifierModel


def test_calibrator_fit_uses_public_api():
    """Calibrator state must be set via .fit(), not private attributes."""
    calib = IsotonicCalibrator()
    assert not calib._is_fitted
    calib.fit(np.array([0.1, 0.5, 0.9]), np.array([0, 1, 1]))
    assert calib._is_fitted


def test_ece_improves_after_calibration():
    """ECE after isotonic fit must be <= ECE before on the same data."""
    rng = np.random.default_rng(42)
    raw = rng.uniform(0, 1, 200)
    # Deliberately miscalibrated: true positives concentrated at low scores
    y = (raw < 0.3).astype(int)
    ece_before = compute_ece(y, raw)
    calib = IsotonicCalibrator()
    calib.fit(raw, y)
    ece_after = compute_ece(y, calib.predict(raw))
    # Isotonic calibration should never make ECE worse on its own training data
    assert ece_after <= ece_before, (
        f"Calibration must not degrade ECE: {ece_before:.4f} → {ece_after:.4f}"
    )


def test_calibration_not_applied_when_unfitted():
    """predict_proba must return raw score when calibrator is not fitted."""
    mlp = MagicMock()
    mlp.forward.return_value = 0.75
    # Mocks for other components
    gs = MagicMock()
    tt = MagicMock()
    model = ClassifierModel(gs, tt, mlp)

    # Ensure it's not fitted
    assert not model.calibrator._is_fitted

    result = model.predict_proba(np.zeros(8), [], [], np.zeros(88))
    assert result == pytest.approx(0.75)


def test_ece_argument_order():
    """Verify compute_ece(y_true, y_prob) order."""
    # If y_true=0.1 (impossible) and y_prob=[0,1], ECE calculation would behave differently.
    # We test with a known case where y_true is binary.
    y_true = np.array([1, 0, 0, 0])
    y_prob = np.array([0.25, 0.25, 0.25, 0.25])
    # Mean confidence = 0.25, Fraction positive = 0.25 -> ECE = 0
    ece = compute_ece(y_true, y_prob, n_bins=4)
    assert ece == pytest.approx(0.0)

    # Swapped case (if it accepted probs first)
    # If the function expects (y_true, y_prob), then:
    # compute_ece([1,0,0,0], [0.9, 0.9, 0.9, 0.9]) should be 0.65
    # bin 0.75-1.0: count=4, mean_conf=0.9, frac_pos=0.25 -> |0.9-0.25| = 0.65
    ece_bad = compute_ece(np.array([1, 0, 0, 0]), np.array([0.9, 0.9, 0.9, 0.9]), n_bins=10)
    assert ece_bad == pytest.approx(0.65)
