"""Odlyzko-Schonhage: the fast path must agree with the slow one, and both
with mpmath.

The transform is only worth having if it is *exact* to the accuracy of the
direct sum -- an approximation to an approximation is not a zero-finder.  So
every test here is a comparison against something computed a completely
different way.
"""

from __future__ import annotations

import math

import mpmath as mp
import numpy as np
import pytest

from riemann import dd
from riemann.odlyzko_schonhage import ZBlock, next_fast_len, nufft_type1

mp.mp.dps = 30


def _exact(t0, d):
    """``Z(t0 + d)`` from mpmath, without rounding ``t0 + d`` to a double first."""
    return float(mp.siegelz(mp.mpf(float(t0)) + mp.mpf(float(d))))


# ---------------------------------------------------------------------------
# the transform on its own
# ---------------------------------------------------------------------------

def test_next_fast_len():
    for n in (1, 2, 3, 5, 7, 100, 226, 1000, 12345):
        m = next_fast_len(n)
        assert m >= n
        rest = m
        for p in (2, 3, 5):
            while rest % p == 0:
                rest //= p
        assert rest == 1


@pytest.mark.parametrize("spread,tol", [(10, 1e-8), (14, 1e-12), (18, 1e-13)])
def test_nufft_matches_the_direct_transform(spread, tol):
    rng = np.random.default_rng(0)
    n, modes = 4000, 64
    x = rng.uniform(0.0, 2.0 * math.pi, n)
    c = rng.normal(size=n) + 1j * rng.normal(size=n)
    ks = np.arange(-modes // 2, modes - modes // 2)
    exact = np.array([np.sum(c * np.exp(-1j * k * x)) for k in ks])
    got = nufft_type1(x, c, modes, spread=spread)
    assert np.max(np.abs(got - exact)) / np.sum(np.abs(c)) < tol


def test_nufft_low_word_correction_is_applied_and_grows_with_the_mode_index():
    """The correction exists, is of the size the analysis says, and is zero at k=0.

    It is deliberately *not* asserted that dropping it breaks anything: measured
    rather than bounded, it is worth about 10% (see the module docstring).  What
    is asserted is that the term is really being computed, that it scales like
    ``|k|``, and that it never makes the answer worse.
    """
    n, modes = 200000, 2048
    delta = 0.0625
    ns = np.arange(2.0, n + 2.0)
    x = dd.mul_mod_2pi_dd(delta, dd.log(ns))
    c = (1.0 / np.sqrt(ns)).astype(complex)

    with_low = nufft_type1(x[0], c, modes, x_low=x[1], oversample=4.0)
    without = nufft_type1(x[0], c, modes, oversample=4.0)
    ks = np.arange(-modes // 2, modes - modes // 2)
    diff = np.abs(with_low - without)

    assert diff[modes // 2] < 1e-16                      # k = 0: nothing to fix
    assert diff.max() > 1e-14                            # the edges: a real term
    # and it is linear in |k|: the outer decile must dominate the inner one
    outer = diff[np.abs(ks) > 0.9 * modes // 2].mean()
    inner = diff[np.abs(ks) < 0.1 * modes // 2].mean()
    assert outer > 20 * inner

    # against a reference that keeps the low word itself
    for k in (int(ks[0]), int(ks[-1])):
        a = dd.mul_mod_2pi_dd(float(k), x)
        exact = np.sum(c * np.exp(-1j * a[0]) * (1.0 - 1j * a[1]))
        i = int(np.where(ks == k)[0][0])
        assert abs(with_low[i] - exact) < 1e-12
        assert abs(with_low[i] - exact) <= 2.0 * abs(without[i] - exact)


# ---------------------------------------------------------------------------
# the block
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t0", [1e5, 1e6, 1e8, 1e10])
def test_direct_path_matches_mpmath(t0):
    block = ZBlock(t0, 12.0)
    for d in (-11.5, -3.25, 0.0, 4.125, 9.75):
        assert abs(block.Z_direct(np.array([d]))[0] - _exact(t0, d)) < 1e-9


@pytest.mark.parametrize("t0", [1e5, 1e6, 1e8, 1e10])
def test_fast_path_matches_the_direct_path(t0):
    block = ZBlock(t0, 12.0)
    ds = np.linspace(-11.0, 11.0, 41)
    assert np.max(np.abs(block.Z(ds) - block.Z_direct(ds))) < 1e-11


def test_transform_matches_direct_summation_on_the_grid():
    block = ZBlock(1e8, 20.0)
    offs = block.offsets
    inside = np.abs(offs) <= block.half_width
    got = block.grid_values()[inside]
    exact = block.main_sum_direct(offs[inside])
    assert np.max(np.abs(got - exact)) < 1e-11


def test_grid_offsets_are_exactly_representable():
    """A power-of-two spacing, so k*delta carries no rounding at all."""
    block = ZBlock(1e15, 50.0)
    assert block.delta == 2.0 ** round(math.log2(block.delta))
    k = np.arange(-(block.n_grid // 2), block.n_grid - block.n_grid // 2)
    assert np.array_equal(block.offsets, k * block.delta)
    assert np.array_equal(block.offsets / block.delta, k.astype(float))


def test_ordinates_are_offsets_because_float64_cannot_hold_them():
    """The reason the API takes offsets: at 10^15 a double is coarser than a gap."""
    t0 = 1e15
    assert math.ulp(t0) == 0.125
    assert math.ulp(t0) > 0.6 * dd.mean_gap(t0)
    # so adding a small offset to t0 quantises it hopelessly
    assert (t0 + 0.03) == t0


def test_block_refuses_to_straddle_a_change_in_the_sum_length():
    tau = 400.0
    t0 = 2.0 * math.pi * tau * tau        # exactly where floor(sqrt(t/2pi)) ticks
    with pytest.raises(ValueError, match="straddles"):
        ZBlock(t0, 5.0)


def test_zero_count_matches_the_smooth_prediction():
    for t0 in (1e6, 1e10):
        block = ZBlock(t0, 40.0)
        found = block.zeros(density=16.0)
        assert abs(len(found) - block.expected_count()) < 3.0


def test_reported_zeros_really_are_zeros():
    block = ZBlock(1e10, 20.0)
    found = block.zeros(density=16.0)
    assert len(found) > 50
    assert np.max(np.abs(block.Z_direct(found))) < 1e-8


def test_scan_density_does_not_change_the_answer():
    block = ZBlock(1e8, 30.0)
    counts = [len(block.zeros(density=d)) for d in (8, 16, 32, 64)]
    assert counts[1:] == counts[:-1] or len(set(counts[1:])) == 1


def test_interpolation_is_accurate_near_the_block_edges():
    """The grid overhangs the block by a whole stencil; check it really does."""
    block = ZBlock(1e8, 20.0)
    ds = np.array([-19.99, -19.5, 19.5, 19.99])
    assert np.max(np.abs(block.Z(ds) - block.Z_direct(ds))) < 1e-11


def test_offsets_outside_the_block_are_refused():
    block = ZBlock(1e8, 10.0)
    with pytest.raises(ValueError, match="outside"):
        block.Z(np.array([1e6]))


@pytest.mark.parametrize("t0", [1e13])
def test_agrees_with_mpmath_where_float64_phases_are_useless(t0):
    """At 10^13 the naive phase has lost every digit; this must not have."""
    block = ZBlock(t0, 8.0)
    for d in (-5.5, 0.0, 3.25):
        assert abs(block.Z(np.array([d]))[0] - _exact(t0, d)) < 1e-9
