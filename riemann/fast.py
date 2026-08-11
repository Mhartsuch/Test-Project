"""Vectorised evaluation of ``Z(t)`` (optional numpy acceleration).

The pure-Python implementation in :mod:`riemann.riemann_siegel` is the
reference; this module computes the same quantity on whole arrays so that
hundreds of thousands of zeros are reachable in seconds rather than hours.
:mod:`tests.test_fast` asserts the two agree to ~1e-12.

Two changes are made for speed, both checked:

* ``theta`` uses the asymptotic series rather than ``log Gamma``.  For
  ``t > 50`` the two agree to the last few bits of a double.
* The correction coefficients are read from the same tabulated grid, but the
  barycentric interpolation is done with array arithmetic.
"""

from __future__ import annotations

import math

import numpy as np

from .riemann_siegel import _BARY_W, _GRID, _STENCIL, RS_MAX_ORDER, _coefficient_table
from .zeta import _em_coeffs

__all__ = ["theta_array", "Z_array", "HorizontalLine", "li_coefficients_array",
           "HAVE_NUMPY"]

HAVE_NUMPY = True
TWO_PI = 2.0 * math.pi


def theta_array(t: np.ndarray) -> np.ndarray:
    """Riemann-Siegel theta on an array, via the asymptotic expansion."""
    t = np.asarray(t, dtype=float)
    inv = 1.0 / t
    inv2 = inv * inv
    return (
        0.5 * t * np.log(t / TWO_PI)
        - 0.5 * t
        - math.pi / 8.0
        + inv * (1.0 / 48.0
                 + inv2 * (7.0 / 5760.0
                           + inv2 * (31.0 / 80640.0
                                     + inv2 * 127.0 / 430080.0)))
    )


def li_coefficients_array(n_max: int, gammas, sigmas=None) -> np.ndarray:
    """``lambda_1 .. lambda_n_max`` from zero ordinates, vectorised over zeros.

    Same arithmetic as :func:`riemann.equivalences.li_coefficients`, but it
    keeps a running array of ``w^n = (1 - 1/rho)^n`` and advances all zeros by
    one power per step, so the cost is ``n_max`` passes over the zero array
    rather than an ``n_max x n_zeros`` allocation.

    Stability: on the critical line ``|w| = 1`` exactly, so the running product
    neither grows nor decays and the accumulated relative error after ``n``
    steps is only about ``n * eps``.
    """
    g = np.asarray(list(gammas), dtype=float)
    s = np.full(g.shape, 0.5) if sigmas is None else np.asarray(list(sigmas), dtype=float)

    roots = [g.astype(complex) * 1j + s]
    off = np.abs(s - 0.5) > 1e-15
    if off.any():  # zeros off the line come in quadruples: add the reflection
        roots.append(g[off].astype(complex) * 1j + (1.0 - s[off]))
    rho = np.concatenate(roots)

    w = 1.0 - 1.0 / rho
    powers = np.ones_like(w)
    out = np.empty(n_max, dtype=float)
    n_roots = rho.size
    for i in range(n_max):
        powers *= w
        out[i] = 2.0 * (n_roots - powers.real.sum())
    return out


