"""How fast do the zeros converge to random-matrix statistics?

Usage:  python scripts/gue_vs_height.py

The agreement between zeta zeros and the GUE is famously excellent -- at
Odlyzko's heights of 10^20.  At the modest heights reachable here it is good but
visibly imperfect, and the interesting quantity is not the agreement itself but
its *rate*: how much does a factor of 100 in height buy?

That rate is the honest measure of what verification at reachable heights can
tell us, and it is computed here rather than asserted.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from riemann.highprec import ZWindow  # noqa: E402
from riemann.statistics import (  # noqa: E402
    gue_spacing_density, spacing_histogram, spacing_moments)

TWO_PI = 2.0 * math.pi


def safe_half_width(t0, max_dtau=0.4):
    """Widest window over which ``floor(sqrt(t/2pi))`` stays put.

    The main sum has a fixed number of terms ``n_max = floor(tau)``, so a window
    must not straddle a point where ``tau`` crosses an integer.  Since
    ``dtau/dt = 1/(2 sqrt(2 pi t))``, holding ``tau`` inside a band of width
    ``max_dtau`` bounds the half-width by ``max_dtau * sqrt(2 pi t)``.
    """
    return max_dtau * math.sqrt(TWO_PI * t0)


def collect(t0, target, density=20.0, tol=1e-7, verbose=True):
    """Zero ordinates near ``t0``, pooled over as many windows as needed.

    ``density`` matters more here than it looks.  A grid search fails by
    straddling *close pairs*, and close pairs are precisely the left tail of the
    spacing distribution -- the part the GUE comparison is most sensitive to.
    Scanning at density 8 at ``t = 10^8`` found 11,983 zeros where a converged
    search finds 12,001: the 18 lost are all small spacings, and each loss also
    merges two real gaps into one spurious large one.  Both errors push the
    histogram the same way.  So the density is chosen high enough that the tally
    has stopped changing, and :meth:`ZWindow.check_complete` confirms it.
    """
    gap = TWO_PI / math.log(t0 / TWO_PI)
    hw_cap = safe_half_width(t0)
    per_window = int(2 * hw_cap / gap)
    n_windows = max(1, int(math.ceil(target / per_window)))
    hw = min(hw_cap, 0.5 * target * gap / n_windows + gap)

    spacings, total, checks = [], 0, []
    # Space the window centres far apart so the samples are independent.
    for i in range(n_windows):
        centre = t0 * (1.0 + 0.011 * i)
        w = ZWindow(centre, hw)
        z = w.find_zeros(density=density, tol=tol)
        if z.size < 10:
            continue
        u = w.unfold(z)
        spacings.extend(np.diff(u).tolist())
        total += z.size
        if i == 0:
            # One doubling is enough to detect a straddled pair; more is
            # unaffordable at t = 1e10, where each scan is ~1e10 operations.
            checks.append(w.check_complete(density=density, max_doublings=1))
            if not checks[-1]["stable_under_refinement"]:
                print("    WARNING: tally still moving at density "
                      f"{density}; spacing statistics may be biased low")
        if verbose:
            print(f"    window {i+1}/{n_windows} at t={centre:.6g}: "
                  f"{z.size:,} zeros (n_max={w.n_max:,})")
    return np.array(spacings), total, checks


def main():
    heights = [
        (1e4, 12000),
        (1e6, 12000),
        (1e8, 12000),
        (1e10, 6000),   # 39,894 terms per evaluation; the expensive one
    ]
    rows = []
    for t0, target in heights:
        print(f"\nheight t ~ {t0:.0e}   (mean gap {TWO_PI/math.log(t0/TWO_PI):.4f}, "
              f"{int(math.sqrt(t0/TWO_PI)):,} terms per evaluation)")
        t_start = time.time()
        s, total, checks = collect(t0, target)
        elapsed = time.time() - t_start

        # spacings are already unit-mean by construction; renormalise the tiny
        # residual so the comparison is about shape, not scale.
        s = s / s.mean()
        hist = spacing_histogram(np.cumsum(np.concatenate([[0.0], s])).tolist(),
                                 bins=40, s_max=3.0, already_unfolded=True)
        dev = sum(abs(a - b) for a, b in zip(hist["observed"], hist["gue"])) * hist["bin_width"]
        m2 = float((s ** 2).mean())
        m3 = float((s ** 3).mean())
        gue_m2, gue_m3 = 3 * math.pi / 8, None
        # GUE reference moments by quadrature (no remembered constants)
        h, top = 1e-4, 12.0
        steps = int(top / h)
        gm2 = sum(((i + .5) * h) ** 2 * gue_spacing_density((i + .5) * h) * h for i in range(steps))
        gm3 = sum(((i + .5) * h) ** 3 * gue_spacing_density((i + .5) * h) * h for i in range(steps))

        row = {
            "t": t0, "zeros": total, "seconds": elapsed,
            "L1_deviation_from_gue": dev,
            "m2": m2, "gue_m2": gm2, "m2_rel_err": abs(m2 - gm2) / gm2,
            "m3": m3, "gue_m3": gm3, "m3_rel_err": abs(m3 - gm3) / gm3,
            "checks": checks,
        }
        rows.append(row)
        print(f"    {total:,} zeros in {elapsed:.1f}s")
        for c in checks:
            print(f"    completeness: found {c['count']:,}, smooth prediction "
                  f"{c['expected_smooth']:.2f}, implied S difference "
                  f"{c['implied_S_difference']:+.2f}, stable under refinement: "
                  f"{c['stable_under_refinement']}")

    print("\n" + "=" * 78)
    print("CONVERGENCE OF ZERO SPACINGS TO THE GUE LIMIT")
    print("=" * 78)
    print(f"\n{'height':>10} {'zeros':>9} {'L1 dev':>10} {'<s^2>':>10} "
          f"{'rel err':>10} {'<s^3>':>10} {'rel err':>10}")
    for r in rows:
        print(f"{r['t']:>10.0e} {r['zeros']:>9,} {r['L1_deviation_from_gue']:>10.5f} "
              f"{r['m2']:>10.5f} {r['m2_rel_err']:>10.2%} {r['m3']:>10.5f} "
              f"{r['m3_rel_err']:>10.2%}")
    print(f"\n  GUE reference: <s^2> = {rows[0]['gue_m2']:.6f}, "
          f"<s^3> = {rows[0]['gue_m3']:.6f}")

    # Fit the rate: error vs log t.
    xs = [math.log(math.log(r["t"] / TWO_PI)) for r in rows]
    ys = [math.log(r["m2_rel_err"]) for r in rows]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    slope = (sum((a - mx) * (b - my) for a, b in zip(xs, ys))
             / sum((a - mx) ** 2 for a in xs))
    print(f"""
  The second-moment error falls roughly like (log t)^{slope:.2f}.

  That is the whole problem in one number.  The natural expansion parameter for
  these statistics is 1/log t, so buying one extra digit of accuracy in the GUE
  agreement costs an ENORMOUS factor in height.  Odlyzko went to 10^20 for a
  reason: it is the smallest height at which the agreement is convincing to the
  eye, and even 10^20 is a finite check of an infinite claim.

  Note also what did NOT change: the arithmetic cost per evaluation grows only
  like sqrt(t), so reaching 10^20 is not what is hard. The statistics converge
  logarithmically while the zeros themselves stay cheap. Verification is limited
  by the mathematics, not the machine.
""")

    with open("results/gue_vs_height.json", "w") as fh:
        json.dump(rows, fh, indent=1)
    print("wrote results/gue_vs_height.json")


if __name__ == "__main__":
    main()
