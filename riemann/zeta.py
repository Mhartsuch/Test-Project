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
    abs_total = 0.0
    for k in range(1, n):
        term = cmath.exp(-s * math.log(k))
        total += term
        abs_total += abs(term)

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
    # ... plus floating-point roundoff from the head sum, which dominates once
    # N is large.  This is the standard worst-case forward-error bound for
    # recursive summation, (n-1) * eps * sum |x_i| -- note it uses the sum of
    # ABSOLUTE values, not |total|.  On the critical line the terms are
    # k^{-1/2}, so sum|x_i| ~ 2 sqrt(N) while |total| stays O(1); using the
    # latter understates the error by an order of magnitude and produces a
    # "bound" that the true error violates.  Pessimistic by roughly sqrt(n)
    # relative to typical behaviour, but it is an actual bound.
    roundoff = 2.220446049250313e-16 * n * abs_total
    return total, truncation + roundoff


def zeta(s: complex, n_terms: int | None = None, m_terms: int = 12) -> complex:
    """The Riemann zeta function ``zeta(s)``."""
    return zeta_with_error(s, n_terms, m_terms)[0]


def _log_sin(z: complex) -> complex:
    """``log sin z``, stable for large ``|Im z|``.

    ``sin z = (e^{iz} - e^{-iz})/2i`` overflows as written once ``|Im z|``
    exceeds a few hundred, even though ``sin z`` is then merely large rather
    than infinite.  Factoring out the dominant exponential keeps everything
    finite:

    ``Im z > 0``:  ``sin z = e^{-iz}(e^{2iz} - 1)/2i``
    ``Im z < 0``:  ``sin z = e^{+iz}(1 - e^{-2iz})/2i``

    In each case the bracket is ``-1 + O(e^{-2|Im z|})`` or
    ``1 + O(e^{-2|Im z|})`` and is evaluated directly -- note the two brackets
    differ by a sign, and writing both as ``(1 - ...)`` costs a factor of
    ``-1 = e^{i pi}``, which negates ``zeta`` throughout ``Re s < 1/2``.
    """
    if abs(z.imag) < 30.0:
        return cmath.log(cmath.sin(z))
    log_2i = cmath.log(2j)
    if z.imag > 0:
        return -1j * z - log_2i + cmath.log(cmath.exp(2j * z) - 1.0)
    return 1j * z - log_2i + cmath.log(1.0 - cmath.exp(-2j * z))


def _chi(s: complex) -> complex:
    """The factor ``chi(s)`` in ``zeta(s) = chi(s) zeta(1-s)``.

    ``chi(s) = 2^s pi^{s-1} sin(pi s / 2) Gamma(1-s)``.  Every factor is
    computed logarithmically: for ``s = sigma + it`` with ``t`` large,
    ``sin(pi s/2)`` grows like ``e^{pi t/2}`` and ``Gamma(1-s)`` decays just as
    fast, so the product is perfectly tame while the factors are not.
    Evaluating them separately overflows above ``t ~ 450``.
    """
    s = complex(s)
    return cmath.exp(
        s * math.log(2.0)
        + (s - 1.0) * log_pi
        + _log_sin(math.pi * s / 2.0)
        + log_gamma(1.0 - s)
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


def zeta_prime(s: complex, n_terms: int | None = None, m_terms: int = 12) -> complex:
    """``zeta'(s)``, by differentiating the Euler-Maclaurin expansion termwise.

    Analytic rather than a finite difference, because this is used to *locate
    zeros of* ``zeta'`` (Speiser's theorem), and a difference quotient loses
    half its digits exactly where the function is small.

    Differentiating each piece of the expansion in :func:`zeta_with_error`:

    * ``sum_{k<N} k^{-s}``           ->  ``-sum_{k<N} (log k) k^{-s}``
    * ``N^{-s}/2``                   ->  ``-(log N) N^{-s}/2``
    * ``N^{1-s}/(s-1)``              ->  ``N^{1-s}[-log N/(s-1) - 1/(s-1)^2]``
    * ``c_j P_j(s) N^{-s-2j+1}``     ->  ``c_j N^{-s-2j+1}[P_j'(s) - P_j(s) log N]``

    where ``P_j(s) = prod_{i=0}^{2j-2}(s+i)`` and, since ``P_j`` is a product of
    linear factors, ``P_j'(s) = P_j(s) * sum_{i=0}^{2j-2} 1/(s+i)`` -- so the
    logarithmic-derivative sum is accumulated alongside ``P_j`` itself.
    """
    s = complex(s)
    if s == 1.0:
        raise ValueError("zeta has a pole at s = 1")
    if s.real < 0.5:
        # No clean functional equation shortcut for the derivative; shift the
        # working point instead by using more terms.
        n_terms = n_terms or max(24, int(1.2 * abs(s.imag)) + 24)

    n = int(n_terms if n_terms is not None else max(12, int(0.6 * abs(s.imag)) + 12))
    m = int(m_terms)

    total = 0.0 + 0.0j
    for k in range(2, n):                      # log 1 = 0
        lk = math.log(k)
        total -= lk * cmath.exp(-s * lk)

    log_n = math.log(n)
    n_neg_s = cmath.exp(-s * log_n)
    total -= 0.5 * log_n * n_neg_s
    total += n_neg_s * n * (-log_n / (s - 1.0) - 1.0 / (s - 1.0) ** 2)

    coeffs = _em_coeffs(m)
    rising = s                                  # P_1(s) = s
    harm = 1.0 / s                              # sum 1/(s+i) over the same factors
    n_pow = n_neg_s / n
    inv_n2 = 1.0 / (n * n)
    for k in range(1, m + 1):
        if k > 1:
            rising *= (s + (2 * k - 3)) * (s + (2 * k - 2))
            harm += 1.0 / (s + (2 * k - 3)) + 1.0 / (s + (2 * k - 2))
            n_pow *= inv_n2
        total += coeffs[k - 1] * n_pow * rising * (harm - log_n)
    return total


def zeta_prime_over_zeta(s: complex) -> complex:
    """``zeta'(s)/zeta(s)``."""
    return zeta_prime(s) / zeta(s)
