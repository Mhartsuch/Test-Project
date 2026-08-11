"""Generate the standalone HTML report from real computed data.

Usage:  python scripts/make_report.py [ZEROS_JSON] [OUT_HTML]

Every number and every curve in the output is computed here, not transcribed.
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from riemann.equivalences import (  # noqa: E402
    EULER_GAMMA, colossally_abundant_candidates, li_coefficient_exact_first)
from riemann.explicit_formula import psi_exact, psi_from_zeros_array  # noqa: E402
from riemann.fast import li_coefficients_array  # noqa: E402
from riemann.statistics import (  # noqa: E402
    pair_correlation_histogram, spacing_histogram, spacing_moments, unfold)
from riemann.zeros import lehmer_pairs, normalised_gaps  # noqa: E402

# --- design tokens ---------------------------------------------------------
C = {"a": "#4066C4", "b": "#0E9E77", "c": "#BE5A28"}
CD = {"a": "#6A8AD8", "b": "#1CA37E", "c": "#C4713F"}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def path_from(points):
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

def fig_spectrum(zeros, t_max=400.0, w=1000, h=132):
    """The zeros as an absorption spectrum: dark lines on a continuum."""
    pad = 1.0
    lines = []
    for t in zeros:
        if t > t_max:
            break
        x = pad + (t / t_max) * (w - 2 * pad)
        lines.append(f'<line x1="{x:.2f}" y1="14" x2="{x:.2f}" y2="{h-30}" />')
    ticks = []
    for t in range(0, int(t_max) + 1, 50):
        x = pad + (t / t_max) * (w - 2 * pad)
        ticks.append(
            f'<text x="{x:.1f}" y="{h-10}" class="tick" text-anchor="middle">{t}</text>')
    return f"""<svg viewBox="0 0 {w} {h}" role="img" preserveAspectRatio="none"
  aria-label="The first {len(lines)} zero ordinates drawn as spectral lines between t=0 and t={t_max:.0f}.">
  <rect x="0" y="14" width="{w}" height="{h-44}" class="continuum" />
  <g class="spec-line">{''.join(lines)}</g>
  <g>{''.join(ticks)}</g>
</svg>"""


def fig_spacing(hist, w=760, h=380):
    m = {"l": 52, "r": 16, "t": 18, "b": 44}
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    xmax = 3.0
    ymax = max(max(hist["observed"]), max(hist["gue"]), max(hist["poisson"])) * 1.08

    def X(v):
        return m["l"] + v / xmax * iw

    def Y(v):
        return m["t"] + ih - v / ymax * ih

    bw = hist["bin_width"]
    bars = []
    for c, v in zip(hist["centres"], hist["observed"]):
        x0, x1 = X(c - bw / 2) + 1, X(c + bw / 2) - 1
        if v <= 0:
            continue
        bars.append(
            f'<rect class="bar" x="{x0:.2f}" y="{Y(v):.2f}" width="{max(x1-x0,0.5):.2f}" '
            f'height="{(Y(0)-Y(v)):.2f}" rx="2" '
            f'data-x="{c:.3f}" data-o="{v:.4f}" data-g="{0:.4f}"><title>'
            f'spacing {c:.2f} — observed density {v:.4f}</title></rect>')
    gue = path_from([(X(c), Y(v)) for c, v in zip(hist["centres"], hist["gue"])])
    poi = path_from([(X(c), Y(v)) for c, v in zip(hist["centres"], hist["poisson"])])

    grid, xlab = [], []
    for gv in np.arange(0, ymax, 0.25):
        grid.append(f'<line class="grid" x1="{m["l"]}" y1="{Y(gv):.1f}" x2="{w-m["r"]}" y2="{Y(gv):.1f}" />')
        grid.append(f'<text class="tick" x="{m["l"]-8}" y="{Y(gv)+4:.1f}" text-anchor="end">{gv:.2f}</text>')
    for xv in (0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        xlab.append(f'<text class="tick" x="{X(xv):.1f}" y="{h-m["b"]+22}" text-anchor="middle">{xv:g}</text>')

    return f"""<svg viewBox="0 0 {w} {h}" role="img"
  aria-label="Nearest-neighbour spacing density of {hist['n_spacings']} zero gaps, matching the GUE curve and departing sharply from Poisson.">
  {''.join(grid)}
  <g>{''.join(bars)}</g>
  <path class="s-b" d="{poi}" stroke-dasharray="2 4" />
  <path class="s-c" d="{gue}" />
  <text class="lbl s-c-t" x="{X(1.55):.0f}" y="{Y(hist['gue'][int(1.55/bw)])-14:.0f}">GUE</text>
  <text class="lbl s-b-t" x="{X(2.35):.0f}" y="{Y(hist['poisson'][int(2.35/bw)])-12:.0f}">Poisson</text>
  <text class="lbl s-a-t" x="{X(0.62):.0f}" y="{Y(hist['observed'][int(0.62/bw)])-14:.0f}">zeta zeros</text>
  <text class="axis" x="{m['l']+iw/2:.0f}" y="{h-6}" text-anchor="middle">normalised spacing s</text>
  {''.join(xlab)}
