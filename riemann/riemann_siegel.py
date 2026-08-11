"""The Riemann-Siegel formula for the Hardy Z-function.

Motivation
----------
Euler-Maclaurin needs ``O(t)`` terms to evaluate ``zeta(1/2 + it)``.  The
Riemann-Siegel formula needs only ``O(sqrt(t))``, which is the entire reason
large-scale verification of RH is possible at all.  Riemann derived it around
1859; it sat unread in his Nachlass until Siegel dug it out in 1932.

Definitions
-----------
The Riemann-Siegel theta function is

.. math::  \\theta(t) = \\arg \\Gamma\\!\\left(\\tfrac14 + \\tfrac{it}{2}\\right)
                        - \\tfrac{t}{2}\\log \\pi

and the Hardy Z-function is

.. math::  Z(t) = e^{i\\theta(t)} \\zeta\\!\\left(\\tfrac12 + it\\right).

``Z`` is *real* for real ``t`` and ``|Z(t)| = |zeta(1/2+it)|``, so zeros of
``zeta`` on the critical line are exactly the real zeros of ``Z`` -- and they
can be located by looking for sign changes, which is both cheap and robust.

The formula
-----------
With ``tau = sqrt(t/2 pi)``, ``N = floor(tau)`` and ``p = tau - N``,

.. math::
   Z(t) = 2\\sum_{n=1}^{N} \\frac{\\cos(\\theta(t) - t\\log n)}{\\sqrt n}
        + (-1)^{N-1}\\tau^{-1/2}\\sum_{k=0}^{K} C_k(p)\\,\\tau^{-k}
        + O(t^{-(K+1)/2 - 1/4}).

The correction coefficients are built from the entire function

.. math::  \\Psi(p) = \\frac{\\cos\\bigl(2\\pi(p^2 - p - 1/16)\\bigr)}{\\cos(2\\pi p)}

and its derivatives.  ``Psi`` is written as a ratio whose numerator and
denominator both vanish at ``p = 1/4, 3/4``; the singularities are removable
but the quotient is numerically unusable there, and high-order finite
differences of it are hopeless.  Instead the derivatives are obtained from
Cauchy's integral formula

.. math::
   \\Psi^{(k)}(p) = \\frac{k!}{2\\pi i}\\oint \\frac{\\Psi(z)}{(z-p)^{k+1}}\\,dz
                  = \\frac{k!}{r^{k}}\\cdot\\frac1M\\sum_{j}
                    \\Psi(p + re^{i\\phi_j})\\,e^{-ik\\phi_j},

evaluated on a circle by the trapezoid rule -- which converges *geometrically*
for analytic integrands.  The quadrature angles are offset by half a step so
that no node lands on the real axis, which sidesteps the removable
singularities entirely: the zeros of ``cos(2 pi z)`` are all real, so at a
strictly complex node the denominator is bounded away from zero.
"""

from __future__ import annotations

import cmath
import math
from functools import lru_cache

from .special import TWO_PI, log_gamma, log_pi
from .zeta import zeta

__all__ = [
    "theta",
    "theta_asymptotic",
    "Z",
    "Z_via_zeta",
    "zeta_on_critical_line",
    "gram_point",
    "psi_derivative",
    "correction_coefficient",
    "RS_MAX_ORDER",
]

RS_MAX_ORDER = 3

_PI2 = math.pi ** 2
_PI4 = _PI2 * _PI2
_PI6 = _PI4 * _PI2


# ---------------------------------------------------------------------------
# theta
# ---------------------------------------------------------------------------

def theta(t: float) -> float:
    """Riemann-Siegel theta, evaluated exactly through ``log Gamma``."""
    return log_gamma(0.25 + 0.5j * t).imag - 0.5 * t * log_pi


