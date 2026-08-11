"""A functional equation is not enough: zeros off the critical line.

Usage:  python scripts/davenport_heilbronn_demo.py

The single most useful constraint on any attempted proof of RH is that it must
fail for the Davenport-Heilbronn function.  This script constructs that
function from scratch, verifies it really does satisfy a Riemann-type
functional equation, and then exhibits its zeros off the critical line --
including zeros with real part near 2, in a region where zeta has none at all.
"""

from __future__ import annotations

import cmath
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann.davenport_heilbronn import (  # noqa: E402
    CHI, XI, XI_EVEN, check_functional_equation, coefficients,
    count_zeros_in_rectangle, f, find_zeros_in_rectangle, gauss_sum,
    root_number, xi_for_sign)
from riemann.zeta import zeta  # noqa: E402

RULE = "=" * 78


def main():
    print(RULE)
    print("THE DAVENPORT-HEILBRONN FUNCTION")
    print(RULE)
    print("""
  Riemann's zeta function has two structural properties: an EULER PRODUCT
  (because of unique factorisation) and a FUNCTIONAL EQUATION relating s to
  1-s.  A natural hope is that RH follows from the functional equation plus
  soft analysis.  It does not, and this function is why.

  Build it from the character chi mod 5 with chi(2) = i:
""")
    print(f"    chi(1..4) = {[CHI[n] for n in range(1, 5)]}")
    print(f"    chi(-1) = chi(4) = {CHI[4]:.0f}   -> chi is ODD")
    tau = gauss_sum()
    eps = root_number()
    print(f"    Gauss sum tau(chi)   = {tau.real:+.10f} {tau.imag:+.10f}i")
    print(f"    |tau(chi)| = {abs(tau):.12f}   sqrt(5) = {math.sqrt(5):.12f}   "
          f"(equal <=> chi primitive)")
    print(f"    root number eps      = {eps.real:+.10f} {eps.imag:+.10f}i   "
          f"|eps| = {abs(eps):.12f}")
    print(f"    arg eps = phi        = {cmath.phase(eps):.12f}")

    print("""
  Set f(s) = A L(s,chi) + conj(A) L(s,conj chi) with A = (1 - i xi)/2, and
  complete it with G(s) = (5/pi)^((s+1)/2) Gamma((s+1)/2).  Requiring

      G(s) f(s) = eta G(1-s) f(1-s)

  forces eps = eta * conj(A)/A, which has TWO solutions -- one per sign eta.
  Both are derived below from the Gauss sum; neither is quoted.
""")
    print(f"  {'branch':>10} {'xi':>18} {'|a_2| = |xi|':>14}   {'max rel error in F.E.':>24}")
    for eta in (+1, -1):
        x = xi_for_sign(eta)
        chk = check_functional_equation(xi=x, eta=eta)
        print(f"  {'eta = %+d' % eta:>10} {x:>18.10f} {abs(x):>14.4f}   "
              f"{chk['max_rel_diff']:>24.2e}")
    print("""
  Both are genuine functional equations of Riemann type -- verified to ~1e-13.
  The difference between them is one number.  Expanding f as a Dirichlet series
  gives real coefficients of period 5:

      a = (1, xi, -xi, -1, 0)
""")
    print(f"    eta = +1:  a = {[round(v, 6) for v in coefficients(XI_EVEN)]}")
    print(f"    eta = -1:  a = {[round(v, 6) for v in coefficients(XI)]}")
    print("""
  For eta = -1 we have |a_2| = 3.52 > 1: the SECOND term of the series can
  outweigh the first.  That is precisely what lets f vanish far to the right,
  and it is precisely what an Euler product forbids.  zeta has no zeros at all
  in Re s > 1, because there its Euler product converges and no factor vanishes.
""")

    print(RULE)
    print("ZEROS WITH Re(s) > 1  --  where zeta has none")
    print(RULE)
    zs = find_zeros_in_rectangle(complex(1.02, 0.05), complex(3.0, 60.0),
                                 grid=44, xi=XI)
    print(f"\n  {len(zs)} zeros of f found with 1 < Re s < 3, 0 < Im s < 60:\n")
    print(f"  {'Re s':>14} {'Im s':>14} {'|f(s)|':>12} {'|zeta(s)| there':>18}")
    for z in zs:
        print(f"  {z.real:>14.9f} {z.imag:>14.9f} {abs(f(z, XI)):>12.1e} "
              f"{abs(zeta(z)):>18.6f}")
    print("""
  The last column is the point.  At each of these s, zeta is nowhere near zero
  -- it cannot be, since Re s > 1 puts it inside the Euler product's region of
  convergence.  f vanishes there anyway.
""")

    print(RULE)
    print("A CROSS-CHECK, AND A TRAP WORTH RECORDING")
    print(RULE)
    print("""
  Because the coefficients a_n are real, f(conj s) = conj(f(s)); combined with
  the functional equation this makes rho -> 1 - conj(rho) an involution on the
  zeros.  Applying it to each zero found above is a direct correctness test:
""")
    print(f"  {'zero rho':>30} {'reflection 1 - conj(rho)':>30} {'|f| there':>12}")
    for z in zs:
        r = 1 - z.conjugate()
        print(f"  {'%+.7f %+.7fi' % (z.real, z.imag):>30} "
              f"{'%+.7f %+.7fi' % (r.real, r.imag):>30} {abs(f(r, XI)):>12.1e}")
    print("""
  Every reflection is also a zero, so the quadruple structure holds: this
  function has zeros at Re s ~ 2 AND at Re s ~ -1, straddling the critical line
  at the maximum possible distance.

  The same involution also caught a real error in this analysis.  It forces the
  zero counts in strips symmetric about Re s = 1/2 to be EQUAL.  For the
  eta = +1 branch (whose zeros all lie ON the line), rectangles with edges
  placed exactly at Re s = 1/2 reported:
""")
    for lo, hi, lab in [
        (complex(0.5, 0.1), complex(1.0, 100.0), "(1/2, 1)"),
        (complex(0.0, 0.1), complex(0.5, 100.0), "(0, 1/2)"),
    ]:
        n = count_zeros_in_rectangle(lo, hi, per_side=500, xi=XI_EVEN)
        print(f"    zeros with Re s in {lab:>9}, 0 < Im s < 100 :  {n:9.4f}   <- WRONG")
    print("\n  and with the edges moved off the line by 0.02:\n")
    for lo, hi, lab in [
        (complex(0.52, 0.1), complex(1.0, 100.0), "(0.52, 1)"),
        (complex(0.0, 0.1), complex(0.48, 100.0), "(0, 0.48)"),
    ]:
        n = count_zeros_in_rectangle(lo, hi, per_side=500, xi=XI_EVEN)
        print(f"    zeros with Re s in {lab:>9}, 0 < Im s < 100 :  {n:9.4f}")
    print("""
  The first pair is unequal, so it must be wrong -- and it is: the winding
  number is defined only when no zero lies ON the contour, and Re s = 1/2 is
  where most of that branch's zeros sit.

  A SECOND ERROR, WORTH RECORDING.  Having fixed that, a Newton search over
  Im s < 60 found all 28 of the eta = +1 branch's zeros on the critical line,
  and I wrote that this branch "appears to satisfy an analogue of RH".  That
  was wrong, and searching a little higher shows it:
""")
    both = {}
    for label, x in (("eta = +1", XI_EVEN), ("eta = -1", XI)):
        zs2 = find_zeros_in_rectangle(complex(-0.6, 0.05), complex(1.6, 200.0),
                                      grid=80, xi=x)
        on = [z for z in zs2 if abs(z.real - 0.5) < 1e-6]
        off = [z for z in zs2 if abs(z.real - 0.5) >= 1e-6]
        both[label] = (on, off)
        print(f"    {label}:  {len(zs2):>3} zeros with -0.6 < Re s < 1.6, "
              f"0 < Im s < 200   ->  {len(on):>3} on the line, "
              f"{len(off):>2} OFF it")
    print("\n    lowest off-line zeros of the eta = +1 branch:")
    for z in sorted(both["eta = +1"][1], key=lambda z: z.imag)[:4]:
        print(f"        Re = {z.real:+.7f}   Im = {z.imag:.6f}   "
              f"|f| = {abs(f(z, XI_EVEN)):.1e}")
    print("""
  Its first off-line zero is at Im s = 85.7 -- just above where the search had
  stopped.  Note also that they arrive in reflected pairs at identical height
  (0.8085 and 0.1915), exactly as the involution requires.

  So BOTH branches have zeros off the critical line.  Neither has an Euler
  product, and neither obeys an analogue of RH.  The eta = -1 branch is the
  more dramatic only because |a_2| > 1 lets its zeros escape the critical strip
  entirely.

  The irony is not lost: concluding "all zeros are on the line" from a search
  that stopped at Im s = 60, when the first counterexample sits at 85.7, is
  precisely the failure mode that docs/03 is about. It is a great deal easier
  to describe that error than to avoid it.
""")

    print(RULE)
    print("WHAT THIS RULES OUT")
    print(RULE)
    print("""
  Any proof of the Riemann Hypothesis must use the Euler product in an
  essential way.  Symmetry, growth order, gamma factors, contour manipulation,
  and every other consequence of the functional equation alone are shared by a
  function whose zeros are demonstrably NOT on the critical line -- some of them
  not even in the critical strip.

  So the first question to ask of any claimed proof is:

      WHERE DOES THIS ARGUMENT FAIL FOR DAVENPORT-HEILBRONN?

  If it does not fail, the argument is wrong, and this can be checked before
  reading the details.  Combined with the other constraint from docs/02 -- that
  Rodgers and Tao proved Lambda >= 0, so RH holds with exactly zero margin and
  no averaging argument can see it -- the space of possible proofs is narrow
  and well mapped. That is the real reason the problem is hard: not that nobody
  has been clever enough, but that the obvious routes are provably blocked.
""")


if __name__ == "__main__":
    main()