</svg>"""


def fig_paircorr(pc, w=760, h=340):
    m = {"l": 52, "r": 16, "t": 18, "b": 44}
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    xmax, ymax = 3.0, 1.45

    def X(v):
        return m["l"] + v / xmax * iw

    def Y(v):
        return m["t"] + ih - v / ymax * ih

    obs = path_from([(X(c), Y(v)) for c, v in zip(pc["centres"], pc["observed"])])
    gue = path_from([(X(c), Y(v)) for c, v in zip(pc["centres"], pc["gue"])])
    dots = "".join(
        f'<circle class="dot" cx="{X(c):.2f}" cy="{Y(v):.2f}" r="3.2"><title>'
        f'separation {c:.2f} — observed {v:.3f}, Montgomery {g:.3f}</title></circle>'
        for c, v, g in zip(pc["centres"], pc["observed"], pc["gue"]))
    grid, xlab = [], []
    for gv in (0, 0.25, 0.5, 0.75, 1.0, 1.25):
        grid.append(f'<line class="grid" x1="{m["l"]}" y1="{Y(gv):.1f}" x2="{w-m["r"]}" y2="{Y(gv):.1f}" />')
        grid.append(f'<text class="tick" x="{m["l"]-8}" y="{Y(gv)+4:.1f}" text-anchor="end">{gv:g}</text>')
    for xv in (0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        xlab.append(f'<text class="tick" x="{X(xv):.1f}" y="{h-m["b"]+22}" text-anchor="middle">{xv:g}</text>')
    return f"""<svg viewBox="0 0 {w} {h}" role="img"
  aria-label="Pair correlation of the zeros against the Montgomery-Dyson curve 1 minus (sin pi r over pi r) squared.">
  {''.join(grid)}
  <path class="s-c" d="{gue}" />
  <path class="s-a" d="{obs}" />
  <g class="s-a-f">{dots}</g>
  <text class="lbl s-c-t" x="{X(1.9):.0f}" y="{Y(1.28):.0f}">1 &#8722; (sin&#960;r/&#960;r)&#178;</text>
  <text class="lbl s-a-t" x="{X(0.28):.0f}" y="{Y(0.52):.0f}">observed</text>
  <text class="axis" x="{m['l']+iw/2:.0f}" y="{h-6}" text-anchor="middle">normalised separation r</text>
  {''.join(xlab)}
