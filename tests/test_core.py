"""Validation against mpmath as an independent oracle.

Nothing in ``riemann/`` uses mpmath; it is imported only here.  That keeps the
verification genuinely independent -- these tests compare two separately
written implementations rather than checking an implementation against itself.
"""

from __future__ import annotations

import math

import mpmath as mp
import pytest

from riemann.counting import N, S
from riemann.equivalences import (
    li_coefficient_exact_first,
    li_coefficients,
    mertens,
    mobius_sieve,
)
from riemann.explicit_formula import psi_exact, psi_from_zeros, von_mangoldt_sieve
from riemann.riemann_siegel import (
    Z,
    Z_via_zeta,
    correction_coefficient,
    gram_point,
    psi_derivative,
    theta,
    theta_asymptotic,
)
from riemann.special import bernoulli, log_gamma
from riemann.statistics import gue_spacing_density, spacings, unfold
from riemann.zeros import find_zeros, mean_gap
from riemann.zeta import eta, zeta, zeta_with_error

mp.mp.dps = 30


# ---------------------------------------------------------------------------
# special functions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("k", [2, 4, 6, 8, 12, 20, 30])
def test_bernoulli_matches_mpmath(k):
    assert bernoulli(k) == pytest.approx(float(mp.bernoulli(k)), rel=1e-13)


@pytest.mark.parametrize("z", [3.5 + 0j, 0.25 + 5j, 0.25 + 500j, 2 + 0.3j, 1 + 1j])
def test_log_gamma_matches_mpmath(z):
    assert abs(log_gamma(z) - complex(mp.loggamma(z))) < 1e-11


def test_log_gamma_raises_at_poles():
    with pytest.raises(ValueError):
        log_gamma(0)
    with pytest.raises(ValueError):
        log_gamma(-3)


# ---------------------------------------------------------------------------
# zeta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "s",
    [2 + 0j, 3 + 4j, 0.5 + 14.134725j, 0.5 + 100j, 0.5 + 1000j, -0.5 + 2j, 0.75 + 30j],
)
def test_zeta_matches_mpmath(s):
    value, bound = zeta_with_error(s)
    assert abs(value - complex(mp.zeta(s))) < max(bound, 1e-12)


def test_zeta_error_bound_is_not_optimistic():
    """The reported bound must actually bound the observed error."""
    for t in (50.0, 200.0, 800.0):
        s = 0.5 + 1j * t
        value, bound = zeta_with_error(s)
        assert abs(value - complex(mp.zeta(s))) <= bound


def test_zeta_pole_raises():
    with pytest.raises(ValueError):
        zeta(1.0)


@pytest.mark.parametrize("s", [0.5 + 14.134725j, 2 + 0j, 0.5 + 30j, 1.5 + 3j])
def test_eta_route_agrees_with_euler_maclaurin(s):
    """Dirichlet eta is a completely different series; it must agree."""
    assert abs(eta(s, 60) / (1 - 2 ** (1 - s)) - zeta(s)) < 1e-11


# ---------------------------------------------------------------------------
# Riemann-Siegel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t", [20.0, 100.0, 1000.0, 1e4, 1e5])
def test_theta_matches_mpmath(t):
    assert theta(t) == pytest.approx(float(mp.siegeltheta(t)), abs=1e-9)


@pytest.mark.parametrize("t", [50.0, 500.0, 5000.0, 50000.0])
def test_theta_asymptotic_agrees_with_exact(t):
    assert theta(t) == pytest.approx(theta_asymptotic(t), abs=1e-8)


def test_psi_removable_singularities():
    """Psi(p) = cos(2 pi (p^2-p-1/16))/cos(2 pi p) is 0/0 at p = 1/4, 3/4.

    Both are removable with value 1/2 (L'Hopital).  The Cauchy-integral route
    must produce that rather than a division blow-up.
    """
    assert psi_derivative(0.25, 0) == pytest.approx(0.5, abs=1e-10)
    assert psi_derivative(0.75, 0) == pytest.approx(0.5, abs=1e-10)


