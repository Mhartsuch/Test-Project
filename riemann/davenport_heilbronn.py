"""The Davenport-Heilbronn function: a functional equation is not enough.

Why this matters
----------------
It is tempting to think RH must follow from the symmetry ``xi(s) = xi(1-s)``
together with some soft analytic input.  It cannot, and this function is the
proof.  Davenport and Heilbronn (1936) exhibited a Dirichlet series that

* satisfies a functional equation of exactly Riemann's type, relating ``s`` to
  ``1-s`` through the same gamma factor, and
* has infinitely many zeros **off** the critical line -- including zeros with
  real part greater than 1, where ``zeta`` has none at all.

What it lacks is an **Euler product**.  So any proof of RH must use the Euler
product in an essential way, and the first test to apply to a claimed proof is:
*where does this argument fail for Davenport-Heilbronn?*  If it does not fail,
it is wrong.  This module makes that concrete by computing the off-line zeros.

Construction
------------
Let ``chi`` be the primitive character mod 5 with ``chi(2) = i`` -- so
``chi(1),...,chi(4) = 1, i, -i, -1``.  It is odd (``chi(-1) = chi(4) = -1``).
Set

.. math::  f(s) = \\frac{1 - i\\xi}{2} L(s,\\chi) + \\frac{1 + i\\xi}{2} L(s,\\bar\\chi)

for a real constant ``xi``.  Writing ``A = (1 - i xi)/2`` and completing with
``G(s) = (5/\\pi)^{(s+1)/2}\\Gamma((s+1)/2)``, the odd-character functional
equation ``G(s)L(s,\\chi) = \\epsilon(\\chi) G(1-s) L(1-s,\\bar\\chi)`` gives

.. math::  G(s)f(s) = G(1-s)\\bigl[A\\epsilon(\\chi)L(1-s,\\bar\\chi)
                       + \\bar A \\epsilon(\\bar\\chi) L(1-s,\\chi)\\bigr],

so ``G(s)f(s) = eta G(1-s)f(1-s)`` for a sign ``eta = +-1`` exactly when
``epsilon(chi) = eta * bar A / A``.  Since ``|epsilon| = 1``, writing
``epsilon = e^{i phi}`` and ``bar A / A = (1 + i xi)/(1 - i xi) = e^{2 i psi}``
with ``xi = tan psi`` gives **two** admissible constants, one per sign:

.. math::
   \\eta = +1:\\quad \\xi = \\tan(\\phi/2), \\qquad
   \\eta = -1:\\quad \\xi = -\\cot(\\phi/2),
   \\qquad \\phi = \\arg\\epsilon(\\chi) = \\arg\\frac{\\tau(\\chi)}{i\\sqrt5}.

Both are genuine functional equations of Riemann type; a root number of ``-1``
is entirely ordinary.  But only the second is the Davenport-Heilbronn function,
and the reason is visible in one number: ``phi = 0.5536``, so

* ``eta = +1`` gives ``xi = +0.2841``, and ``|a_2| = 0.284 < 1``;
* ``eta = -1`` gives ``xi = -3.5201``, and ``|a_2| = 3.520 > 1``.

With ``|a_2| > 1`` the second term of the Dirichlet series can outweigh the
first, and ``f`` acquires zeros with ``Re s > 1``.  With ``|a_2| < 1`` it cannot,
and in fact every zero found in ``-0.5 < Re s < 1.5`` for that branch lies on
the critical line.  The default here is therefore the ``eta = -1`` branch.

Both constants are **derived** from the Gauss sum rather than quoted, and
:func:`check_functional_equation` verifies each numerically to ``~1e-13``.

Evaluation
----------
Expanding, ``f(s) = sum_n a_n n^{-s}`` with ``a_n`` real and periodic mod 5:
``a = (1, xi, -xi, -1, 0)``.  The period sums to zero, so the series converges
for ``Re s > 0``; for continuation everywhere the Hurwitz representation is used

.. math::  f(s) = 5^{-s}\\sum_{r=1}^{4} a_r\\,\\zeta(s, r/5).

The interesting consequence is visible directly in ``a``: because
``|a_2| = xi > 1``, the second term of the series can overwhelm the first, and
``f`` acquires zeros with ``Re s > 1``.  ``zeta``, protected by its Euler
product, never can.
"""

from __future__ import annotations

import cmath
import math

from .special import log_gamma
from .zeta import _em_coeffs

__all__ = [
    "gauss_sum",
    "root_number",
    "XI",
    "coefficients",
    "hurwitz_zeta",
    "f",
    "completed",
    "check_functional_equation",
    "count_zeros_in_rectangle",
    "find_zeros_in_rectangle",
]