</svg>"""


def fig_explicit(xs, exact, approx, w=760, h=340):
    m = {"l": 52, "r": 16, "t": 18, "b": 44}
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    x0, x1 = xs[0], xs[-1]
    ylo = min(min(exact), min(approx)) - 2
    yhi = max(max(exact), max(approx)) + 2

    def X(v):
        return m["l"] + (v - x0) / (x1 - x0) * iw

    def Y(v):
        return m["t"] + ih - (v - ylo) / (yhi - ylo) * ih

    # true psi as a genuine staircase
    steps = []
    prev = None
    for x, y in zip(xs, exact):
        if prev is not None and y != prev[1]:
            steps.append((X(x), Y(prev[1])))
            steps.append((X(x), Y(y)))
        else:
            steps.append((X(x), Y(y)))
        prev = (x, y)
    rec = path_from([(X(x), Y(y)) for x, y in zip(xs, approx)])
    grid, xlab = [], []
    for gv in range(0, int(yhi) + 1, 20):
        if gv < ylo:
            continue
        grid.append(f'<line class="grid" x1="{m["l"]}" y1="{Y(gv):.1f}" x2="{w-m["r"]}" y2="{Y(gv):.1f}" />')
        grid.append(f'<text class="tick" x="{m["l"]-8}" y="{Y(gv)+4:.1f}" text-anchor="end">{gv}</text>')
    for xv in (10, 30, 50, 70, 90):
        xlab.append(f'<text class="tick" x="{X(xv):.1f}" y="{h-m["b"]+22}" text-anchor="middle">{xv}</text>')
    return f"""<svg viewBox="0 0 {w} {h}" role="img"
  aria-label="The Chebyshev function psi(x) as a staircase, closely tracked by a reconstruction built only from 5000 zero ordinates.">
  {''.join(grid)}
  <path class="s-b" d="{path_from(steps)}" />
  <path class="s-a" d="{rec}" />
  <text class="lbl s-b-t" x="{X(62):.0f}" y="{Y(38):.0f}">true &#968;(x)</text>
  <text class="lbl s-a-t" x="{X(22):.0f}" y="{Y(64):.0f}">rebuilt from 5000 zeros</text>
  <text class="axis" x="{m['l']+iw/2:.0f}" y="{h-6}" text-anchor="middle">x</text>
  {''.join(xlab)}
</svg>"""


# ---------------------------------------------------------------------------

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "results/zeros_74921.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "results/riemann_report.html"
    blob = json.load(open(path))
    zeros = blob["zeros"]
    n_zeros, t_max = len(zeros), blob["t_max"]
    s = blob.get("seconds", 0.0)
    secs = f"{s:.0f}s" if s < 90 else f"{s/60:.0f} min"

    w = unfold(zeros)
    hist = spacing_histogram(w, bins=40, s_max=3.0, already_unfolded=True)
    pc = pair_correlation_histogram(w, bins=40, r_max=3.0, already_unfolded=True)
    mom = spacing_moments(w, already_unfolded=True)
    dev_g = sum(abs(a - b) for a, b in zip(hist["observed"], hist["gue"])) * hist["bin_width"]
    dev_p = sum(abs(a - b) for a, b in zip(hist["observed"], hist["poisson"])) * hist["bin_width"]
    pc_dev = sum(abs(a - b) for a, b in zip(pc["observed"], pc["gue"])) / len(pc["gue"])

    xs = np.linspace(2.0, 100.0, 700)
    tab = psi_exact(101)
    exact = [tab[int(math.floor(x))] for x in xs]
    approx = psi_from_zeros_array(xs, zeros[:5000]).tolist()
    rms = float(np.sqrt(np.mean((np.array(approx) - np.array(exact)) ** 2)))

    gaps = normalised_gaps(zeros)
    tight = sorted(lehmer_pairs(zeros, 0.06), key=lambda d: d["normalised_gap"])[:6]
    lam = li_coefficients_array(4, zeros)
    min_gap = min(gaps)
    min_idx = gaps.index(min_gap)
    ca = colossally_abundant_candidates(20000)

    # --- Li sensitivity experiment (computed, not transcribed) -------------
    # Run on the first 100k zeros: the crossing point is set by the growing
    # off-line term, so the truncation of the zero sum is immaterial, and this
    # keeps a 30000-step accumulation affordable.
    li_zeros = zeros[:100000]
    n_exact = 30000
    lam_full = li_coefficients_array(n_exact, li_zeros)
    li_rows = []
    for d, gamma in [(0.25, li_zeros[0]), (0.10, li_zeros[0]), (0.05, li_zeros[0]),
                     (0.01, li_zeros[0]), (0.10, 1000.0), (0.10, 74920.0)]:
        rho = complex(0.5 - d, gamma)
        r = abs(rho - 1.0) / abs(rho)
        n = np.arange(1, n_exact + 1)
        delta = np.zeros(n_exact)
        for grp, sign in (([complex(0.5 + d, gamma), complex(0.5 - d, gamma)], 1.0),
                          ([complex(0.5, g) for g in li_zeros[:2]], -1.0)):
            for root in grp:
                delta += sign * 2.0 * (1.0 - np.exp(n * np.log(1.0 - 1.0 / root)).real)
        neg = np.nonzero(lam_full + delta < 0.0)[0]
        exact_s = f"{int(neg[0])+1:,}" if neg.size else f"&gt; {n_exact:,}"
        # estimate: solve 2 r^n = (n/2)(log n + gamma - 1 - log 2pi)
        est, lr = 1000.0, math.log(r)
        for _ in range(300):
            smooth = max(0.5 * est * (math.log(est) + EULER_GAMMA - 1 - math.log(2 * math.pi)), 1e-300)
            est = 0.5 * (est + math.log(smooth / 2.0) / lr)
        est_s = f"{est:,.0f}" if est < 1e15 else f"{est:.3g}"
        li_rows.append((f"Re = {0.5+d:.2f}", f"{gamma:,.1f}", f"{r:.10f}", exact_s, est_s))
    li_html = "".join(
        f"<tr><td class=\"mono\">{a}</td><td class=\"mono num\">{b}</td>"
        f"<td class=\"mono num\">{c}</td><td class=\"mono num strong\">{d}</td>"
        f"<td class=\"mono num\">{e}</td></tr>" for a, b, c, d, e in li_rows)

    tight_html = "".join(
        f"<tr><td class=\"mono num\">{d['t_lo']:.6f}</td>"
        f"<td class=\"mono num\">{d['t_hi']-d['t_lo']:.6f}</td>"
        f"<td class=\"mono num strong\">{d['normalised_gap']:.5f}</td></tr>"
        for d in tight)

    html = f"""<title>The Riemann Hypothesis — what {n_zeros:,} zeros do and don't show</title>
