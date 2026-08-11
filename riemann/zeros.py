"""Locating zeros of ``zeta`` on the critical line.

Strategy
--------
``Z(t)`` is real, so a zero of ``zeta`` on the critical line shows up as a sign
change of ``Z`` -- something a computer can detect with total reliability.  The
only real difficulty is *missing* zeros: two zeros very close together produce
two sign changes that a coarse grid straddles in a single step, and the scan
silently reports none.

So the search is deliberately structured in two parts:

1. Scan on a grid fine enough that a miss is unlikely, and refine every sign
   change by bisection.
2. **Independently** count the zeros in the strip with the argument principle
   (:mod:`riemann.counting`) and check the two numbers agree.

Step 2 is what makes the result meaningful.  Without it one can only say "we
found some zeros on the line"; with it one can say "in this range every zero of
``zeta`` lies on the critical line and is simple".  Where the counts disagree,
:func:`find_zeros` automatically rescans the suspicious neighbourhoods at
higher resolution rather than reporting a number it cannot justify.
"""

from __future__ import annotations

import bisect
import math

from .counting import N, count_zeros_in_strip
from .riemann_siegel import RS_MAX_ORDER, Z, Z_via_zeta, gram_point, theta

try:  # optional acceleration
    import numpy as np

    from .fast import Z_array

    _HAVE_FAST = True
except ImportError:  # pragma: no cover - exercised only without numpy
    _HAVE_FAST = False

__all__ = [
    "mean_gap",
    "find_zeros",
    "first_n_zeros",
    "normalised_gaps",
    "lehmer_pairs",
    "estimate_height_for_count",
    "noise_floor",
]

TWO_PI = 2.0 * math.pi
_FAST_MIN_T = 15.0


def mean_gap(t: float) -> float:
    """Average spacing between consecutive zero ordinates near height ``t``.

    Differentiating ``N(t) ~ (t/2pi) log(t/2pi e)`` gives density
    ``log(t/2pi) / 2pi``, hence gap ``2pi / log(t/2pi)``.  At ``t = 10^4`` this
    is ``0.68``; at ``t = 10^{12}`` it is ``0.23``.  Zeros get denser, but only
    logarithmically -- which is why brute-force verification remains feasible to
    remarkable heights.
    """
    return TWO_PI / math.log(t / TWO_PI)


def estimate_height_for_count(n: int) -> float:
    """Height ``T`` at which roughly ``n`` zeros have occurred (inverts ``N``)."""
    if n < 1:
        return 15.0
    t = max(20.0, TWO_PI * math.e * n / max(math.log(n + 2.0), 1.0))
    for _ in range(200):
        f = theta(t) / math.pi + 1.0 - n
        fp = 0.5 * math.log(t / TWO_PI) / math.pi
        step = f / fp
        t -= step
        if t < 15.0:
            t = 15.0
        if abs(step) < 1e-10 * t:
            break
    return t


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------

def _scan_scalar(t_lo, t_hi, step, order):
    brackets = []
    t = t_lo
    prev_t, prev_z = t, Z(t, order)
    while t < t_hi:
        t = min(t + step, t_hi)
        z = Z(t, order)
        if prev_z == 0.0:
            brackets.append((prev_t - 1e-9, prev_t + 1e-9))
        elif (prev_z > 0.0) != (z > 0.0):
            brackets.append((prev_t, t))
        prev_t, prev_z = t, z
        if t >= t_hi:
            break
    return brackets


def _refine_scalar(brackets, order, iters=80):
    out = []
    for lo, hi in brackets:
        flo = Z(lo, order)
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            if mid <= lo or mid >= hi:
                break
            fmid = Z(mid, order)
            if (flo > 0.0) == (fmid > 0.0):
                lo, flo = mid, fmid
            else:
                hi = mid
        out.append(0.5 * (lo + hi))
    return out


