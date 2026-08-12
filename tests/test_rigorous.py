"""Certified enclosures and Turing's method.

Two kinds of test here, and the distinction matters:

* *validity* -- the enclosure really encloses, checked against mpmath.  A bound
  that fails once is not a bound.
* *usefulness* -- the enclosure is narrow enough to decide a sign.  A bound of
  ``[-inf, inf]`` is always valid and never useful.

Turing's method is checked against ``mpmath.nzeros``, which implements the same
theorem independently, at heights where a wrong answer would be visible.
"""

from __future__ import annotations

import math

import mpmath as mp
import numpy as np
import pytest

from riemann import rigorous as R
from riemann.interval import Interval
from riemann.odlyzko_schonhage import ZBlock
from riemann.riemann_siegel import correction_coefficient

mp.mp.dps = 30


# ---------------------------------------------------------------------------
# the pieces
# ---------------------------------------------------------------------------

def test_psi_interval_matches_the_quadrature_coefficient():
    """Two completely different evaluations of ``C_0`` must agree."""
    for i in range(101):
        p = i / 100.0
        enclosure = R.psi_interval(p)
        assert abs(enclosure.mid - correction_coefficient(p, 0)) < 1e-10
        assert enclosure.width < 1e-13


def test_psi_interval_survives_the_removable_singularities():
    """``p = 1/4`` and ``3/4`` are where the quotient form dies; the value is 1/2."""
    for p in (0.25, 0.75):
        enclosure = R.psi_interval(p)
        assert enclosure.contains(0.5)
        assert enclosure.width < 1e-14
    # and just beside them
    for p in (0.25 - 1e-12, 0.25 + 1e-12, 0.75 - 1e-9, 0.75 + 1e-9):
        assert abs(R.psi_interval(p).mid - 0.5) < 1e-8


def test_psi_interval_rejects_arguments_outside_the_unit_interval():
    with pytest.raises(ValueError):
        R.psi_interval(1.5)


def test_cos_certified_is_valid_and_tight():
    rng = np.random.default_rng(0)
    a = rng.uniform(-25.0, 25.0, 5000)
    values, bound = R.cos_certified(a)
    assert bound < 1e-13
    for i in range(300):
        enclosure = Interval(float(a[i])).cos()
        assert values[i] - bound <= enclosure.hi
        assert values[i] + bound >= enclosure.lo


def test_cos_certified_does_not_rely_on_libm():
    """It should agree with numpy -- but it must not be *computing* with it."""
    rng = np.random.default_rng(1)
    a = rng.uniform(-25.0, 25.0, 20000)
    values, bound = R.cos_certified(a)
    assert np.max(np.abs(values - np.cos(a))) < bound


def test_tree_sum_has_the_advertised_depth():
    for n in (1, 2, 3, 1000, 1 << 20):
        _, depth = R.tree_sum(np.ones(n))
        assert depth == math.ceil(math.log2(max(n, 1)))


def test_tree_sum_is_accurate():
    rng = np.random.default_rng(2)
    x = rng.normal(size=200000)
    total, _ = R.tree_sum(x)
    assert abs(total - math.fsum(x)) < 1e-10


def test_theta_mod_certified_is_valid():
    for t0, d in ((1e6, 0.0), (1e10, 3.5), (1e15, 37.5)):
        value, bound = R.theta_mod_certified(t0, d)
        exact = mp.siegeltheta(mp.mpf(t0) + mp.mpf(d))
        exact = float(mp.fmod(exact, 2 * mp.pi))
        diff = (value - exact + math.pi) % (2 * math.pi) - math.pi
        assert abs(diff) <= bound + 1e-14, (t0, d, diff, bound)


def test_gabcke_bound_is_refused_below_its_range():
    with pytest.raises(ValueError):
        R.rs_remainder_bound(100.0)


