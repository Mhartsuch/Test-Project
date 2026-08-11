"""Zeros at great height: Riemann-Siegel with the phase computed exactly.

The problem
-----------
Riemann-Siegel needs only ``O(sqrt(t))`` terms, so evaluating ``Z`` at ``t = 10^10``
costs a mere 39,894 cosines.  The obstruction to going high is not arithmetic
volume -- it is *precision*.  Every term is ``cos(theta(t) - t log n)``, and at
``t = 10^10`` the angle ``theta(t)`` is about ``1.0 x 10^11``.  A double holds
16 significant digits, so representing that angle already costs ``10^-5`` of
absolute error; propagated through the sum it puts the error in ``Z`` at roughly
``4 x 10^-3``.  The mean gap between zeros there is ``0.2965``.  The noise is
1.5% of a zero spacing, and spacing statistics computed from it are worthless.

The fix
-------
Do not evaluate the phase absolutely -- evaluate it *relative to the window*.
For a window of half-width ``h`` about ``t0``, write ``t = t0 + delta``:

.. math::
   \\theta(t) - t\\log n
     = \\underbrace{\\bigl[\\theta(t_0) - t_0\\log n\\bigr]}_{\\text{reduced mod } 2\\pi\\text{ once, in high precision}}
       + \\underbrace{\\bigl[\\Delta\\theta(\\delta) - \\delta\\log n\\bigr]}_{\\text{small; double precision is ample}}

The first bracket is a per-``n`` constant, computed once with :mod:`mpmath` and
reduced modulo ``2 pi``, so its size is bounded by ``2 pi`` regardless of how
large ``t0`` is.  The second bracket never exceeds about ``h log N``, which for
a window of a few thousand is only ``10^4`` -- comfortably inside double
precision.

The increment ``Delta theta`` must itself avoid cancellation, so it is taken
from the Taylor expansion of ``theta`` about ``t0`` rather than by subtracting
two enormous numbers:

.. math::
   \\Delta\\theta(\\delta) = \\tfrac{\\delta}{2}\\log\\frac{t_0}{2\\pi}
        + \\frac{\\delta^2}{4t_0} - \\frac{\\delta^3}{12t_0^2}
        + \\frac{\\delta^4}{24 t_0^3} - \\cdots

using ``theta'(t) = (1/2) log(t/2 pi) + O(t^-2)``.

The result is a phase accurate to about ``10^-11`` at any height, which is
roughly ``10^8`` times better than the naive evaluation at ``t = 10^10`` and
costs one high-precision pass over ``n`` per window.
"""

from __future__ import annotations

import math

import numpy as np

from .riemann_siegel import RS_MAX_ORDER, _coefficient_table
from .fast import _interp_array

__all__ = ["ZWindow", "window_for_zero_count"]

TWO_PI = 2.0 * math.pi


def window_for_zero_count(t0: float, n_zeros: int) -> float:
    """Half-width about ``t0`` containing roughly ``n_zeros`` zeros."""
    gap = TWO_PI / math.log(t0 / TWO_PI)
    return 0.5 * n_zeros * gap