def test_correction_coefficients_antisymmetry():
    """C_1 and C_3 are odd about p = 1/2, so they vanish there."""
    assert correction_coefficient(0.5, 1) == pytest.approx(0.0, abs=1e-9)
    assert correction_coefficient(0.5, 3) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("t", [1000.0, 12345.6, 74920.0])
def test_Z_matches_mpmath_siegelz(t):
    """Accuracy in the regime Riemann-Siegel is actually used for."""
    assert Z(t) == pytest.approx(float(mp.siegelz(t)), abs=1e-8)


@pytest.mark.parametrize("t,worst", [(20.0, 1e-4), (30.0, 1e-5), (100.0, 1e-7)])
def test_Z_low_t_degradation_is_as_documented(t, worst):
    """Riemann-Siegel is asymptotic and genuinely weak at low t.

    This pins the documented behaviour in both directions: the error must stay
    under the stated ceiling, and must not be suspiciously tiny either (which
    would mean the truncation order silently changed).  It is precisely this
    degradation that makes ``find_zeros`` re-polish low zeros with
    Euler-Maclaurin -- without that, the first zeros come out to only five or
    six correct digits.
    """
    err = abs(Z(t) - float(mp.siegelz(t)))
    assert err < worst
    assert err > 1e-12


@pytest.mark.parametrize("t", [30.0, 100.0, 400.0])
def test_Z_riemann_siegel_agrees_with_euler_maclaurin(t):
    assert Z(t) == pytest.approx(Z_via_zeta(t), abs=1e-5)


def test_riemann_siegel_order3_beats_order2():
    """Guards the C_3 constants: order 3 must be more accurate than order 2.

    An earlier wrong denominator (15360 instead of 3840 on Psi^(5)) made order
    3 *worse*, and this is the assertion that catches that class of error.
    """
    total2 = total3 = 0.0
    for t in (2000.0, 4000.0, 8000.0, 16000.0, 32000.0):
        exact = float(mp.siegelz(t))
        total2 += abs(Z(t, 2) - exact)
        total3 += abs(Z(t, 3) - exact)
    assert total3 < total2 / 10.0


def test_gram_points():
    # Values obtained independently by root-finding on mpmath.siegeltheta.
    for n, known in [(-1, 9.6669080561302), (0, 17.845599540411),
                     (1, 23.170282701246), (2, 27.670182217816)]:
        g = gram_point(n)
        assert g == pytest.approx(known, abs=1e-9)
        assert theta(g) == pytest.approx(n * math.pi, abs=1e-9)


# ---------------------------------------------------------------------------
# counting and zeros
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("T,expected", [(100.0, 29), (235.0, 99), (1000.0, 649),
                                        (10000.0, 10142)])
def test_zero_count_known_values(T, expected):
    count, residual = N(T)
    assert count == expected
    assert residual < 1e-6  # a large residual means the count is not trustworthy


def test_S_is_small():
    """S(T) is O(log T) but is tiny in practice; a big value signals a bug."""
    for T in (100.0, 1000.0, 10000.0):
        assert abs(S(T)) < 3.0


def test_first_zeros_match_mpmath():
    zeros = find_zeros(14.0, 100.0)
    assert len(zeros) == 29
    for i, z in enumerate(zeros):
        assert z == pytest.approx(float(mp.im(mp.zetazero(i + 1))), abs=1e-9)


def test_zero_search_finds_the_lehmer_pair():
    """The pair near t = 7005.06 is the classic near-miss; a coarse scan that
    does not verify against the strip count will silently lose it."""
    zeros = find_zeros(7000.0, 7010.0)
    close = [(b - a) for a, b in zip(zeros, zeros[1:])]
    assert min(close) == pytest.approx(0.0377, abs=1e-3)


def test_zero_search_is_complete_over_a_range():
    lo, hi = 500.0, 700.0
    zeros = find_zeros(lo, hi)
    assert len(zeros) == N(hi)[0] - N(lo)[0]