def theta_asymptotic(t: float) -> float:
    """Asymptotic expansion of ``theta`` (reference / speed comparison).

    .. math::
       \\theta(t) \\sim \\frac{t}{2}\\log\\frac{t}{2\\pi} - \\frac t2
                      - \\frac\\pi8 + \\frac1{48t} + \\frac7{5760t^3}
                      + \\frac{31}{80640 t^5} + \\frac{127}{430080 t^7}
    """
    if t <= 0:
        raise ValueError("theta_asymptotic requires t > 0")
    inv = 1.0 / t
    inv2 = inv * inv
    return (
        0.5 * t * math.log(t / TWO_PI)
        - 0.5 * t
        - math.pi / 8.0
        + inv * (1.0 / 48.0
                 + inv2 * (7.0 / 5760.0
                           + inv2 * (31.0 / 80640.0
                                     + inv2 * 127.0 / 430080.0)))
    )


# ---------------------------------------------------------------------------
# Psi and its derivatives
# ---------------------------------------------------------------------------

def _psi(z: complex) -> complex:
    return cmath.cos(TWO_PI * (z * z - z - 0.0625)) / cmath.cos(TWO_PI * z)


def psi_derivative(p: float, k: int, radius: float = 0.5, nodes: int = 256) -> float:
    """``Psi^{(k)}(p)`` by trapezoidal quadrature of Cauchy's integral formula.

    The half-step angular offset keeps every quadrature node off the real axis,
    so the removable singularities of the quotient form of ``Psi`` are never
    evaluated.
    """
    total = 0.0 + 0.0j
    for j in range(nodes):
        phi = TWO_PI * (j + 0.5) / nodes
        total += _psi(p + radius * cmath.exp(1j * phi)) * cmath.exp(-1j * k * phi)
    return math.factorial(k) * (total / nodes).real / radius ** k


def correction_coefficient(p: float, k: int) -> float:
    """The Riemann-Siegel correction coefficient ``C_k(p)``, ``0 <= k <= 3``.

    Coefficients as in Edwards, *Riemann's Zeta Function*, sec. 7.4 (the form
    used by Haselgrove, Brent and Odlyzko).  The rational constants are
    ``2^5*3 = 96``, ``2^6 = 64``, ``2^11*3^2 = 18432``, ``2^8*3*5 = 3840`` and
    ``2^16*3^4 = 5308416``.

    Every one of these was confirmed *empirically* rather than trusted to
    recall: ``scripts/verify_rs_coefficients.py`` extracts the true ``C_k(p)``
    from high-precision values of ``Z`` by fixing the fractional part ``p``,
    sweeping ``tau = N + p``, and least-squares fitting the remainder against
    powers of ``1/tau``.  Fitting the resulting ``C_3(p)`` against the basis
    ``{Psi', Psi^(5), Psi^(9)}`` recovers the denominators to 7 significant
    figures.  This caught a genuine error: the ``Psi^(5)`` denominator is
    ``3840``, and an initial value of ``15360`` made order 3 *less* accurate
    than order 2.
    """
    if k == 0:
        return psi_derivative(p, 0)
    if k == 1:
        return -psi_derivative(p, 3) / (96.0 * _PI2)
    if k == 2:
        return (psi_derivative(p, 2) / (64.0 * _PI2)
                + psi_derivative(p, 6) / (18432.0 * _PI4))
    if k == 3:
        return (-psi_derivative(p, 1) / (64.0 * _PI2)
                - psi_derivative(p, 5) / (3840.0 * _PI4)
                - psi_derivative(p, 9) / (5308416.0 * _PI6))
    raise ValueError(f"C_k implemented only for k <= {RS_MAX_ORDER}, got {k}")


# --- tabulation + barycentric interpolation -------------------------------
#
# Each C_k costs a few hundred complex cosines, which is far too slow to repeat
# inside a zero search.  They are smooth functions of p on [0,1], so they are
# tabulated once on a uniform grid and evaluated by local barycentric Lagrange
# interpolation of degree 7.

_GRID = 256
_STENCIL = 8
# Barycentric weights for 8 equispaced nodes: w_j = (-1)^j * C(7, j).
_BARY_W = tuple(
    (-1.0) ** j * math.comb(_STENCIL - 1, j) for j in range(_STENCIL)
)