class ZWindow:
    """``Z(t)`` on a bounded window about ``t0``, with the phase de-biased.

    Parameters
    ----------
    t0:
        Centre of the window.
    half_width:
        Maximum ``|t - t0|`` that will be requested.  Keep it modest: the
        second bracket above grows like ``half_width * log N``, and the
        ``n_max`` of the main sum is fixed from ``t0``, so a window that is too
        wide is both less accurate and (at the edges) formally wrong.
    dps:
        Working precision for the one-time phase reduction.
    """

    def __init__(self, t0: float, half_width: float, order: int = RS_MAX_ORDER,
                 dps: int | None = None):
        import mpmath as mp

        self.t0 = float(t0)
        self.half_width = float(half_width)
        self.order = int(order)

        tau0 = math.sqrt(self.t0 / TWO_PI)
        self.n_max = int(tau0)
        if self.n_max < 1:
            raise ValueError("t0 too small for the Riemann-Siegel formula")

        # Enough guard digits to reduce t0 * log n modulo 2 pi and still have
        # ~12 digits left over.
        need = int(math.log10(max(self.t0, 10.0))) + 25
        with mp.workdps(dps or need):
            t0m = mp.mpf(repr(self.t0))
            two_pi = 2 * mp.pi
            theta0 = mp.siegeltheta(t0m)
            self.theta0_mod = float(mp.fmod(theta0, two_pi))
            phase = np.empty(self.n_max, dtype=float)
            for n in range(1, self.n_max + 1):
                phase[n - 1] = float(mp.fmod(t0m * mp.log(n), two_pi))
        self._phase0 = phase                      # (t0 log n) mod 2 pi
        self._log_n = np.log(np.arange(1.0, self.n_max + 1.0))
        self._inv_sqrt_n = 1.0 / np.sqrt(np.arange(1.0, self.n_max + 1.0))
        self._tables = [np.asarray(_coefficient_table(k)) for k in range(self.order + 1)]
        self._half_log = 0.5 * math.log(self.t0 / TWO_PI)

    # -- theta increment ----------------------------------------------------
    def dtheta(self, delta):
        """``theta(t0 + delta) - theta(t0)``, by Taylor expansion about ``t0``.

        Computed as a series rather than a difference of two numbers of size
        ``10^11``, which would lose every digit that matters.
        """
        d = np.asarray(delta, dtype=float)
        t0 = self.t0
        return d * (self._half_log
                    + d / (4.0 * t0)
                    - d * d / (12.0 * t0 * t0)
                    + d ** 3 / (24.0 * t0 ** 3))

    def theta(self, ts):
        """``theta(t)`` reduced modulo ``2 pi`` (only the phase is meaningful)."""
        return self.theta0_mod + self.dtheta(np.asarray(ts, dtype=float) - self.t0)

    # -- Z ------------------------------------------------------------------
    def Z(self, ts, block: int = 256) -> np.ndarray:
        """``Z(t)`` for ``t`` within the window."""
        ts = np.atleast_1d(np.asarray(ts, dtype=float))
        if np.any(np.abs(ts - self.t0) > self.half_width * 1.000001):
            raise ValueError("t outside the window this object was built for")

        out = np.empty(ts.size, dtype=float)
        for start in range(0, ts.size, block):
            chunk = ts[start:start + block]
            delta = chunk - self.t0
            th = self.theta0_mod + self.dtheta(delta)

            # angle = [theta0 - t0 log n]  +  [dtheta - delta log n]
            angle = (th[:, None] - self._phase0[None, :]
                     - delta[:, None] * self._log_n[None, :])
            total = 2.0 * np.sum(np.cos(angle) * self._inv_sqrt_n[None, :], axis=1)

            tau = np.sqrt(chunk / TWO_PI)
            p = tau - self.n_max
            inv_tau = 1.0 / tau
            corr = np.zeros_like(chunk)
            power = np.ones_like(chunk)
            for k in range(self.order + 1):
                corr += _interp_array(self._tables[k], p) * power
                power *= inv_tau
            sign = 1.0 if (self.n_max - 1) % 2 == 0 else -1.0
            out[start:start + block] = total + sign * np.sqrt(inv_tau) * corr
        return out

    # -- zeros --------------------------------------------------------------
    def find_zeros(self, density: float = 8.0, tol: float = 1e-9,
                   max_refine: int = 60) -> np.ndarray:
        """All sign changes of ``Z`` in the window, refined by bisection."""
        gap = TWO_PI / math.log(self.t0 / TWO_PI)
        step = gap / density
        lo_t = self.t0 - self.half_width
        n_pts = int(math.ceil(2.0 * self.half_width / step)) + 1
        grid = lo_t + step * np.arange(n_pts)
        grid = grid[grid <= self.t0 + self.half_width]
        vals = self.Z(grid)

        idx = np.nonzero(np.signbit(vals[:-1]) != np.signbit(vals[1:]))[0]
        if idx.size == 0:
            return np.empty(0)
        lo, hi = grid[idx].copy(), grid[idx + 1].copy()
        flo, fhi = vals[idx].copy(), vals[idx + 1].copy()

        # Illinois (modified regula falsi) rather than bisection.  Refinement
        # dominates the cost at large t -- each evaluation is a sum over 39,894
        # terms at t = 10^10 -- and bisection needs ~20 iterations to cross a
        # grid cell where Illinois needs ~7, while keeping the bracket and so
        # the guaranteed convergence.
        for _ in range(max_refine):
            denom = fhi - flo
            step = np.where(denom != 0.0, flo * (hi - lo) / denom, 0.5 * (hi - lo))
            mid = lo - step
            # keep the trial point strictly inside the bracket
            mid = np.clip(mid, lo + 0.01 * (hi - lo), hi - 0.01 * (hi - lo))
            fmid = self.Z(mid)
            same = np.signbit(fmid) == np.signbit(flo)
            new_lo = np.where(same, mid, lo)
            new_flo = np.where(same, fmid, flo * 0.5)
            new_hi = np.where(same, hi, mid)
            new_fhi = np.where(same, fhi * 0.5, fmid)
            lo, flo, hi, fhi = new_lo, new_flo, new_hi, new_fhi
            if np.all(hi - lo < tol):
                break
        return 0.5 * (lo + hi)

    def expected_count(self) -> float:
        """``(theta(t1) - theta(t0))/pi``: the smooth prediction for the tally.

        Since ``N(t) = theta(t)/pi + 1 + S(t)``, the number of zeros in the
        window differs from this by ``S(t_hi) - S(t_lo)``, which is small.
        """
        h = self.half_width
        return (self.dtheta(h) - self.dtheta(-h)) / math.pi

    def check_complete(self, density: float = 8.0, verbose: bool = False,
                       max_doublings: int = 4) -> dict:
        """Empirical completeness check for a window.

        The argument-principle count used at low height is unaffordable here --
        it needs ``zeta`` itself, at ``O(t)`` cost.  Two weaker but real checks
        are available using only ``Z``:

        1. **Smooth-count agreement.** The tally must differ from
           ``Delta theta / pi`` by ``S(t_hi) - S(t_lo)``, and ``S`` is small.
           A shortfall of 2 or more is a missed pair, not a fluctuation.
        2. **Density stability.** Re-scan at double resolution.  Grid searches
           fail by *missing* close pairs, never by inventing them, so if the
           tally does not increase when the grid is refined, no pair was
           straddled.

        Neither is a proof of completeness, and this returns a dict saying so
        rather than a boolean pretending otherwise.
        """
        counts = []
        d = density
        prev = self.find_zeros(density=d)
        counts.append((d, int(prev.size)))
        for _ in range(max_doublings):
            d *= 2.0
            nxt = self.find_zeros(density=d)
            counts.append((d, int(nxt.size)))
            if nxt.size == prev.size:
                break
            prev = nxt
        final = counts[-1][1]
        expected = self.expected_count()
        return {
            "t0": self.t0,
            "count": final,
            "counts_by_density": counts,
            "converged_density": counts[-1][0],
            "stable_under_refinement": len(counts) >= 2 and counts[-1][1] == counts[-2][1],
            "expected_smooth": expected,
            "implied_S_difference": final - expected,
            "plausible": abs(final - expected) < 3.0
            and len(counts) >= 2 and counts[-1][1] == counts[-2][1],
        }

    def unfold(self, zeros) -> np.ndarray:
        """Unit-mean-spacing coordinates ``theta(t)/pi`` within the window.

        Only *differences* matter for spacing statistics, so the unreduced part
        of ``theta(t0)`` cancels and the reduced phase is sufficient.
        """
        z = np.asarray(zeros, dtype=float)
        return (self.dtheta(z - self.t0)) / math.pi