def test_mean_gap_matches_observed_density():
    zeros = find_zeros(1000.0, 1200.0)
    observed = (zeros[-1] - zeros[0]) / (len(zeros) - 1)
    assert observed == pytest.approx(mean_gap(1100.0), rel=0.05)


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

def test_unfolding_gives_unit_mean_spacing():
    zeros = find_zeros(1000.0, 2000.0)
    s = spacings(zeros)
    assert sum(s) / len(s) == pytest.approx(1.0, abs=0.01)


def test_gue_density_is_normalised_with_unit_mean():
    h, top = 1e-3, 12.0
    n = int(top / h)
    mass = sum(gue_spacing_density((i + 0.5) * h) * h for i in range(n))
    mean = sum((i + 0.5) * h * gue_spacing_density((i + 0.5) * h) * h for i in range(n))
    assert mass == pytest.approx(1.0, abs=1e-6)
    assert mean == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# arithmetic side
# ---------------------------------------------------------------------------

def test_mobius_and_mertens_known_values():
    mu = mobius_sieve(100)
    assert [mu[n] for n in (1, 2, 3, 4, 5, 6, 30, 49)] == [1, -1, -1, 0, -1, 1, -1, 0]
    m = mertens(1000000)
    assert m[1000000] == 212  # classical value


def test_von_mangoldt_and_psi():
    lam = von_mangoldt_sieve(50)
    assert lam[8] == pytest.approx(math.log(2))
    assert lam[9] == pytest.approx(math.log(3))
    assert lam[6] == 0.0
    psi = psi_exact(1000)
    # psi(x) ~ x by the prime number theorem
    assert psi[1000] == pytest.approx(1000.0, rel=0.02)


def test_li_lambda_1_against_closed_form():
    zeros = find_zeros(14.0, 2000.0)
    lam = li_coefficients(1, zeros)
    # Truncating the zero sum leaves a tail of size ~ log(T)/T.
    assert lam[0] == pytest.approx(li_coefficient_exact_first(), abs=5e-3)


def test_xi_is_symmetric_about_the_critical_line():
    """xi(s) = xi(1-s) -- the functional equation in its cleanest form."""
    from riemann.zeta import xi
    for s in (2 + 3j, 0.5 + 14.134725j, 0.3 + 7j, -0.4 + 2j):
        assert abs(xi(s) - xi(1 - s)) < 1e-12 * max(1.0, abs(xi(s)))


def test_xi_vanishes_at_a_zeta_zero():
    from riemann.zeta import xi
    assert abs(xi(0.5 + 14.134725141734695j)) < 1e-15


def test_lagarias_inequality_holds():
    from riemann.equivalences import check_lagarias
    r = check_lagarias(3000)
    assert r["holds"]
    assert r["smallest_slack"] >= 0.0


def test_robin_ratio_stays_below_e_gamma():
    from riemann.equivalences import check_robin
    r = check_robin(40000)
    assert r["violations"] == []
    assert r["max_ratio"] < r["e_gamma"]


def test_colossally_abundant_ratio_climbs_towards_e_gamma():
    """Gronwall: the limsup is exactly e^gamma, approached along these numbers.

    Regression test for a real error: with too short a prime list the greedy
    search exhausts it, is forced to keep raising exponents on primes it
    already has, and the ratio turns around and FALLS -- contradicting the
    theorem.
    """
    from riemann.equivalences import EULER_GAMMA, colossally_abundant_candidates
    ca = colossally_abundant_candidates(4000)
    assert not ca[-1]["prime_list_exhausted"]
    assert ca[-1]["robin_ratio"] > ca[len(ca) // 4]["robin_ratio"]
    assert ca[-1]["margin"] > 0
    assert ca[-1]["robin_ratio"] < math.exp(EULER_GAMMA)


def test_explicit_formula_reconstructs_psi():
    zeros = find_zeros(14.0, 1500.0)
    for x in (20.5, 50.5, 90.5):
        approx = psi_from_zeros(x, zeros)
        assert approx == pytest.approx(psi_exact(int(x))[int(x)], abs=2.0)