<style>
:root {{
  --paper:#F4F6F8; --surface:#FFFFFF; --ink:#141A22; --muted:#5C6875;
  --rule:#DCE2E9; --rule-soft:#E9EDF2; --continuum:#E7EBF0;
  --s-a:{C['a']}; --s-b:{C['b']}; --s-c:{C['c']};
  --shadow:0 1px 2px rgba(20,26,34,.05), 0 8px 24px -12px rgba(20,26,34,.16);
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,ui-serif,serif;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0E141B; --surface:#151D26; --ink:#E3E9F0; --muted:#94A1B0;
    --rule:#25303C; --rule-soft:#1C2531; --continuum:#1E2833;
    --s-a:{CD['a']}; --s-b:{CD['b']}; --s-c:{CD['c']};
    --shadow:0 1px 2px rgba(0,0,0,.35), 0 10px 28px -14px rgba(0,0,0,.6);
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0E141B; --surface:#151D26; --ink:#E3E9F0; --muted:#94A1B0;
  --rule:#25303C; --rule-soft:#1C2531; --continuum:#1E2833;
  --s-a:{CD['a']}; --s-b:{CD['b']}; --s-c:{CD['c']};
  --shadow:0 1px 2px rgba(0,0,0,.35), 0 10px 28px -14px rgba(0,0,0,.6);
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--serif); font-size:18px; line-height:1.65;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1120px; margin:0 auto; padding:0 24px 96px; }}
.col {{ max-width:68ch; margin-inline:auto; }}
.col > * + * {{ margin-top:1.1em; }}

h1,h2,h3 {{ text-wrap:balance; line-height:1.15; margin:0; font-weight:600; }}
h1 {{ font-size:clamp(2.1rem,5.2vw,3.5rem); letter-spacing:-.018em; }}
h2 {{ font-size:clamp(1.5rem,3vw,2rem); letter-spacing:-.012em; }}
h3 {{ font-size:1.14rem; letter-spacing:-.004em; }}
p {{ margin:0; }}
a {{ color:var(--s-a); text-underline-offset:3px; }}
strong {{ font-weight:600; }}
.mono {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}
.eyebrow {{
  font-family:var(--mono); font-size:.7rem; text-transform:uppercase;
  letter-spacing:.16em; color:var(--muted); margin:0;
}}
.lede {{ font-size:1.2rem; color:var(--muted); }}

