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

python -m pytest tests/ -q                # 92 tests against mpmath
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

---

## Three things the computation caught

Real work produces real mistakes; these are documented because the corrections
are more instructive than the code.

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

There was a fourth in the analysis rather than the code: the Robin-criterion
computation initially used too few primes, exhausted its list, and produced a
ratio that *fell* where Gronwall's theorem says it must rise. Documented in
[`docs/03`](docs/03-strength-of-evidence.md) §4.

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
