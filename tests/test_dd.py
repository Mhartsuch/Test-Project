"""Double-double arithmetic, against :mod:`decimal` at 45 digits."""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

import numpy as np
import pytest

from riemann import dd


def _exact_log(n: int, prec: int = 45) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = prec
        return Decimal(n).ln()


# ---------------------------------------------------------------------------
# the error-free transformations
# ---------------------------------------------------------------------------

def test_two_sum_is_exact():
    rng = np.random.default_rng(0)
    a = rng.normal(size=5000) * 10 ** rng.uniform(-8, 8, 5000)
    b = rng.normal(size=5000) * 10 ** rng.uniform(-8, 8, 5000)
    s, e = dd.two_sum(a, b)
    for i in range(200):
        with localcontext() as ctx:
            ctx.prec = 60
            assert Decimal(s[i]) + Decimal(e[i]) == Decimal(a[i]) + Decimal(b[i])


def test_two_prod_is_exact():
    rng = np.random.default_rng(1)
    a = rng.normal(size=2000)
    b = rng.normal(size=2000)
    p, e = dd.two_prod(a, b)
    for i in range(200):
        with localcontext() as ctx:
            ctx.prec = 80
            assert Decimal(p[i]) + Decimal(e[i]) == Decimal(a[i]) * Decimal(b[i])


# ---------------------------------------------------------------------------
# the logarithm
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [2, 3, 5, 7, 10, 12345, 1_000_003, 8_388_609, 12_615_662])
def test_log_is_accurate_to_32_digits(n):
    hi, lo = dd.log(float(n))
    with localcontext() as ctx:
        ctx.prec = 45
        got = Decimal(float(hi)) + Decimal(float(lo))
        exact = _exact_log(n)
        assert abs((got - exact) / exact) < Decimal("1e-31")


def test_log_matches_math_log_in_the_high_word():
    n = np.arange(1.0, 20000.0)
    hi, lo = dd.log(n)
    assert np.max(np.abs(hi - np.log(n))) < 1e-12
    # the low word is a genuine correction, not noise
    assert np.max(np.abs(lo[1:])) > 1e-18


def test_log_chunking_is_transparent():
    n = np.arange(1.0, 100001.0)
    a = dd.log(n, chunk=1 << 20)
    b = dd.log(n, chunk=4096)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_log_rejects_non_positive():
    with pytest.raises(ValueError):
        dd.log(np.array([1.0, 0.0]))


# ---------------------------------------------------------------------------
# the reduction that makes 10^15 possible
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t", [1e6, 1e10, 1e15])
def test_mul_mod_2pi_beats_float64(t):
    """The whole point: float64 cannot do this and the double-double can."""
    ns = np.array([2.0, 3.0, 97.0, 1000003.0])
    reduced = dd.mul_mod_2pi(t, dd.log(ns))
    with localcontext() as ctx:
        ctx.prec = 60
        two_pi = 2 * dd.pi_decimal(60)
        for i, n in enumerate(ns):
            exact = Decimal(t) * Decimal(int(n)).ln()
            exact -= two_pi * (exact / two_pi).to_integral_value(
                rounding="ROUND_HALF_EVEN")
            err = abs(Decimal(float(reduced[i])) - exact)
            # allow the answer to differ by a whole turn: only the phase matters
            err = min(err, abs(err - two_pi))
            assert err < Decimal("1e-14"), (t, n, err)

    # ... whereas the naive float64 computation is worthless at 1e15
    if t == 1e15:
        naive = math.fmod(t * math.log(2.0), 2.0 * math.pi)
        assert abs(naive - float(reduced[0])) > 1e-3


def test_mul_mod_2pi_dd_keeps_a_low_word():
    hi, lo = dd.mul_mod_2pi_dd(0.0625, dd.log(np.arange(2.0, 1000.0)))
    assert np.max(np.abs(lo)) < 1e-16
    assert np.max(np.abs(lo)) > 1e-20     # it is a real correction


def test_mul_mod_2pi_chunking_is_transparent():
    x = dd.log(np.arange(1.0, 60001.0))
    a = dd.mul_mod_2pi_dd(1e15, x, chunk=1 << 20)
    b = dd.mul_mod_2pi_dd(1e15, x, chunk=1024)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


# ---------------------------------------------------------------------------
# constants and theta
# ---------------------------------------------------------------------------

def test_pi_decimal_agrees_with_machin():
    from riemann.interval import machin_pi
    assert str(dd.pi_decimal(45))[:46] == str(machin_pi(45))[:46]


def test_theta_series_coefficients_reproduce_the_textbook_four():
    """The closed form must give back 1/48, 7/5760, 31/80640, 127/430080."""
    from fractions import Fraction
    got = dd.theta_series_coefficients(5)
    assert got[:5] == (Fraction(1, 48), Fraction(7, 5760), Fraction(31, 80640),
                       Fraction(127, 430080), Fraction(511, 1216512))


def test_four_terms_is_not_enough_but_eight_is():
    """The reason the coefficients are generated rather than quoted.

    Truncating where the textbooks do leaves an error at ``t = 200`` that
    *exceeds* the first omitted term -- by 6 parts in 10^5, which is small but
    is the difference between a bound and a wish.  Eight terms puts the residual
    below 10^-40 and the question stops mattering.
    """
    mp = pytest.importorskip("mpmath")
    mp.mp.dps = 60
    exact = Decimal(mp.nstr(mp.siegeltheta(mp.mpf(200.0)), 50))

    short = abs(dd.theta_decimal(200.0, 45, terms=4) - exact)
    first_omitted = Decimal(511) / (Decimal(1216512) * Decimal(200) ** 9)
    assert short > first_omitted            # the naive bound is *not* a bound
    assert short < Decimal("1.001") * first_omitted

    long = abs(dd.theta_decimal(200.0, 45, terms=8) - exact)
    assert long < Decimal("1e-40")
    assert long < dd.theta_truncation_bound(200.0, terms=8)


@pytest.mark.parametrize("t", [200.0, 1e6, 1e10, 1e15])
def test_theta_decimal_matches_mpmath_within_its_stated_bound(t):
    mp = pytest.importorskip("mpmath")
    mp.mp.dps = 50
    got = dd.theta_decimal(t, 45)
    exact = Decimal(mp.nstr(mp.siegeltheta(mp.mpf(t)), 45))
    allowed = dd.theta_truncation_bound(t) + abs(got) * Decimal("1e-43")
    assert abs(got - exact) <= allowed, (t, abs(got - exact), allowed)


def test_theta_over_pi_needs_more_than_float64():
    """``N(10^15)`` is 5e15: a double holds the integer but not the fraction.

    Turing's method needs ``theta(T)/pi`` to a few thousandths, and at this
    height an ulp is a whole unit -- so the smooth count has to be carried in
    :mod:`decimal` or the method cannot close.
    """
    value = dd.theta_over_pi(1e15)
    assert Decimal("5.04e15") < value < Decimal("5.05e15")
    lost = abs(Decimal(float(value)) - value)
    assert lost > Decimal("1e-3"), lost
