"""Interval arithmetic: the enclosures must actually enclose.

Every test here has the same shape -- compute an interval, ask :mod:`mpmath` at
50 digits for the true value, assert containment.  A bound that is merely
usually right is not a bound.
"""

from __future__ import annotations

import math
import random

import mpmath as mp
import pytest

from riemann.interval import Interval, LOG_2, PI, machin_pi

mp.mp.dps = 50


def test_machin_pi_is_correct():
    # compare 40 digits out of the 45 requested: the last few are the ones the
    # two libraries round differently, not the ones either gets wrong.
    assert str(machin_pi(45))[:41] == mp.nstr(mp.pi, 45)[:41]


def test_machin_pi_is_not_a_quoted_constant():
    """Increasing the requested precision must actually produce more digits."""
    short, long = str(machin_pi(20)), str(machin_pi(60))
    assert long.startswith(short[:20])
    assert len(long) > len(short) + 30


def test_pi_interval_contains_pi():
    assert PI.lo <= mp.pi <= PI.hi
    assert PI.width < 1e-15
    assert LOG_2.lo <= mp.log(2) <= LOG_2.hi


# ---------------------------------------------------------------------------
# arithmetic
# ---------------------------------------------------------------------------

def test_arithmetic_encloses():
    rng = random.Random(0)
    for _ in range(500):
        a = Interval(*sorted((rng.uniform(-9, 9), rng.uniform(-9, 9))))
        b = Interval(*sorted((rng.uniform(-9, 9), rng.uniform(-9, 9))))
        for _ in range(5):
            x = rng.uniform(a.lo, a.hi)
            y = rng.uniform(b.lo, b.hi)
            assert (a + b).contains(x + y)
            assert (a - b).contains(x - y)
            assert (a * b).contains(x * y)


def test_division_by_a_straddling_interval_is_refused():
    with pytest.raises(ZeroDivisionError):
        Interval(1.0) / Interval(-1.0, 1.0)


def test_powers():
    a = Interval(1.5, 2.5)
    assert (a ** 3).contains(2.0 ** 3)
    assert (a ** 0).contains(1.0)


def test_sign_is_only_claimed_when_certain():
    assert Interval(1e-30, 1.0).sign() == 1
    assert Interval(-1.0, -1e-30).sign() == -1
    assert Interval(-1e-30, 1e-30).sign() == 0
    assert Interval(0.0, 1.0).sign() == 0     # touching zero is not positive


def test_empty_interval_is_refused():
    with pytest.raises(ValueError):
        Interval(1.0, 0.0)


# ---------------------------------------------------------------------------
# elementary functions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,oracle", [
    ("exp", mp.exp), ("cos", mp.cos), ("sin", mp.sin),
])
def test_point_enclosures(name, oracle):
    rng = random.Random(1)
    xs = [0.0, 1.0, -1.0, math.pi, math.pi / 2, -math.pi / 4, 1e-9, 12.5]
    xs += [rng.uniform(-30, 30) for _ in range(200)]
    for x in xs:
        iv = getattr(Interval(x), name)()
        exact = oracle(mp.mpf(x))
        assert iv.lo <= exact <= iv.hi, (name, x, iv, exact)


@pytest.mark.parametrize("name,oracle", [("log", mp.log), ("sqrt", mp.sqrt)])
def test_positive_only_enclosures(name, oracle):
    rng = random.Random(2)
    xs = [1.0, 2.0, 0.5, 1e-8, 1e12] + [rng.uniform(1e-6, 1e6) for _ in range(200)]
    for x in xs:
        iv = getattr(Interval(x), name)()
        assert iv.lo <= oracle(mp.mpf(x)) <= iv.hi


def test_trig_over_wide_intervals_covers_the_interior():
    rng = random.Random(3)
    for _ in range(200):
        a = rng.uniform(-8, 8)
        w = 10 ** rng.uniform(-14, 0)
        iv = Interval(a, a + w)
        for name, oracle in (("cos", mp.cos), ("sin", mp.sin)):
            out = getattr(iv, name)()
            for s in (0.0, 0.19, 0.5, 0.83, 1.0):
                assert out.lo <= oracle(mp.mpf(a + s * w)) <= out.hi


def test_trig_stays_within_minus_one_and_one():
    for x in (math.pi / 2, -math.pi / 2, 0.0, math.pi):
        for name in ("sin", "cos"):
            iv = getattr(Interval(x), name)()
            assert -1.0 <= iv.lo and iv.hi <= 1.0


def test_log_of_an_interval_reaching_zero_is_refused():
    with pytest.raises(ValueError):
        Interval(0.0, 1.0).log()


def test_enclosures_are_tight_enough_to_be_useful():
    """A correct but useless bound is a failure mode too."""
    for x in (0.3, 2.0, 11.0):
        assert Interval(x).cos().width < 1e-15
        assert Interval(x).exp().width < 1e-15 * math.exp(x) + 1e-15