class HorizontalLine:
    """Evaluate ``zeta(sigma + it)`` for many ``sigma`` at one fixed ``t``.

    The argument-principle count walks a horizontal segment from ``2 + iT`` to
    ``1/2 + iT``, evaluating ``zeta`` at dozens of points that all share the
    same imaginary part.  In the Euler-Maclaurin head sum

    .. math::  \\sum_{k<N} k^{-\\sigma-it}
             = \\sum_{k<N} k^{-\\sigma}\\,e^{-it\\log k},

    the expensive oscillatory factor ``e^{-it log k}`` depends only on ``t``, so
    it is computed once and reused for every ``sigma`` on the line.  That turns
    an ``O(m N)`` transcendental cost into ``O(N)`` plus ``m`` cheap array
    passes, which is what makes it affordable to *localise* missing zeros by
    bisecting on ``N(t)`` rather than guessing where they might be.
    """

    def __init__(self, t: float, n_terms: int | None = None, m_terms: int = 12):
        self.t = float(t)
        self.n = int(n_terms or max(12, int(0.6 * abs(self.t)) + 12))
        self.m = int(m_terms)
        k = np.arange(1, self.n, dtype=float)
        self._log_k = np.log(k)
        self._phase = np.exp(-1j * self.t * self._log_k)
        self._coeffs = _em_coeffs(self.m)
        self._log_n = math.log(self.n)

    def at(self, sigma: float) -> complex:
        s = complex(sigma, self.t)
        head = complex(np.sum(np.exp(-sigma * self._log_k) * self._phase))

        n_pow_neg_s = np.exp(-s * self._log_n)
        total = head + 0.5 * n_pow_neg_s + n_pow_neg_s * self.n / (s - 1.0)

        rising = s
        n_pow = n_pow_neg_s / self.n
        inv_n2 = 1.0 / (self.n * self.n)
        for k in range(1, self.m + 1):
            if k > 1:
                rising *= (s + (2 * k - 3)) * (s + (2 * k - 2))
                n_pow *= inv_n2
            total += self._coeffs[k - 1] * rising * n_pow
        return complex(total)


def _interp_array(table: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Degree-7 barycentric Lagrange interpolation on the uniform C_k grid."""
    x = p * _GRID
    i0 = np.clip(x.astype(np.int64) - _STENCIL // 2 + 1, 0, _GRID + 1 - _STENCIL)
    num = np.zeros_like(x)
    den = np.zeros_like(x)
    exact = np.zeros_like(x)
    hit = np.zeros(x.shape, dtype=bool)
    for j in range(_STENCIL):
        idx = i0 + j
        d = x - idx
        on_node = d == 0.0
        if on_node.any():
            exact = np.where(on_node & ~hit, table[idx], exact)
            hit |= on_node
            d = np.where(on_node, 1.0, d)
        w = _BARY_W[j] / d
        num += w * table[idx]
        den += w
    return np.where(hit, exact, num / den)


def Z_array(ts: np.ndarray, order: int = RS_MAX_ORDER, block: int = 20000) -> np.ndarray:
    """``Z(t)`` for an array of ``t >= 15``, using Riemann-Siegel to ``C_order``."""
    ts = np.atleast_1d(np.asarray(ts, dtype=float))
    if np.any(ts < 15.0):
        raise ValueError("Z_array requires t >= 15; use riemann_siegel.Z for small t")

    tables = [np.asarray(_coefficient_table(k)) for k in range(order + 1)]
    out = np.empty_like(ts)

    for start in range(0, ts.size, block):
        chunk = ts[start:start + block]
        tau = np.sqrt(chunk / TWO_PI)
        n_max = np.floor(tau).astype(np.int64)
        p = tau - n_max
        th = theta_array(chunk)

        # Main sum: 2 * sum_{n<=n_max} cos(theta - t log n)/sqrt(n), with terms
        # beyond each row's own n_max masked out.
        top = int(n_max.max())
        n = np.arange(1, top + 1, dtype=float)
        log_n = np.log(n)
        inv_sqrt_n = 1.0 / np.sqrt(n)
        mask = n[None, :] <= n_max[:, None]
        angles = th[:, None] - chunk[:, None] * log_n[None, :]
        total = 2.0 * np.sum(np.where(mask, np.cos(angles) * inv_sqrt_n[None, :], 0.0), axis=1)

        inv_tau = 1.0 / tau
        corr = np.zeros_like(chunk)
        power = np.ones_like(chunk)
        for k in range(order + 1):
            corr += _interp_array(tables[k], p) * power
            power *= inv_tau
        sign = np.where((n_max - 1) % 2 == 0, 1.0, -1.0)
        out[start:start + block] = total + sign * np.sqrt(inv_tau) * corr

    return out
