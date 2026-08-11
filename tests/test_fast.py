"""The accelerated paths must agree with the pure-Python reference.

``riemann/fast.py`` exists purely for speed.  Every function in it duplicates
something already implemented without numpy, so the only thing worth testing is
that the duplication is faithful.
"""

from __future__ import annotations

import numpy as np
import pytest

from riemann.equivalences import li_coefficients
from riemann.explicit_formula import psi_from_zeros, psi_from_zeros_array
from riemann.fast import HorizontalLine, Z_array, li_coefficients_array, theta_array
from riemann.riemann_siegel import Z, theta
from riemann.zeros import find_zeros
from riemann.zeta import zeta


def test_theta_array_matches_scalar():
    ts = np.array([20.0, 137.5, 1000.0, 54321.0])
    fast = theta_array(ts)
    for t, f in zip(ts, fast):
        assert f == pytest.approx(theta(float(t)), abs=1e-8)


def test_Z_array_matches_scalar():
    ts = np.array([20.0, 100.0, 1234.5, 20000.0, 74920.0])
    fast = Z_array(ts)
    for t, f in zip(ts, fast):
        assert f == pytest.approx(Z(float(t)), abs=1e-9)


def test_Z_array_rejects_small_t():
    with pytest.raises(ValueError):
        Z_array(np.array([10.0]))


def test_Z_array_handles_block_boundaries():
    """Blocking must not change results; n_max varies within a block."""
    ts = np.linspace(1000.0, 1100.0, 5000)
    a = Z_array(ts, block=97)
    b = Z_array(ts, block=100000)
    assert np.max(np.abs(a - b)) < 1e-12


def test_horizontal_line_matches_zeta():
    for t in (100.0, 1000.0):
        line = HorizontalLine(t)
        for sigma in (0.5, 0.9, 1.4, 2.0):
            assert abs(line.at(sigma) - zeta(complex(sigma, t))) < 1e-10


def test_li_array_matches_scalar():
    zeros = find_zeros(14.0, 500.0)
    a = li_coefficients_array(12, zeros)
    b = li_coefficients(12, zeros)
    assert np.max(np.abs(np.asarray(a) - np.asarray(b))) < 1e-10


def test_li_array_off_line_zeros_add_reflection():
    """An off-line zero must bring its reflected partner, giving 4 roots."""
    on = li_coefficients_array(5, [14.0], [0.5])
    off = li_coefficients_array(5, [14.0], [0.7])
    assert not np.allclose(on, off)
    # The reflected partner has |1-1/rho| > 1, so the perturbation grows.
    big = li_coefficients_array(4000, [14.0], [0.7])
    assert abs(big[-1]) > abs(off[-1]) * 100


def test_psi_from_zeros_array_matches_scalar():
    zeros = find_zeros(14.0, 300.0)
    xs = [10.5, 33.3, 77.7]
    fast = psi_from_zeros_array(xs, zeros)
    for x, f in zip(xs, fast):
        assert f == pytest.approx(psi_from_zeros(x, zeros), abs=1e-9)
