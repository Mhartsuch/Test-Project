# What is actually rigorous here, and what is not

This file is the honest accounting. Claims of "rigour" in numerical work are
worth exactly as much as the weakest link, so every input is classified into
one of four tiers and named explicitly.

- **(A) Proved here.** A consequence of IEEE-754 semantics, or an
  alternating/geometric series tail, derived and applied in this repository.
- **(B) Proved elsewhere, applied here.** A published theorem used as stated,
  with the citation given.
- **(C) Calibrated.** A constant measured empirically against an independent
  oracle and then inflated by a safety factor. Not a proof.
- **(D) Assumed.** Anything relied on without justification.

There is nothing in tier (D). Tiers (B) and (C) are listed exhaustively below.

---

## The shape of the argument

For an interval `[a, b]` the program outputs `VERIFIED` when two independently
computed integers agree:

1. **A lower bound from sign changes.** For each pair of adjacent grid points
   the computed `Z` values are compared against a rigorous a-priori bound `E`
   on `|Z_computed - Z_exact|`. If `|Z| > E` at both ends and the signs
   differ, then `Z` genuinely changes sign, so it has a zero of odd order
   between them. `Z(t)` is real for real `t`, so that zero is a zero of
   `zeta` with real part exactly `1/2`. Counting these gives `N(b) - N(a) >= F`.

2. **An upper bound from Turing's method.** Using only that certified sign
   changes are genuine zeros — never that we found all of them — the mean of
   `S(t) = N(t) - 1 - theta(t)/pi` over an interval is bounded, which pins
   `N(a)` and `N(b)` to single integers.

If `F` equals `N(b) - N(a)`, then no zero was missed. Every zero in `[a, b]`
has been located in a certified bracket on the critical line, and since the
count is exact, each is simple.

A `NOT VERIFIED` result is never silently swallowed: the program distinguishes
"Turing zone too short" from "zeros are missing from the certified list", and
reports the number of unresolved grid pairs (adjacent points where `|Z|` did
not exceed `E`, so no sign could be assigned).

---

## Tier A — proved in this repository

**Interval arithmetic.** `iv` operations compute round-to-nearest and then
widen by one ulp in each direction. IEEE-754 guarantees `+ - * /` and `sqrt`
are correctly rounded, so the exact result is within half an ulp of the
computed one and therefore inside the widened interval. This is valid whatever
the ambient rounding mode. Requires `-ffp-contract=off`, which
`iv_self_test()` checks at runtime by verifying that `a*b - a*b` written twice
is exactly zero.

**pi and log 2.** Derived from scratch at start-up, not trusted as literals:
`pi` from Machin's `16 atan(1/5) - 4 atan(1/239)` with the alternating-series
truncation bounded by the first omitted term, and `log 2` from `2 atanh(1/3)`
with the positive-term tail bounded geometrically. The hard-coded
double-double constants are then *checked* against those derivations and agree
to about `5e-32`. Run `./zeta selftest` to see it.

**exp, log, sin, cos.** Argument reduction in double-double, then a Taylor or
`atanh` series whose truncation is bounded analytically (alternating series ->
first omitted term; positive series -> geometric tail). Measured tightness:
2 ulps for `exp`, 4 ulps for `log`, ~1.5e-15 for `sin`/`cos` including
reduction of arguments as large as `1e15`.

**Riemann-Siegel truncation of the main sum.** The Taylor expansion inside the
Odlyzko-Schoenhage evaluator is bounded by `rho^D / D!` times `sum |a_k|`,
where `rho = pi (M-1) / Q` is exact given the grid geometry. At the settings
used for `t = 1e15` this term is `~3e-17`, six orders below the total bound.

**Compensated summation.** The main sum has `N ~ 1.3e7` terms; naive summation
would accumulate `N * eps * sum|x| ~ 2e-5` of error, which would swamp
everything. Kahan-Babuska-Neumaier brings this to `~2 eps sum|x| ~ 3e-12`,
independent of `N`.

**Double-word rounding.** Bounded per operation by `DD_OP_EPS = 2^-102`. See
tier B for where that constant comes from.

---

## Tier B — theorems used as stated

1. **Double-word arithmetic error bounds.** Joldes, Muller, Popescu, *Tight
   and rigorous error bounds for basic building blocks of double-word
   arithmetic*, ACM TOMS 44(2), 2018. They prove relative error `3*2^-106` for
   the accurate double-word sum and `4*2^-106` for the fma-based product. This
   code uses `2^-102` per operation — a factor of 16 of headroom over the
   worst of those.

