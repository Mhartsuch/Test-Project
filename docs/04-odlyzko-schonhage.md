# Height 10¹⁵: the algorithm, and what "verified" is worth

*Two separate problems stand between `t = 10^10` and `t = 10^15`. One is
arithmetic volume and is solved by the Odlyzko–Schönhage algorithm. The other is
precision, and it is solved by refusing to store the answer in a float at all.
Neither has anything to do with the Riemann Hypothesis; both have to be dealt
with before a single zero can be looked at.*

---

## 1. Why height is hard

The Riemann–Siegel formula computes `Z(t)` with

```
N = floor(sqrt(t / 2π))
```

terms. That is the celebrated square-root saving over Euler–Maclaurin, and it is
what makes any of this possible. But it is still growth:

| `t` | terms in the main sum | mean gap between zeros |
|---|---|---|
| 10⁶ | 398 | 0.5246 |
| 10¹⁰ | 39,894 | 0.2965 |
| 10¹³ | 1,261,566 | 0.2185 |
| 10¹⁵ | 12,615,662 | 0.1921 |

A single evaluation at 10¹⁵ costs 12.6 million cosines — around three seconds
here once the phases are set up. That sounds affordable until you count how many
are needed. Zeros sit 0.19 apart, so a search grid fine enough not to straddle
close pairs and a block of a thousand zeros needs some 25,000 evaluations, which
is the better part of a day. And the cost per zero never improves, however many
you want.

### The second problem, which is worse

At `t = 10^15`, `θ(t) ≈ 1.6 × 10^16`. Every term of the main sum is
`cos(θ(t) − t log n)`, and a float64 carries about 16 significant digits — so
the *integer part alone* exhausts the format. The fractional part of the angle,
which is the only part that matters, is gone before the first cosine is
evaluated.

This is not a subtle loss. At `t = 10^10` the existing
[`riemann/highprec.py`](../riemann/highprec.py) measured plain float64 at
`3.7 × 10^-5` of error against a zero gap of `0.2965`. Five orders of magnitude
further up, there is nothing left at all.

---

## 2. Odlyzko–Schönhage: the wrong object was being computed

Odlyzko and Schönhage's observation (1988) is that the expensive thing is not
`Z` at a point but the main sum

```
F(t) = Σ_{n≤N} n^{-1/2} e^{-it log n}
```

and `F` is a sum of `N` pure exponentials in `t`. Sample it at `M` equally
spaced points `t_j = t₀ + (j − M/2)δ`:

```
F(t_j) = Σ_{n≤N} c_n e^{-i k x_n},    k = j − M/2,
         c_n = n^{-1/2} e^{-i t₀ log n},   x_n = δ log n.
```

That is a **nonuniform discrete Fourier transform**: `M` output modes from `N`
sources sitting at irregular frequencies `x_n`. It costs `O(N + M log M)`
instead of `O(NM)`. The per-point cost of `Z` falls from `N` to `N/M + log M`,
and — this is the part that matters — it keeps falling as the block gets bigger.

Odlyzko and Schönhage got there by expanding `Σ c_n/(1 − z_n w)` with the fast
multipole method and reading off Taylor coefficients. This implementation uses
the Greengard–Lee Gaussian-gridding NUFFT, which is the same idea — a smooth
kernel cheap in one domain and rapidly decaying in the other — with better
numerical behaviour, since the poles never come near the contour. The complexity
is identical and it is the complexity that is the point.

Measured, at the default settings:

| `t` | terms `N` | setup | transform | direct, per point | fast, per point |
|---|---|---|---|---|---|
| 10⁸ | 3,989 | 0.6 s | 0.0 s | 0.5 ms | 4 µs |
| 10¹⁰ | 39,894 | 0.0 s | 0.0 s | 2.8 ms | 3 µs |
| 10¹² | 398,942 | 0.3 s | 0.6 s | 36 ms | 2 µs |
| 10¹⁴ | 3,989,422 | 3.5 s | 5.9 s | 0.66 s | 2 µs |
| 10¹⁵ | 12,615,662 | 11.9 s | 18.2 s | 3.14 s | 2 µs |

The block at 10¹⁵ used for the rest of this document — half-width 100,
containing 1041 zeros — took **9.9 s of setup, 18.4 s of transform and 0.2 s of
searching**: 29 seconds in total. The same search done directly needs 25,601
evaluations at 3.1 s each, which is **22 hours**.