# The character mod 5 with chi(2) = i.
CHI = {1: 1 + 0j, 2: 1j, 3: -1j, 4: -1 + 0j, 0: 0j}


def gauss_sum() -> complex:
    """``tau(chi) = sum_{n mod 5} chi(n) e^{2 pi i n / 5}``."""
    return sum(CHI[n] * cmath.exp(2j * math.pi * n / 5.0) for n in range(1, 5))


def root_number() -> complex:
    """``epsilon(chi) = tau(chi) / (i sqrt 5)`` -- unimodular for primitive odd chi."""
    return gauss_sum() / (1j * math.sqrt(5.0))


def xi_for_sign(eta: int = -1) -> float:
    """The constant ``xi`` giving completed-function sign ``eta = +-1``."""
    half = cmath.phase(root_number()) / 2.0
    if eta == 1:
        return math.tan(half)
    if eta == -1:
        return -1.0 / math.tan(half)
    raise ValueError("eta must be +1 or -1")


#: ``eta = -1`` branch: the Davenport-Heilbronn function proper (``|xi| > 1``).
XI = xi_for_sign(-1)
#: ``eta = +1`` branch, kept for contrast (``|xi| < 1``; no zeros off the line found).
XI_EVEN = xi_for_sign(+1)
ETA = -1


def coefficients(xi: float = None) -> list:
    """The real, period-5 Dirichlet coefficients ``(a_1 .. a_5)``."""
    x = XI if xi is None else xi
    return [1.0, x, -x, -1.0, 0.0]


# ---------------------------------------------------------------------------
# Hurwitz zeta
# ---------------------------------------------------------------------------

def hurwitz_zeta(s: complex, a: float, n_terms: int | None = None,
                 m_terms: int = 12) -> complex:
    """``zeta(s, a) = sum_{k>=0} (k+a)^{-s}``, by Euler-Maclaurin.

    Same expansion as :func:`riemann.zeta.zeta`, with ``k + a`` in place of
    ``k``; the ``a = 1`` case reduces to the Riemann zeta function, which is
    what the test-suite checks.
    """
    s = complex(s)
    if s == 1.0:
        raise ValueError("Hurwitz zeta has a pole at s = 1")
    if a <= 0:
        raise ValueError("a must be positive")

    n = int(n_terms if n_terms is not None else max(12, int(0.6 * abs(s.imag)) + 12))
    m = int(m_terms)

    total = 0.0 + 0.0j
    for k in range(n):
        total += cmath.exp(-s * math.log(k + a))

    w = n + a
    log_w = math.log(w)
    w_neg_s = cmath.exp(-s * log_w)
    total += w_neg_s * w / (s - 1.0) + 0.5 * w_neg_s

    coeffs = _em_coeffs(m)
    rising = s
    w_pow = w_neg_s / w
    inv_w2 = 1.0 / (w * w)
    for k in range(1, m + 1):
        if k > 1:
            rising *= (s + (2 * k - 3)) * (s + (2 * k - 2))
            w_pow *= inv_w2
        total += coeffs[k - 1] * rising * w_pow
    return total


# ---------------------------------------------------------------------------
# the function itself
# ---------------------------------------------------------------------------

def f(s: complex, xi: float = None) -> complex:
    """The Davenport-Heilbronn function, continued to the whole plane."""
    s = complex(s)
    a = coefficients(xi)
    total = sum(a[r - 1] * hurwitz_zeta(s, r / 5.0) for r in range(1, 5))
    return cmath.exp(-s * math.log(5.0)) * total


def completed(s: complex, xi: float = None) -> complex:
    """``G(s) f(s)`` with ``G(s) = (5/pi)^{(s+1)/2} Gamma((s+1)/2)``."""
    s = complex(s)
    g = cmath.exp(0.5 * (s + 1.0) * math.log(5.0 / math.pi)
                  + log_gamma(0.5 * (s + 1.0)))
    return g * f(s, xi)


def check_functional_equation(points=None, xi: float = None,
                              eta: int = None) -> dict:
    """Verify ``G(s)f(s) = eta G(1-s)f(1-s)`` numerically.

    This is what licenses calling ``f`` a counterexample at all: if it did not
    satisfy a Riemann-type functional equation, its off-line zeros would prove
    nothing about RH.  The derived ``xi`` is confirmed here rather than assumed.
    """
    if points is None:
        points = [2 + 3j, 0.7 + 11j, 1.3 + 5j, -0.4 + 2j, 0.5 + 20j, 2.2 + 0.5j]
    x = XI if xi is None else xi
    e = ETA if eta is None else eta
    rows = []
    for s in points:
        left, right = completed(s, x), e * completed(1 - s, x)
        scale = max(abs(left), abs(right), 1e-300)
        rows.append({"s": s, "lhs": left, "rhs": right,
                     "rel_diff": abs(left - right) / scale})
    return {"xi": x, "eta": e,
            "root_number": root_number(),
            "rows": rows,
            "max_rel_diff": max(r["rel_diff"] for r in rows)}


