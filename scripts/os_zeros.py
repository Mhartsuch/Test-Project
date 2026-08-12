"""Zeros at great height by Odlyzko-Schonhage.

Usage:  python scripts/os_zeros.py [T0] [HALF_WIDTH] [OUTFILE]

Defaults to a block of about a thousand zeros centred at ``t = 10^15``.

The point of the exercise is the *cost curve*, not the block itself.  Direct
Riemann-Siegel costs ``N = sqrt(t/2 pi)`` per evaluation no matter how many
evaluations are wanted; the transform costs ``N`` once and then almost nothing
per point, so this script prints both and lets the ratio speak.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann import dd  # noqa: E402
from riemann.odlyzko_schonhage import ZBlock  # noqa: E402


def scaling_table() -> None:
    """Cost per evaluation, direct against transformed, as the height grows."""
    print("scaling: one block of ~200 zeros at each height")
    print()
    print("      t          N terms   setup  transform   direct/pt    fast/pt   speedup")
    print("  " + "-" * 76)
    for exponent in (8, 10, 12, 14, 15):
        t0 = 10.0 ** exponent
        half = 100 * dd.mean_gap(t0)
        start = time.time()
        block = ZBlock(t0, half)
        setup = time.time() - start

        start = time.time()
        block.grid_values()
        transform = time.time() - start

        probe = np.array([-0.3, 0.1, 0.7])
        start = time.time()
        block.Z_direct(probe)
        direct = (time.time() - start) / probe.size

        start = time.time()
        block.Z(np.linspace(-half, half, 4096))
        fast = (time.time() - start) / 4096

        # A search at 16 points per gap needs this many evaluations per zero.
        per_zero_direct = 16 * direct
        per_zero_fast = (setup + transform) / 200 + 16 * fast
        print(f"  1e{exponent:<3d}  {block.n_max:>13,}  {setup:6.1f}s  {transform:8.1f}s"
              f"  {direct:9.4f}s  {fast:9.6f}s  {per_zero_direct / per_zero_fast:8.0f}x")
    print()


def main() -> None:
    t0 = float(sys.argv[1]) if len(sys.argv) > 1 else 1e15
    half = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
    out = sys.argv[3] if len(sys.argv) > 3 else f"results/os_zeros_{t0:.0e}.json"

    if os.environ.get("SCALING", "1") == "1":
        scaling_table()

    print(f"block: t = {t0:.10g} +- {half:g}")
    print(f"  mean gap here is {dd.mean_gap(t0):.6f}, "
          f"and consecutive doubles are {math.ulp(t0):g} apart"
          f" -- {math.ulp(t0) / dd.mean_gap(t0):.2f} of a gap")

    start = time.time()
    block = ZBlock(t0, half, verbose=True)
    setup = time.time() - start
    print(f"  setup {setup:.1f}s: {block.n_max:,} double-double logarithms, "
          f"reduced modulo 2 pi")

    start = time.time()
    block.grid_values()
    transform = time.time() - start
    print(f"  transform {transform:.1f}s: {block.n_grid:,} grid values from "
          f"{block.n_max:,} sources")

    start = time.time()
    zeros = block.zeros(density=16.0)
    search = time.time() - start
    print(f"  search {search:.1f}s: {len(zeros)} sign changes "
          f"(smooth prediction {block.expected_count():.2f})")

    # spot-check a handful against a full N-term sum
    sample = zeros[:: max(1, len(zeros) // 8)][:8]
    start = time.time()
    residual = block.Z_direct(sample)
    print(f"  spot check ({time.time() - start:.1f}s): max |Z| at a reported zero "
          f"is {np.max(np.abs(residual)):.2e}, over {len(sample)} full "
          f"{block.n_max:,}-term evaluations")

    gaps = np.diff(zeros) / dd.mean_gap(t0)
    print()
    print(f"  normalised gaps: mean {gaps.mean():.6f}, min {gaps.min():.6f}, "
          f"max {gaps.max():.6f}")
    tightest = int(np.argmin(gaps))
    print(f"  closest pair at t = {t0:.10g} + {zeros[tightest]:.9f}, "
          f"separation {gaps.min():.6f} of a mean gap")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as fh:
        json.dump({
            "t0": t0,
            "half_width": block.half_width,
            "n_terms": block.n_max,
            "grid_points": block.n_grid,
            "delta": block.delta,
            "seconds": {"setup": setup, "transform": transform, "search": search},
            "count": len(zeros),
            "expected_smooth": block.expected_count(),
            "note": "ordinates are offsets from t0; t0 + offset loses digits in "
                    "float64 above ~1e13",
            "offsets": zeros.tolist(),
        }, fh)
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