Note that the fixed cost is paid once whatever the block size, so the ratio is
not a property of the algorithm alone: at 10⁸ with only 200 zeros wanted the
setup dominates and the transform is barely worth having. The advantage arrives
with `N` and with block size together, which is exactly what the complexity says
it should do.

### Two samples per zero is already four times more than needed

`F` is band-limited. Its frequencies `−log n` all lie in `[−log N, 0]`, a band of
half-width

```
Ω = ½ log N = ¼ log(t/2π),
```

so Nyquist permits a sample spacing of `π/Ω`, which is exactly **twice the mean
zero gap**. Sampling `F` at two points per zero therefore oversamples by a factor
of four, and everything between grid points is recovered by interpolation rather
than by another `N`-term sum.

`Z` itself is *not* band-limited — `Z(t) = 2 Re(e^{iθ(t)} F(t))` and `θ` is not
linear — so the interpolation is applied to `F`, and `θ` is evaluated exactly at
the target point, which costs nothing. The interpolation is a Gaussian-windowed
cardinal series,

```
G(t) ≈ Σ_{|j−j₀|<q} G(t_j) sinc((t−t_j)/δ) exp(−(t−t_j)²/2σ²),
       σ = δ sqrt(q / ((1−λ)π)),   λ = δΩ/π,
```

which converges like `exp(−(1−λ)πq/2)`. Two samples per gap puts `λ` at `0.25`,
and rounding `δ` down to a power of two drops it further — to `0.163` at 10¹⁵ —
so with `q = 32` the bound is `e^{-42}`. Measured against full direct summation
at 10¹⁵ it comes out at `5.9 × 10^-14`, which is the direct sum's own roundoff:
the interpolation is not the limiting factor and cannot be made to be.

The practical consequence is that a *search* grid can be as fine as you like.
The transform grid stays at two points per gap because that is all the Nyquist
rate asks for; the zero search then runs on an *interpolated* grid at 24.6 points
per gap — sixteen requested, rounded up to a power-of-two subdivision — and each
of those points costs a 64-term stencil rather than a 12.6-million-term sum. A
scan at two points per gap misses about 8% of the zeros to straddled close pairs;
at 24.6 the tally stops moving.

---

## 3. The ordinate is not a floating-point number

Near `t = 10^15`, consecutive float64 values are **0.125 apart**. The mean gap
between zeros there is `0.1921`. A double cannot name a zero ordinate at that
height to better than two thirds of the distance to its neighbour:

```python
>>> t0 = 1e15
>>> math.ulp(t0)
0.125
>>> t0 + 0.03 == t0
True
```

So `ZBlock` never accepts an absolute `t`. Every method takes an **offset** from
an exactly-representable `t₀`, and the offset — being of size 100 rather than
10¹⁵ — carries a further fourteen digits.

The same reasoning forces the grid spacing to be a **power of two**. Then `kδ` is
exact for every integer `k`, and `δ log n` is exact in double-double (a power of
two only shifts an exponent), so the grid the transform computes on is the grid
the rest of the code believes it is computing on. With an arbitrary `δ` the two
differ by `10^-14` in `t`, which sounds harmless and is not: `|F'| ≈ 10^5` at
`t = 10^15`, so it moves the main sum by `10^-9`. That discrepancy is what this
implementation spent its first debugging session chasing, and it looked exactly
like a broken transform.

### Double-double, and no dependency

Reducing `t log n` modulo `2π` needs 17 digits before the fraction even starts.
[`riemann/dd.py`](../riemann/dd.py) carries an unevaluated sum of two doubles —
about 32 digits — built from Knuth's `two_sum` and Dekker's `two_prod`, which are
*identities* of IEEE-754 arithmetic rather than approximations.

The logarithm is the interesting part. It is needed to 32 digits for every `n` up
to 12.6 million. Writing `n = m 2^e` with `frexp` (exact), picking the nearest of
4096 tabulated points `c`, and using

```
log n = e log 2 + log c + 2 atanh((m−c)/(m+c))
```

works because `m − c` is *exact* by Sterbenz' lemma and `|z| < 2^-13`, so four
series terms reach `10^-36`. The table of `log c` is generated once from the
standard library's `decimal`, so the package still has no third-party dependency
outside numpy. All 12.6 million logarithms take 8 seconds.