def _scan_fast(t_lo, t_hi, step, order):
    n_pts = int(math.ceil((t_hi - t_lo) / step)) + 1
    grid = t_lo + step * np.arange(n_pts, dtype=float)
    grid[-1] = min(grid[-1], t_hi)
    vals = Z_array(grid, order)
    sign_change = np.signbit(vals[:-1]) != np.signbit(vals[1:])
    idx = np.nonzero(sign_change)[0]
    return grid[idx], grid[idx + 1], vals[idx], grid, vals


def _refine_fast(lo, hi, flo, order, iters=60):
    lo = lo.copy()
    hi = hi.copy()
    flo = flo.copy()
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fmid = Z_array(mid, order)
        same = np.signbit(fmid) == np.signbit(flo)
        lo = np.where(same, mid, lo)
        flo = np.where(same, fmid, flo)
        hi = np.where(same, hi, mid)
        if np.all(hi - lo < 1e-13 * np.maximum(1.0, np.abs(lo))):
            break
    return 0.5 * (lo + hi)


def find_zeros(
    t_lo: float = 14.0,
    t_hi: float = 100.0,
    density: float = 8.0,
    order: int = RS_MAX_ORDER,
    verify: bool = True,
    max_rescans: int = 6,
    polish_below: float = 1000.0,
    verbose: bool = False,
) -> list:
    """Ordinates of the zeros of ``zeta(1/2 + it)`` for ``t_lo < t <= t_hi``.

    Parameters
    ----------
    density:
        Sample points per mean zero gap.  ``8`` is comfortable; close pairs are
        caught by the verification step regardless.
    verify:
        Cross-check the tally against the argument-principle count and rescan
        locally until they agree.  Turning this off makes the result *fast* but
        no longer a statement about all zeros in the strip.
    polish_below:
        Zeros below this height are re-refined with Euler-Maclaurin, which has
        no asymptotic error floor.  See :func:`_polish_exact`.
    """
    if t_lo >= t_hi:
        return []

    step = mean_gap(t_hi) / density
    zeros = []

    # Region below the Riemann-Siegel cutoff: scalar path (uses Euler-Maclaurin).
    split = max(t_lo, min(t_hi, _FAST_MIN_T + 5.0))
    if t_lo < split:
        b = _scan_scalar(t_lo, split, min(step, 0.05), order)
        zeros.extend(_refine_scalar(b, order))

    grid = vals = None
    if split < t_hi:
        if _HAVE_FAST:
            lo, hi, flo, grid, vals = _scan_fast(split, t_hi, step, order)
            if lo.size:
                zeros.extend(_refine_fast(lo, hi, flo, order).tolist())
        else:  # pragma: no cover
            b = _scan_scalar(split, t_hi, step, order)
            zeros.extend(_refine_scalar(b, order))

    zeros.sort()

    if not verify:
        return zeros

    expected = count_zeros_in_strip(t_lo, t_hi)
    rescans = 0
    while len(zeros) != expected and rescans < max_rescans:
        rescans += 1
        missing = expected - len(zeros)
        if missing < 0:
            # More roots than the strip contains means the search manufactured
            # some; that is a bug, not something to paper over by trimming.
            raise RuntimeError(
                f"found {len(zeros)} zeros but the argument principle allows only "
                f"{expected} over ({t_lo}, {t_hi}] -- spurious roots detected"
            )
        if verbose:
            print(f"  pass {rescans}: {len(zeros)} found, {expected} expected "
                  f"({missing} missing); localising by argument principle")
        for a, b, need in locate_deficits(zeros, t_lo, t_hi, verbose=verbose):
            for z in _hunt_interval(a, b, need, order, verbose):
                k = bisect.bisect_left(zeros, z)
                near = min((abs(z - zeros[j]) for j in (k - 1, k) if 0 <= j < len(zeros)),
                           default=math.inf)
                if near > 1e-7 and t_lo < z <= t_hi:
                    zeros.insert(k, z)
        zeros.sort()

    if polish_below > t_lo:
        zeros = _polish_exact(zeros, min(polish_below, t_hi))

    if len(zeros) != expected:
        raise RuntimeError(
            f"zero search did not close: found {len(zeros)} on the line but the "
            f"argument principle reports {expected} in the strip over "
            f"({t_lo}, {t_hi}]. Increase `density` or `max_rescans`."
        )
    return zeros


