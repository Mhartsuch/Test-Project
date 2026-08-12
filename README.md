# The Riemann Hypothesis: computation and honest assessment

A from-scratch computational study of the Riemann zeta function, its zeros, and
what the evidence for RH is actually worth.

**This does not prove the Riemann Hypothesis, and does not claim to.** RH has
been open since 1859 and has resisted Hardy, Littlewood, Selberg, Weil, Connes,
Bombieri, Conrey, Sarnak and Tao. What this repository contains is real
mathematics that can be run and checked: correct code, verified against an
independent oracle, plus a map of why the known attacks fail and a quantitative
measurement of how weak the numerical evidence really is.

---

## What it does

**Computes 999,998 zeros of ζ(½+it) to height 600,269 in 8 minutes** (100,000 in
17 seconds), each one verified complete against an independent
argument-principle count — so the result is not "we found a lot of zeros on the
line" but "every zero of ζ in this strip is on the critical line, and simple."

**Reproduces the Montgomery–Odlyzko phenomenon.** Zero spacings fit the GUE
random-matrix distribution **17.3× better** than Poisson; pair correlation
matches `1 − (sin πr/πr)²` to a mean absolute deviation of 0.014. The zeros
repel each other like eigenvalues.

**Rebuilds the primes from the zeros.** Feeding 5000 zero ordinates into von
Mangoldt's explicit formula reproduces the prime-power staircase with RMS error
0.077 — and all twelve of the steepest rises land on prime powers.

**Measures how weak the evidence is.** A zero placed at `Re(ρ) = 0.6` — a
catastrophic violation of RH — would keep Li's criterion positive until
`n ≈ 21,000`; the same violation at height 74,920 hides until `n ≈ 1.7 × 10¹²`.
Details in [`docs/03`](docs/03-strength-of-evidence.md).