`riemann.highprec` solved the same problem at 10¹⁰ by calling mpmath once per
window — which works, but puts a third-party library inside the library rather
than in the tests, and does not scale to 12.6 million reductions.

---

## 4. What "verified" means here

Finding zeros and proving things about them are different activities, and the
gap between them is where computational number theory usually gets vague. Two
claims are wanted and they need completely different machinery.

### Claim 1: each bracket contains a zero *on the line*

`Z` is real and continuous, so a bracket on which the sign of `Z` is certain and
opposite contains a zero of `Z`, hence a zero of `ζ` exactly on the critical
line. "Certain" has to mean an enclosure, not an estimate — so
[`riemann/rigorous.py`](../riemann/rigorous.py) returns an interval provably
containing `Z(t)` and accepts the sign only when the whole interval lies on one
side of zero.

The error budget at `t = 10^15`, every line of it bounded rather than estimated:

| source | bound |
|---|---|
| `θ(t) mod 2π` | 2 × 10⁻¹⁶ |
| phase `t log n mod 2π` (double-double) | 2 × 10⁻¹⁶ |
| `(d−s) log n` | 2 × 10⁻¹⁵ |
| cosine evaluation | 6 × 10⁻¹⁵ |
| weights `n^{-1/2}` | 1 × 10⁻¹⁶ |
| summation (explicit binary tree, depth 24) | 2 × 10⁻¹¹ |
| `C₀(p)` (interval arithmetic) | 1 × 10⁻¹⁶ |
| Riemann–Siegel remainder (Gabcke) | 7 × 10⁻¹³ |
| **total** | **≈ 1.5 × 10⁻¹⁰** |

against a typical `|Z|` of `0.3` at the ends of a bracket from a scan at sixteen
points per gap. Nine orders of magnitude of headroom.

Three of those lines are worth spelling out, because each is a place where a
"rigorous" computation normally stops being rigorous.

**Not trusting `cos`.** C makes no accuracy promise about `cos` whatsoever, and
the usual defence — everyone knows it is under an ulp — is exactly the kind of
claim this repository exists to not make. `cos_certified` evaluates the cosine
itself: reduce modulo `π/2` against a double-double `π`, removing the integer
multiple with an exact `two_prod`, then sum a Taylor series short enough to bound
by hand (first omitted term `2 × 10^-18`) and add the Horner rounding bound
explicitly. It agrees with the platform's libm to `1.1 × 10^-16`, so libm was in
fact fine — but nothing rests on that.

**Not trusting the summation shape.** numpy's `sum` is pairwise and accurate, but
its exact tree is an implementation detail, and a bound cannot rest on an
implementation detail. `tree_sum` adds the second half of the array to the first,
repeatedly: a binary tree of depth exactly `⌈log₂ N⌉ = 24`, so the classical
`γ_24 Σ|x_i|` bound applies with nothing assumed. It costs one extra pass.

**Not quoting the `θ` coefficients.** The asymptotic series for `θ` is printed
everywhere with four correction terms — `1/48`, `7/5760`, `31/80640`,
`127/430080` — and then nobody can bound what was dropped. In fact truncating
there leaves an error at `t = 200` that *exceeds* the first omitted term, by six
parts in 10⁵: small, but the difference between a bound and a wish. The closed
form

```
a_k = (2^{2k−1} − 1)/2^{2k} · |B_{2k}| / (2k(2k−1))
```

reproduces all four exactly, and the package already computes Bernoulli numbers
exactly, so eight terms cost nothing and drop the residual at `t = 200` from
`8 × 10^-25` to `7 × 10^-41`.

### Claim 2: there are no other zeros

This cannot come from evaluating `Z`, because `Z` says nothing about zeros off
the line. It comes from **Turing's method**.

Write `S(t) = N(t) − θ(t)/π − 1`, where `N(t)` counts zeros of `ζ` in the whole
critical strip up to height `t`. Above a target height `T`, every certified zero
forces `N` up: `N(t) ≥ m + L(t)`, with `L` counting certified zeros in `(T, t]`.
Integrating against Trudgian's bound `|∫S| ≤ 2.067 + 0.059 log t` gives

