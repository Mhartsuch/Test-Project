"""The explicit formula: rebuilding the primes out of the zeros.

This is the bridge that makes RH matter.  It is one thing to be told that the
zeros of an analytic function control the distribution of primes; it is another
to take a list of zero ordinates, feed them into a trigonometric sum, and watch
the prime powers appear as jumps in the output.  That is what this module does.

The formula
-----------
Von Mangoldt's explicit formula for the Chebyshev function
``psi(x) = sum_{p^k <= x} log p`` is *exact*:

.. math::
   \\psi_0(x) = x - \\sum_{\\rho} \\frac{x^{\\rho}}{\\rho}
              - \\log 2\\pi - \\tfrac12\\log\\!\\left(1 - x^{-2}\\right),

the sum running over all non-trivial zeros, paired as ``rho`` and
``bar rho``.  (``psi_0`` is ``psi`` with the value at a jump taken as the
midpoint.)  The last two terms come from the pole at ``s = 1`` and the trivial
zeros.  Writing ``rho = 1/2 + i gamma`` and combining conjugates,

.. math::
   \\sum_{\\rho}\\frac{x^{\\rho}}{\\rho}
     = 2\\sqrt x \\sum_{\\gamma>0}
       \\frac{\\tfrac12\\cos(\\gamma\\log x) + \\gamma\\sin(\\gamma\\log x)}
            {\\tfrac14 + \\gamma^2}.

Each zero contributes a pure wave in ``log x``, of frequency ``gamma`` and
amplitude ``~ sqrt x / gamma``.  The primes are the interference pattern.

Where RH enters
---------------
The size of the error term ``psi(x) - x`` is governed by the real parts of the
zeros: a zero at ``Re rho = sigma`` contributes an oscillation of size
``x^{sigma}``.  RH -- all ``sigma = 1/2`` -- is *exactly* the statement that

.. math::  \\psi(x) = x + O\\!\\left(x^{1/2}\\log^2 x\\right),

which is the smallest error term the oscillations could conceivably allow.  RH
is not a statement that the primes are random; it is the statement that they
are as regular as they can possibly be.

A caveat on truncation
----------------------
Truncating the sum at ``gamma < T`` gives a smoothed approximation, not a
partial sum that converges nicely.  The series is only conditionally
convergent, and cutting it produces Gibbs-type ringing at each jump.  The
reconstruction below therefore tracks the *shape* of the staircase well while
overshooting at the steps themselves; that is a property of the truncation, not
an error in the computation.
"""

from __future__ import annotations

import math

__all__ = [
    "von_mangoldt_sieve",
    "psi_exact",
    "psi_from_zeros",
    "zero_contribution",
    "prime_counting_error",
]


def von_mangoldt_sieve(limit: int) -> list:
    """``Lambda(n)`` for ``n <= limit``: ``log p`` if ``n = p^k``, else ``0``."""
    lam = [0.0] * (limit + 1)
    is_composite = bytearray(limit + 1)
    for p in range(2, limit + 1):
        if not is_composite[p]:
            lp = math.log(p)
            q = p
            while q <= limit:
                lam[q] = lp
                if q > limit // p:
                    break
                q *= p
            for m in range(p * p, limit + 1, p):
                is_composite[m] = 1
    return lam


def psi_exact(limit: int) -> list:
    """Cumulative ``psi(n) = sum_{m<=n} Lambda(m)`` for ``n <= limit``."""
    lam = von_mangoldt_sieve(limit)
    out = [0.0] * (limit + 1)
    running = 0.0
    for n in range(1, limit + 1):
        running += lam[n]
        out[n] = running
    return out


def zero_contribution(x: float, gammas) -> float:
    """The oscillating term ``sum_rho x^rho / rho`` over the given ordinates.

    Conjugate pairs are combined, so ``gammas`` should contain only the positive
    ordinates.
    """
    log_x = math.log(x)
    total = 0.0
    for g in gammas:
        total += (0.5 * math.cos(g * log_x) + g * math.sin(g * log_x)) / (0.25 + g * g)
    return 2.0 * math.sqrt(x) * total


def psi_from_zeros(x: float, gammas) -> float:
    """Reconstruct ``psi(x)`` from zero ordinates via the explicit formula."""
    if x <= 1.0:
        raise ValueError("x must exceed 1")
    correction = -0.5 * math.log(1.0 - x ** -2.0) if x > 1.0 else 0.0
    return x - zero_contribution(x, gammas) - math.log(2.0 * math.pi) - correction


def prime_counting_error(xs, gammas, limit: int | None = None) -> dict:
    """Compare the reconstruction to the true ``psi`` on a set of points."""
    top = limit or int(max(xs)) + 1
    exact = psi_exact(top)
    rows = []
    for x in xs:
        approx = psi_from_zeros(float(x), gammas)
        true = exact[int(x)]
        rows.append({
            "x": float(x),
            "psi_exact": true,
            "psi_from_zeros": approx,
            "error": approx - true,
            "error_over_sqrt_x": (approx - true) / math.sqrt(x),
        })
    return {"rows": rows, "n_zeros_used": len(gammas)}
