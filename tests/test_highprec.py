"""The windowed high-precision path, against mpmath at height."""

from __future__ import annotations

import math

import mpmath as mp
import numpy as np
import pytest

from riemann.fast import Z_array
from riemann.highprec import ZWindow, window_for_zero_count

mp.mp.dps = 35


def _exact(t):
    """``Z(t)`` from mpmath at *exactly* the same double.

    Note ``mp.mpf(float)``, not ``mp.mpf(repr(float))``.  ``repr`` gives the
    shortest decimal that round-trips through a double, but mpmath reads that
    string as an exact decimal at its own (higher) precision -- so the two
    libraries end up evaluating at points up to half an ulp apart.  At
    ``t = 10^10`` that is ``1e-6`` of argument, which shows up as a spurious
    ``3e-7`` disagreement in ``Z`` and looks exactly like a precision bug in the
    code under test.  It is not; it is a bug in the comparison.
    """
    return float(mp.siegelz(mp.mpf(float(t))))


@pytest.mark.parametrize("t0", [1e5, 1e6, 1e8, 1e10])
def test_windowed_Z_matches_mpmath(t0):
    w = ZWindow(t0, 12.0)
    ts = t0 + np.linspace(-10.0, 10.0, 7)
    got = w.Z(ts)
    for t, g in zip(ts, got):
        assert abs(g - _exact(t)) < 1e-10


def test_windowed_beats_plain_float64_at_height():
    """The whole point of the module: accuracy must not decay with height.

    The naive path loses roughly one digit per decade because theta(t) itself
    stops fitting in a double; the windowed path should not.
    """
    t0 = 1e10
    w = ZWindow(t0, 12.0)
    ts = t0 + np.linspace(-8.0, 8.0, 5)
    windowed = max(abs(a - _exact(t)) for a, t in zip(w.Z(ts), ts))
    naive = max(abs(a - _exact(t)) for a, t in zip(Z_array(ts), ts))
    assert windowed < 1e-10
    assert naive > 1e-6
    assert naive / windowed > 1e4


def test_window_rejects_points_outside():
    w = ZWindow(1e6, 5.0)
    with pytest.raises(ValueError):
        w.Z(np.array([1e6 + 50.0]))


def test_dtheta_matches_true_theta_increment():
    """The Taylor increment must reproduce theta differences exactly."""
    t0 = 1e8
    w = ZWindow(t0, 500.0)
    for d in (-400.0, -1.0, 0.5, 123.0, 400.0):
        exact = float(mp.siegeltheta(mp.mpf(repr(t0 + d)))
                      - mp.siegeltheta(mp.mpf(repr(t0))))
        assert abs(float(w.dtheta(d)) - exact) < 1e-7


def test_zeros_in_window_are_zeros():
    """Located to the resolution of a double, which is the real ceiling.

    At ``t = 10^8`` one ulp is ``1.5e-8``, so a root cannot be pinned more
    finely than that no matter how many bisection steps are taken -- and since
    ``|Z'|`` is of order 10-100 there, ``|Z|`` at the returned point is around
    ``1e-6`` and no smaller.  Asserting a sign change across a few ulps is the
    meaningful statement; asserting ``|Z| < 1e-7`` is asking for more precision
    than the input argument can carry.
    """
    t0 = 1e8
    w = ZWindow(t0, 30.0)
    z = w.find_zeros()
    assert z.size > 100
    ulp = np.spacing(t0)
    left, right = w.Z(z - 4 * ulp), w.Z(z + 4 * ulp)
    assert np.all(np.signbit(left) != np.signbit(right))
    # and they are strictly increasing and spaced near the expected mean gap
    gaps = np.diff(z)
    assert np.all(gaps > 0)
    expected = 2 * math.pi / math.log(1e8 / (2 * math.pi))
    assert abs(gaps.mean() - expected) / expected < 0.05


def test_window_count_matches_smooth_prediction():
    """Zero tally must differ from Delta theta / pi only by S, which is small."""
    w = ZWindow(1e8, 40.0)
    chk = w.check_complete()
    assert chk["stable_under_refinement"]
    assert abs(chk["implied_S_difference"]) < 3.0


def test_unfolded_spacings_have_unit_mean():
    w = ZWindow(1e6, 200.0)
    z = w.find_zeros(density=20.0)
    s = np.diff(w.unfold(z))
    assert abs(s.mean() - 1.0) < 0.01


def test_window_for_zero_count():
    t0 = 1e6
    hw = window_for_zero_count(t0, 400)
    w = ZWindow(t0, hw)
    assert 350 < w.find_zeros(density=20.0).size < 450