```
m ≤ [ B + ∫_T^{T₂}(θ/π + 1) − ∫_T^{T₂} L ] / (T₂ − T),
```

and the same argument below `T` gives a lower bound. Two constraints, one integer
between them.

Three things about this deserve emphasis.

**It needs no completeness assumption.** Leaving zeros out of the lists only
widens the bracket; it cannot make the answer wrong. What the zeros must be is
*genuine*, which is what the enclosures establish. The logic runs in the safe
direction.

**It determines `N(T)` outright.** Not the number of zeros found — the number
that *exist*, roughly `5 × 10^15` at `t = 10^15`, without anyone having counted
that far. This is how Odlyzko was able to say which zeros he had computed at
10²⁰. It also means the smooth count `θ(T)/π` has to be carried in `decimal`:
at that height an ulp of a double is a whole unit, and Turing's method needs the
fractional part to a few thousandths.

**Together the two claims close.** If `N(T₂) − N(T₁)` equals the number of
certified brackets in between, then every zero of `ζ` in that range is simple and
on the critical line — an off-line zero, or a double one, would make the counts
disagree. Checked against `mpmath.nzeros`, which implements the same theorem
independently, the counts agree exactly at 10⁶, 10⁸ and 10¹⁰.

---

## 5. The two things that are taken on faith

Everything above is self-contained. Two things are not, and they are the load
-bearing external inputs:

1. **Gabcke's bound** on the Riemann–Siegel remainder,
   `|R| ≤ 0.127 t^{-3/4}` for the formula truncated after `C₀`
   (Gabcke 1979, Satz 5.2). Deriving it is a thesis, not a function. It is
   checked numerically against mpmath from `t = 10^3` to `10^13`, where the
   observed ratio to the claimed constant runs between 0.11 and 0.33 — evidence
   that it holds, and not a proof of it.
2. **Trudgian's bound** `|∫_{t₁}^{t₂} S| ≤ 2.067 + 0.059 log t₂` for
   `t₁ ≥ 168π` (Trudgian 2011, improving Lehman 1970 and Turing 1953). Without
   it there is no Turing's method at all.

A third, much smaller: the tail of the `θ` expansion is assumed to be enveloped
by twice its leading term. Successive terms fall by a factor of about `t²/4`, so
at the worst height used anywhere here the whole tail exceeds its leading term by
six parts in 10⁵ — but "assumed" is the right word, and the quantity being
bounded is `7 × 10^-41`.

They are named `GABCKE`, `TURING_A` and `TURING_B` so that anyone with better
constants can substitute them.

---

## 6. What this does and does not show

**It does not prove the Riemann Hypothesis, and does not bear on it much.** It
proves a statement about one block of a thousand consecutive zeros, at one
height, out of infinitely many. [`docs/03`](03-strength-of-evidence.md) computes
what evidence of this kind is worth, and the answer is: less than it looks. A
zero placed at `Re ρ = 0.6` at height 74,920 keeps Li's criterion positive until
`n ≈ 1.7 × 10^12`. Verifying a block at 10¹⁵ does not make that better; it makes
the unverified region start higher.

**What it does show** is that the verification is real rather than rhetorical.
The statement "every zero in this range is simple and on the critical line" is
either backed by an enclosure for every sign and a count that cannot be evaded,
or it is a claim about how a program behaved. This repository already found, and
documented, a zero-search that *manufactured* 102,401 zeros below a height that
admits 100,000, by hunting where `|Z|` was smallest — which is exactly where
roundoff dominates. That is what an unverified search looks like from the inside:
entirely convincing.

The gap between "we computed a lot of zeros" and "we proved these are all of
them" is the whole subject, and it is bridged by Turing's method and by interval
arithmetic — not by computing harder.

---

## 7. Reproducing it

```bash
python scripts/os_zeros.py 1e15 100         # find a block; prints the cost curve
python scripts/rigorous_verify.py 1e15 100  # certify it and count it
python -m pytest tests/test_os.py tests/test_rigorous.py -q
```

The first takes about a minute, the second a little over an hour — dominated by
the two full 12.6-million-term enclosures each certified bracket requires. That
asymmetry is the honest summary of the whole exercise: *finding* a thousand
zeros at 10¹⁵ is now cheap, and *proving* them is still expensive, because a
proof will not accept an interpolation.
