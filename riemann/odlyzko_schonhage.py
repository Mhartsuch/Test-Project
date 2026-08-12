"""Odlyzko-Schonhage: many values of ``Z(t)`` for the price of a few.

The bottleneck
--------------
Riemann-Siegel evaluates ``Z(t)`` with ``N = floor(sqrt(t/2 pi))`` cosines.  At
``t = 10^15`` that is ``N = 12{,}615{,}662`` terms -- about a third of a second
here -- and one evaluation is not enough for anything: locating a single zero
takes several, and the mean gap between zeros at that height is ``0.192``, so a
block of a thousand zeros spans ``t``-range 192 and needs of the order of ten
thousand evaluations.  Done one at a time that is an hour of arithmetic for a
thousand zeros, and the cost per zero never improves no matter how many you
want.

Odlyzko and Schonhage (1988) observed that this is the wrong way round.  The
expensive object is not ``Z`` at a point but the *main sum*

.. math::  F(t) = \\sum_{n=1}^{N} n^{-1/2} e^{-it\\log n},

and ``F`` is a sum of ``N`` pure exponentials in ``t``.  Sampling it at ``M``
equally spaced points ``t_j = t_0 + (j - M/2)\\delta`` gives

.. math::  F(t_j) = \\sum_{n=1}^{N} c_n e^{-ik x_n},
           \\qquad k = j - M/2,\\; x_n = \\delta\\log n,\\;
           c_n = n^{-1/2}e^{-it_0\\log n},

which is a *nonuniform discrete Fourier transform*: ``M`` output modes from
``N`` sources at irregular frequencies ``x_n``.  That costs ``O(N + M\\log M)``
rather than ``O(NM)``.  The per-point cost of ``Z`` therefore falls from ``N``
to ``N/M + \\log M``, and it keeps falling as the block gets bigger.

Odlyzko and Schonhage reached the same place by expanding
``\\sum_n c_n/(1 - z_n w)`` with the fast multipole method and reading off Taylor
coefficients.  The transform used here is the Greengard-Lee Gaussian-gridding
NUFFT, which is the same idea -- a smooth kernel that is cheap in one domain
and rapidly decaying in the other -- with better numerical behaviour, since the
poles never come near the contour.  The complexity is what matters and it is
unchanged.

Getting off the grid for free
-----------------------------
``F`` is band-limited: its frequencies ``-\\log n`` all lie in ``[-\\log N, 0]``,
a band of half-width ``\\Omega = \\tfrac12\\log N = \\tfrac14\\log(t/2\\pi)``.
Nyquist therefore allows a sample spacing of ``\\pi/\\Omega = 2\\times`` the mean
zero gap: **two samples per zero already oversamples by a factor of four.**  So
``F`` between grid points is recovered by band-limited interpolation, and the
zero search never needs another ``N``-term sum.

``Z`` itself is *not* band-limited -- ``Z(t) = 2\\,\\mathrm{Re}\\,(e^{i\\theta(t)}F(t))``
and ``\\theta`` is not linear -- so the interpolation is applied to ``F`` and
``\\theta`` is evaluated exactly at the target point, which costs nothing.

Precision
---------
Everything above is arithmetically delicate at ``t = 10^15``; see
:mod:`riemann.dd`.  Two places need the double-double machinery:

* ``c_n`` needs ``t_0\\log n`` reduced modulo ``2\\pi``, and that number is
  ``1.6\\times10^{16}`` -- 17 digits gone before the fraction starts;
* ``x_n = \\delta\\log n`` is kept as a double-double, because the mode index
  ``k`` multiplies it.  Rounding ``x_n`` to a single double costs
  ``10^{-16}``, and the *worst case* over ``|k| \\le 1688`` and
  ``\\sum n^{-1/2} = 7100`` is ``10^{-9}``.  Writing ``x_n = \\hat x_n +
  \\varepsilon_n`` and expanding ``e^{-ik\\varepsilon_n} = 1 - ik\\varepsilon_n +
  O(k^2\\varepsilon_n^2)`` turns the fix into *one extra transform*, on the
  weights ``c_n\\varepsilon_n``, with a residual of ``10^{-24}``.

  Honesty about what that buys: measured rather than bounded, it is worth
  about 10%.  The roundings are independent across ``n`` and mostly cancel, so
  at ``t = 10^{13}`` the transform lands ``1.16\\times10^{-13}`` from the direct
  sum with the correction and ``1.27\\times10^{-13}`` without, both being close
  to the transform's own floor of ``\\varepsilon\\sum|c_n| e^{k^2\\tau}``.  The
  correction is kept because a *bound* has to cover the worst case and it costs
  one FFT out of a computation dominated by the spreading step -- but it is not
  what makes this work, and saying otherwise would be inventing a difficulty to
  have solved it.
"""

