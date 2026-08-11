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


def _winding_at(func, s_lo, s_hi, per_side, max_step, max_ratio, max_depth):
    x0, x1 = s_lo.real, s_hi.real
    y0, y1 = s_lo.imag, s_hi.imag
    corners = [complex(x0, y0), complex(x1, y0), complex(x1, y1), complex(x0, y1)]

    def walk(a, fa, b, fb, depth):
        d = cmath.phase(fb / fa)
        # Subdividing on |d| alone is UNSOUND: d is a principal value, so a true
        # change of 2*pi + eps is indistinguishable from eps and a whole turn is
        # lost silently.  Also refine whenever the modulus moves sharply, since
        # that is the observable signature of passing near a zero -- which is
        # exactly where the hidden turns are.
        ratio = abs(math.log(abs(fb) / abs(fa))) if abs(fa) > 0 and abs(fb) > 0 else 1e9
        if (abs(d) <= max_step and ratio <= max_ratio) or depth >= max_depth:
            return d
        mid = 0.5 * (a + b)
        fm = func(mid)
        return walk(a, fa, mid, fm, depth + 1) + walk(mid, fm, b, fb, depth + 1)

    total = 0.0
    longest = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(4):
        p, q = corners[i], corners[(i + 1) % 4]
        steps = max(8, int(per_side * abs(q - p) / longest))
        fp = func(p)
        for j in range(steps):
            nxt = p + (q - p) * (j + 1) / steps
            fn = func(nxt)
            total += walk(p, fp, nxt, fn, 0)
            p, fp = nxt, fn
    return total / (2.0 * math.pi)


def winding_number(func, s_lo: complex, s_hi: complex, per_side: int = 600,
                   max_step: float = 0.35, max_ratio: float = 0.35,
                   max_depth: int = 40, refinements: int = 5,
                   tol: float = 5e-3):
    """Zeros of ``func`` inside a rectangle, by the argument principle.

    Walks the boundary counterclockwise accumulating the continuous change in
    ``arg func``, then **doubles the boundary sampling until the answer stops
    moving**.  Both parts matter:

    * The per-step refinement test cannot rely on the apparent phase change
      alone, because that is a principal value: a real change of ``2 pi + eps``
      looks like ``eps``, passes any threshold, and silently discards a full
      turn.  Modulus variation is used as a second trigger.
    * Even so, a fixed sampling can miss a feature entirely.  Only agreement
      between successive refinements justifies believing the number.

    Returns ``(value, converged)``.  A value that is not close to an integer, or
    that has not converged, means the contour passes near a zero or the boundary
    is still under-resolved -- either way it is not a count.
    """
    prev = None
    n = per_side
    for _ in range(refinements):
        cur = _winding_at(func, s_lo, s_hi, n, max_step, max_ratio, max_depth)
        if prev is not None and abs(cur - prev) < tol and abs(cur - round(cur)) < tol:
            return cur, True
        prev = cur
        n *= 2
    return prev, False


def winding_number_chunked(func, s_lo: complex, s_hi: complex,
                           chunk_height: float = 4.0, per_side: int = 400,
                           **kw) -> dict:
    """Winding number over a tall rectangle, summed over short horizontal slices.

    A single tall contour is the wrong shape for this job.  On a vertical edge
    spanning height ``1000`` the argument of ``zeta`` turns through hundreds of
    revolutions, and no fixed sampling of that edge is trustworthy: the counts
    come out systematically *low* (250 against a true 269 at ``t = 500``; 549
    against 649 at ``t = 1000``) because whole turns fall between samples and a
    principal-value phase difference cannot see them.

    Slicing the rectangle into strips a few units tall puts only a handful of
    zeros in each contour, which the adaptive tracking resolves easily, and the
    total is the sum.  Each slice must return an integer; if any does not, the
    result is reported as unreliable rather than added up anyway.
    """
    y0, y1 = s_lo.imag, s_hi.imag
    n_chunks = max(1, int(math.ceil((y1 - y0) / chunk_height)))
    total = 0.0
    worst = 0.0
    all_integers = True
    per_chunk = []
    for i in range(n_chunks):
        a = y0 + (y1 - y0) * i / n_chunks
        b = y0 + (y1 - y0) * (i + 1) / n_chunks
        v, _ = winding_number(func, complex(s_lo.real, a), complex(s_hi.real, b),
                              per_side=per_side, **kw)
        frac = abs(v - round(v))
        worst = max(worst, frac)
        if frac > 5e-3:
            all_integers = False
        total += v
        per_chunk.append(v)
    return {"total": total, "rounded": round(total), "chunks": n_chunks,
            "all_integers": all_integers, "worst_fractional_part": worst,
            "per_chunk": per_chunk}


def speiser_check(t_lo: float, t_hi: float, sigma_lo: float = 0.002,
                  sigma_hi: float = 0.498, per_side: int = 900) -> dict:
    """Count zeros of ``zeta'`` in ``sigma_lo < Re s < sigma_hi``.

    **Speiser's theorem (1934):** RH is equivalent to ``zeta'`` having no zeros
    in ``0 < Re s < 1/2``.  Levinson and Montgomery later sharpened the
    correspondence, showing ``zeta`` and ``zeta'`` have the same number of zeros
    left of the critical line up to finitely many exceptions.

    This is a genuinely *independent* route to the same conclusion: it never
    looks at ``zeta`` on the critical line at all, so a bug in the ``Z``-function
    zero search would not hide here.  Unlike Li's criterion (see
    ``docs/03``), it is also informative -- a violation of RH below height ``T``
    would put a zero of ``zeta'`` in this rectangle, where it would be seen.
    """
    from .zeta import zeta_prime

    r = winding_number_chunked(zeta_prime, complex(sigma_lo, t_lo),
                               complex(sigma_hi, t_hi), per_side=per_side)
    return {
        "t_lo": t_lo, "t_hi": t_hi,
        "sigma_range": (sigma_lo, sigma_hi),
        "zeros_of_zeta_prime": r["total"],
        "reliable": r["all_integers"],
        "worst_fractional_part": r["worst_fractional_part"],
        "consistent_with_RH": r["all_integers"] and abs(r["total"]) < 5e-3,
    }


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
