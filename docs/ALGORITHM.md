# The Odlyzko-Schoenhage multi-evaluation, as implemented here

## The problem

The Riemann-Siegel formula evaluates

    Z(t) = 2 sum_{k=1}^{N} k^{-1/2} cos(theta(t) - t log k) + R(t),
    N = floor(sqrt(t / 2pi))

in `O(sqrt(t))` operations. At `t = 1e15` that is `N = 12,615,662` terms —
about one second per evaluation here. Finding the zeros in a window needs
thousands of evaluations, so the naive cost is `O(M N)` for `M` sample points:
tens of thousands of seconds for a few thousand zeros.

Odlyzko and Schoenhage (1988) observed that the main sum, restricted to a
window in `t`, is a band-limited object that can be evaluated at *many*
equally spaced points for barely more than the cost of one. This file
describes the form of that idea implemented in `src/os.c`.

## Step 1 — dyadic blocks

Split `k in [1, N]` into blocks `[K, 2K)`. Inside a block, write
`log k = log K + u_k` with `u_k in [0, log 2)`:

    F(t) = sum_b e^{-i t log K_b} * sum_{k in block b} k^{-1/2} e^{-i t u_k}

The block phase `e^{-i t log K_b}` is `O(1)` per block per point — negligible.
The inner sums are where the work is, and `u_k` is now confined to an interval
of length `log 2` regardless of how large `k` is.

## Step 2 — absorb the window origin

With `t = t0 + j*delta`,

    e^{-i t u_k} = e^{-i t0 u_k} * e^{-i j delta u_k}

Define `a_k = k^{-1/2} e^{-i t0 u_k}`. Computing these is the **only** `O(N)`
pass, done once per window. Everything after this is independent of `N`.

## Step 3 — bin and Taylor-expand

Partition `[0, log 2)` into `P` bins of width `h = log2/P`, centres
`v_m = (m + 1/2) h`. For `k` in bin `m`, write `u_k = v_m + w_k` with
`|w_k| <= h/2`, and rescale `what_k = 2 w_k / h in [-1, 1]`. Then

    e^{-i j delta u_k} = e^{-i j delta v_m} * sum_{d} (-i beta_j)^d what_k^d / d!

with `beta_j = j delta h / 2`. The `k`-dependence collapses into moments

    S[b][d][m] = sum_{k in bin m} a_k what_k^d

which are computed in the same `O(N)` pass, at `D` multiply-accumulates per
term.

## Step 4 — the bin sum is a DFT

Choose `delta = 2 pi P / (Q log 2)` for an FFT length `Q`. Then
`delta * h = 2 pi / Q` exactly, so

    e^{-i j delta v_m} = e^{-i beta_j} * e^{-2 pi i j m / Q}

and summing over `m` for all `j` at once is a length-`Q` DFT. One FFT per
(block, Taylor order): `B * D` transforms in total.

## The key simplification

Substituting `delta` and `h` into `beta_j`:

    beta_j = j delta h / 2 = pi j / Q

so the largest Taylor argument over the window is

    rho = pi (M - 1) / Q

**independent of `P`.** The number of bins drops out entirely: only the
oversampling ratio `Q/M` controls how deep the Taylor expansion must go. That
makes the design a one-parameter trade-off, and it makes the truncation error
rigorously boundable a priori:

    |truncation| <= (rho^D / D!) * sum_k |a_k|

With `Q = 8M` we get `rho ~ 0.39` and `D = 15` suffices for `1e-18`.

## Cost

| stage | cost | at `t=1e15`, `M=45000` |
|---|---|---|
| coefficients `a_k` (the only `O(N)` pass) | `O(N D)` | 1.6 s |
| transforms | `O(B D Q log Q)` | 21.4 s |
| assembly | `O(M (B D + k_small))` | 1.5 s |
| **total** | | **24.8 s** |
| direct, for comparison | `O(M N)` | ~11.7 hours |

## The thing that actually bites: the grid must be double-double

This is worth stating loudly because it is invisible until it isn't.

At `t = 1e15`, one ulp of an IEEE double is `0.125`. The mean spacing between
consecutive zeros is `2 pi / log(t/2pi) = 0.192`. **Consecutive zeros are less
than two ulps apart.** A `double` cannot name a grid point, let alone a zero.

Computing the grid as `t0 + j*delta` in double precision quantises it to a
lattice coarser than the spacing itself. The Taylor/FFT machinery works off
the exact real `t0 + j*delta`, while the block phases (multiplied by
`log K ~ 16`) and `theta` would be evaluated at the rounded value. The two
disagree, and the resulting error is proportional to `t`:

| height | error with a double grid | error with a dd grid |
|---|---|---|
| `1e7` | 1.6e-9 | 4.3e-13 |
| `1e8` | 1.2e-8 | 6.7e-14 |
| `1e9` | 1.1e-7 | 4.5e-13 |

The signature that identified this: the error was **exactly** at round-off
(`4.4e-16`) at `j = 0`, where `t_j = t0` exactly, and jumped to `1e-8` for
every `j > 0` — while being completely insensitive to FFT length and Taylor
depth. That rules out the approximation machinery and points at the grid.

The same issue appears again in Turing's method, in a different disguise:
`N(t) ~ 5e15` at `t = 1e15` exceeds `2^52`, so one ulp of a double *is 1.0*
there, and the entire integer window Turing's method resolves fits inside a
single rounding step. The bounds have to be formed as offsets from a reference
integer, with the cancelling parts done in double-double.

## References

- A. M. Odlyzko and A. Schoenhage, *Fast algorithms for multiple evaluations
  of the Riemann zeta function*, Trans. AMS 309 (1988), 797-809.
- A. M. Odlyzko, *The 1e20-th zero of the Riemann zeta function and 175
  million of its neighbors* (1992).
- X. Gourdon, *The 1e13 first zeros of the Riemann zeta function, and zeros
  computation at very large height* (2004).
- H. M. Edwards, *Riemann's Zeta Function*, Academic Press 1974.
