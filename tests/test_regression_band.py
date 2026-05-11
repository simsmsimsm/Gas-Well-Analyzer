"""Tests for _regression_band() — linear regression with 95% CI bands."""
import numpy as np
import pytest
from app import _regression_band


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _perfect_line(slope=2.0, intercept=5.0, n=50):
    x = np.linspace(0, 10, n)
    y = slope * x + intercept
    return x, y


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_returns_eight_values():
    x, y = _perfect_line()
    x_line = np.linspace(x.min(), x.max(), 100)
    result = _regression_band(x, y, x_line)
    # y_line, ci_upper, ci_lower, slope, intercept, r, p, se
    assert len(result) == 8


def test_output_arrays_match_x_line_length():
    x, y = _perfect_line()
    x_line = np.linspace(x.min(), x.max(), 300)
    y_line, ci_up, ci_lo, *_ = _regression_band(x, y, x_line)
    assert len(y_line) == 300
    assert len(ci_up) == 300
    assert len(ci_lo) == 300


# ---------------------------------------------------------------------------
# Correctness on a known perfect line (y = 2x + 5, no noise)
# ---------------------------------------------------------------------------

def test_slope_recovered_on_perfect_line():
    x, y = _perfect_line(slope=2.0, intercept=5.0)
    x_line = np.linspace(0, 10, 50)
    _, _, _, slope, intercept, r, p, se = _regression_band(x, y, x_line)
    assert abs(slope - 2.0) < 1e-8


def test_intercept_recovered_on_perfect_line():
    x, y = _perfect_line(slope=2.0, intercept=5.0)
    x_line = np.linspace(0, 10, 50)
    _, _, _, slope, intercept, r, p, se = _regression_band(x, y, x_line)
    assert abs(intercept - 5.0) < 1e-8


def test_r_is_one_on_perfect_line():
    x, y = _perfect_line()
    x_line = np.linspace(0, 10, 50)
    _, _, _, slope, intercept, r, p, se = _regression_band(x, y, x_line)
    assert abs(abs(r) - 1.0) < 1e-6


def test_se_is_zero_on_perfect_line():
    x, y = _perfect_line()
    x_line = np.linspace(0, 10, 50)
    _, _, _, slope, intercept, r, p, se = _regression_band(x, y, x_line)
    assert abs(se) < 1e-8


# ---------------------------------------------------------------------------
# CI band ordering
# ---------------------------------------------------------------------------

def test_ci_upper_always_above_y_line():
    rng = np.random.default_rng(0)
    x = np.linspace(0, 10, 80)
    y = 3 * x + 1 + rng.normal(0, 1, 80)
    x_line = np.linspace(0, 10, 200)
    y_line, ci_up, ci_lo, *_ = _regression_band(x, y, x_line)
    assert np.all(ci_up >= y_line)


def test_ci_lower_always_below_y_line():
    rng = np.random.default_rng(1)
    x = np.linspace(0, 10, 80)
    y = 3 * x + 1 + rng.normal(0, 1, 80)
    x_line = np.linspace(0, 10, 200)
    y_line, ci_up, ci_lo, *_ = _regression_band(x, y, x_line)
    assert np.all(ci_lo <= y_line)


def test_ci_band_is_symmetric_around_y_line():
    rng = np.random.default_rng(2)
    x = np.linspace(0, 10, 80)
    y = 3 * x + 1 + rng.normal(0, 1, 80)
    x_line = np.linspace(0, 10, 200)
    y_line, ci_up, ci_lo, *_ = _regression_band(x, y, x_line)
    upper_delta = ci_up - y_line
    lower_delta = y_line - ci_lo
    np.testing.assert_allclose(upper_delta, lower_delta, rtol=1e-10)


def test_ci_band_widens_away_from_mean():
    """CI band should be narrowest at x̄ and widen toward the extremes."""
    rng = np.random.default_rng(3)
    x = np.linspace(0, 10, 100)
    y = 2 * x + 1 + rng.normal(0, 1, 100)
    x_line = np.linspace(0, 10, 500)
    y_line, ci_up, ci_lo, *_ = _regression_band(x, y, x_line)
    half_width = ci_up - y_line
    mid = len(half_width) // 2
    assert half_width[0] > half_width[mid]
    assert half_width[-1] > half_width[mid]


# ---------------------------------------------------------------------------
# Negative slope
# ---------------------------------------------------------------------------

def test_negative_slope_recovered():
    x = np.linspace(0, 10, 60)
    y = -3 * x + 20 + np.random.default_rng(4).normal(0, 0.5, 60)
    x_line = np.linspace(0, 10, 100)
    _, _, _, slope, *_ = _regression_band(x, y, x_line)
    assert slope < 0


# ---------------------------------------------------------------------------
# Minimum viable sample (n = 3 exposes the n-2 division)
# ---------------------------------------------------------------------------

def test_minimum_three_points_does_not_crash():
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([1.0, 3.0, 5.0])
    x_line = np.linspace(0, 2, 10)
    # Should not raise ZeroDivisionError despite n-2 == 1
    y_line, ci_up, ci_lo, slope, intercept, r, p, se = _regression_band(x, y, x_line)
    assert abs(slope - 2.0) < 1e-8