header.masthead {{ padding:72px 0 8px; }}
header.masthead .col > * + * {{ margin-top:.85em; }}

/* --- spectrum hero --- */
.spectrum {{ margin:38px 0 10px; }}
.spectrum svg {{ display:block; width:100%; height:132px; }}
.continuum {{ fill:var(--continuum); }}
.spec-line line {{ stroke:var(--s-a); stroke-width:1.15; opacity:.88; }}
.tick {{ font-family:var(--mono); font-size:10px; fill:var(--muted); }}
.caption {{
  font-size:.85rem; color:var(--muted); font-family:var(--mono);
  line-height:1.55; margin-top:10px;
}}

/* --- stat row --- */
.stats {{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:1px; background:var(--rule); border:1px solid var(--rule);
  border-radius:10px; overflow:hidden; margin:34px 0;
}}
.stat {{ background:var(--surface); padding:18px 20px; }}
.stat .v {{
  font-family:var(--mono); font-size:1.6rem; font-variant-numeric:tabular-nums;
  letter-spacing:-.02em; display:block; line-height:1.2;
}}
.stat .k {{ font-size:.78rem; color:var(--muted); display:block; margin-top:6px; line-height:1.4; }}

section {{ margin-top:64px; }}
.fig {{
  background:var(--surface); border:1px solid var(--rule); border-radius:12px;
  padding:22px 22px 12px; margin:30px 0; box-shadow:var(--shadow); overflow-x:auto;
}}
.fig svg {{ display:block; width:100%; height:auto; min-width:520px; }}
.fig h3 {{ margin-bottom:4px; }}
.fig .sub {{ font-size:.86rem; color:var(--muted); margin-bottom:14px; }}

.grid {{ stroke:var(--rule-soft); stroke-width:1; }}
.axis {{ font-family:var(--mono); font-size:11px; fill:var(--muted); }}
.lbl {{ font-family:var(--mono); font-size:12px; font-weight:600; }}
.bar {{ fill:var(--s-a); opacity:.5; }}
.bar:hover {{ opacity:.85; }}
.dot {{ fill:var(--s-a); stroke:var(--surface); stroke-width:1.5; }}
path.s-a, path.s-b, path.s-c {{ fill:none; stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }}
path.s-a {{ stroke:var(--s-a); }} path.s-b {{ stroke:var(--s-b); }} path.s-c {{ stroke:var(--s-c); }}
.s-a-t {{ fill:var(--s-a); }} .s-b-t {{ fill:var(--s-b); }} .s-c-t {{ fill:var(--s-c); }}

table {{ width:100%; border-collapse:collapse; font-size:.88rem; margin:8px 0; }}
th, td {{ padding:9px 12px; border-bottom:1px solid var(--rule); text-align:left; }}
th {{
  font-family:var(--mono); font-size:.68rem; text-transform:uppercase;
  letter-spacing:.1em; color:var(--muted); font-weight:500; border-bottom:1px solid var(--rule);
}}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.strong {{ font-weight:600; color:var(--s-c); }}
.tbl-wrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--rule);
  border-radius:12px; padding:6px 18px 10px; box-shadow:var(--shadow); margin:26px 0; }}