# ---------------------------------------------------------------------------
# zeros
# ---------------------------------------------------------------------------

def count_zeros_in_rectangle(s_lo: complex, s_hi: complex, per_side: int = 400,
                             xi: float = None) -> float:
    """Winding number of ``f`` around a rectangle: the enclosed zero count.

    Argument principle, by continuous tracking of ``arg f`` around the boundary
    with adaptive subdivision -- the same technique used for ``zeta`` in
    :mod:`riemann.counting`.

    .. warning::
       The winding number is only defined if **no zero lies on the contour**.
       Putting a rectangle edge at ``Re s = 1/2`` is therefore a trap here,
       because that is exactly where most of the zeros are: an early version of
       this analysis reported 21 zeros in ``(1/2, 1)`` and 26 in ``(0, 1/2)``
       for a branch whose zeros are in fact *all* on the line.  The counts were
       an artefact of 28 zeros sitting on the boundary, and the giveaway was
       that the functional equation forces those two counts to be equal.
       Offset any edge away from ``Re s = 1/2``, and treat a non-integer result
       as evidence that a zero is on the contour rather than as a count.
    """
    x0, x1 = s_lo.real, s_hi.real
    y0, y1 = s_lo.imag, s_hi.imag
    corners = [complex(x0, y0), complex(x1, y0), complex(x1, y1), complex(x0, y1)]

    def walk(a: complex, fa: complex, b: complex, fb: complex, depth: int) -> float:
        d = cmath.phase(fb / fa)
        if abs(d) <= 0.35 or depth >= 30:
            return d
        mid = 0.5 * (a + b)
        fm = f(mid, xi)
        return walk(a, fa, mid, fm, depth + 1) + walk(mid, fm, b, fb, depth + 1)

    total = 0.0
    for i in range(4):
        p, q = corners[i], corners[(i + 1) % 4]
        fp = f(p, xi)
        for j in range(per_side):
            nxt = p + (q - p) * (j + 1) / per_side
            fn = f(nxt, xi)
            total += walk(p, fp, nxt, fn, 0)
            p, fp = nxt, fn
    return total / (2.0 * math.pi)


def _newton(s0: complex, xi: float = None, iters: int = 60, h: float = 1e-6,
            box: tuple = (-6.0, 8.0, -10.0, 4000.0)):
    """Newton on ``f``, confined to a box.

    Unconstrained Newton on a function with this many nearby zeros happily
    diverges to where the Euler-Maclaurin evaluation overflows, so each iterate
    is rejected if it leaves the region of interest.
    """
    x_lo, x_hi, y_lo, y_hi = box
    s = complex(s0)
    for _ in range(iters):
        try:
            v = f(s, xi)
            if abs(v) < 1e-14:
                break
            d = (f(s + h, xi) - f(s - h, xi)) / (2.0 * h)
        except (OverflowError, ValueError):
            return None
        if d == 0:
            return None
        step = v / d
        if abs(step) > 5.0:                 # damp wild jumps
            step *= 5.0 / abs(step)
        s -= step
        if not (x_lo <= s.real <= x_hi and y_lo <= s.imag <= y_hi):
            return None
        if abs(step) < 1e-13:
            break
    try:
        return s if abs(f(s, xi)) < 1e-9 else None
    except (OverflowError, ValueError):
        return None


def find_zeros_in_rectangle(s_lo: complex, s_hi: complex, grid: int = 26,
                            xi: float = None, tol: float = 1e-8) -> list:
    """Locate zeros of ``f`` in a rectangle by Newton from a grid of seeds."""
    x0, x1 = s_lo.real, s_hi.real
    y0, y1 = s_lo.imag, s_hi.imag
    found = []
    for i in range(grid):
        for j in range(grid):
            seed = complex(x0 + (x1 - x0) * (i + 0.5) / grid,
                           y0 + (y1 - y0) * (j + 0.5) / grid)
            r = _newton(seed, xi)
            if r is None:
                continue
            if not (x0 - 1e-9 <= r.real <= x1 + 1e-9 and y0 - 1e-9 <= r.imag <= y1 + 1e-9):
                continue
            if all(abs(r - q) > 1e-6 for q in found):
                found.append(r)
    return sorted(found, key=lambda z: (z.imag, z.real))
