"""Counting zeros in the critical strip -- the argument principle.

Locating zeros on the critical line is only half the job.  To say anything
about RH one must also know how many zeros the strip contains *in total* up to
height ``T``; if those two numbers agree, every zero below ``T`` is on the
line.  This module supplies the total.

The Riemann-von Mangoldt formula
--------------------------------
.. math::
   N(T) = \\frac{\\theta(T)}{\\pi} + 1 + S(T),
   \\qquad S(T) = \\frac1\\pi \\arg\\zeta\\!\\left(\\tfrac12 + iT\\right),

where the argument is defined by continuous variation along the path
``2 -> 2 + iT -> 1/2 + iT`` starting from ``arg zeta(2) = 0``.  The first two
terms are smooth and explicitly computable; all the arithmetic subtlety sits in
``S(T)``, which is known to be ``O(log T)`` but is conjectured (and numerically
observed) to be extremely small on average -- its mean value is ``0``, and it
is unbounded only very slowly.

Why the vertical leg is free
----------------------------
On the line ``Re s = 2`` we have ``|zeta(s) - 1| <= sum_{n>=2} n^{-2}
= pi^2/6 - 1 = 0.6449... < 1``, so ``zeta`` stays inside the disc of radius
``0.645`` about ``1``.  That disc misses the origin entirely, so the argument
cannot wind: the principal value of ``arg zeta(2 + iT)`` *is* its continuous
value.  Only the horizontal leg needs to be tracked, and it is tracked by
adaptive subdivision -- refining wherever consecutive samples move the argument
by more than a set amount, so a jump of a full turn cannot be missed.
"""

from __future__ import annotations

import cmath
import math

from .riemann_siegel import theta
from .zeta import zeta

try:  # optional acceleration; identical arithmetic, ~50x faster on the line
    from .fast import HorizontalLine

    _HAVE_FAST = True
except ImportError:  # pragma: no cover
    _HAVE_FAST = False

__all__ = [
    "S",
    "N",
    "riemann_von_mangoldt_smooth",
    "count_zeros_in_strip",
    "zero_count_consistency",
]

_MAX_STEP_ARG = 0.35  # radians; consecutive samples may not turn more than this


def riemann_von_mangoldt_smooth(T: float) -> float:
    """The smooth part ``theta(T)/pi + 1`` of the zero-counting function.

    Asymptotically ``(T/2pi) log(T/2pi e) + 7/8``.  Rounding this alone already
    predicts ``N(T)`` correctly the overwhelming majority of the time, because
    ``S(T)`` is usually small -- but "usually" is not "always", which is exactly
    why ``S`` must be computed rather than assumed.
    """
    return theta(T) / math.pi + 1.0


def S(T: float, sigma_start: float = 2.0) -> float:
    """``S(T) = arg zeta(1/2 + iT) / pi`` by continuous variation.

    The horizontal leg from ``sigma_start + iT`` to ``1/2 + iT`` is walked with
    adaptive subdivision: whenever two consecutive samples differ in argument by
    more than :data:`_MAX_STEP_ARG`, the interval between them is bisected.
    """
    if _HAVE_FAST:
        line = HorizontalLine(T)
        evaluate = line.at
    else:  # pragma: no cover
        def evaluate(sigma):
            return zeta(complex(sigma, T))

    z_start = evaluate(sigma_start)
    arg_total = cmath.phase(z_start)  # no winding on Re s = 2 (see module docs)

    def walk(s_a: float, z_a: complex, s_b: float, z_b: complex, depth: int) -> float:
        delta = cmath.phase(z_b / z_a)  # principal, in (-pi, pi]
        if abs(delta) <= _MAX_STEP_ARG or depth >= 40:
            return delta
        mid = 0.5 * (s_a + s_b)
        z_mid = evaluate(mid)
        return walk(s_a, z_a, mid, z_mid, depth + 1) + walk(mid, z_mid, s_b, z_b, depth + 1)

    n_coarse = 24
    sigmas = [sigma_start + (0.5 - sigma_start) * i / n_coarse for i in range(n_coarse + 1)]
    prev_s, prev_z = sigmas[0], z_start
    for s_next in sigmas[1:]:
        z_next = evaluate(s_next)
        arg_total += walk(prev_s, prev_z, s_next, z_next, 0)
        prev_s, prev_z = s_next, z_next

    return arg_total / math.pi


def N(T: float) -> tuple:
    """Return ``(count, residual)``: the number of zeros with ``0 < Im rho < T``.

    ``count`` is an integer; ``residual`` is the distance of the raw value from
    that integer, and is a direct quality indicator -- a residual near ``0.5``
    means the computation is untrustworthy (``T`` is probably too close to a
    zero ordinate), while a residual below ``1e-6`` means the count is solid.
    """
    raw = riemann_von_mangoldt_smooth(T) + S(T)
    nearest = round(raw)
    return int(nearest), abs(raw - nearest)


def count_zeros_in_strip(t_lo: float, t_hi: float) -> int:
    """Number of zeros with ordinate in ``(t_lo, t_hi]``, from the argument principle."""
    hi, _ = N(t_hi)
    lo, _ = N(t_lo)
    return hi - lo


def zero_count_consistency(zeros, t_lo: float, t_hi: float) -> dict:
    """Compare a list of found critical-line zeros against the strip total.

    This is the step that turns "we found a lot of zeros on the line" into
    "every zero in this range is on the line, and simple".  If ``found`` equals
    ``expected``, then in ``(t_lo, t_hi]`` the zeros are exactly the ones
    located, all of them lie on ``Re s = 1/2``, and all are simple (a multiple
    zero would show up as a deficit in the sign-change count).
    """
    found = sum(1 for z in zeros if t_lo < z <= t_hi)
    expected = count_zeros_in_strip(t_lo, t_hi)
    n_hi, r_hi = N(t_hi)
    n_lo, r_lo = N(t_lo)
    return {
        "t_lo": t_lo,
        "t_hi": t_hi,
        "found_on_line": found,
        "expected_in_strip": expected,
        "all_accounted_for": found == expected,
        "N(t_hi)": n_hi,
        "N(t_lo)": n_lo,
        "residual": max(r_hi, r_lo),
        "S(t_hi)": S(t_hi),
    }
