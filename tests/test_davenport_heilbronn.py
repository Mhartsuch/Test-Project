"""The Davenport-Heilbronn counterexample.

These tests pin the fact that motivates the whole failure-mode analysis: a
Riemann-type functional equation does not force zeros onto the critical line.
"""

from __future__ import annotations

import cmath
import math

import pytest

from riemann.davenport_heilbronn import (
    CHI, ETA, XI, XI_EVEN, check_functional_equation, coefficients,
    count_zeros_in_rectangle, f, find_zeros_in_rectangle, gauss_sum,
    hurwitz_zeta, root_number, xi_for_sign)
from riemann.zeta import zeta


def test_character_is_primitive_and_odd():
    assert CHI[4] == -1                      # chi(-1) = -1, so chi is odd
    assert abs(gauss_sum()) == pytest.approx(math.sqrt(5.0), rel=1e-13)
    assert abs(root_number()) == pytest.approx(1.0, rel=1e-13)


def test_hurwitz_reduces_to_zeta():
    for s in (2 + 0j, 3 + 4j, 0.5 + 14.134725j, -0.5 + 2j):
        assert abs(hurwitz_zeta(s, 1.0) - zeta(s)) < 1e-11


def test_hurwitz_known_value():
    """zeta(s, 1/2) = (2^s - 1) zeta(s)."""
    for s in (2 + 0j, 3 + 1j):
        assert abs(hurwitz_zeta(s, 0.5) - (2 ** s - 1) * zeta(s)) < 1e-10


@pytest.mark.parametrize("eta", [+1, -1])
def test_both_branches_satisfy_a_functional_equation(eta):
    """Both derived xi give G(s)f(s) = eta G(1-s)f(1-s)."""
    chk = check_functional_equation(xi=xi_for_sign(eta), eta=eta)
    assert chk["max_rel_diff"] < 1e-10


def test_the_two_branches_are_distinguished_by_a_2():
    """|a_2| > 1 is exactly what lets f vanish to the right of Re s = 1."""
    assert abs(XI_EVEN) < 1.0
    assert abs(XI) > 1.0
    assert ETA == -1
    assert coefficients(XI)[0] == 1.0
    assert coefficients(XI)[3] == -1.0
    assert coefficients(XI)[4] == 0.0


def test_zeros_exist_off_the_critical_line():
    """The headline fact. zeta has NO zeros with Re s > 1; f has several."""
    zs = find_zeros_in_rectangle(complex(1.02, 0.05), complex(3.0, 60.0),
                                 grid=40, xi=XI)
    assert len(zs) >= 4
    for z in zs:
        assert z.real > 1.0
        assert abs(f(z, XI)) < 1e-9
        assert abs(zeta(z)) > 0.5          # zeta is nowhere near zero there


def test_reflection_involution_holds():
    """rho -> 1 - conj(rho) maps zeros to zeros; verified relatively."""
    zs = find_zeros_in_rectangle(complex(1.02, 0.05), complex(3.0, 40.0),
                                 grid=34, xi=XI)
    assert zs
    for z in zs:
        r = 1 - z.conjugate()
        here = abs(f(r, XI))
        nearby = abs(f(r + 0.15, XI))
        assert here / nearby < 1e-6        # a zero relative to the local scale


def test_both_branches_have_zeros_off_the_line():
    """Neither branch obeys an analogue of RH -- but you must look high enough.

    Regression test for a real error: a search stopping at ``Im s = 60`` found
    all 28 of the ``eta = +1`` branch's zeros on the critical line and invited
    the conclusion that it satisfies RH.  Its first off-line zero is at
    ``Im s = 85.7``.
    """
    for xi in (XI, XI_EVEN):
        zs = find_zeros_in_rectangle(complex(-0.6, 0.05), complex(1.6, 120.0),
                                     grid=60, xi=xi)
        off = [z for z in zs if abs(z.real - 0.5) >= 1e-6]
        assert off, "expected zeros off the critical line"
        for z in off:
            assert abs(f(z, xi)) < 1e-9


def test_off_line_zeros_come_in_reflected_pairs():
    """``rho`` and ``1 - conj(rho)`` share a height and straddle the line."""
    zs = find_zeros_in_rectangle(complex(-0.6, 0.05), complex(1.6, 120.0),
                                 grid=60, xi=XI_EVEN)
    off = [z for z in zs if abs(z.real - 0.5) >= 1e-6]
    heights = sorted({round(z.imag, 5) for z in off})
    assert heights
    for h in heights:
        at_h = sorted(z.real for z in off if abs(z.imag - h) < 1e-4)
        assert len(at_h) >= 2
        assert at_h[0] + at_h[-1] == pytest.approx(1.0, abs=1e-6)