**Independently rediscovers Lehmer's pair** at `t = 7005.06`, and finds much
tighter ones — the closest at `t = 273193.663138`, where two zeros sit
`0.005704` apart (normalised gap **0.0097**, over four times tighter than
Lehmer's 0.0421) and `Z` rises to only `2.0 × 10⁻⁴` between them. Confirmed
against mpmath at 2,958× the numerical noise floor, so the double crossing is
real and not roundoff.

**Verifies the constraint that rules out soft proofs.** The Davenport–Heilbronn
function — a Riemann-type functional equation with **no Euler product** — is
constructed from scratch (its constant derived from the Gauss sum, not quoted),
its functional equation confirmed to `3 × 10⁻¹²`, and its zeros located **off**
the critical line, including six with `Re(s) > 1` where ζ provably has none.
This is the fact any claimed proof of RH must contend with, now checked rather
than cited.

**Reaches height 10¹⁰** by evaluating the Riemann–Siegel phase relative to a
window origin. At `t = 10¹⁰` plain float64 gives an error of `3.7 × 10⁻⁵` —
1.5% of a zero gap, useless for statistics. The windowed path gives
`1.4 × 10⁻¹³`, **2.6 × 10⁸ times better**, and independent of height.

**Reaches height 10¹⁵ with Odlyzko–Schönhage.** A single evaluation of `Z` there
costs 12.6 million cosines, and a search over a block of a thousand zeros needs
25,601 of them — 22 hours. Recognising the main sum as a *nonuniform Fourier
transform* over the frequencies `log n` collapses that to one transform:
**1041 zeros in 29 seconds**, agreeing with mpmath to `10⁻¹³` and with full
direct summation to `5.9 × 10⁻¹⁴`. `Z` turns out to be band-limited, with two
samples per zero already oversampling fourfold, so everything between grid
points comes from interpolation and never from another sum. Details in
[`docs/04`](docs/04-odlyzko-schonhage.md).

**Proves them, rather than reporting them.** Every sign change is re-evaluated
with full 12.6-million-term sums and an *enclosure*: an interval that provably
contains `Z(t)`, accepted only when it lies wholly on one side of zero. The
cosine is not libm's — C promises nothing about its accuracy, so it is computed
here with a bound derived by hand. The summation is an explicit binary tree, so
its depth is a fact rather than an implementation detail. Then Turing's method
fixes `N(T)` — the number of zeros of `ζ` in the *whole strip*, about
`5 × 10¹⁵`, without anyone counting that far — at both ends, and the counts
close. Every zero in the range is proved simple, on the critical line, and
carries a known index.

To be clear about the scope, since it is easy to overread: this is **a block at
10¹⁵, not everything below it**. There are about `5 × 10¹⁵` zeros under that
height and no one has enumerated them; what is verified here is one interval of
a thousand consecutive zeros, in the way Odlyzko's studies at 10²⁰ and 10²² were
blocks. Reaching higher does not make the evidence for RH much stronger —
[`docs/03`](docs/03-strength-of-evidence.md) puts a number on how little — it
moves where the unexamined region begins.

**Measures the Selberg central limit theorem.** `S(T)` — where all the
arithmetic content of the zero distribution lives — has mean 0, kurtosis
climbing 2.52 → 2.71 toward Gaussian, and variance slope `0.0439` against
Selberg's asymptotic `1/2π² = 0.0507`. The shape converges long before the
constant does.

---

## Quick start

```bash
pip install -r requirements.txt        # numpy (speed), mpmath + pytest (tests only)

python scripts/compute_zeros.py 10000     # compute and verify zeros
python scripts/gue_statistics.py          # random matrix comparison
python scripts/explicit_formula_demo.py   # primes out of zeros
python scripts/evidence_strength.py       # how much is any of this worth?
python scripts/davenport_heilbronn_demo.py# zeros OFF the critical line
python scripts/selberg_clt.py             # the log log wall, measured
python scripts/gue_vs_height.py           # GUE convergence vs height
python scripts/os_zeros.py 1e15 100       # a thousand zeros at height 10^15
python scripts/rigorous_verify.py 1e15 100# ... certified, and counted

python -m pytest tests/ -q                # 210 tests against mpmath
```

All output is plain text with ASCII plots — no plotting library needed.

---

## Design: the core has no dependencies

Everything mathematical is implemented from scratch in pure Python. `mpmath`
appears **only** in `tests/`, as an independent oracle. That distinction is the
point: the tests compare two separately written implementations rather than
checking an implementation against itself. `numpy` is used only in `fast.py`,
which duplicates already-tested pure-Python functions for speed, and is itself
tested for agreement with them.

| module | contents |
|---|---|
| `special.py` | exact Bernoulli numbers (rational arithmetic), complex `log Γ` |
| `zeta.py` | Euler–Maclaurin ζ(s) with reported truncation **and** roundoff bounds |
| `riemann_siegel.py` | θ(t), Hardy's Z(t), correction coefficients `C₀…C₃` |
| `counting.py` | `N(T)` by continuous argument tracking |
| `zeros.py` | sign-change search, verified against the strip count |
| `statistics.py` | unfolding, spacings, pair correlation, GUE reference |
| `explicit_formula.py` | ψ(x) rebuilt from zeros |
| `equivalences.py` | Mertens, Robin, Lagarias, Li coefficients |
| `fast.py` | numpy-vectorised duplicates of the above |
| `highprec.py` | windowed Riemann–Siegel; accuracy independent of height |
| `davenport_heilbronn.py` | functional equation without an Euler product |
| `dd.py` | double-double arithmetic: 32 digits from pairs of float64 |
| `odlyzko_schonhage.py` | the main sum as a nonuniform FFT; band-limited interpolation |
| `interval.py` | outward-rounded intervals; elementary functions with proofs |
| `rigorous.py` | certified enclosures of `Z`, and Turing's method |

---

## What the computation caught

Real work produces real mistakes. These are documented because the corrections
are more instructive than the code, and because a project arguing that
verification is weaker than it looks had better be candid about its own.

**A wrong Riemann–Siegel coefficient.** The `C₃` correction term involves
`Ψ⁽⁵⁾(p)` divided by a rational constant. Rather than trust recall, I extracted
the true coefficients from high-precision data — fixing the fractional part `p`,
sweeping `τ = N + p`, and least-squares fitting the remainder against powers of
`1/τ`. The denominator is **3840**, not 15360, and the wrong value made order 3
*less* accurate than order 2. See `scripts/verify_rs_coefficients.py`.

**A zero-search that manufactured zeros.** The first version hunted for missed
zeros in the grid cells where `|Z|` was smallest — which are exactly the cells
where roundoff dominates, since the accuracy of `Z` is limited by representing
`θ(t) ≈ 3.1 × 10⁵` in double precision. It reported 102,401 zeros below a height
that admits only 100,000. Replaced by bisecting on `N(t)` itself, which localises
every missing zero exactly instead of guessing.

**A "bound" the true error exceeded.** The reported roundoff bound on ζ used
`|total|` where the worst-case forward-error bound for recursive summation needs
`Σ|terms|`. On the critical line the terms are `k^{−1/2}`, so `Σ|terms| ~ 2√N`
while `|total|` stays `O(1)` — an order of magnitude of understatement, caught
by a test asserting the bound actually bounds.

**ζ overflowed for σ < ½ above t ≈ 450.** `χ(s) = 2ˢπ^{s−1} sin(πs/2) Γ(1−s)`
was evaluated factor by factor. For large `t`, `sin(πs/2)` grows like `e^{πt/2}`
and `Γ(1−s)` decays just as fast: the product is perfectly tame, the factors are
not. Now computed in log space.

**The fix for that then negated ζ throughout σ < ½.** Factoring
`sin z = −e^{−iz}(1 − e^{2iz})/2i` and writing the bracket as `(1 − …)` drops a
`log(−1) = iπ`. The symptom was a relative error of exactly 2.00 — which is a
pleasant kind of bug, since the number tells you what happened.

**An argument-principle count that lost whole revolutions.** The refinement test
compared *principal* phase differences, so a true turn of `2π + ε` looked like
`ε`, passed the threshold, and vanished. Adding a modulus-variation trigger
helped but was not enough: a single tall contour gives 250 where the answer is
269. Chunking into short strips reproduces 29, 99, 269 exactly.

**Contour through the zeros.** Counting Davenport–Heilbronn zeros with a
rectangle edge at `Re s = ½` — where its zeros are — gave 21 and 26 for two
strips the functional equation forces to be *equal*. A winding number is
undefined when a zero sits on the contour; the asymmetry is what exposed it.

**Spacing statistics biased by a coarse scan.** GUE histograms were built at a
grid density where the tally had not yet converged. The ~18 zeros lost at
`t = 10⁸` were all close pairs — precisely the left tail the GUE comparison
depends on — and each loss also merges two real gaps into one spurious large one.

**A grid that was not where it said it was.** The new transform disagreed with
direct summation by `3.5 × 10⁻¹⁰` — a thousand times worse than either method's
own accuracy. The tell was that the discrepancy did not move when *any*
parameter of the transform changed: not the spreading width, not the
oversampling, not the precision of the phases. It was not an error in the
transform at all. The transform computes the main sum at the exact real number
`t₀ + kδ`; the comparison evaluated it at `fl(t₀ + kδ)`, and those differ by up
to half an ulp. At `t = 10¹⁵` that is `0.0625`, and `|F′| ≈ 10⁵`. Fixed by
rounding the grid spacing down to a **power of two**, which makes `kδ` exact for
every `k` — and `δ log n` exact in double-double as a bonus.

**An ordinate that a double cannot hold.** Chasing that led to the more basic
fact: near `t = 10¹⁵` consecutive float64 values are `0.125` apart and the mean
gap between zeros is `0.1921`. A double cannot name a zero there to better than
two thirds of the way to its neighbour — `1e15 + 0.03 == 1e15` is `True`. The
whole interface had to be rewritten to take offsets from an exact `t₀`, which is
also why zero ordinates are reported as a pair rather than a number.

**A "bound" on θ that was not one — again.** The asymptotic series for `θ` is
printed everywhere with four correction terms, and every implementation
truncates there and then bounds the tail by the first omitted term. That bound
is false: at `t = 200` the true residual *exceeds* it, by six parts in 10⁵. Small
— and exactly the difference between a bound and a wish. The fix was to stop
quoting: `a_k = (2^{2k−1}−1)/2^{2k} · |B_{2k}|/(2k(2k−1))` reproduces all four
printed coefficients exactly, the package already has exact Bernoulli numbers, and
eight terms drop the residual to `7 × 10⁻⁴¹`. This is the *second* time in this
repository that a quantity called a bound turned out not to bound anything.

**An interpolation reading off the end of its grid.** The band-limited
reconstruction uses 32 samples either side, but the transform grid was built to
cover only the block — so points near the edges were interpolated from samples
that did not exist. It cost 6 zeros out of 76, and presented as a plausible
close-pair miss rather than as an index error, which is the dangerous kind.

**And a claim that had to be withdrawn.** The frequencies `δ log n` are kept as
double-doubles because the mode index multiplies their rounding error, and the
worst case over `|k| ≤ 1688` is `10⁻⁹`. That reasoning is sound and the
correction is cheap, so it stays — but the first draft of the documentation said
it was what made the computation possible. Measured, the roundings are
independent across `n` and mostly cancel: `1.16 × 10⁻¹³` with the correction
against `1.27 × 10⁻¹³` without. Worth 10%, not worth a paragraph claiming
otherwise. A worst-case bound is not a measurement, and a repository arguing
that verification is weaker than it looks should not dress one up as the other.

**And one in the analysis rather than the code**, twice over: the Robin-criterion
computation used too few primes, exhausted its list, and produced a ratio that
*fell* where Gronwall's theorem says it must rise; and a Newton search stopping
at `Im s = 60` led me to write that one Davenport–Heilbronn branch "appears to
satisfy an analogue of RH". Its first off-line zero is at `Im s = 85.7`. That is
exactly the failure mode [`docs/03`](docs/03-strength-of-evidence.md) is about,
committed while writing the document warning against it.

---

## The documents

- **[`docs/01-landscape.md`](docs/01-landscape.md)** — the statement, why it
  matters, what is actually proved, and the equivalent formulations.
- **[`docs/02-failure-modes.md`](docs/02-failure-modes.md)** — the attacks and
  precisely where each breaks: the function-field analogue and the missing
  surface over `Spec(Z)`; Hilbert–Pólya and Connes' circularity; zero-free
  regions that shrink to zero width; the mollifier ceiling; Selberg's parity
  obstruction; and the constraints any proof must satisfy.
- **[`docs/03-strength-of-evidence.md`](docs/03-strength-of-evidence.md)** — how
  much the numerical evidence is worth, computed rather than asserted.
- **[`docs/04-odlyzko-schonhage.md`](docs/04-odlyzko-schonhage.md)** — how to get
  to 10¹⁵, why the ordinate stops being a floating-point number on the way, and
  what separates "we computed these zeros" from "we proved these are all of
  them".

---

## The honest summary

The strongest reason to believe RH is that **the analogue over function fields
is a theorem** (Weil 1948, Deligne 1974). Its proof runs through the surface
`C × C` and gets its essential positivity from the Hodge index theorem. Over the
integers the corresponding surface does not exist — `Spec(Z) × Spec(Z)` has no
base to be a product over — and constructing a substitute is what the serious
modern programmes (Connes–Consani, Deninger, `F₁` geometry, Arakelov theory) are
all trying to do. That is where the problem lives.

The second strongest reason is the GUE statistics reproduced here: something is
probably a spectrum, and spectra of self-adjoint operators are real. Nobody can
produce the operator.

Counting zeros is not a good reason, and `docs/03` says how weak it is in
numbers rather than adjectives. Meanwhile Rodgers and Tao proved `Λ ≥ 0`, so
RH is now equivalent to `Λ = 0` **exactly** — it is true with no margin at all,
which is why every soft or averaging argument is doomed before it starts.

None of that is a reason not to compute. It is a reason to be precise about what
the computation shows.
