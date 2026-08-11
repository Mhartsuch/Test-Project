"""The Riemann zeta function via Euler-Maclaurin summation.

This is the *reference* implementation used throughout the package: it is slow
but its error is controlled by an explicit, checkable bound, so it is the thing
that everything faster (the Riemann-Siegel formula) gets validated against.

The Euler-Maclaurin representation is, for any integers ``N >= 1``, ``M >= 1``,

.. math::
   \\zeta(s) = \\sum_{n=1}^{N-1} n^{-s}
             + \\frac{N^{-s}}{2}
             + \\frac{N^{1-s}}{s-1}
             + \\sum_{k=1}^{M} \\frac{B_{2k}}{(2k)!}
               \\Big(\\prod_{j=0}^{2k-2}(s+j)\\Big) N^{-s-2k+1}
             + E_{M}(s, N)

valid for ``Re(s) > -2M-1``, ``s != 1``.  The remainder obeys the classical
bound (Edwards, *Riemann's Zeta Function*, sec. 6.4)

.. math::
   |E_M| \\le \\Big|\\frac{s + 2M + 1}{\\sigma + 2M + 1}\\Big| \\cdot |T_M|

where ``T_M`` is the last retained correction term.  We use that bound both to
choose the parameters adaptively and to *report* a rigorous error estimate.
"""

from __future__ import annotations

import cmath
import math
from functools import lru_cache

from .special import bernoulli_exact, log_gamma, log_pi

__all__ = ["zeta", "zeta_with_error", "eta", "xi", "zeta_prime_over_zeta"]


@lru_cache(maxsize=None)
def _em_coeffs(m: int) -> tuple:
    """``B_{2k} / (2k)!`` for ``k = 1 .. m``."""
    out = []
    fact = 1
    for k in range(1, m + 1):
        # (2k)! computed incrementally
        fact *= (2 * k - 1) * (2 * k)
        out.append(float(bernoulli_exact(2 * k)) / fact)
    return tuple(out)


def zeta_with_error(s: complex, n_terms: int | None = None, m_terms: int = 12):
    """Return ``(zeta(s), error_bound)`` using Euler-Maclaurin.

    Parameters
    ----------
    s:
        Point of evaluation (``s != 1``).
    n_terms:
        Number of leading Dirichlet terms ``N``.  When ``None`` a value is
        chosen from ``|Im s|`` that keeps the asymptotic series useful.
    m_terms:
        Number of Bernoulli correction terms ``M``.
    """
    s = complex(s)
    if s == 1.0:
        raise ValueError("zeta has a pole at s = 1")

    if s.real < 0.5:
        # Functional equation:  zeta(s) = chi(s) zeta(1-s)
        v, err = zeta_with_error(1.0 - s, n_terms, m_terms)
        c = _chi(s)
        return c * v, abs(c) * err

    if n_terms is None:
        # The correction terms only start decaying once N is comparable to
        # |t|/2; below that the asymptotic series is useless.
        n_terms = max(12, int(0.6 * abs(s.imag)) + 12)

    n = int(n_terms)
    m = int(m_terms)

    total = 0.0 + 0.0j
    for k in range(1, n):
        total += cmath.exp(-s * math.log(k))

    log_n = math.log(n)
    n_pow_neg_s = cmath.exp(-s * log_n)
    total += 0.5 * n_pow_neg_s
    total += n_pow_neg_s * n / (s - 1.0)

    # Correction terms.  ``rising`` accumulates prod_{j=0}^{2k-2} (s+j).
    coeffs = _em_coeffs(m)
    rising = s
    n_pow = n_pow_neg_s / n  # N^{-s-1}
    inv_n2 = 1.0 / (n * n)
    last = 0.0 + 0.0j
    for k in range(1, m + 1):
        if k > 1:
            rising *= (s + (2 * k - 3)) * (s + (2 * k - 2))
            n_pow *= inv_n2
        last = coeffs[k - 1] * rising * n_pow
        total += last

    # Truncation error (Edwards sec. 6.4) ...
    truncation = abs((s + 2 * m + 1) / (s.real + 2 * m + 1)) * abs(last)
    # ... plus accumulated floating-point roundoff from the head sum, which
    # dominates once N is large.  Each of the N terms has modulus <= 1 on the
    # critical line, and naive summation accumulates ~ eps * N of relative
    # error.  Reporting only the truncation bound would badly understate the
    # true error at large |t|, so both are included.
    roundoff = 2.220446049250313e-16 * n * max(1.0, abs(total))
    return total, truncation + roundoff


def zeta(s: complex, n_terms: int | None = None, m_terms: int = 12) -> complex:
    """The Riemann zeta function ``zeta(s)``."""
    return zeta_with_error(s, n_terms, m_terms)[0]


def _chi(s: complex) -> complex:
    """The factor ``chi(s)`` in ``zeta(s) = chi(s) zeta(1-s)``.

    ``chi(s) = 2^s pi^{s-1} sin(pi s / 2) Gamma(1-s)``, evaluated through
    logarithms where possible to avoid overflow.
    """
    s = complex(s)
    return (
        cmath.exp(s * math.log(2.0) + (s - 1.0) * log_pi)
        * cmath.sin(math.pi * s / 2.0)
        * cmath.exp(log_gamma(1.0 - s))
    )


def eta(s: complex, terms: int = 60) -> complex:
    """Dirichlet eta ``(1-2^{1-s}) zeta(s)`` by Euler transformation.

    An independent route to ``zeta`` on the critical strip, used as a
    consistency check rather than for production evaluation.  Uses the
    Borwein-style alternating-series acceleration.
    """
    n = terms
    # d_k = n * sum_{i=0}^{k} (n+i-1)! 4^i / ((n-i)! (2i)!), built by term ratio.
    dk = [0.0] * (n + 1)
    c = 1.0  # the i = 0 term equals 1
    running = c
    dk[0] = running
    for i in range(1, n + 1):
        c *= 4.0 * (n + i - 1) * (n - i + 1) / ((2 * i) * (2 * i - 1))
        running += c
        dk[i] = running
    dn = dk[n]

    total = 0.0 + 0.0j
    sign = 1.0
    for k in range(n):
        total += sign * (dk[k] - dn) * cmath.exp(-s * math.log(k + 1))
        sign = -sign
    return -total / dn


def xi(s: complex) -> complex:
    """Riemann's completed zeta ``xi(s) = 1/2 s(s-1) pi^{-s/2} Gamma(s/2) zeta(s)``.

    Entire, and satisfies the symmetry ``xi(s) = xi(1-s)``.  Its zeros are
    exactly the non-trivial zeros of ``zeta``; RH is the statement that they
    all have real part 1/2.
    """
    s = complex(s)
    return (
        0.5
        * s
        * (s - 1.0)
        * cmath.exp(-s / 2.0 * log_pi + log_gamma(s / 2.0))
        * zeta(s)
    )


def zeta_prime_over_zeta(s: complex, h: float = 1e-5) -> complex:
    """``zeta'(s)/zeta(s)`` by a centred complex difference.

    Used only for diagnostics; the argument-principle zero count in
    :mod:`riemann.counting` uses continuous argument tracking instead, which is
    far better conditioned near zeros.
    """
    s = complex(s)
    num = zeta(s + h) - zeta(s - h)
    return num / (2.0 * h) / zeta(s)
