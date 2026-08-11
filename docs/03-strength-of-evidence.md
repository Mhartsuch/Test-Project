# How much is the evidence for RH actually worth?

*This is the one document here containing work I did rather than summarised.
The question — "if RH were false, how far would we have had to look before this
test noticed?" — is not new, but the specific numbers below were computed in
this repository and can be reproduced with `python scripts/evidence_strength.py`.*

The short answer: **the numerical evidence for RH is far weaker than it looks,
and the strong evidence is not numerical at all.**

---

## 1. Li's criterion is exponentially blind

Li's criterion says RH ⟺ `λ_n ≥ 0` for every `n ≥ 1`, where
`λ_n = Σ_ρ [1 − (1 − 1/ρ)^n]`. It is positive for every `n` anyone has
computed. That sounds like evidence. Here is why it is barely any.

Start from an exact observation. On the critical line,

$$|1 - 1/\rho| = \frac{|\rho - 1|}{|\rho|} = \frac{|-\tfrac12 + i\gamma|}{|\tfrac12 + i\gamma|} = 1 \quad \text{exactly.}$$

So under RH every term of Li's sum stays on the unit circle and `λ_n` grows only
polynomially — empirically and asymptotically like `(n/2)(log n + γ − 1 − log 2π)`,
which this repository verifies directly against `λ_n` computed from 100,000
zeros.

A zero off the line breaks the symmetry. Zeros come in quadruples
`{ρ, ρ̄, 1−ρ, 1−ρ̄}`, and whichever member has `Re < ½` gives `|1 − 1/ρ| > 1`.
*That* term grows geometrically, and eventually drags `λ_n` negative. The
criterion works. The question is when.

I put a single zero off the line (preserving the total zero count, so the
comparison is honest) and computed `λ_n` directly from all 100,000 zeros out to
`n = 30,000`, alongside an analytic estimate of the crossing point:

| violation | \|1 − 1/ρ\| | λ_n first negative (exact) | (estimated) |
|---|---|---|---|
| `Re = 0.75`, `γ = 14.1` | 1.0012501383 | **7,551** | 7,557 |
| `Re = 0.60`, `γ = 14.1` | 1.0004999989 | **20,968** | 21,244 |
| `Re = 0.55`, `γ = 14.1` | 1.0002499776 | > 30,000 | 45,955 |
| `Re = 0.51`, `γ = 14.1` | 1.0000499911 | > 30,000 | 268,899 |
| `Re = 0.60`, `γ = 1000` | 1.0000001000 | > 30,000 | 205,824,871 |
| `Re = 0.60`, `γ = 74920` | 1.0000000000 | > 30,000 | 1,685,051,944,864 |

The exact and estimated columns agree wherever both are computable (7,551 vs
7,557; 20,968 vs 21,244), which is what licenses reading the rows that direct
computation cannot reach.

Read the second row. A zero at `Re(ρ) = 0.6` is not a near miss — it is a
catastrophic failure of RH, a zero a tenth of the way to the edge of the critical
strip. Li's criterion would not notice until `n ≈ 21,000`.

Read the last row. The *same* violation, moved up to height 74,920 — still
utterly trivial by the standards of where zeros live — hides until
`n ≈ 1.7 × 10¹²`.

The reason is structural: the growth rate is
`|1 − 1/ρ| ≈ 1 + d/(γ² + ¼)` for a violation of size `d` at height `γ`, so
sensitivity decays like `1/γ²`. **The criterion is least sensitive exactly where
the unchecked zeros are.** Verifying `λ_n > 0` for all `n` up to a few thousand
excludes essentially nothing.

## 2. What checking zeros excludes

This project verified all 999,998 zeros to height 600,269, each one confirmed
against an independent argument-principle count. Gourdon checked 10¹³ zeros;
Platt's verification to height 3.06 × 10¹⁰ is rigorous. All on the line.

What does that rule out? A counterexample *below that height*. Nothing else.

That would be a reasonable inference if zeta's behaviour were uniform in `t`.
It is not. The quantities that govern zeta in the critical strip involve
`log log t`, and at the computational frontier `log log t` has barely started:

| height `t` | `log t` | `log log t` |
|---|---|---|
| 10⁴ | 9.2 | 2.22 |
| 10¹⁰ | 23.0 | 3.14 |
| 10¹³ | 29.9 | 3.40 |
| 10³⁰ | 69.1 | 4.24 |
| 10¹⁰⁰ | 230.3 | 5.44 |
| 10¹⁰⁰⁰ | 2302.6 | 7.74 |

Going from the frontier of computation (10¹³) to 10¹⁰⁰ moves `log log t` from
3.4 to 5.4. Any phenomenon that switches on when `log log t` is large simply has
not begun. And this is not a hypothetical worry — it is exactly what happened in
the next two sections.

### 2a. Measuring the wall: Selberg's theorem

This can be made precise rather than rhetorical. Write
`N(T) = θ(T)/π + 1 + S(T)`; the first two terms are elementary, so **all** the
arithmetic content of the zero distribution sits in `S(T)`. Selberg proved that
`S(T)` is asymptotically Gaussian with variance `(1/2π²) log log T`.

Because every zero below 600,269 has been located and verified, `S(t)` is
available almost for free as `N(t) − θ(t)/π − 1`. Over 300,000 sample points per
band (`scripts/selberg_clt.py`), cross-checked against the argument principle to
`6.7 × 10⁻¹⁰`:

| height band | log log t | mean S | var S | sd S | skew | kurtosis |
|---|---|---|---|---|---|---|
| 10² – 10³ | 1.366 | 0.0002 | 0.1474 | 0.384 | −0.004 | 2.517 |
| 10³ – 10⁴ | 1.828 | −0.0001 | 0.1683 | 0.410 | −0.001 | 2.617 |
| 10⁴ – 10⁵ | 2.143 | 0.0008 | 0.1822 | 0.427 | −0.003 | 2.674 |
| 10⁵ – 3×10⁵ | 2.325 | 0.0013 | 0.1895 | 0.435 | 0.001 | 2.688 |
| 3×10⁵ – 6×10⁵ | 2.409 | −0.0008 | 0.1933 | 0.440 | 0.003 | 2.705 |

Fitted: `Var S(T) = 0.0439 log log T + 0.0877`, against Selberg's asymptotic
slope `1/2π² = 0.0507`. Skewness is already zero and kurtosis is climbing toward
the Gaussian value 3 — **the shape has converged long before the variance has**.
Selberg's theorem is visible; Selberg's constant is not.

Now extrapolate the standard deviation:

| height T | log log T | typical \|S(T)\| |
|---|---|---|
| 10⁴ | 2.22 | 0.335 |
| 10¹⁰ | 3.14 | 0.399 |
| 10¹³ | 3.40 | 0.415 |
| 10¹⁰⁰ | 5.44 | 0.525 |
| 10¹⁰⁰⁰ | 7.74 | 0.626 |

From the largest verification ever performed out to 10¹⁰⁰, the typical size of
`S` grows from 0.415 to 0.525. Yet `S(T)` is **unbounded** — it must be. Every
phenomenon that could falsify RH lives in the tail of this distribution, and the
distribution widens at the rate of the logarithm of a logarithm. That is the
wall, in numbers.

## 3. The Mertens conjecture: the cautionary tale

Mertens conjectured `|M(x)| < √x`, where `M` is the summed Möbius function. It
implies RH. It was verified to 10⁹. It looked completely safe.

**It is false.** Odlyzko and te Riele disproved it in 1985, by exploiting
near-resonances among the zeros. The disproof is *indirect*: it shows
`limsup M(x)/√x > 1.06` without exhibiting any `x`. **No explicit counterexample
is known today**, four decades later. The first is believed to lie beyond 10²⁰.

Computed here to `x = 2 × 10⁶`, `|M(x)|/√x` reaches only **0.2205** — less than
a quarter of the way to a boundary that the conjecture said could never be
crossed, and which is in fact crossed. A search of that kind was never going to
find anything, and no amount of extending it would have.

The structural point: RH survives this, because RH only needs
`M(x) = O(x^{1/2+ε})`, which is much weaker than the conjecture that died. But
the epistemics do not survive. A closely related, natural, heavily-verified
conjecture in this exact area turned out to be false in a range no computation
can reach.

