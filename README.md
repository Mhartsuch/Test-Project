# Zeros of the Riemann zeta function at height 10^15

An implementation of the Odlyzko-Schoenhage multi-evaluation algorithm for the
Riemann-Siegel main sum, with rigorous verification of the resulting zero
counts via interval arithmetic and Turing's method.

Self-contained C11: no FFTW, no MPFR, no GMP. The double-double arithmetic,
the interval library, and the FFT are all here.

## Result

```
$ ./zeta verify 1e15 2000

main sum length N = 12615662
  O-S window: t0=999999999999922.125000  N=12615662  m=44968  delta=0.0120163
              Q=524288  P=695  blocks=16  rho=0.2694  Taylor D=15
              coef 1.61s  fft 21.37s  assemble 1.50s  total 24.76s
              error bound 1.190e-08

certified sign changes : 2813
unresolved grid pairs  : 0
O-S error bound        : 1.190e-08

Turing verification
  zone length        : 77.829 each side
  |Int S| bound      : 6.4857
  slack at a, b      : 0.1627, 0.1639  (must be < 1)
  N(a)               : 5045354828589534
  N(b)               : 5045354828591534
  zeros expected     : 2000
  zeros certified    : 2000
  RESULT             : VERIFIED -- all zeros in the range are simple and on the critical line
```

2000 consecutive zeros near `t = 1e15`, starting from zero number
5,045,354,828,589,535, each located in a certified bracket on the critical
line, with the count independently confirmed by Turing's method. Total runtime
43 s on 4 cores (25 s of it in the O-S evaluator, 18 s building the log table).

The 44 968 grid points would have taken about **11.7 hours** by direct
Riemann-Siegel evaluation at 0.94 s each. The O-S evaluator did them in 24.8 s
— roughly a **1700x** speed-up, and that ratio grows with the window size.

## Build and test

```sh
make            # builds ./zeta and the test binaries
make check      # runs the full suite (~2 min)
./zeta selftest # arithmetic + constant verification only
```

Requires gcc or clang and libm. `-ffp-contract=off` is mandatory and is set in
the Makefile — the interval arithmetic depends on each written floating-point
operation being individually correctly rounded, and `iv_self_test()` checks
this at runtime.

`mpmath` is used only to regenerate `tests/oracle.h` and to run
`scripts/calibrate_rs.py`; the library and tests do not need it.

## Usage

```
zeta selftest                     arithmetic and constant checks
zeta eval   T [J]                 Z(T) by direct Riemann-Siegel
zeta window T COUNT [opts]        O-S grid, report timings
zeta zeros  T COUNT [opts]        locate and certify zeros near T
zeta verify T COUNT [opts]        as `zeros', plus Turing verification

  --delta D    grid spacing (default: mean zero gap / 16)
  --over  K    FFT oversampling Q/M (default 8)
  --J     j    Riemann-Siegel correction terms, 0 or 1 (default 1)
  --zone  L    Turing zone length on each side (default: 12 * S-bound)
  --refine W   bisect brackets to width W, re-certifying the sign each step
  --list       print each certified zero
```

## How it works

`docs/ALGORITHM.md` describes the O-S evaluator: dyadic blocks, binning,
Taylor expansion about bin centres, and one FFT per (block, Taylor order). The
design collapses to a single parameter because the largest Taylor argument
turns out to be `rho = pi (M-1) / Q`, independent of the number of bins.

`docs/RIGOR.md` is the honest accounting of what is proved here, what is cited
from the literature, and the one constant that is calibrated rather than
proved. Read it before quoting any number from this program.

## Layout

```
src/dd.h          double-double arithmetic (~31 digits)
src/interval.[ch] rigorous interval arithmetic; self-verified pi, log 2;
                  rigorous exp/log/sin/cos with analytic error bounds
src/fft.[ch]      self-contained radix-2 complex FFT
src/rs.[ch]       Riemann-Siegel theta, Psi, Z; Euler-Maclaurin oracle
src/os.[ch]       the Odlyzko-Schoenhage multi-evaluation
src/zeros.[ch]    Gram points, certified sign changes, bisection
src/turing.[ch]   Turing's method
src/main.c        CLI
tests/            six self-checking binaries; oracle.h is mpmath-generated
scripts/          calibration helper
```

## Two things that were not obvious

**The grid has to be double-double.** At `t = 1e15` one ulp of a double is
`0.125` while consecutive zeros are `0.192` apart — a double cannot name a
zero. Computing grid points as `t0 + j*delta` in double precision produces an
error proportional to `t` (`1.1e-7` at `t = 1e9`) that is completely
insensitive to FFT size and Taylor depth. Carrying the grid in double-double
drops it to `4.5e-13`.

**Turing's method needs the same treatment, for a different reason.** `N(t)`
is about `5e15` at `t = 1e15`, past `2^52`, so one ulp of a double there *is*
1.0 — the integer window the method is designed to resolve fits entirely
inside one rounding step. The bounds must be computed as offsets from a
reference integer.

Both show up as suspiciously round numbers (`slack = 0.0000` and exactly
`-1.0000`) rather than as anything that looks like a numerical error.

## Scope

`zeta verify T COUNT` proves a statement about one interval. It is not a
verification of the Riemann hypothesis up to `1e15` — that would be the same
code in a loop over roughly `5e15` zeros. What is demonstrated here is that
the machinery reaches `1e15` correctly and at a cost that makes such a sweep a
question of compute time rather than of method.

## References

- Odlyzko & Schoenhage, *Fast algorithms for multiple evaluations of the
  Riemann zeta function*, Trans. AMS 309 (1988), 797-809.
- Edwards, *Riemann's Zeta Function*, Academic Press 1974.
- Lehman, *On the distribution of zeros of the Riemann zeta-function*,
  Proc. LMS (3) 20 (1970).
- Joldes, Muller & Popescu, *Tight and rigorous error bounds for basic
  building blocks of double-word arithmetic*, ACM TOMS 44(2), 2018.
