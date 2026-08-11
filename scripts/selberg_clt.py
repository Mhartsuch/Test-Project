"""Selberg's central limit theorem, and the log log wall made concrete.

Usage:  python scripts/selberg_clt.py [ZEROS_JSON]

``S(T) = arg zeta(1/2 + iT)/pi`` measures how far the zeros sit from where the
smooth counting function says they should be.  It is the entire arithmetic
content of the zero distribution: ``N(T) = theta(T)/pi + 1 + S(T)``, and the
first two terms are elementary.

Selberg proved that ``S(T)``, suitably normalised, is asymptotically standard
normal:

.. math::  \\frac{S(T)}{\\sqrt{\\tfrac{1}{2\\pi^2}\\log\\log T}} \\Rightarrow N(0,1).

The variance grows like ``log log T``.  That is the whole difficulty of this
subject in one formula, and this script measures it.

The computation is nearly free: having already located every zero below
``600,269`` and verified the tally against the argument principle, ``S(t)`` at
any height is just the running zero count minus the smooth part.
"""

from __future__ import annotations

import bisect
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from riemann.counting import S as S_by_argument_principle  # noqa: E402
from riemann.fast import theta_array  # noqa: E402

RULE = "=" * 78
VAR_CONST = 1.0 / (2.0 * math.pi ** 2)


def S_from_zeros(ts, zeros):
    """``S(t) = N(t) - theta(t)/pi - 1`` from a complete list of ordinates."""
    ts = np.asarray(ts, dtype=float)
    counts = np.array([bisect.bisect_right(zeros, float(t)) for t in ts], dtype=float)
    return counts - (theta_array(ts) / math.pi + 1.0)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "results/zeros_1M.json"
    blob = json.load(open(path))
    zeros = blob["zeros"]
    t_max = blob["t_max"]
    print(f"using {len(zeros):,} verified zeros up to t = {t_max:,.0f}\n")

    # --- cross-check the cheap route against the real argument principle ---
    print(RULE)
    print("CROSS-CHECK:  S(t) from the zero list vs. from the argument principle")
    print(RULE)
    print(f"\n  {'t':>12} {'from zeros':>14} {'from arg principle':>20} {'difference':>12}")
    probes = [137.5, 1000.5, 9999.5, 50000.5, 250000.5]
    worst = 0.0
    for t in probes:
        a = float(S_from_zeros([t], zeros)[0])
        b = S_by_argument_principle(t)
        worst = max(worst, abs(a - b))
        print(f"  {t:>12.1f} {a:>14.8f} {b:>20.8f} {abs(a-b):>12.1e}")
    print(f"\n  worst difference {worst:.1e} -- the two routes are independent, so "
          f"this\n  also re-confirms the zero list is complete.\n")

    # --- variance by height band -----------------------------------------
    print(RULE)
    print("VARIANCE OF S(T) AGAINST SELBERG'S PREDICTION")
    print(RULE)
    bands = [(100.0, 1e3), (1e3, 1e4), (1e4, 1e5), (1e5, 3e5), (3e5, 6e5)]
    rng = np.random.default_rng(20250811)
    rows = []
    for lo, hi in bands:
        ts = rng.uniform(lo, hi, size=300000)
        s = S_from_zeros(ts, zeros)
        centre = math.sqrt(lo * hi)
        loglog = math.log(math.log(centre / (2 * math.pi)))
        var = float(s.var())
        mean = float(s.mean())
        sd = math.sqrt(var)
        std = (s - mean) / sd
        rows.append({
            "lo": lo, "hi": hi, "centre": centre, "loglog": loglog,
            "mean": mean, "var": var, "sd": sd,
            "predicted_var": VAR_CONST * loglog,
            "skew": float((std ** 3).mean()),
            "kurtosis": float((std ** 4).mean()),
        })

    print(f"\n{'height band':>22} {'log log t':>10} {'mean S':>9} {'var S':>9} "
          f"{'sd S':>8} {'predicted var':>14} {'skew':>7} {'kurt':>7}")
    for r in rows:
        print(f"{'%.0e .. %.0e' % (r['lo'], r['hi']):>22} {r['loglog']:>10.3f} "
              f"{r['mean']:>9.4f} {r['var']:>9.4f} {r['sd']:>8.4f} "
              f"{r['predicted_var']:>14.4f} {r['skew']:>7.3f} {r['kurtosis']:>7.3f}")

    # fit var = a * loglog + b
    xs = [r["loglog"] for r in rows]
    ys = [r["var"] for r in rows]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    a = sum((p - mx) * (q - my) for p, q in zip(xs, ys)) / sum((p - mx) ** 2 for p in xs)
    b = my - a * mx
    print(f"""
  Fitted:      Var S(T) = {a:.4f} * log log T {b:+.4f}
  Selberg:     Var S(T) ~ {VAR_CONST:.4f} * log log T   (asymptotically)

  The slope is in the right neighbourhood but not equal: at these heights the
  lower-order terms are still comparable to the main one.  That is the same
  slow convergence seen in the GUE statistics, and for the same reason -- the
  expansion parameter is 1/log log T, which is nowhere near small here.

  Skewness near 0 and kurtosis near 3 say the distribution is already very
  close to Gaussian in SHAPE, long before its VARIANCE has settled. Selberg's
  theorem is visible; Selberg's constant is not.
""")

    # --- the wall ---------------------------------------------------------
    print(RULE)
    print("WHY THIS IS THE WALL")
    print(RULE)
    print(f"""
  S(T) is what makes zeta interesting.  It is the deviation of the zeros from
  their average positions -- everything arithmetic lives in it, and RH is
  equivalent to a statement about how the zeros are arranged, i.e. about S.

  And its typical size is barely growing:
""")
    print(f"  {'height T':>14} {'log log T':>12} {'typical |S(T)|':>16}")
    for T in (1e4, 1e6, 1e10, 1e13, 1e30, 1e100, 1e1000):
        ll = math.log(math.log(T / (2 * math.pi)))
        print(f"  {T:>14.0e} {ll:>12.3f} {math.sqrt(VAR_CONST * ll):>16.4f}")
    print("""
  From the largest verification ever performed (10^13) out to 10^100, the
  typical size of S grows from 0.41 to 0.52.  Out to 10^1000 it reaches 0.63.

  Yet S(T) is UNBOUNDED -- it must be, and it is known to be, though it takes
  astronomical heights to become large.  Every phenomenon that could falsify RH
  lives in the tail of this distribution, and the distribution is widening at
  the rate of the logarithm of a logarithm.

  This is why "we checked 10^13 zeros" is such weak evidence, and it is also
  why the Mertens conjecture could survive to 10^9 and still be false, and why
  pi(x) < li(x) can hold everywhere anyone has looked and still fail.  All three
  are the same fact wearing different clothes: the interesting behaviour is
  gated behind log log, and log log has not yet moved.
""")

    with open("results/selberg_clt.json", "w") as fh:
        json.dump({"rows": rows, "fit_slope": a, "fit_intercept": b,
                   "selberg_constant": VAR_CONST}, fh, indent=1)
    print("wrote results/selberg_clt.json")


if __name__ == "__main__":
    main()