from __future__ import annotations

import math

import numpy as np

from . import dd
from .fast import _interp_array
from .riemann_siegel import RS_MAX_ORDER, _coefficient_table

__all__ = ["nufft_type1", "ZBlock", "next_fast_len"]

TWO_PI = 2.0 * math.pi


def next_fast_len(n: int) -> int:
    """Smallest ``>= n`` that is a product of 2s, 3s and 5s (fast for FFT)."""
    if n <= 1:
        return 1
    best = 1 << (n - 1).bit_length()
    p5 = 1
    while p5 < best:
        p3 = p5
        while p3 < best:
            p2 = 1 << max(0, (-(-n // p3)).bit_length() - 1)
            while p2 * p3 < n:
                p2 *= 2
            best = min(best, p2 * p3)
            p3 *= 3
        p5 *= 5
    return best


# ---------------------------------------------------------------------------
# the transform
# ---------------------------------------------------------------------------

def nufft_type1(x, c, n_modes: int, oversample: float = 2.0, spread: int = 18,
                x_low=None, chunk: int = 1 << 20):
    """``h_k = sum_n c_n exp(-i k x_n)`` for ``k = -M/2 .. M/2 - 1``.

    Gaussian gridding (Dutt-Rokhlin; Greengard-Lee 2004).  A periodic Gaussian
    ``g_tau`` is convolved onto a uniform grid of ``R M`` points, transformed
    with an ordinary FFT, and divided by ``\\hat g_tau(k) = sqrt(tau/pi)
    e^{-k^2 tau}``.  Both the truncation of the Gaussian at ``spread`` grid
    points and the aliasing of the trapezoid rule decay like
    ``exp(-2 pi \\cdot spread/3)`` at ``R = 2``, which is ``4\\times10^{-17}`` for
    the default ``spread = 18``.

    The three-exponential factorisation

    .. math:: e^{-(jh-\\Delta)^2/4\\tau}
              = e^{-\\Delta^2/4\\tau}\\,\\bigl(e^{\\Delta h/2\\tau}\\bigr)^{j}
                \\,e^{-j^2h^2/4\\tau}

    means each source costs two exponentials rather than ``2\\,spread`` of them.

    Parameters
    ----------
    x, c:
        Source frequencies (any real numbers; used modulo ``2 pi``) and complex
        weights.
    x_low:
        Optional low word of ``x`` in a double-double splitting.  When given,
        the first-order correction ``-ik\\varepsilon_n`` is applied, which is
        what keeps the result meaningful at large ``|k|``; see the module
        docstring.
    """
    x = np.asarray(x, dtype=float)
    c = np.asarray(c, dtype=complex)
    m = int(n_modes)
    if m % 2:
        raise ValueError("n_modes must be even")
    mr = next_fast_len(int(math.ceil(oversample * m)))
    ratio = mr / m
    tau = math.pi * spread / (ratio * (ratio - 0.5) * m * m)

    hx = TWO_PI / mr
    grid = np.zeros(mr, dtype=complex)
    grid_eps = np.zeros(mr, dtype=complex) if x_low is not None else None
    e3 = np.exp(-((np.arange(-spread + 1, spread + 1) * hx) ** 2) / (4.0 * tau))

    for start in range(0, x.size, chunk):
        xs = np.mod(x[start:start + chunk], TWO_PI)
        cs = c[start:start + chunk]
        m0 = np.floor(xs / hx).astype(np.int64)
        diff = xs - m0 * hx
        e1 = np.exp(-diff * diff / (4.0 * tau))
        e2 = np.exp(diff * hx / (2.0 * tau))

        run = e1 * e2 ** (-spread + 1)
        if x_low is not None:
            eps = cs * x_low[start:start + chunk]
        for j in range(-spread + 1, spread + 1):
            w = run * e3[j + spread - 1]
            idx = (m0 + j) % mr
            wc = w * cs
            grid += np.bincount(idx, weights=wc.real, minlength=mr) \
                + 1j * np.bincount(idx, weights=wc.imag, minlength=mr)
            if x_low is not None:
                we = w * eps
                grid_eps += np.bincount(idx, weights=we.real, minlength=mr) \
                    + 1j * np.bincount(idx, weights=we.imag, minlength=mr)
            run = run * e2

    ks = np.arange(-(m // 2), m - m // 2)
    deconv = math.sqrt(math.pi / tau) * np.exp(ks * ks * tau) / mr

    out = np.fft.fft(grid)[ks % mr] * deconv
    if x_low is not None:
        out = out - 1j * ks * (np.fft.fft(grid_eps)[ks % mr] * deconv)
    return out


# ---------------------------------------------------------------------------
# a block of the critical line
# ---------------------------------------------------------------------------

class ZBlock:
    """``Z`` on ``[t0 - h, t0 + h]``, set up once and then nearly free.

    Construction costs one pass over the ``N`` terms of the main sum -- the
    double-double logarithms and the reduction of ``t_0 log n`` modulo ``2 pi``.
    After that, :meth:`Z` evaluates at any number of points inside the block at
    ``O(1)`` cost each.

    The ordinate is not a float
    ---------------------------
    Every method here takes an **offset** ``d`` from ``t0``, never an absolute
    ``t``.  That is not a convenience; it is forced.  Consecutive float64 values
    near ``10^15`` are ``0.125`` apart, while the mean gap between zeros there
    is ``0.192`` -- so a double cannot name a zero ordinate at that height to
    better than two thirds of the distance to its neighbour.  Carrying the
    ordinate as an exactly-representable ``t0`` plus a small offset restores
    ``10^{-14}`` of resolution.

    For the same reason the grid spacing is rounded **down to a power of two**.
    Then ``k\\delta`` is exact for every integer ``k``, and ``\\delta\\log n`` is
    exact in double-double (a power of two only shifts the exponent), so the
    grid the transform computes on is the grid the rest of the code thinks it
    is computing on.  With an arbitrary ``\\delta`` the two differ by
    ``10^{-14}`` in ``t``, which sounds harmless and is not: ``|F'| = 10^5`` at
    ``t = 10^15``, so it moves the main sum by ``10^{-9}``.

    Parameters
    ----------
    t0, half_width:
        Centre and half-width of the block.  ``t0`` should be exactly
        representable (a round number is ideal).
    samples_per_gap:
        Grid density, in samples per mean zero gap.  The Nyquist limit is
        ``0.5``; the default oversamples fourfold, which is what makes the
        interpolation converge as fast as it does.
    order:
        Number of Riemann-Siegel correction terms, ``C_0 .. C_order``.
    """

    def __init__(self, t0: float, half_width: float, samples_per_gap: float = 2.0,
                 order: int = RS_MAX_ORDER, spread: int = 18,
                 interp_points: int = 32, verbose: bool = False):
        self.t0 = float(t0)
        self.order = int(order)
        self.spread = int(spread)
        self.interp_points = int(interp_points)

        self.gap = dd.mean_gap(self.t0)
        # round the sample spacing down to a power of two (see the class docs)
        self.delta = 2.0 ** math.floor(math.log2(self.gap / float(samples_per_gap)))
        # and snap the half-width to a whole number of samples
        self.half_width = math.ceil(float(half_width) / self.delta) * self.delta

        tau_lo = math.sqrt((self.t0 - self.half_width) / TWO_PI)
        tau_hi = math.sqrt((self.t0 + self.half_width) / TWO_PI)
        if math.floor(tau_lo) != math.floor(tau_hi):
            raise ValueError(
                "the block straddles an integer of sqrt(t/2pi), where the main "
                "sum changes length.  Split it at "
                f"t = {TWO_PI * math.floor(tau_hi) ** 2!r}"
            )
        self.n_max = int(math.floor(tau_lo))
        if self.n_max < 2:
            raise ValueError("t0 is too small for the Riemann-Siegel formula")

        # The grid must overhang the block by a full interpolation stencil at
        # each end, or points near the edge are reconstructed from samples that
        # do not exist.
        self.n_grid = next_fast_len(2 * int(round(self.half_width / self.delta))
                                    + 2 * self.interp_points + 2)
        if self.n_grid % 2:
            self.n_grid += 1

        self._setup(verbose)
        self._grid_values = None

    def __repr__(self):  # pragma: no cover - display only
        return (f"ZBlock(t0={self.t0!r}, half_width={self.half_width!r}, "
                f"N={self.n_max}, grid={self.n_grid})")

    # -- one-time setup ----------------------------------------------------
    def _setup(self, verbose: bool) -> None:
        n = np.arange(1.0, self.n_max + 1.0)
        log_n = dd.log(n)

        # (t0 log n) mod 2 pi -- the reduction that needs all 32 digits.
        self._base = dd.mul_mod_2pi_dd(self.t0, log_n)
        self._inv_sqrt_n = 1.0 / np.sqrt(n)

        # log n is kept at full double-double width.  Dropping the low word
        # perturbs log n by 1.5e-15, and both the mode index of the transform
        # and the re-centring shift of the direct path multiply that.
        self._log_n_dd = log_n
        self._log_n = log_n[0]
        del n

        # exp(-i b): the low word of the phase enters linearly, so one complex
        # multiply by (1 - i b_lo) absorbs it exactly to this order.
        self._c = (self._inv_sqrt_n * np.exp(-1j * self._base[0])
                   * (1.0 - 1j * self._base[1]))

        self._theta0 = dd.theta_mod_2pi(self.t0)
        self._half_log = dd.mul_d(dd.sub(dd.log(self.t0), dd.log(TWO_PI)), 0.5)
        self._tables = [np.asarray(_coefficient_table(k)) for k in range(self.order + 1)]
        if verbose:
            print(f"    ZBlock: N = {self.n_max:,} terms, "
                  f"grid = {self.n_grid:,} points at delta = {self.delta:g}")

    # -- theta -------------------------------------------------------------
    def _dtheta_small(self, d):
        t0 = self.t0
        return d * d * (1.0 / (4.0 * t0)
                        - d / (12.0 * t0 * t0)
                        + d * d / (24.0 * t0 ** 3))

    def dtheta(self, d):
        """``theta(t0 + d) - theta(t0)`` modulo ``2 pi``.

        The leading part ``d\\,\\theta'(t_0)`` reaches ``1.6 x 10^5`` across a
        block of width ``10^4`` at ``t = 10^15``, so it is formed and reduced in
        double-double; the curvature terms are tiny and plain doubles carry them
        with room to spare.  ``theta'(t) = (1/2) log(t/2 pi) - 1/(48 t^2)``.
        """
        d = np.asarray(d, dtype=float)
        lead = dd.mul_mod_2pi_dd(1.0, dd.mul_d(self._half_log, d))
        return dd.to_float(lead) + self._dtheta_small(d)

    def dtheta_exact(self, d):
        """``theta(t0 + d) - theta(t0)``, *not* reduced modulo ``2 pi``.

        Wanted whenever the value rather than the phase matters: counting zeros,
        and Turing's method.
        """
        d = np.asarray(d, dtype=float)
        return dd.to_float(dd.mul_d(self._half_log, d)) + self._dtheta_small(d)

    def theta_mod(self, d):
        """``theta(t0 + d)`` modulo ``2 pi``."""
        return self._theta0 + self.dtheta(d)

    def _correction(self, d):
        """``(-1)^{N-1} tau^{-1/2} sum_k C_k(p) tau^{-k}``.

        Only ``p = tau - N`` is needed, to about ``10^{-9}``; a plain double
        ``t`` is ample here, unlike everywhere else in this class.
        """
        d = np.asarray(d, dtype=float)
        tau = np.sqrt((self.t0 + d) / TWO_PI)
        p = tau - self.n_max
        inv_tau = 1.0 / tau
        corr = np.zeros_like(tau)
        power = np.ones_like(tau)
        for k in range(self.order + 1):
            corr += _interp_array(self._tables[k], p) * power
            power *= inv_tau
        sign = 1.0 if (self.n_max - 1) % 2 == 0 else -1.0
        return sign * np.sqrt(inv_tau) * corr

    def _assemble(self, d, f):
        """``Z = 2 Re(e^{i theta} F) + correction``."""
        th = self.theta_mod(d)
        return 2.0 * (np.cos(th) * f.real - np.sin(th) * f.imag) + self._correction(d)

    # -- the slow, accurate path -------------------------------------------
    def main_sum_direct(self, d, recentre: float = 0.5):
        """``F(t0 + d)`` by direct summation: ``O(N)`` per point.

        The reference path.  The fast path is checked against it, and the
        certified path in :mod:`riemann.rigorous` uses it exclusively.

        Requested offsets are grouped into runs of width ``recentre``.  Within a
        run the phase is ``[(t0 + s) log n mod 2 pi] + (d - s) log n``, whose
        second piece never exceeds ``0.5 log N = 8`` radians and so costs only
        ``9 x 10^{-16}`` per term in plain doubles.  ``d - s`` is itself exact:
        the two are within a factor of two of each other, so Sterbenz applies.
        Re-centring costs one reduction pass per run, amortised over every point
        in it.
        """
        d = np.atleast_1d(np.asarray(d, dtype=float))
        self._check_inside(d)
        out = np.empty(d.size, dtype=complex)

        order = np.argsort(d)
        i = 0
        while i < order.size:
            shift = float(d[order[i]])
            j = i
            while j < order.size and d[order[j]] - shift <= recentre:
                j += 1
            base = (dd.add(self._base, dd.mul_mod_2pi_dd(shift, self._log_n_dd))
                    if shift != 0.0 else self._base)
            base_sum = base[0] + base[1]
            for k in order[i:j]:
                angle = base_sum + (d[k] - shift) * self._log_n
                out[k] = complex(np.sum(np.cos(angle) * self._inv_sqrt_n),
                                 -np.sum(np.sin(angle) * self._inv_sqrt_n))
            i = j
        return out

    def Z_direct(self, d, recentre: float = 0.5):
        """``Z(t0 + d)`` by direct summation of the main sum."""
        d = np.atleast_1d(np.asarray(d, dtype=float))
        return self._assemble(d, self.main_sum_direct(d, recentre=recentre))

    # -- the fast path -----------------------------------------------------
    @property
    def offsets(self) -> np.ndarray:
        """The uniform sample offsets ``k delta`` -- exact, because ``delta`` is
        a power of two."""
        k = np.arange(-(self.n_grid // 2), self.n_grid - self.n_grid // 2)
        return k * self.delta

    def grid_values(self, force: bool = False) -> np.ndarray:
        """``F`` on the whole grid, by one nonuniform FFT."""
        if self._grid_values is None or force:
            x = dd.mul_mod_2pi_dd(self.delta, self._log_n_dd)
            self._grid_values = nufft_type1(
                x[0], self._c, self.n_grid, spread=self.spread, x_low=x[1])
        return self._grid_values

    def Z_grid(self) -> np.ndarray:
        """``Z`` on the grid."""
        return self._assemble(self.offsets, self.grid_values())

    # -- band-limited interpolation ----------------------------------------
    def main_sum(self, d):
        """``F(t0 + d)`` anywhere in the block, by band-limited interpolation.

        ``F`` has frequencies in ``[-log N, 0]``; after removing the band centre
        the remainder is band-limited to ``|omega| <= Omega = (log N)/2``, and
        the grid spacing sits at ``lambda = delta Omega/pi`` of the Nyquist
        rate.  The Gaussian-windowed cardinal series

        .. math::
           G(t) \\approx \\sum_{|j - j_0| < q} G(t_j)\\,
                        \\operatorname{sinc}\\frac{t-t_j}{\\delta}\\,
                        e^{-(t-t_j)^2/2\\sigma^2},
           \\qquad \\sigma = \\delta\\sqrt{\\frac{q}{(1-\\lambda)\\pi}},

        converges like ``e^{-(1-\\lambda)\\pi q/2}`` (Qian 2003), which at the
        defaults ``lambda = 0.25``, ``q = 32`` is ``4 x 10^{-17}``.
        """
        d = np.atleast_1d(np.asarray(d, dtype=float))
        self._check_inside(d)
        values = self.grid_values()
        offs = self.offsets
        q = self.interp_points

        omega = 0.5 * math.log(self.n_max)
        lam = self.delta * omega / math.pi
        if lam >= 1.0:  # pragma: no cover - excluded by the constructor
            raise ValueError("grid is below the Nyquist rate")
        sigma = self.delta * math.sqrt(q / ((1.0 - lam) * math.pi))

        # band-centre the samples: G(t) = F(t) e^{i (t - t0) omega}
        centred = values * np.exp(1j * offs * omega)

        j0 = np.floor((d - offs[0]) / self.delta).astype(np.int64)
        j0 = np.clip(j0, q - 1, self.n_grid - q - 1)
        idx = j0[:, None] + np.arange(-q + 1, q + 1)[None, :]
        u = (d[:, None] - offs[idx]) / self.delta
        w = np.sinc(u) * np.exp(-(u * self.delta) ** 2 / (2.0 * sigma * sigma))
        return np.sum(w * centred[idx], axis=1) * np.exp(-1j * d * omega)

    def Z(self, d):
        """``Z(t0 + d)`` anywhere in the block -- the fast path."""
        d = np.atleast_1d(np.asarray(d, dtype=float))
        return self._assemble(d, self.main_sum(d))

    # -- zeros -------------------------------------------------------------
    def scan(self, density: float = 16.0):
        """``Z`` on a fine grid of ``density`` points per mean gap.

        The transform grid sits at two samples per gap because that is all the
        Nyquist rate of ``F`` requires -- but a sign-change search at two
        samples per gap straddles close pairs and loses of the order of 8% of
        the zeros.  The interpolation of :meth:`main_sum` costs ``2q = 64``
        multiplications per point against the ``N = 10^7`` of a genuine
        evaluation, so the search grid can be refined essentially for free.

        The step is ``delta`` divided by a power of two, which keeps every scan
        offset exactly representable.
        """
        shrink = 2 ** max(0, math.ceil(math.log2(self.delta * density / self.gap)))
        step = self.delta / shrink
        n = int(round(self.half_width / step))
        offs = np.arange(-n, n + 1) * step
        return offs, self.Z(offs)

    def brackets(self, density: float = 16.0) -> np.ndarray:
        """Cells across which ``Z`` changes sign, as offset pairs.

        These are what :mod:`riemann.rigorous` certifies: a cell whose two
        endpoints have *provably* opposite signs contains a zero of ``Z``, hence
        a zero of ``zeta`` on the critical line, with no appeal to how it was
        found.
        """
        offs, vals = self.scan(density)
        idx = np.nonzero(np.signbit(vals[:-1]) != np.signbit(vals[1:]))[0]
        return np.stack([offs[idx], offs[idx + 1]], axis=1)

    def zeros(self, tol: float = 1e-11, max_iter: int = 60,
              density: float = 16.0) -> np.ndarray:
        """Offsets of every sign change of ``Z`` in the block, refined.

        Completeness is a separate question, answered in
        :mod:`riemann.rigorous`; a sign change found here is a genuine zero, but
        a grid can always straddle a close pair.
        """
        cells = self.brackets(density)
        if cells.size == 0:
            return np.empty(0)
        lo, hi = cells[:, 0].copy(), cells[:, 1].copy()
        flo, fhi = self.Z(lo), self.Z(hi)
        for _ in range(max_iter):
            denom = fhi - flo
            step = np.where(denom != 0.0, flo * (hi - lo) / denom, 0.5 * (hi - lo))
            mid = np.clip(lo - step, lo + 0.01 * (hi - lo), hi - 0.01 * (hi - lo))
            fmid = self.Z(mid)
            same = np.signbit(fmid) == np.signbit(flo)
            lo, flo, hi, fhi = (np.where(same, mid, lo),
                                np.where(same, fmid, flo * 0.5),
                                np.where(same, hi, mid),
                                np.where(same, fhi * 0.5, fmid))
            if np.all(hi - lo < tol):
                break
        return 0.5 * (lo + hi)

    # -- helpers -----------------------------------------------------------
    def _check_inside(self, d) -> None:
        limit = self.half_width + self.interp_points * self.delta
        if np.any(np.abs(d) > limit):
            raise ValueError("offset outside the block")

    def expected_count(self) -> float:
        """``(theta(t_hi) - theta(t_lo))/pi``: the smooth prediction for the tally."""
        h = self.half_width
        return float(self.dtheta_exact(h) - self.dtheta_exact(-h)) / math.pi