@lru_cache(maxsize=None)
def _coefficient_table(k: int) -> tuple:
    return tuple(correction_coefficient(i / _GRID, k) for i in range(_GRID + 1))


def _interp(table: tuple, p: float) -> float:
    x = p * _GRID
    i0 = min(max(int(x) - _STENCIL // 2 + 1, 0), _GRID + 1 - _STENCIL)
    num = 0.0
    den = 0.0
    for j in range(_STENCIL):
        d = x - (i0 + j)
        if d == 0.0:
            return table[i0 + j]
        w = _BARY_W[j] / d
        num += w * table[i0 + j]
        den += w
    return num / den


def _C(p: float, k: int) -> float:
    return _interp(_coefficient_table(k), p)


# ---------------------------------------------------------------------------
# The Z function
# ---------------------------------------------------------------------------

def Z(t: float, order: int = RS_MAX_ORDER) -> float:
    """Hardy's ``Z(t)`` via Riemann-Siegel, using ``C_0 .. C_order``.

    Accuracy is roughly ``t^{-(order+1)/2 - 1/4}``; at ``order = 3`` that is
    about ``1e-7`` near ``t = 1e4`` and improves as ``t`` grows.
    """
    t = float(t)
    if t < 0:
        return Z(-t, order)
    if t < 15.0:
        # Below the first zero the asymptotic correction is not yet useful.
        return Z_via_zeta(t)

    tau = math.sqrt(t / TWO_PI)
    n_max = int(tau)
    p = tau - n_max

    th = theta(t)
    total = 0.0
    for n in range(1, n_max + 1):
        total += math.cos(th - t * math.log(n)) / math.sqrt(n)
    total *= 2.0

    inv_tau = 1.0 / tau
    corr = 0.0
    power = 1.0
    for k in range(order + 1):
        corr += _C(p, k) * power
        power *= inv_tau
    sign = 1.0 if (n_max - 1) % 2 == 0 else -1.0
    return total + sign * math.sqrt(inv_tau) * corr


def Z_via_zeta(t: float) -> float:
    """``Z(t)`` computed from the Euler-Maclaurin ``zeta`` -- the slow oracle."""
    return (cmath.exp(1j * theta(t)) * zeta(0.5 + 1j * t)).real


def zeta_on_critical_line(t: float, order: int = RS_MAX_ORDER) -> complex:
    """``zeta(1/2 + it)`` recovered from ``Z(t)``."""
    return cmath.exp(-1j * theta(t)) * Z(t, order)


# ---------------------------------------------------------------------------
# Gram points
# ---------------------------------------------------------------------------

def gram_point(n: int, tol: float = 1e-12, max_iter: int = 100) -> float:
    """The ``n``-th Gram point ``g_n``: the solution of ``theta(g_n) = n pi``.

    Gram points interlace the zeros remarkably often ("Gram's law"), which
    makes them excellent starting brackets for a zero search -- though the law
    is false infinitely often, so nothing here may *assume* it.

    ``theta`` is strictly increasing for ``t > 6.29...``, so ``g_n`` is unique
    there; indices ``n >= -1`` are supported (``g_{-1} = 9.6669...``,
    ``g_0 = 17.8455...``).
    """
    if n < -1:
        raise ValueError("gram_point is defined here for n >= -1")
    target = n * math.pi

    # Bracket inside the region where theta is increasing.
    lo = 7.0
    hi = max(20.0, TWO_PI * math.e)
    while theta(hi) < target:
        hi *= 2.0

    # Bisect to a safe neighbourhood, then polish with Newton (theta' is known
    # exactly: d(theta)/dt = (1/2) log(t / 2 pi) + O(t^-2)).
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if theta(mid) < target:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-6:
            break

    t = 0.5 * (lo + hi)
    for _ in range(max_iter):
        f = theta(t) - target
        fp = 0.5 * math.log(t / TWO_PI)
        if fp <= 0.0:
            break
        step = f / fp
        t -= step
        if abs(step) < tol * max(1.0, abs(t)):
            break
    return t
