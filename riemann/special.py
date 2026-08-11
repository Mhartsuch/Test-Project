"""Special functions built from scratch (no third-party dependencies).

Everything here is implemented directly so that the rest of the package does not
rest on a black box.  ``mpmath`` is used in the test-suite as an *independent*
oracle, never inside the library itself.

Contents
--------
* Exact Bernoulli numbers (rational arithmetic via :mod:`fractions`).
* Complex ``log Gamma`` via the Stirling/Binet asymptotic series with argument
  shifting, branch-tracked so that it is continuous.
* Helpers for the completed zeta function.
"""

from __future__ import annotations

import cmath
import math
from fractions import Fraction
from functools import lru_cache

__all__ = [
    "bernoulli",
    "bernoulli_exact",
    "log_gamma",
    "gamma",
    "log_pi",
    "TWO_PI",
]

TWO_PI = 2.0 * math.pi
log_pi = math.log(math.pi)
_LOG_2PI = math.log(TWO_PI)


# ---------------------------------------------------------------------------
# Bernoulli numbers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _bernoulli_table(n: int) -> tuple:
    """Exact ``B_0 .. B_n`` (Akiyama-Tanigawa; uses the ``B_1 = +1/2``
    convention, which is irrelevant here because only even indices are used)."""
    a = [Fraction(0)] * (n + 1)
    out = []
    for m in range(n + 1):
        a[m] = Fraction(1, m + 1)
        for j in range(m, 0, -1):
            a[j - 1] = j * (a[j - 1] - a[j])
        out.append(a[0])
    return tuple(out)


def bernoulli_exact(k: int) -> Fraction:
    """Exact Bernoulli number ``B_k`` as a :class:`~fractions.Fraction`."""
    if k < 0:
        raise ValueError("k must be non-negative")
    # Grow the cached table in chunks so repeated calls stay cheap.
    size = max(32, 1 << (k.bit_length()))
    return _bernoulli_table(size)[k]


def bernoulli(k: int) -> float:
    """Bernoulli number ``B_k`` as a float."""
    return float(bernoulli_exact(k))


# Coefficients ``B_{2k} / (2k (2k-1))`` of the Stirling series for log Gamma.
@lru_cache(maxsize=None)
def _stirling_coeffs(terms: int) -> tuple:
    return tuple(
        float(bernoulli_exact(2 * k) / (2 * k * (2 * k - 1)))
        for k in range(1, terms + 1)
    )


# ---------------------------------------------------------------------------
# log Gamma for complex argument
# ---------------------------------------------------------------------------

def log_gamma(z: complex, terms: int = 10, shift_to: float = 14.0) -> complex:
    """Principal-branch ``log Gamma(z)``, continuous in the upper half plane.

    The Stirling (Binet) asymptotic series

    .. math::
        \\log\\Gamma(z) \\sim (z-\\tfrac12)\\log z - z + \\tfrac12\\log 2\\pi
                            + \\sum_{k\\ge1} \\frac{B_{2k}}{2k(2k-1)z^{2k-1}}

    is accurate only for large ``|z|``, so the argument is first shifted right
    by an integer amount using ``Gamma(z+1) = z Gamma(z)``.

    Branch
    ------
    For ``Re(z) > 0`` -- the only region this package actually evaluates -- the
    result agrees with the principal branch and is a continuous function of
    ``z``, which is what :func:`riemann.riemann_siegel.theta` requires.  For
    ``Re(z) < 0`` the accumulated ``log`` of each shift factor is taken on the
    principal branch, so the value can differ from the analytic continuation by
    an integer multiple of ``2 pi i``.  That is harmless for :func:`gamma`
    (``exp`` kills the ambiguity) but means the raw logarithm should not be
    trusted there.  A ``ValueError`` is raised at the poles.
    """
    z = complex(z)
    if z.imag == 0.0 and z.real <= 0.0 and z.real == int(z.real):
        raise ValueError(f"Gamma has a pole at z = {z}")

    # Gamma(z) = Gamma(z+n) / (z (z+1) ... (z+n-1))
    acc = 0.0 + 0.0j
    w = z
    while w.real < shift_to:
        acc -= cmath.log(w)
        w += 1.0

    result = (w - 0.5) * cmath.log(w) - w + 0.5 * _LOG_2PI
    inv = 1.0 / w
    inv2 = inv * inv
    p = inv
    for c in _stirling_coeffs(terms):
        result += c * p
        p *= inv2
    return result + acc


def gamma(z: complex) -> complex:
    """``Gamma(z)`` for complex ``z``."""
    return cmath.exp(log_gamma(z))
