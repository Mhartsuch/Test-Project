"""zeta', the log-sin fix, and the argument-principle counting tool."""

from __future__ import annotations

import cmath
import math

import mpmath as mp
import pytest

from riemann.counting import N, speiser_check, winding_number, winding_number_chunked
from riemann.zeta import _chi, _log_sin, zeta, zeta_prime

mp.mp.dps = 30


@pytest.mark.parametrize(
    "s", [2 + 0j, 3 + 4j, 0.5 + 14.134725j, 0.5 + 100j, 0.25 + 30j, 0.1 + 20j,
          -0.3 + 8j, 0.6 + 50j])
def test_zeta_prime_matches_mpmath(s):
    assert abs(zeta_prime(s) - complex(mp.zeta(s, derivative=1))) < 1e-11


@pytest.mark.parametrize("z", [1 + 0.5j, 0.3 + 5j, 2 + 40j, -1 + 100j, 0.5 - 60j])
def test_log_sin_matches_direct_where_direct_works(z):
    assert abs(cmath.exp(_log_sin(z)) - cmath.sin(z)) < 1e-9 * max(1.0, abs(cmath.sin(z)))


def test_log_sin_sign_regression():
    """Regression: the Im z > 0 branch dropped a factor of -1.

    Factoring ``sin z = -e^{-iz}(1 - e^{2iz})/2i`` and then writing the bracket
    as ``(1 - ...)`` without the leading minus negates the result -- and since
    ``_chi`` feeds the functional equation, it negated ``zeta`` throughout
    ``Re s < 1/2``.  The symptom was a relative error of exactly 2.0.
    """
    for z in (0.7 + 45j, 1.2 + 200j, -0.4 + 900j):
        # Compared in LOG space: sin(-0.4 + 900i) is about e^900 and overflows a
        # double, which is the entire reason this function exists.  The phase is
        # only defined modulo 2 pi.
        got = _log_sin(z)
        want = complex(mp.log(mp.sin(mp.mpc(z.real, z.imag))))
        d = got - want
        phase = (d.imag + math.pi) % (2 * math.pi) - math.pi
        assert abs(d.real) < 1e-10 * max(1.0, abs(want.real))
        assert abs(phase) < 1e-10


@pytest.mark.parametrize("s", [0.2 + 500j, 0.1 + 1000j, -0.3 + 2000j, 0.4 + 800j])
def test_zeta_left_of_half_at_large_t(s):
    """These overflowed before chi was evaluated logarithmically."""
    got, want = zeta(s), complex(mp.zeta(s))
    assert abs(got - want) / abs(want) < 1e-10


@pytest.mark.parametrize("hi,known", [(100.0, 29), (235.0, 99)])
def test_chunked_winding_recovers_the_zeta_count(hi, known):
    r = winding_number_chunked(zeta, complex(0.002, 0.5), complex(0.998, hi),
                               chunk_height=4.0, per_side=300)
    assert r["all_integers"]
    assert r["rounded"] == known == N(hi)[0]


def test_tall_contour_is_the_unreliable_one():
    """Documents why chunking exists: one tall contour undercounts.

    Not a statement about what the right answer is -- it is a statement that a
    single tall rectangle does not produce it, which is why the chunked routine
    is the one used.
    """
    tall, _ = winding_number(zeta, complex(0.002, 0.5), complex(0.998, 500.0),
                             per_side=800, refinements=2)
    chunked = winding_number_chunked(zeta, complex(0.002, 0.5),
                                     complex(0.998, 500.0), chunk_height=4.0,
                                     per_side=300)
    assert chunked["rounded"] == 269
    assert tall < 269          # undercounts by losing whole turns


def test_speiser_finds_no_zeros_left_of_the_line():
    """RH <=> zeta' has no zeros in 0 < Re s < 1/2."""
    r = speiser_check(0.5, 120.0, per_side=300)
    assert r["reliable"]
    assert r["consistent_with_RH"]
    assert abs(r["zeros_of_zeta_prime"]) < 5e-3


def test_zeta_prime_does_have_zeros_right_of_the_line():
    """Sanity: the region just right of the line is NOT empty, so a zero count
    of 0 to the left is a real constraint rather than a broken contour."""
    r = winding_number_chunked(zeta_prime, complex(0.502, 0.5),
                               complex(1.6, 100.0), chunk_height=4.0,
                               per_side=300)
    assert r["all_integers"]
    assert r["rounded"] > 10