def noise_floor(t: float) -> float:
    """Estimated absolute accuracy of the computed ``Z(t)`` in double precision.

    The limiting factor is not the Riemann-Siegel truncation but the *argument*
    of the cosines: ``theta(t)`` grows like ``(t/2) log(t/2 pi)``, reaching
    ``3.1e5`` at ``t = 75000``, so representing it as a double already costs
    ``~7e-11`` of absolute error.  That error enters every term of the main sum,
    and ``|dZ/dtheta|`` is of order ``sqrt(N) = tau^{1/2}``, giving

    .. math::  \\text{floor}(t) \\approx 16\\,\\epsilon\\,|\\theta(t)|\\,\\tau^{1/2}.

    This matters for more than bookkeeping: any search that hunts for zeros in
    the places where ``|Z|`` is *smallest* is hunting precisely where roundoff
    dominates, and will happily "find" sign changes that are pure noise.
    """
    tau = math.sqrt(max(t, 15.0) / TWO_PI)
    return 16.0 * 2.220446049250313e-16 * abs(theta(t)) * math.sqrt(tau)


def locate_deficits(zeros, t_lo, t_hi, resolve_width=0.5, verbose=False):
    """Bisect on the argument principle to pin down *where* zeros are missing.

    Guessing which grid cells hide a missed zero does not work well.  The
    obvious heuristic -- rank cells by the smallest sampled ``|Z|`` -- fails in
    both directions: a close pair need not produce a small *sampled* value, and
    the cells with the smallest values are the ones where roundoff dominates,
    so the heuristic simultaneously misses real zeros and invents fake ones.

    The argument principle answers the question directly.  ``N(t)`` is available
    at any height, so comparing it against the running tally of located zeros
    gives an exact deficit for any subinterval; recursing into whichever halves
    carry a nonzero deficit localises every missing zero to a short interval in
    ``O(log)`` evaluations.  Nothing is guessed, and a deficit cannot be
    silently mislaid.

    Returns a list of ``(a, b, count)`` intervals whose total is the deficit.
    """
    order = sorted(zeros)

    def found_in(a, b):
        return bisect.bisect_right(order, b) - bisect.bisect_right(order, a)

    cache = {}

    def count_to(t):
        if t not in cache:
            cache[t] = N(t)[0]
        return cache[t]

    def recurse(a, b, depth):
        deficit = (count_to(b) - count_to(a)) - found_in(a, b)
        if deficit == 0:
            return []
        if b - a <= resolve_width or depth > 60:
            if verbose:
                print(f"    deficit {deficit} localised to ({a:.6f}, {b:.6f})")
            return [(a, b, deficit)]
        mid = 0.5 * (a + b)
        return recurse(a, mid, depth + 1) + recurse(mid, b, depth + 1)

    return recurse(t_lo, t_hi, 0)


def _hunt_interval(a, b, need, order, verbose=False):
    """Exhaustively find ``need`` extra zeros in a short interval.

    The interval is tiny by the time this runs, so the step can be shrunk
    aggressively.  Refinement stops at :func:`noise_floor`: below that scale a
    sign change carries no information, and reporting one would be inventing
    data rather than measuring it.
    """
    floor = 20.0 * noise_floor(b)
    step = (b - a) / 64.0
    for _ in range(24):
        n_pts = int(math.ceil((b - a) / step)) + 1
        if _HAVE_FAST:
            grid = a + (b - a) * np.arange(n_pts) / (n_pts - 1)
            vals = Z_array(grid, order)
            crossing = np.signbit(vals[:-1]) != np.signbit(vals[1:])
            solid = np.maximum(np.abs(vals[:-1]), np.abs(vals[1:])) > floor
            idx = np.nonzero(crossing & solid)[0]
            roots = _refine_fast(grid[idx], grid[idx + 1], vals[idx], order).tolist() \
                if idx.size else []
        else:  # pragma: no cover
            roots = _refine_scalar(_scan_scalar(a, b, step, order), order)
        if len(roots) >= need:
            return roots
        step /= 4.0
    if verbose:
        print(f"    WARNING: only {len(roots)} of {need} recovered in ({a}, {b})")
    return roots


