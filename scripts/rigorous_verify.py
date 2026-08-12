"""Certified zeros: proofs rather than measurements.

Usage:  python scripts/rigorous_verify.py [T0] [HALF_WIDTH] [OUTFILE]

Three things happen here, in increasing order of what they claim.

1. **Self-checks.**  The interval arithmetic is checked against
   :mod:`mpmath`, and Gabcke's remainder bound -- the one analytic input this
   package does not derive -- is checked against ``mpmath`` at heights spanning
   thirteen orders of magnitude.  That is evidence, not proof, and is labelled
   as such.
2. **Certification.**  Every sign change found by the fast path is re-evaluated
   with full ``N``-term sums and rigorous error bounds.  A bracket survives only
   if the *enclosure* of ``Z`` at each end lies strictly on one side of zero.
3. **Completeness.**  Turing's method fixes ``N(T)`` at both ends of the inner
   range.  If the difference equals the number of certified brackets between
   them, every zero of ``zeta`` in that range -- on the line or off it -- has
   been accounted for, and each one is simple and on the critical line.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann import dd, rigorous as R  # noqa: E402
from riemann.interval import Interval  # noqa: E402
from riemann.odlyzko_schonhage import ZBlock  # noqa: E402


def check_interval_arithmetic() -> None:
    """The enclosures must actually enclose."""
    try:
        import mpmath as mp
    except ImportError:  # pragma: no cover
        print("  (mpmath not installed; skipping)")
        return
    mp.mp.dps = 50
    rng = np.random.default_rng(0)
    checks = 0
    worst = 0.0
    for _ in range(400):
        x = float(rng.uniform(-20.0, 20.0))
        for name, oracle in (("cos", mp.cos), ("sin", mp.sin), ("exp", mp.exp)):
            iv = getattr(Interval(x), name)()
            exact = oracle(mp.mpf(x))
            assert iv.lo <= exact <= iv.hi, (name, x, iv, exact)
            worst = max(worst, iv.width)
            checks += 1
        if x > 0:
            for name, oracle in (("log", mp.log), ("sqrt", mp.sqrt)):
                iv = getattr(Interval(x), name)()
                assert iv.lo <= oracle(mp.mpf(x)) <= iv.hi
                checks += 1
    print(f"  interval elementary functions: {checks} enclosures, all valid, "
          f"widest {worst:.2e}")

    # and the vectorised cosine that the certified sums actually use
    angles = rng.uniform(-25.0, 25.0, 200000)
    values, bound = R.cos_certified(angles)
    bad = 0
    for i in range(300):
        iv = Interval(float(angles[i])).cos()
        if not (values[i] - bound <= iv.hi and values[i] + bound >= iv.lo):
            bad += 1
    print(f"  cos_certified: proved bound {bound:.2e}; consistent with the "
          f"interval enclosure on 300 samples: {bad == 0}")
    print(f"    (observed agreement with the platform's libm cos: "
          f"{np.max(np.abs(values - np.cos(angles))):.2e} -- so libm is fine "
          f"here, but nothing rests on it)")


def check_gabcke() -> None:
    """Is Gabcke's constant really an upper bound?  Evidence, not proof."""
    try:
        import mpmath as mp
    except ImportError:  # pragma: no cover
        print("  (mpmath not installed; skipping)")
        return
    print("  Gabcke's bound |R_0| <= 0.127 t^(-3/4), checked against mpmath:")
    print("        t        max |R_0| t^(3/4)    ratio to 0.127")
    mp.mp.dps = 30
    rng = np.random.default_rng(1)
    for exponent in (3, 5, 7, 9, 11, 13):
        t0 = 10.0 ** exponent
        block = ZBlock(t0, 8.0 * dd.mean_gap(t0), order=0)
        offsets = rng.uniform(-4.0, 4.0, 12) * dd.mean_gap(t0)
        worst = 0.0
        for d in offsets:
            approx = float(block.Z_direct(np.array([float(d)]))[0])
            exact = float(mp.siegelz(mp.mpf(t0) + mp.mpf(float(d))))
            worst = max(worst, abs(approx - exact) * (t0 + float(d)) ** 0.75)
        print(f"    1e{exponent:<3d}    {worst:.6f}            {worst / 0.127:.4f}")
    print("    (a ratio below 1 everywhere is consistent with the theorem; it "
          "is not a proof of it)")


def main() -> None:
    t0 = float(sys.argv[1]) if len(sys.argv) > 1 else 1e15
    half = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
    out = sys.argv[3] if len(sys.argv) > 3 else f"results/certified_{t0:.0e}.json"

    print("self-checks")
    check_interval_arithmetic()
    print()
    if os.environ.get("GABCKE", "1") == "1":
        check_gabcke()
        print()

    print(f"certified verification at t = {t0:.10g} +- {half:g}")
    start = time.time()
    block = ZBlock(t0, half, verbose=True)
    print(f"  setup {time.time() - start:.1f}s")

    start = time.time()
    result = R.verify_block(block, verbose=True)
    elapsed = time.time() - start
    print(f"  {elapsed:.0f}s for {result['certified']} certified brackets "
          f"({elapsed / max(1, 2 * result['certified']):.2f}s per full "
          f"{block.n_max:,}-term enclosure)")

    if result.get("complete"):
        t1, t2 = result["inner_range"]
        first = result["N_t1"] + 1
        last = result["N_t2"]
        print()
        print(f"  zeros number {first:,} to {last:,} of zeta(1/2 + it) are")
        print(f"  proved to lie on the critical line, and to be simple.")
        print(f"  The first of them is at t = {t0:.10g} + "
              f"{result['inner_brackets'][0][0]:.9f}")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    payload = {k: v for k, v in result.items() if k != "inner_brackets"}
    payload["turing_lower"] = {k: str(v) for k, v in result["turing_lower"].items()}
    payload["turing_upper"] = {k: str(v) for k, v in result["turing_upper"].items()}
    payload["seconds"] = elapsed
    payload["brackets_offsets"] = result["inner_brackets"].tolist()
    with open(out, "w") as fh:
        json.dump(payload, fh)
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