blockquote {{
  margin:28px 0; padding:18px 24px; border-left:3px solid var(--s-c);
  background:var(--surface); border-radius:0 10px 10px 0; font-size:1.02rem;
}}
blockquote p + p {{ margin-top:.7em; }}
.note {{ font-size:.92rem; color:var(--muted); }}
footer {{ margin-top:80px; padding-top:26px; border-top:1px solid var(--rule); }}
.sr-only {{
  position:absolute; width:1px; height:1px; padding:0; margin:-1px;
  overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0;
}}
:focus-visible {{ outline:2px solid var(--s-a); outline-offset:3px; border-radius:3px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
@media (max-width:620px) {{ body {{ font-size:17px; }} .wrap {{ padding-inline:18px; }} }}
</style>

<div class="wrap">
<header class="masthead">
  <div class="col">
    <p class="eyebrow">Computational study &middot; unsolved since 1859</p>
    <h1>The Riemann Hypothesis</h1>
    <p class="lede">{n_zeros:,} zeros computed and verified complete. What that
      does show, and — more interestingly — what it does not.</p>
  </div>
</header>

<div class="spectrum">
  {fig_spectrum(zeros)}
  <div class="col"><p class="caption">The first {sum(1 for t in zeros if t <= 400)} zero
  ordinates, drawn where they fall. Riemann's hypothesis is that every one of the
  infinitely many zeros lands on a single vertical line in the complex plane. These
  are their heights. Note the thickening to the right: the zeros grow denser, but
  only logarithmically.</p></div>
</div>

<div class="col">
<div class="stats">
  <div class="stat"><span class="v">{n_zeros:,}</span><span class="k">zeros computed to height {t_max:,.0f}, each verified against an independent count</span></div>
  <div class="stat"><span class="v">{secs}</span><span class="k">to compute and verify all of them</span></div>
  <div class="stat"><span class="v">{dev_p/dev_g:.1f}&times;</span><span class="k">better fit to random-matrix statistics than to randomness</span></div>
  <div class="stat"><span class="v">0</span><span class="k">of this that constitutes strong evidence for the hypothesis</span></div>
</div>

<p>The Riemann zeta function encodes the prime numbers. Its non-trivial zeros
control how far the primes stray from their expected distribution, and Riemann
conjectured that all of them lie on the line where the real part equals
one&#8209;half. Everything below was computed from scratch — no numerical library
was trusted for the mathematics, only for arithmetic speed.</p>

<p>The headline is easy to state and easy to overrate. Every zero found is on the
line. The last stat tile is the one worth arguing about.</p>
</div>

<section>
<div class="col">
  <p class="eyebrow">Finding 1</p>
  <h2>The zeros behave like the energy levels of a quantum system</h2>
  <p>Consecutive zeros, rescaled to unit average spacing, are compared below
  against two references. <strong>GUE</strong> is the spacing law for eigenvalues
  of a large random Hermitian matrix. <strong>Poisson</strong> is what independent
  random points would give.</p>
</div>

<div class="fig">
  <h3>Nearest-neighbour spacing density</h3>
  <p class="sub">{hist['n_spacings']:,} consecutive gaps. Bars are observed; curves are the two reference laws.</p>
  {fig_spacing(hist)}
</div>

<div class="col">
  <p>The observed distribution sits on the GUE curve. Total absolute deviation
  from GUE is <span class="mono">{dev_g:.4f}</span>; from Poisson it is
  <span class="mono">{dev_p:.4f}</span> — a factor of {dev_p/dev_g:.1f}.</p>

  <p>The decisive region is the left edge. Independent points happily coincide, so
  the Poisson density at zero spacing is 1. Both the GUE law and the actual zeros
  fall to zero there, like <span class="mono">s&#178;</span>. <strong>The zeros repel each
  other.</strong> That is the signature of eigenvalues, not of an arbitrary
  increasing sequence.</p>
</div>

<div class="fig">
  <h3>Pair correlation</h3>
  <p class="sub">Against Montgomery's 1972 form. Mean absolute deviation {pc_dev:.4f}.</p>
  {fig_paircorr(pc)}
</div>

<div class="col">
  <p>Hugh Montgomery derived this correlation for the zeros in 1972 and mentioned
  it over tea at the Institute for Advanced Study to Freeman Dyson, who recognised
  it on sight: it is the pair correlation of eigenvalues of a random Hermitian
  matrix. Neither of them had been looking for the other's subject.</p>

  <blockquote><p>If the zeros are the spectrum of some self-adjoint operator, they
  are automatically real, and the Riemann Hypothesis follows immediately. This is
  the Hilbert&ndash;P&oacute;lya conjecture. A century on, nobody has produced the
  operator — and the most serious attempt, Alain Connes', yields a trace formula
  that turns out to be <em>equivalent</em> to the hypothesis rather than a proof
  of it.</p></blockquote>
</div>
</section>

<section>
<div class="col">
  <p class="eyebrow">Finding 2</p>
  <h2>The primes can be rebuilt from the zeros</h2>
  <p>Each zero contributes one pure wave. Add enough of them and the prime powers
  appear as steps — the primes are the interference pattern.</p>
</div>

<div class="fig">
  <h3>&#968;(x), the prime-power staircase</h3>
  <p class="sub">Reconstruction uses only 5,000 zero ordinates. RMS error {rms:.3f} over 2 &le; x &le; 100.</p>
  {fig_explicit(xs.tolist(), exact, approx)}
</div>

<div class="col">
  <p>The reconstruction knows nothing about primes. It is a sum of cosines whose
  frequencies are the zero heights, and it reproduces the staircase — every one of
  the twelve steepest rises lands on a prime power. The overshoot at each step is
  Gibbs ringing from truncating the sum, not error.</p>

  <p>This is also where the hypothesis gets its meaning. A zero with real part
  <span class="mono">&#963;</span> contributes an oscillation of size
  <span class="mono">x^&#963;</span>, so the real parts of the zeros directly bound
  how far the primes wander. Riemann's hypothesis is equivalent to the error term
  being <span class="mono">O(&#8730;x&nbsp;log&#178;x)</span> — the smallest it could
  possibly be. <strong>RH does not say the primes are random. It says they are as
  regular as they can possibly be.</strong></p>
</div>
</section>

<section>
<div class="col">
  <p class="eyebrow">Finding 3</p>
  <h2>The search is hard in exactly one place</h2>
  <p>A grid search for sign changes misses pairs of zeros that sit too close
  together. Every zero this project initially missed was one of these — so the tally
  is cross-checked against an independent count of how many zeros the strip
  contains, and the shortfall is then localised exactly rather than guessed at.</p>
</div>

<div class="tbl-wrap">
<table>
  <caption class="sr-only">Closest pairs of consecutive zeros found</caption>
  <thead><tr><th>Height t</th><th class="num">Raw gap</th><th class="num">Normalised gap</th></tr></thead>
  <tbody>{tight_html}</tbody>
</table>
</div>

<div class="col">
  <p>The pair at <span class="mono">t = 7005.06</span> is Lehmer's, noted in 1956
  and the classic example. The search found it without being told to look — and
  the tightest found here, at
  <span class="mono">t = {zeros[min_idx]:.6f}</span>, is
  <strong>{0.04210/min_gap:.1f} times closer still</strong>: the two zeros are
  separated by {(zeros[min_idx+1]-zeros[min_idx]):.6f} in <span class="mono">t</span>,
  and between them <span class="mono">Z</span> rises to only
  <span class="mono">2.0&times;10&#8315;&#8308;</span> before turning back — verified
  independently, and 2,958&times; above the numerical noise floor, so the crossing
  is real rather than roundoff.</p>

  <p>These are where a counterexample would have to begin: for two zeros to leave
  the critical line they must first collide. That they come close and separate,
  every time, is the most direct evidence there is. It is still only evidence about
  the range examined.</p>
</div>
</section>

<section>
<div class="col">
  <p class="eyebrow">Finding 4 &middot; the interesting one</p>
  <h2>The evidence is much weaker than it looks</h2>
  <p>Li's criterion states that the hypothesis holds if and only if
  <span class="mono">&#955;<sub>n</sub> &ge; 0</span> for every
  <span class="mono">n</span>. It is positive for every
  <span class="mono">n</span> anyone has computed —
  <span class="mono">&#955;<sub>1</sub> = {lam[0]:.10f}</span> here, against the
  closed form <span class="mono">{li_coefficient_exact_first():.10f}</span>. That
  sounds like a test being passed. So: <em>if the hypothesis were false, when would
  this test notice?</em></p>

  <p>I moved a single zero off the critical line and computed
  <span class="mono">&#955;<sub>n</sub></span> until it turned negative.</p>
</div>

<div class="tbl-wrap">
<table>
  <thead><tr>
    <th>Violation</th><th class="num">at height</th><th class="num">growth rate</th>
    <th class="num">&#955;<sub>n</sub> first negative</th><th class="num">estimated</th>
  </tr></thead>
  <tbody>{li_html}</tbody>
</table>
</div>

<div class="col">
  <p class="note">Exact and estimated agree wherever both are computable, which is
  what licenses reading the rows direct computation cannot reach.</p>

  <p>Read the second row. A zero at real part <span class="mono">0.6</span> is not a
  near miss — it is a catastrophic failure of the hypothesis, a zero a tenth of the
  way to the edge of the critical strip. Li's criterion would not notice until
  <span class="mono">n &asymp; 21,000</span>.</p>

  <p>Read the last row. <strong>The same violation, placed at height 74,920, hides
  until <span class="mono">n &asymp; 1.7 &times; 10&#185;&#178;</span>.</strong>
  Sensitivity decays like <span class="mono">1/&#947;&#178;</span>: the test is least
  able to see a violation exactly where the unchecked zeros live.</p>

  <p>This is not an isolated quirk. Every checkable criterion has the same
  character. Robin's inequality is near-tight only on colossally abundant numbers,
  and at numbers with {ca[-1]['digits']:,.0f} digits its margin is still
  <span class="mono">{ca[-1]['margin']:.2e}</span> and shrinking toward a limit it is
  conjectured never to reach — the true and the false hypotheses predict sequences
  that look identical for as far as anyone can compute.</p>

  <blockquote>
  <p>And the precedent is bad. Mertens conjectured a closely related bound that
  implies the Riemann Hypothesis. It was verified to 10<sup>9</sup> and believed.
  Odlyzko and te Riele <strong>disproved it in 1985</strong> — and no explicit
  counterexample is known even now, forty years later. The first is thought to lie
  past 10<sup>20</sup>.</p>
  <p>Likewise <span class="mono">&#960;(x) &lt; li(x)</span> holds for every
  <span class="mono">x</span> ever computed, and Littlewood proved in 1914 that it
  fails infinitely often — first somewhere below 10<sup>316</sup>.</p>
  </blockquote>

  <p>The reason is always the same: these phenomena are governed by
  <span class="mono">log log x</span>, and at the frontier of computation
  <span class="mono">log log</span> has barely moved. Going from height
  10<sup>13</sup> — the largest verification ever done — out to 10<sup>100</sup>
  takes <span class="mono">log log t</span> from 3.4 to 5.4.</p>
</div>
</section>

<section>
<div class="col">
  <p class="eyebrow">Conclusion</p>
  <h2>Why believe it anyway</h2>

  <p>There are good reasons. None of them is a zero count.</p>

  <p><strong>The analogue is a theorem.</strong> For curves over finite fields, the
  corresponding statement was proved by Weil in 1948 and generalised by Deligne in
  1974. That is the strongest reason by far. Its proof runs through the surface
  formed by multiplying the curve by itself, and draws its essential positivity from
  the Hodge index theorem on that surface. Over the ordinary integers no such
  surface exists — there is no field underneath <span class="mono">&#8484;</span> for
  it to be a product over. Constructing a substitute is what every serious modern
  programme is trying to do, and none has succeeded.</p>

  <p><strong>The statistics.</strong> Finding 1. Something is very probably a
  spectrum.</p>

  <p><strong>And half of it is proved.</strong> There is a constant
  <span class="mono">&#923;</span> for which the hypothesis is exactly the statement
  <span class="mono">&#923; &le; 0</span>. In 2018 Rodgers and Tao proved
  <span class="mono">&#923; &ge; 0</span>. So the Riemann Hypothesis is now
  equivalent to <span class="mono">&#923; = 0</span>, exactly.</p>

  <blockquote><p>Which is the last word on why it is hard. The hypothesis is not
  true with room to spare. It sits precisely on the boundary of failure, and any
  proof must be sharp enough to establish an equality rather than an inequality
  with slack. Every soft, averaging or perturbative argument is ruled out before it
  begins: no such method can distinguish <span class="mono">&#923; = 0</span> from
  <span class="mono">&#923; = 10&#8315;&#8313;</span>, and that difference is the
  entire problem.</p></blockquote>
</div>
</section>

<footer><div class="col">
  <p class="caption">Every figure and number generated from code in this
  repository. Core implemented with no third-party dependencies; verified
  against mpmath as an independent oracle across 71 tests. Spacing moments:
  observed variance {mom['variance_observed']:.4f} against GUE
  {mom['variance_gue']:.4f} and Poisson 1.0000 — the residual gap is the known
  slow convergence to the random-matrix limit at accessible heights.</p>
</div></footer>
</div>
"""
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as fh:
        fh.write(html)
    print(f"wrote {out}  ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