def _polish_exact(zeros, t_max, gap_frac=0.02):
    """Re-refine low-lying zeros with Euler-Maclaurin instead of Riemann-Siegel.

    Riemann-Siegel is *asymptotic*: truncated at ``C_3`` its error is around
    ``1e-6`` near ``t = 50`` and only drops below ``1e-9`` past ``t ~ 1000``.
    Since ``|Z'|`` is ``O(1)`` there, that error transfers almost one-for-one
    into the location of the root -- which is why the low zeros come out with
    only five or six correct digits.  Euler-Maclaurin has no such floor, so
    below ``t_max`` the roots are re-bracketed and bisected against it.  The
    cost is ``O(t)`` per evaluation, which is why it is not used everywhere.
    """
    out = []
    for z in zeros:
        if z > t_max:
            out.append(z)
            continue
        h = gap_frac * mean_gap(z)
        lo = hi = None
        for _ in range(8):
            a, b = z - h, z + h
            fa, fb = Z_via_zeta(a), Z_via_zeta(b)
            if (fa > 0.0) != (fb > 0.0):
                lo, hi, flo = a, b, fa
                break
            h *= 2.0
        if lo is None:
            out.append(z)
            continue
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            if mid <= lo or mid >= hi:
                break
            fmid = Z_via_zeta(mid)
            if (flo > 0.0) == (fmid > 0.0):
                lo, flo = mid, fmid
            else:
                hi = mid
        out.append(0.5 * (lo + hi))
    return out


def first_n_zeros(n: int, **kwargs) -> list:
    """The first ``n`` zero ordinates, verified against the strip count."""
    t_hi = estimate_height_for_count(n + 3) + 5.0
    zeros = find_zeros(14.0, t_hi, **kwargs)
    if len(zeros) < n:
        raise RuntimeError(f"only located {len(zeros)} zeros below {t_hi}")
    return zeros[:n]


# ---------------------------------------------------------------------------
# derived quantities
# ---------------------------------------------------------------------------

def normalised_gaps(zeros) -> list:
    """Rescale consecutive gaps to unit mean density.

    The local density of zeros grows like ``log(t/2pi)/2pi``, so raw gaps shrink
    with height and their distribution is not stationary.  Multiplying by the
    local density,

    .. math::  \\delta_n = (\\gamma_{n+1} - \\gamma_n)\\,
                           \\frac{\\log(\\gamma_n / 2\\pi)}{2\\pi},

    removes the trend and gives a sequence of mean ``1`` -- the object that
    Montgomery's pair-correlation conjecture and the GUE comparison are about.
    """
    out = []
    for a, b in zip(zeros, zeros[1:]):
        out.append((b - a) * math.log(a / TWO_PI) / TWO_PI)
    return out


def lehmer_pairs(zeros, threshold: float = 0.15) -> list:
    """Unusually close pairs of zeros (small normalised gap).

    Named for Lehmer's 1956 observation of the pair near ``t = 7005.06``, where
    ``Z`` barely crosses zero between two consecutive roots.  Such pairs are the
    natural place to look for a counterexample to RH: if two zeros on the line
    were to collide and leave it, they would first have to approach.  They are
    also exactly the configurations that a coarse grid search will miss.
    """
    gaps = normalised_gaps(zeros)
    return [
        {"index": i, "t_lo": zeros[i], "t_hi": zeros[i + 1], "normalised_gap": g}
        for i, g in enumerate(gaps)
        if g < threshold
    ]