2. **FFT round-off.** The componentwise bound
   `|X_k^computed - X_k^exact| <= C log2(n) eps sum_j |x_j|`
   for radix-2 Cooley-Tukey with a correctly-rounded twiddle table
   (Higham, *Accuracy and Stability of Numerical Algorithms*, 2nd ed., ch. 24).
   `FFT_ERR_C = 12` is used, above the constant proved there. The twiddle
   table itself is built in double-double and rounded once, so it is accurate
   to well under an ulp — a naive recurrence would drift far more than the
   transform's own error.

3. **Euler-Maclaurin remainder.** For
   `zeta(s) = sum_{n<M} n^-s + M^-s/2 + M^{1-s}/(s-1) + sum_k B_2k/(2k)! (s)_{2k-1} M^{-s-2k+1} + R_K`,
   the bound
   `|R_K| <= |(s)_{2K+1} / (sigma + 2K + 1)| |B_{2K+2}/(2K+2)!| M^{-sigma-2K-1}`
   (Edwards, *Riemann's Zeta Function*, sec. 6.4).

4. **Turing's S-integral bound.** `|Int_{t1}^{t2} S(t) dt| <= 2.30 + 0.128 log(t2/2pi)`
   for `t2 >= 2pi`. Lehman, *On the distribution of zeros of the Riemann
   zeta-function*, Proc. LMS (3) 20 (1970), Theorem 2.

   **This is the single most load-bearing external input in the program.**
   Everything else could be wrong by orders of magnitude without changing a
   conclusion; this constant enters the verification linearly. It is isolated
   in one function, `turing_S_bound()` in `src/turing.c`, so it can be
   replaced. Sharper bounds exist in the literature (Trudgian's are of the
   same shape with smaller constants); the more conservative Lehman form is
   used deliberately. **Anyone depending on a published result from this code
   should check this constant against the paper.**

---

## Tier C — calibrated, not proved

**The Riemann-Siegel asymptotic remainder.** After including correction terms
`C_0 .. C_J`, the omitted tail is bounded as
`|Z - RS_J| <= K_J * tau^{-(2J+3)/2)}`, `tau = sqrt(t/2pi)`.

`K_J` was measured over 105 heights in `[100, 2e5]` against mpmath
(`scripts/calibrate_rs.py`): the observed suprema were `0.031`, `0.0053` and
`0.00036` for `J = 0, 1, 2`. The code uses `3.0`, `0.6`, `0.05` — a safety
factor of about 100.

This is the one place where a measured quantity is used as if it were a bound,
and it deserves scrutiny. Two things limit the damage:

- Gabcke's thesis proves a bound of this shape (`0.053 t^{-11/4}` for the
  expansion through `C_4`), so the *form* is not in doubt, only the constant.
- The bound is irrelevant at the heights that matter. At `t = 1e6` it is
  `~3e-7`; at `t = 1e15` with `J = 1` it is `~1e-18`, which is nine orders of
  magnitude below the floating-point noise floor of the same computation
  (`~1e-8`). A calibration error of even `10^6` would change nothing at
  `t = 1e15`. Below `t ~ 1e6` the code does not rely on it: the independent,
  fully rigorous Euler-Maclaurin path is used instead.

---

## The error budget at t = 1e15

From an actual run (`./zeta verify 1e15 2000`), the total bound is `1.19e-8`,
composed of:

| source | size | tier |
|---|---|---|
| coefficient phase error (`t0 * log`-table error, dd rounding) | `1.1e-8` | A/B |
| FFT round-off | `4.7e-10` | B |
| theta error, coherent across all terms | `~1e-10` | A/B |
| Taylor truncation in the O-S expansion | `3.1e-17` | A |
| Riemann-Siegel asymptotic tail (`J=1`) | `~1e-18` | C |

The budget is dominated by tier-A/B terms; the one calibrated input is ten
orders of magnitude below the total. The bound is conservative: measured
disagreement between the O-S grid and direct Riemann-Siegel evaluation is
`~4e-13`, about 30 000 times smaller than the bound claims.

---

## Known limitations

- **Not a replacement for a formally verified computation.** There is no
  machine-checked proof. Tiers B and C are trust boundaries.
- **The `K_J` calibration was measured only up to `t = 2e5`.** The scaling in
  `tau` is theoretically motivated but extrapolated.
- **Verification is per-window.** `zeta verify T COUNT` proves a statement
  about one interval. Covering `[0, 1e15]` continuously is the same code in a
  loop, but it is roughly `5e15` zeros and is not something this program has
  been run to do.
- **The zeros are located, not certified to high precision, by default.**
  Brackets are one grid cell wide (`~0.012` at `t = 1e15`). `--refine` narrows
  them by bisection with the sign re-certified at each step, but each step
  costs a full `O(N)` evaluation.
