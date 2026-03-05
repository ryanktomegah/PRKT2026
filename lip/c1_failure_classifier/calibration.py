"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

calibration.py — Isotonic/Platt calibration and ECE computation
"""

from __future__ import annotations

import logging
from typing import Literal, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IsotonicCalibrator — PAVA
# ---------------------------------------------------------------------------

class IsotonicCalibrator:
    """Isotonic regression calibrator using the Pool Adjacent Violators (PAVA) algorithm.

    Fits a non-decreasing step function mapping raw classifier scores to
    calibrated probabilities.  Appropriate when the calibration curve is
    monotone but not necessarily linear.

    Attributes
    ----------
    _x_:
        Knot positions (raw scores) after fitting.
    _y_:
        Calibrated probability at each knot.
    """

    def __init__(self) -> None:
        self._x_: Optional[np.ndarray] = None
        self._y_: Optional[np.ndarray] = None

    def fit(self, scores: np.ndarray, y_true: np.ndarray) -> "IsotonicCalibrator":
        """Fit the isotonic regression on calibration data.

        Parameters
        ----------
        scores:
            Raw model scores (not necessarily probabilities), shape ``(n,)``.
        y_true:
            Binary ground-truth labels, shape ``(n,)``.

        Returns
        -------
        IsotonicCalibrator
            Self (for chaining).
        """
        scores = np.asarray(scores, dtype=np.float64)
        y_true = np.asarray(y_true, dtype=np.float64)

        order = np.argsort(scores, kind="stable")
        xs = scores[order]
        ys = y_true[order]

        # PAVA: build blocks of equal isotonic values
        # Each block: (sum_y, count, mean_x) — merge when monotonicity is violated
        blocks: list = []  # each element: [sum_y, count, mean_x]
        for x_val, y_val in zip(xs, ys):
            blocks.append([y_val, 1, x_val])
            # Pool adjacent violators
            while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
                prev = blocks.pop(-2)
                curr = blocks[-1]
                merged_sum = prev[0] + curr[0]
                merged_cnt = prev[1] + curr[1]
                merged_x = (prev[2] * prev[1] + curr[2] * curr[1]) / merged_cnt
                blocks[-1] = [merged_sum, merged_cnt, merged_x]

        self._x_ = np.array([b[2] for b in blocks], dtype=np.float64)
        self._y_ = np.array([b[0] / b[1] for b in blocks], dtype=np.float64)

        logger.info("IsotonicCalibrator.fit: %d knots", len(self._x_))
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        """Apply isotonic calibration via piecewise-constant interpolation.

        Parameters
        ----------
        scores:
            Raw model scores, shape ``(n,)``.

        Returns
        -------
        np.ndarray
            Calibrated probabilities in ``[0, 1]``, shape ``(n,)``.

        Raises
        ------
        RuntimeError
            If :meth:`fit` has not been called.
        """
        if self._x_ is None or self._y_ is None:
            raise RuntimeError("IsotonicCalibrator must be fitted before predict()")

        scores = np.asarray(scores, dtype=np.float64)
        result = np.empty_like(scores)

        for i, s in enumerate(scores):
            if s <= self._x_[0]:
                result[i] = self._y_[0]
            elif s >= self._x_[-1]:
                result[i] = self._y_[-1]
            else:
                # Find the nearest knot to the left
                idx = np.searchsorted(self._x_, s, side="right") - 1
                result[i] = self._y_[idx]

        return np.clip(result, 0.0, 1.0)


# ---------------------------------------------------------------------------
# PlattCalibrator — logistic scaling
# ---------------------------------------------------------------------------

class PlattCalibrator:
    """Platt scaling calibrator.

    Fits a logistic regression of the form
    ``P(y=1|s) = σ(A·s + B)`` using the Newton–Raphson method as in
    Lin et al. (2007).

    Attributes
    ----------
    A_:
        Slope of the logistic transform.
    B_:
        Intercept of the logistic transform.
    """

    def __init__(self) -> None:
        self.A_: float = 1.0
        self.B_: float = 0.0

    def fit(
        self,
        scores: np.ndarray,
        y_true: np.ndarray,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> "PlattCalibrator":
        """Fit the Platt scaling parameters via gradient descent.

        Parameters
        ----------
        scores:
            Raw model scores, shape ``(n,)``.
        y_true:
            Binary ground-truth labels, shape ``(n,)``.
        max_iter:
            Maximum number of gradient-descent iterations.
        tol:
            Convergence tolerance on the gradient norm.

        Returns
        -------
        PlattCalibrator
            Self (for chaining).
        """
        scores = np.asarray(scores, dtype=np.float64)
        y_true = np.asarray(y_true, dtype=np.float64)

        n_pos = np.sum(y_true)
        n_neg = len(y_true) - n_pos

        # Label smoothing (Lin et al., 2007)
        t_pos = (n_pos + 1.0) / (n_pos + 2.0)
        t_neg = 1.0 / (n_neg + 2.0)
        t = np.where(y_true == 1.0, t_pos, t_neg)

        A, B = 0.0, np.log((n_neg + 1.0) / (n_pos + 1.0))
        lr = 1e-3

        for _ in range(max_iter):
            fval = A * scores + B
            p = 1.0 / (1.0 + np.exp(-fval))
            p = np.clip(p, 1e-12, 1.0 - 1e-12)

            grad_A = float(np.sum((p - t) * scores))
            grad_B = float(np.sum(p - t))

            A -= lr * grad_A
            B -= lr * grad_B

            grad_norm = np.sqrt(grad_A ** 2 + grad_B ** 2)
            if grad_norm < tol:
                break

        self.A_ = float(A)
        self.B_ = float(B)
        logger.info("PlattCalibrator.fit: A=%.5f, B=%.5f", self.A_, self.B_)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        """Apply Platt scaling.

        Parameters
        ----------
        scores:
            Raw model scores, shape ``(n,)``.

        Returns
        -------
        np.ndarray
            Calibrated probabilities in ``[0, 1]``, shape ``(n,)``.
        """
        scores = np.asarray(scores, dtype=np.float64)
        logits = self.A_ * scores + self.B_
        probs = 1.0 / (1.0 + np.exp(-logits))
        return np.clip(probs, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Expected Calibration Error
# ---------------------------------------------------------------------------

def compute_ece(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute the Expected Calibration Error (ECE).

    Partitions predictions into *n_bins* equal-width probability bins and
    computes the weighted average of ``|mean_confidence - fraction_positive|``
    per bin.

    .. math::
        \\text{ECE} = \\sum_{m=1}^{M} \\frac{|B_m|}{n}
                      \\bigl|\\overline{\\hat{p}}_{B_m} - \\bar{y}_{B_m}\\bigr|

    Parameters
    ----------
    y_true:
        Binary ground-truth labels, shape ``(n,)``.
    y_prob:
        Predicted probabilities, shape ``(n,)``.
    n_bins:
        Number of calibration bins.

    Returns
    -------
    float
        ECE ∈ [0, 1].  Lower is better.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_prob = np.asarray(y_prob, dtype=np.float64)
    n = len(y_true)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if not np.any(mask):
            continue
        bin_size = int(np.sum(mask))
        mean_conf = float(np.mean(y_prob[mask]))
        frac_pos = float(np.mean(y_true[mask]))
        ece += (bin_size / n) * abs(mean_conf - frac_pos)

    logger.debug("compute_ece: ECE=%.5f (n_bins=%d)", ece, n_bins)
    return float(ece)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def calibrate(
    method: Literal["isotonic", "platt"],
    y_cal: np.ndarray,
    scores_cal: np.ndarray,
    scores_test: np.ndarray,
) -> np.ndarray:
    """Fit a calibrator on calibration data and apply it to test scores.

    Parameters
    ----------
    method:
        Calibration strategy: ``'isotonic'`` or ``'platt'``.
    y_cal:
        Ground-truth binary labels for the calibration set, shape ``(n_cal,)``.
    scores_cal:
        Raw model scores for the calibration set, shape ``(n_cal,)``.
    scores_test:
        Raw model scores for the test set to calibrate, shape ``(n_test,)``.

    Returns
    -------
    np.ndarray
        Calibrated probabilities for the test set, shape ``(n_test,)`` ∈ [0, 1].

    Raises
    ------
    ValueError
        If *method* is not ``'isotonic'`` or ``'platt'``.
    """
    y_cal = np.asarray(y_cal, dtype=np.float64)
    scores_cal = np.asarray(scores_cal, dtype=np.float64)
    scores_test = np.asarray(scores_test, dtype=np.float64)

    if method == "isotonic":
        calibrator: IsotonicCalibrator | PlattCalibrator = IsotonicCalibrator()
    elif method == "platt":
        calibrator = PlattCalibrator()
    else:
        raise ValueError(f"Unknown calibration method '{method}'. Choose 'isotonic' or 'platt'.")

    calibrator.fit(scores_cal, y_cal)
    calibrated = calibrator.predict(scores_test)
    logger.info(
        "calibrate(%s): mean_cal=%.4f → mean_calib=%.4f",
        method, float(np.mean(scores_test)), float(np.mean(calibrated)),
    )
    return calibrated