## 4. Robin's criterion: a margin shrinking to zero

Robin: RH ⟺ `σ(n) < e^γ n log log n` for all `n > 5040`.

Brute force over `n` is the wrong instrument — the inequality is only ever
near-tight on *colossally abundant* numbers, products of primorials that become
astronomically large at once. Following those instead (`log n` and
`log(σ(n)/n)` tracked in floating point, so `n` itself never needs
representing):

| digits of `n` | `σ(n)/(n log log n)` | margin below `e^γ` |
|---|---|---|
| 4.7 | 1.751246515 | 0.029825903 |
| 7,275 | 1.779884862 | 0.001187556 |
| 25,343 | 1.780507409 | 0.000565009 |
| 54,951 | 1.780717257 | 0.000355161 |
| 96,728 | 1.780820343 | 0.000252075 |

Gronwall's theorem says this ratio has limsup **exactly** `e^γ = 1.781072418`,
approached along these very numbers. So the margin *must* shrink to zero. RH is
the assertion that it shrinks to zero without ever touching it.

At numbers with 96,728 digits the margin is still 2.5 × 10⁻⁴ and falling. There
is no height at which the numbers settle down and reassure. A true RH and a
false RH predict sequences that look identical for as far as anyone can compute,
differing only in whether a quantity tending to zero ever arrives. **More terms
cannot distinguish them.** This is a criterion that is checkable and yet, by its
own asymptotics, uninformative.

*(A note on getting this right: my first version of this computation used only
the first 60 primes, and produced a Robin ratio that peaked and then decreased —
contradicting Gronwall. The cause was the greedy search exhausting its prime
list and being forced to keep raising exponents on primes it already had. The
falling curve was an artefact of truncation, not arithmetic. It is a small
reminder that in this subject the numerics mislead readily, in both directions.)*

## 5. Skewes: where numerical evidence provably lies

For every `x` anyone has computed, `π(x) < li(x)`. Gauss and Riemann both
believed the inequality universal.

**Littlewood proved in 1914 that it fails** — infinitely often, in both
directions. The first crossing is still unknown; it lies somewhere below about
1.4 × 10³¹⁶ (Bays–Hudson), a region no computation will ever reach.

This is the cleanest case in number theory of a pattern that holds for every
accessible `x` and is nevertheless false. The mechanism is precisely the one
that should worry us about RH: the effect is controlled by the zeros, and the
competing terms only come into balance once `log log x` has grown, putting the
crossover exponentially out of reach.

## 6. And RH has no margin at all

From `docs/02`: Rodgers and Tao proved `Λ ≥ 0` in 2018, and RH ⟺ `Λ ≤ 0`.
Hence **RH ⟺ `Λ = 0` exactly**.

RH is not comfortably true. It is true by exactly zero margin, sitting on the
boundary of failure. This has a direct consequence for evidence: no computation,
and no soft argument, can distinguish `Λ = 0` from `Λ = 10⁻⁹` — and that
distinction is the whole problem.

---

## What actually justifies believing RH

Not the zero counts. The real reasons are structural:

1. **The function field analogue is a theorem** (Weil, Deligne). The same
   statement, in a setting where the necessary geometry exists, is true. This
   is by far the strongest reason.

2. **The GUE statistics.** The zeros repel like eigenvalues of a random
   Hermitian matrix — reproduced in this repository at 12.8× better fit than
   Poisson, with pair correlation matching Montgomery–Dyson to 0.022. It is
   very hard to see how an arbitrary sequence would do this. Something is
   probably a spectrum, and spectra of self-adjoint operators are real.

3. **Coherence.** RH's consequences are extensive and none has produced a
   contradiction, while many independent lines of reasoning converge on it.

4. **`Λ ≥ 0` is proved.** Half of `Λ = 0` is a theorem.

These are good reasons. "We checked 10¹³ zeros" is not one of them — or rather,
it is a very weak one, and this document is an attempt to say exactly how weak,
in numbers rather than adjectives.

The lesson generalises past RH. When a conjecture's failure mode is governed by
`log log x`, verification is close to worthless as evidence, and the honest move
is to compute the sensitivity of your test rather than to report that it passed.