# ---------------------------------------------------------------------------
# the enclosure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t0", [1e6, 1e8, 1e10])
def test_Z_enclosure_contains_mpmath(t0):
    block = ZBlock(t0, 8.0)
    ds = np.array([-7.5, -2.125, 0.0, 3.25, 6.875])
    values, radii = R.Z_enclosure(block, ds)
    for i, d in enumerate(ds):
        exact = float(mp.siegelz(mp.mpf(t0) + mp.mpf(float(d))))
        assert values[i] - radii[i] <= exact <= values[i] + radii[i], (t0, d)


def test_Z_enclosure_is_narrow_enough_to_be_useful():
    block = ZBlock(1e10, 8.0)
    _, radii = R.Z_enclosure(block, np.array([-3.0, 0.0, 3.0]))
    assert np.max(radii) < 1e-6


def test_Z_enclosure_agrees_with_the_uncertified_path():
    block = ZBlock(1e8, 8.0)
    ds = np.linspace(-7.0, 7.0, 9)
    values, radii = R.Z_enclosure(block, ds)
    assert np.max(np.abs(values - block.Z_direct(ds))) < np.max(radii)


def test_recentring_does_not_change_the_answer():
    block = ZBlock(1e8, 8.0)
    ds = np.array([-6.5, -1.0, 0.5, 5.75])
    a, _ = R.Z_enclosure(block, ds, recentre=0.25)
    b, rb = R.Z_enclosure(block, ds, recentre=8.0)
    assert np.max(np.abs(a - b)) < np.max(rb)


# ---------------------------------------------------------------------------
# certification and counting
# ---------------------------------------------------------------------------

def test_certified_brackets_really_bracket():
    block = ZBlock(1e8, 20.0)
    certified, rejected = R.certify_brackets(block, block.brackets(density=16.0))
    assert len(rejected) == 0
    assert len(certified) > 90
    left = block.Z_direct(certified[:, 0])
    right = block.Z_direct(certified[:, 1])
    assert np.all(np.signbit(left) != np.signbit(right))


def test_a_bracket_with_no_sign_change_is_not_certified():
    """Feed it a cell that does not straddle a zero; nothing may be claimed."""
    block = ZBlock(1e8, 20.0)
    zeros = block.zeros(density=16.0)
    # a cell wholly between two zeros, where Z keeps one sign
    mid = 0.5 * (zeros[10] + zeros[11])
    fake = np.array([[mid - 0.01, mid + 0.01]])
    certified, rejected = R.certify_brackets(block, fake)
    assert len(certified) == 0 and len(rejected) == 1


@pytest.mark.parametrize("t0", [1e6, 1e8, 1e10])
def test_turing_reproduces_mpmath_nzeros(t0):
    block = ZBlock(t0, 40.0)
    result = R.verify_block(block, verbose=False)
    t1, t2 = result["inner_range"]
    assert result["N_t1"] == int(mp.nzeros(t1))
    assert result["N_t2"] == int(mp.nzeros(t2))
    assert result["complete"]


def test_turing_closes_with_room_to_spare():
    block = ZBlock(1e8, 40.0)
    result = R.verify_block(block, verbose=False)
    for key in ("turing_lower", "turing_upper"):
        assert 0.0 < result[key]["slack"] < 1.0


def test_turing_needs_no_completeness_assumption():
    """Dropping known zeros may widen the bracket but must never move it wrongly."""
    block = ZBlock(1e8, 40.0)
    certified, _ = R.certify_brackets(block, block.brackets(density=16.0))
    h, width = block.half_width, 20.0
    d1 = -h + width
    left, right = certified[:, 0], certified[:, 1]
    below = left[(right > -h) & (right <= d1)]
    above = right[(left >= d1) & (left < d1 + width)]

    full = R.turing_zero_count(block.t0, d1, below, above, -h, d1 + width)
    thinned = R.turing_zero_count(block.t0, d1, below[::2], above[::2], -h, d1 + width)
    assert full["count"] is not None
    assert thinned["lower"] <= full["lower"]
    assert thinned["upper"] >= full["upper"]
    if thinned["count"] is not None:
        assert thinned["count"] == full["count"]


def test_block_too_narrow_for_turing_is_refused():
    block = ZBlock(1e8, 5.0)
    with pytest.raises(ValueError, match="too narrow"):
        R.verify_block(block, verbose=False)
