"""Certified zeros: sign changes that are proved, and counts that are proved.

What is being claimed
---------------------
:mod:`riemann.odlyzko_schonhage` *finds* zeros.  This module *proves* them, and
proves there are no others.  Two separate statements are involved and they need
completely different machinery:

**Every bracket really contains a zero.**  ``Z`` is real and continuous, so a
bracket ``[a, b]`` on which the sign of ``Z`` is certain and opposite contains a
zero of ``Z``, hence a zero of ``zeta`` exactly on the critical line.  "Certain"
means an enclosure: :func:`Z_enclosure` returns an interval that provably
contains ``Z(t)``, and the sign is accepted only when the whole interval lies on
one side of zero.

**There are no zeros anywhere else.**  That cannot come from evaluating ``Z``,
because ``Z`` says nothing about zeros off the line.  It comes from Turing's
method, which pins ``N(T)`` -- the number of zeros with ``0 < Im rho < T`` in the
whole critical strip -- from an upper bound on ``\\int S(t)\\,dt`` plus the zeros
one has already found.  If ``N(T_2) - N(T_1)`` equals the number of certified
sign changes in ``(T_1, T_2]``, then every zero in that range is on the line and
simple.  Nothing else can be hiding: an off-line zero, or a double one, would
make the counts disagree.

Turing's method is also what supplies the *index*.  It determines ``N(T)``
outright -- roughly ``5 x 10^{15}`` at ``t = 10^{15}`` -- without anybody having
had to count that far, which is how Odlyzko was able to say which zeros he had
computed at ``10^{20}``.

The error budget
----------------
An enclosure is only as honest as the weakest link, so every contribution to

.. math:: Z(t) = 2\\sum_{n\\le N} n^{-1/2}\\cos\\bigl(\\theta(t) - t\\log n\\bigr) + R(t)

is bounded explicitly rather than estimated:

===========================  ======================================  ==========
source                       bound                                   at 10^15
===========================  ======================================  ==========
``theta(t) mod 2 pi``        :mod:`decimal` at 60 digits, then one    2e-16
                             rounding to double
phase ``t log n mod 2 pi``   double-double, ``10^{-32} t\\log n``      2e-16
``(d-s)\\log n``              ``\\varepsilon |d-s|\\log N``              2e-15
``cos`` evaluation           proved below -- *not* libm              6e-15
weights ``n^{-1/2}``         two correctly-rounded ops                1e-16
summation                    explicit binary tree, depth 24           2e-11
``C_0(p)``                   interval arithmetic                      1e-16
Riemann-Siegel remainder     Gabcke, ``0.127\\,t^{-3/4}``              2e-13
===========================  ======================================  ==========

which totals about ``10^{-10}`` at ``t = 10^{15}``, against a typical ``|Z|`` of
``0.3`` at the ends of a bracket from a scan at 16 points per gap.  There are
nine orders of magnitude of headroom, and the certification never has to be
taken on trust.

Not trusting ``cos``
--------------------
The one place where a "rigorous" computation usually stops being rigorous is the
libm call.  C makes no accuracy promise about ``cos`` at all, and the usual
defence -- everyone knows it is under an ulp -- is precisely the kind of claim
this package is about not making.  :func:`cos_certified` therefore evaluates the
cosine itself: reduce modulo ``pi/2`` against a double-double ``pi``, then sum a
Taylor series short enough to bound by hand and long enough that its first
omitted term is ``2 x 10^{-18}``.  The result carries a proved bound, and
:mod:`tests.test_rigorous` checks it against the enclosures of
:mod:`riemann.interval`.

The two imported theorems
-------------------------
Everything above is self-contained.  Two things are not, and are flagged as
loudly as possible because they are the only places where this module asks the
reader to believe something it has not checked:

1. **Gabcke's bound** on the Riemann-Siegel remainder, ``|R| <= 0.127 t^{-3/4}``
   for the formula truncated after ``C_0`` (Gabcke 1979, Satz 5.2).  Deriving it
   is a thesis, not a function.  It is checked numerically here against
   :mod:`mpmath` over ``200 <= t <= 10^{15}`` in
   ``scripts/rigorous_verify.py``, which is evidence and not proof.
2. **Trudgian's bound** ``|\\int_{t_1}^{t_2} S| <= 2.067 + 0.059\\log t_2``
   for ``t_1 \\ge 168\\pi`` (Trudgian 2011, improving Lehman 1970 and Turing
   1953).  Without it there is no Turing's method.

Anyone re-deriving these can substitute their own constants; they are named
:data:`GABCKE`, :data:`TURING_A` and :data:`TURING_B` for exactly that reason.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

import numpy as np

from . import dd
from .interval import Interval, machin_pi

__all__ = [
    "GABCKE",
    "TURING_A",
    "TURING_B",
    "rs_remainder_bound",
    "psi_interval",
    "theta_mod_certified",
    "cos_certified",
    "Z_enclosure",
    "certify_brackets",
    "turing_zero_count",
    "verify_block",
]

# Gabcke (1979), Satz 5.2: |R_k(t)| <= GABCKE[k] * t^{-(2k+3)/4} for t >= 200,
# where R_k is what is left after the terms C_0 .. C_k.
GABCKE = (0.127, 0.053, 0.011, 0.031)

# Trudgian (2011): |int_{t1}^{t2} S(t) dt| <= TURING_A + TURING_B * log(t2).
TURING_A = 2.067
TURING_B = 0.059
TURING_MIN_T = 168.0 * math.pi

_EPS = 2.0 ** -53          # unit roundoff


def rs_remainder_bound(t: float, order: int = 0) -> float:
    """Rigorous bound on the Riemann-Siegel remainder after ``C_0 .. C_order``.

    See the module docstring: this is Gabcke's theorem, not something computed
    here.  Valid for ``t >= 200``.
    """
    if t < 200.0:
        raise ValueError("Gabcke's bound is stated for t >= 200")
    if not 0 <= order < len(GABCKE):
        raise ValueError(f"no bound tabulated for order {order}")
    return GABCKE[order] * t ** (-(2 * order + 3) / 4.0)


# ---------------------------------------------------------------------------
# C_0 = Psi, without the removable singularities
# ---------------------------------------------------------------------------

def _sinc_interval(x: Interval) -> Interval:
    """``sin(pi x)/(pi x)`` as an enclosure, for ``|x| <= 1/2``.

    The series ``sum_k (-1)^k (pi x)^{2k}/(2k+1)!`` alternates, and its terms
    decrease strictly once ``(pi x)^2 < 6``.  At ``|x| = 1/2`` that quantity is
    ``2.47``, so the condition holds on the whole range used here and the
    truncation error is bounded by the first omitted term, with nothing left to
    argue about.  Only ``|2w| <= 1/2`` and ``|w(1 +- 2w)| <= 3/8`` are ever
    asked for.
    """
    # The series is enveloping for (pi x)^2 < 6, i.e. |x| < 0.7797; the guard is
    # set at 0.55 so that outward rounding of an argument of exactly 1/2 cannot
    # trip it, while still refusing anything the bound does not cover.
    if max(abs(x.lo), abs(x.hi)) > 0.55:
        raise ValueError("_sinc_interval is used only on |x| <= 1/2")
    from .interval import PI
    u = (PI * x) ** 2
    total = Interval(1.0)
    term = Interval(1.0)
    for k in range(1, 12):
        term = term * u / float((2 * k) * (2 * k + 1))
        total = total + (term if k % 2 == 0 else -term)
    tail = max(abs(term.lo), abs(term.hi))
    return total + Interval(-tail, tail)


def psi_interval(p) -> Interval:
    """``C_0(p) = Psi(p)`` as a rigorous enclosure, for ``p`` in ``[0, 1]``.

    ``Psi(p) = cos(2 pi (p^2 - p - 1/16)) / cos(2 pi p)`` has removable
    singularities at ``p = 1/4`` and ``p = 3/4``, which the quotient form cannot
    survive numerically.  :mod:`riemann.riemann_siegel` dodges them with Cauchy's
    integral formula on a complex circle; here an exact identity does better.
    Putting ``w = p - 3/4``,

    .. math:: \\Psi(p) = \\frac{\\sin\\bigl(\\pi w(1+2w)\\bigr)}{\\sin(2\\pi w)}
                       = \\frac{1+2w}{2}\\,
                         \\frac{\\operatorname{sinc} w(1+2w)}{\\operatorname{sinc} 2w},

    and the same with ``w = p - 1/4`` and ``1 - 2w``.  Both sides are entire in
    the sinc form -- the singularity has been cancelled algebraically rather
    than avoided -- and switching branch at ``p = 1/2`` keeps ``|2w| <= 1/2``, so
    the denominator never drops below ``2/pi``.  In particular
    ``Psi(1/4) = Psi(3/4) = 1/2`` exactly.
    """
    p = Interval(p) if not isinstance(p, Interval) else p
    if p.lo < -1e-9 or p.hi > 1.0 + 1e-9:
        raise ValueError(f"p must lie in [0, 1], got {p}")
    if p.hi <= 0.5:
        w, s = p - 0.25, -1.0
    elif p.lo >= 0.5:
        w, s = p - 0.75, 1.0
    else:  # straddles the switch-over: take the hull of both branches
        return Interval.hull(psi_interval(Interval(p.lo, 0.5)),
                             psi_interval(Interval(0.5, p.hi)))
    inner = w * (Interval(1.0) + s * 2.0 * w)
    return (Interval(1.0) + s * 2.0 * w) / 2.0 * _sinc_interval(inner) \
        / _sinc_interval(2.0 * w)


# ---------------------------------------------------------------------------
# theta, exactly, one point at a time
# ---------------------------------------------------------------------------

def exact_t(t0: float, d: float = 0.0) -> Decimal:
    """``t0 + d`` as an exact decimal.

    Never write ``t0 + d`` in floating point and expect it to mean what it says:
    near ``10^{15}`` consecutive doubles are ``0.125`` apart, so the sum lands on
    a lattice two thirds as coarse as the gap between zeros, and ``theta`` of the
    wrong point is off by a whole radian.  ``Decimal(float)`` is exact, so this
    is not.
    """
    return Decimal(float(t0)) + Decimal(float(d))


def theta_mod_certified(t0: float, d: float = 0.0, prec: int = 60):
    """``(value, bound)`` with ``|value - theta(t0 + d) mod 2 pi| <= bound``.

    Computed from :mod:`decimal` at 60 digits, so the only errors are the
    truncation of the asymptotic series -- ``10^{-139}`` at ``t = 10^{15}``, and
    below ``10^{-19}`` for any ``t >= 200`` -- and the final rounding to a
    double.  The result is *not* obtained by adding an increment to a stored
    ``theta(t0)``: at a few hundred microseconds a point that is unnecessary,
    and an increment would only add error.
    """
    t = exact_t(t0, d)
    with localcontext() as ctx:
        ctx.prec = prec
        theta = dd.theta_decimal(t, prec)
        two_pi = 2 * machin_pi(prec)
        reduced = theta - two_pi * (theta / two_pi).to_integral_value(
            rounding="ROUND_HALF_EVEN")
        value = float(reduced)
        truncation = float(dd.theta_truncation_bound(float(t)))
    return value, abs(value) * _EPS + truncation + 1e-45


# ---------------------------------------------------------------------------
# cosine, without trusting anybody
# ---------------------------------------------------------------------------

_COS_C = tuple((-1.0) ** k / math.factorial(2 * k) for k in range(1, 10))
_SIN_C = tuple((-1.0) ** k / math.factorial(2 * k + 1) for k in range(1, 9))


def cos_certified(a, a_bound: float = 0.0, a_max: float | None = None):
    """``cos(a)`` elementwise, with a proved bound on the total error.

    Returns ``(values, bound)`` such that for every element
    ``|values[i] - cos(a_exact[i])| <= bound``, where ``a_exact`` is within
    ``a_bound`` of the given ``a``.

    Argument reduction subtracts ``q pi/2`` using a double-double ``pi/2``, the
    integer multiple being removed with an exact :func:`riemann.dd.two_prod` so
    that no significance is lost.  On ``|r| <= pi/4`` the Taylor series for
    ``cos`` through ``r^16`` and ``sin`` through ``r^17`` are alternating with
    decreasing terms, so their truncation errors are below ``2 x 10^{-18}`` and
    ``7 x 10^{-20}``; Horner's rule on ``n`` terms adds at most
    ``gamma_{2n} sum |a_k| |u|^k <= 3 x 10^{-15}``.
    """
    a = np.asarray(a, dtype=float)
    if a_max is None:
        a_max = float(np.max(np.abs(a))) if a.size else 0.0
    amax = float(a_max)

    half_pi = dd.mul_d(dd._constants()["PI"], 0.5)
    q = np.round(a * (1.0 / half_pi[0]))
    prod, err = dd.two_prod(q, half_pi[0])          # exact
    r = ((a - prod) - err) - q * half_pi[1]

    u = r * r
    c = np.full(a.shape, _COS_C[-1])
    for coefficient in _COS_C[-2::-1]:
        c = c * u + coefficient
    cos_r = c * u + 1.0

    s = np.full(a.shape, _SIN_C[-1])
    for coefficient in _SIN_C[-2::-1]:
        s = s * u + coefficient
    sin_r = (s * u + 1.0) * r

    quadrant = np.mod(q, 4.0)
    values = np.where(quadrant % 2 == 0, cos_r, sin_r)
    values = np.where((quadrant == 1) | (quadrant == 2), -values, values)

    # --- the bound ---------------------------------------------------------
    # reduction: one rounding of a - prod (<= eps*max|a|), one of the
    # subtraction of err, one of q*half_pi[1], and the double-double residue.
    reduction = _EPS * amax + 3.0 * _EPS * math.pi + 1e-30 * max(1.0, amax)
    # Horner on 9 (resp. 8) terms, with sum |a_k| |u|^k <= cosh(pi/4) < 1.325
    horner = 18.0 * _EPS * 1.325 / (1.0 - 18.0 * _EPS)
    truncation = 2.1e-18
    return values, reduction + horner + truncation + a_bound


# ---------------------------------------------------------------------------
# the summation
# ---------------------------------------------------------------------------

def tree_sum(x):
    """``sum(x)`` by an explicit balanced binary tree, with a known depth.

    numpy's pairwise summation is accurate but its shape is an implementation
    detail, and a bound cannot rest on an implementation detail.  Repeatedly
    adding the second half of the array to the first is a binary tree of depth
    exactly ``ceil(log2 n)``, every level a contiguous vector add, so the
    classical bound ``|error| <= gamma_{ceil(log2 n)} sum |x_i|`` applies with
    nothing assumed.  It costs one extra pass over the data.
    """
    a = np.asarray(x, dtype=float)
    depth = 0
    while a.size > 1:
        if a.size % 2:
            a = np.concatenate([a, np.zeros(1)])
        half = a.size // 2
        a = a[:half] + a[half:]
        depth += 1
    return float(a[0]), depth


def _tree_depth(n: int) -> int:
    depth = 0
    while n > 1:
        n = (n + 1) // 2
        depth += 1
    return depth


# ---------------------------------------------------------------------------
# the enclosure
# ---------------------------------------------------------------------------

def Z_enclosure(block, offsets, recentre: float = 1.0, chunk: int = 1 << 18):
    """Rigorous enclosures of ``Z(t0 + d)`` for offsets ``d`` in ``block``.

    Returns ``(values, radii)``: the true ``Z`` lies in
    ``[values[i] - radii[i], values[i] + radii[i]]``.

    ``block`` is a :class:`riemann.odlyzko_schonhage.ZBlock`, used only for its
    precomputed phases.  The fast interpolated path plays no part here -- every
    point costs a full ``N``-term sum, because a certificate that leans on an
    interpolation is a certificate about the interpolation.
    """
    offsets = np.atleast_1d(np.asarray(offsets, dtype=float))
    n_terms = block.n_max
    weights = block._inv_sqrt_n
    weight_total = float(np.sum(weights))          # ~ 2 sqrt(N)
    # rigorous upper bound on sum |w_n|: the terms are positive and the sum
    # itself is computed in floating point, so allow for its own roundoff.
    weight_total *= 1.0 + 2.0 * _EPS * _tree_depth(n_terms)

    depth = _tree_depth(min(chunk, n_terms)) + _tree_depth(
        max(1, -(-n_terms // chunk)))
    gamma = depth * _EPS / (1.0 - depth * _EPS)

    values = np.empty(offsets.size)
    radii = np.empty(offsets.size)

    order = np.argsort(offsets)
    i = 0
    while i < order.size:
        shift = float(offsets[order[i]])
        j = i
        while j < order.size and offsets[order[j]] - shift <= recentre:
            j += 1
        base = (dd.add(block._base, dd.mul_mod_2pi_dd(shift, block._log_n_dd))
                if shift != 0.0 else block._base)
        # (t0 + shift) log n mod 2pi, with the double-double residue bounded by
        # the relative accuracy of the product t log n.
        phase_bound = 4.0 * _EPS * abs(block.t0 * math.log(max(n_terms, 2))) * _EPS \
            + 2.0 * _EPS * math.pi

        for k in order[i:j]:
            d = float(offsets[k])
            theta, theta_bound = theta_mod_certified(block.t0, d)
            e = d - shift
            log_max = math.log(n_terms)
            angle_max = 2.0 * math.pi + abs(e) * log_max
            angle_bound = (theta_bound + phase_bound
                           + 2.0 * _EPS * math.pi                  # the two subtractions
                           + _EPS * abs(e) * log_max               # rounding of e*log n
                           + _EPS * angle_max)                     # final subtraction

            # Chunked so the temporaries stay in cache; the summation is a tree
            # within each chunk and a tree over the chunk totals, so the depth
            # is still ceil(log2 N) and the bound below is unchanged.
            partials = []
            cos_bound = 0.0
            for start in range(0, n_terms, chunk):
                stop = start + chunk
                # angle = (theta - base_hi) - base_lo - e*log n
                angle = ((theta - base[0][start:stop]) - base[1][start:stop]) \
                    - e * block._log_n[start:stop]
                cosines, cos_bound = cos_certified(angle, angle_bound,
                                                   a_max=angle_max)
                partials.append(tree_sum(cosines * weights[start:stop])[0])
            total, _ = tree_sum(np.array(partials))

            sum_bound = (weight_total * cos_bound          # per-term cosine error
                         + 2.0 * _EPS * weight_total       # weights and products
                         + gamma * weight_total)           # the tree

            correction, correction_radius = _correction_enclosure(block, d)
            values[k] = 2.0 * total + correction
            radii[k] = (2.0 * sum_bound + correction_radius
                        + rs_remainder_bound(block.t0 + d, 0)
                        + 4.0 * _EPS * abs(2.0 * total + correction))
        i = j
    return values, radii


def _correction_enclosure(block, d: float):
    """``(-1)^{N-1} tau^{-1/2} C_0(p)`` as a centre and radius.

    Only ``C_0`` is used: Gabcke's bound for the formula truncated there is
    ``0.127 t^{-3/4}``, which is ``2 x 10^{-13}`` at ``t = 10^{15}`` -- far below
    everything else in the budget -- and it avoids having to bound the
    interpolation error of the tabulated ``C_1 .. C_3``.
    """
    with localcontext() as ctx:
        ctx.prec = 50
        tau = (exact_t(block.t0, d) / (2 * machin_pi(50))).sqrt()
        p_dec = tau - Decimal(block.n_max)
        p = Interval.from_decimal(p_dec, Decimal(10) ** -45)
        inv_tau = Interval.from_decimal(1 / tau, Decimal(10) ** -45)
    value = inv_tau.sqrt() * psi_interval(p)
    if (block.n_max - 1) % 2:
        value = -value
    return value.mid, value.rad


# ---------------------------------------------------------------------------
# certification
# ---------------------------------------------------------------------------

def certify_brackets(block, brackets, recentre: float = 1.0, verbose: bool = False):
    """Prove that each bracket contains a zero of ``Z``.

    Returns ``(certified, rejected)``: arrays of bracket pairs whose two
    endpoints have provably opposite signs, and those where at least one
    enclosure straddles zero, so that nothing can be concluded.
    """
    brackets = np.atleast_2d(np.asarray(brackets, dtype=float))
    if brackets.size == 0:
        return np.empty((0, 2)), np.empty((0, 2))
    points = brackets.reshape(-1)
    values, radii = Z_enclosure(block, points, recentre=recentre)
    signs = np.where(values - radii > 0.0, 1, np.where(values + radii < 0.0, -1, 0))
    signs = signs.reshape(-1, 2)
    ok = (signs[:, 0] != 0) & (signs[:, 1] != 0) & (signs[:, 0] != signs[:, 1])
    if verbose:
        margin = np.min(np.abs(values) - radii)
        print(f"    certified {int(ok.sum())}/{len(ok)} brackets, "
              f"tightest margin {margin:.3e}, "
              f"typical radius {np.median(radii):.3e}")
    return brackets[ok], brackets[~ok]


# ---------------------------------------------------------------------------
# Turing's method
# ---------------------------------------------------------------------------

def turing_integral_bound(t: float) -> float:
    """``|int S|`` bound over an interval ending at ``t`` (Trudgian 2011)."""
    if t < TURING_MIN_T:
        raise ValueError(f"Turing's bound is stated for t >= {TURING_MIN_T:.1f}")
    return TURING_A + TURING_B * math.log(t)


def _theta_antiderivative(t: Decimal, prec: int) -> Decimal:
    """``int theta(t) dt``, from the same expansion as ``theta`` itself.

    .. math::
       \\int\\theta = \\frac{t^2}4\\log\\frac t{2\\pi} - \\frac{3t^2}8
                     - \\frac{\\pi t}8 + \\frac{\\log t}{48} - \\frac7{11520\\,t^2}

    Evaluated in :mod:`decimal`: at ``t = 10^{15}`` the two endpoint values are
    ``10^{31}`` and their difference is ``10^{18}``, so thirteen digits vanish in
    the subtraction and a double would return noise where an answer accurate to
    ``0.01`` is needed.
    """
    with localcontext() as ctx:
        ctx.prec = prec
        pi = machin_pi(prec)
        return (t * t / 4 * (t / (2 * pi)).ln()
                - 3 * t * t / 8
                - pi * t / 8
                + t.ln() / 48
                - Decimal(7) / (11520 * t * t))


def turing_zero_count(t0: float, d_target: float, below, above,
                      d_low: float, d_high: float, prec: int = 60):
    """``N(t0 + d_target)`` -- zeros of ``zeta`` with ``0 < Im rho < t``.

    Turing's method.  Write ``m = N(T)`` for the target height ``T`` and
    ``S(t) = N(t) - theta(t)/pi - 1``.

    Above ``T``, each certified zero forces ``N`` up: ``N(t) >= m + L(t)``, where
    ``L`` counts the certified zeros in ``(T, t]``.  Integrating against
    Trudgian's ``int S <= B`` gives

    .. math::
       m \\le \\frac{B + \\int_T^{T_2}\\bigl(\\tfrac\\theta\\pi + 1\\bigr)
                     - \\int_T^{T_2} L}{T_2 - T}.

    Below ``T`` the same argument runs the other way -- ``N(t) <= m - L'(t)``
    with ``int S >= -B`` -- and yields a lower bound.  Two constraints, one
    integer between them, and no zero above ``T`` ever had to be counted.

    Note what is *not* assumed: the lists need not be complete.  Leaving zeros
    out only widens the bracket, it cannot make the answer wrong.  What they
    must be is genuine, which is what :func:`certify_brackets` establishes.

    Parameters
    ----------
    below, above:
        Offsets from ``t0`` of certified zeros in ``(d_low, d_target]`` and
        ``(d_target, d_high]``.  Offsets, not absolute heights -- see
        :func:`exact_t`.

    Returns
    -------
    dict with ``count`` (an ``int``, or ``None`` if the bracket did not close),
    ``lower``, ``upper`` and ``slack``.
    """
    t_target = float(t0) + float(d_target)
    t_high = float(t0) + float(d_high)
    with localcontext() as ctx:
        ctx.prec = prec
        pi = machin_pi(prec)
        target = exact_t(t0, d_target)
        lo, hi = exact_t(t0, d_low), exact_t(t0, d_high)

        def smooth_integral(a: Decimal, b: Decimal) -> Decimal:
            """``int_a^b (theta/pi + 1) dt``."""
            return (_theta_antiderivative(b, prec)
                    - _theta_antiderivative(a, prec)) / pi + (b - a)

        # --- upper bound on m, from the zeros above --------------------------
        span_up = hi - target
        bound_up = Decimal(turing_integral_bound(t_high))
        # int_T^{T2} L = sum (T2 - gamma).  Taking gamma as large as its
        # certified bracket allows makes this sum small, which is the
        # conservative direction for an upper bound on m.
        integral_l = sum((hi - exact_t(t0, g) for g in above), Decimal(0))
        upper = (bound_up + smooth_integral(target, hi) - integral_l) / span_up

        # --- lower bound on m, from the zeros below --------------------------
        span_down = target - lo
        bound_down = Decimal(turing_integral_bound(t_target))
        integral_lp = sum((exact_t(t0, g) - lo for g in below), Decimal(0))
        lower = (-bound_down + integral_lp + smooth_integral(lo, target)) / span_down

    lower_int = int(lower.to_integral_value(rounding="ROUND_CEILING"))
    upper_int = int(upper.to_integral_value(rounding="ROUND_FLOOR"))
    count = lower_int if lower_int == upper_int else None
    return {
        "count": count,
        "lower": lower,
        "upper": upper,
        "slack": float(upper - lower),
        "n_below": len(below),
        "n_above": len(above),
    }


# ---------------------------------------------------------------------------
# the whole job
# ---------------------------------------------------------------------------

def verify_block(block, turing_width: float | None = None, density: float = 16.0,
                 recentre: float = 1.0, verbose: bool = True) -> dict:
    """Find, certify and count every zero in a block.

    The steps, in order:

    1. scan for sign changes with the fast interpolated path;
    2. certify each bracket with :func:`Z_enclosure` -- full ``N``-term sums;
    3. run Turing's method at both ends of the inner interval to obtain
       ``N(T_1)`` and ``N(T_2)`` outright;
    4. compare ``N(T_2) - N(T_1)`` with the number of certified brackets in
       between.

    If step 4 agrees, then *every* zero of ``zeta`` with ordinate in
    ``(T_1, T_2]`` is simple and lies exactly on the critical line, and each one
    has a known index.  If it does not agree, the shortfall is reported and
    nothing is claimed.
    """
    h = block.half_width
    if turing_width is None:
        turing_width = max(20.0, 6.0 * turing_integral_bound(block.t0 + h))
    if 2.0 * turing_width >= 2.0 * h:
        raise ValueError("block is too narrow for two Turing windows")

    if verbose:
        print(f"  scanning [{block.t0:.6g} - {h:g}, {block.t0:.6g} + {h:g}] "
              f"at {density:g} points per gap")
    brackets = block.brackets(density=density)
    if verbose:
        print(f"    {len(brackets)} sign changes "
              f"(smooth prediction {block.expected_count():.2f})")

    certified, rejected = certify_brackets(block, brackets, recentre=recentre,
                                           verbose=verbose)
    if len(certified) == 0:
        raise RuntimeError("no bracket could be certified; nothing to count")

    # A certified zero lies somewhere inside its bracket.  For each Turing bound
    # take whichever endpoint makes the bound conservative: the left endpoint
    # when the zero is being pushed down, the right when it is being pushed up.
    d1, d2 = -h + turing_width, h - turing_width
    t1, t2 = block.t0 + d1, block.t0 + d2
    left, right = certified[:, 0], certified[:, 1]

    turing_1 = turing_zero_count(
        block.t0, d1,
        below=left[(right > -h) & (right <= d1)],
        above=right[(left >= d1) & (left < d1 + turing_width)],
        d_low=-h, d_high=d1 + turing_width)

    turing_2 = turing_zero_count(
        block.t0, d2,
        below=left[(right > d2 - turing_width) & (right <= d2)],
        above=right[(left >= d2) & (left < h)],
        d_low=d2 - turing_width, d_high=h)

    inner = certified[(certified[:, 0] >= d1) & (certified[:, 1] <= d2)]
    result = {
        "t0": block.t0,
        "half_width": h,
        "n_terms": block.n_max,
        "brackets": len(brackets),
        "certified": len(certified),
        "rejected": len(rejected),
        "turing_lower": turing_1,
        "turing_upper": turing_2,
        "inner_range": (t1, t2),
        "inner_certified": len(inner),
        "inner_brackets": inner,
    }
    if turing_1["count"] is not None and turing_2["count"] is not None:
        expected = turing_2["count"] - turing_1["count"]
        result["N_t1"] = turing_1["count"]
        result["N_t2"] = turing_2["count"]
        result["zeros_in_range"] = expected
        result["complete"] = (expected == len(inner))
        result["missing"] = expected - len(inner)
    else:
        result["complete"] = False
        result["missing"] = None

    if verbose:
        _report(result)
    return result


def _report(result: dict) -> None:
    if result.get("N_t1") is None:
        print("    Turing's method did not close; no count is claimed")
        for key in ("turing_lower", "turing_upper"):
            print(f"      {key}: slack {result[key]['slack']:.3f}")
        return
    t1, t2 = result["inner_range"]
    print(f"    N({t1:.6f}) = {result['N_t1']:,}")
    print(f"    N({t2:.6f}) = {result['N_t2']:,}")
    print(f"    zeros forced in between: {result['zeros_in_range']:,}; "
          f"certified on the line: {result['inner_certified']:,}")
    if result["complete"]:
        print("    => every zero in this range is simple and on the "
              "critical line")
    else:
        print(f"    => {result['missing']} unaccounted for; nothing claimed")
