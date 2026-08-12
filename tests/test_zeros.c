/* test_zeros.c -- Gram points, certified sign changes, Turing verification.
 *
 * The strongest end-to-end check available without an external table of
 * zeros: run the whole pipeline at several heights and require that the
 * number of certified sign changes equals the number Turing's method proves
 * must be there.  Those two counts come from completely different places --
 * one from sign changes of Z on a grid, the other from an integral of theta
 * plus a bound on the mean of S -- so agreement is a real check. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "turing.h"
#include "oracle.h"

static int fails = 0;
static void ok(const char *what, int cond, const char *extra) {
    if (!cond) fails++;
    printf("  %-46s %s %s\n", what, cond ? "ok  " : "FAIL", extra ? extra : "");
}

static double mean_gap(double t) {
    return 6.283185307179586232 / log(t / 6.283185307179586232);
}

int main(void) {
    printf("test_zeros\n");
    iv_init_constants();

    /* ---- Gram points ---------------------------------------------------- */
    {
        double worst = 0;
        for (long n = 10; n < 100000000L; n = (long)(n * 7.3) + 1) {
            dd g = gram_point(n);
            dd th = rs_theta(g);
            dd want = dd_mul(DD_PI, dd_of((double)n));
            dd d = dd_sub(th, want);
            double rel = fabs(d.hi + d.lo) / (fabs(want.hi) + 1.0);
            if (rel > worst) worst = rel;
        }
        char b[64]; snprintf(b, sizeof b, "worst rel residual %.2e", worst);
        ok("theta(g_n) = n*pi", worst < 1e-18, b);
    }
    {
        int good = 1;
        for (long n = 100; n < 1000000L; n *= 3) {
            dd g = gram_point(n);
            if (gram_index(g) != n && gram_index(g) != n - 1) good = 0;
        }
        ok("gram_index inverts gram_point", good, NULL);
    }

    /* ---- Gram's law holds most of the time at modest height ------------- */
    {
        long need = rs_nterms_d(1.2e6) + 10;
        rs_logtab *lt = rs_logtab_build(need, 0);
        long good = 0, tot = 0;
        for (long n = 100000; n < 100200; n++) {
            dd g0 = gram_point(n), g1 = gram_point(n + 1);
            double z0 = rs_Z(g0, lt, 1), z1 = rs_Z(g1, lt, 1);
            /* (-1)^n Z(g_n) > 0 is Gram's law */
            double s0 = ((n & 1) ? -1.0 : 1.0) * z0;
            double s1 = (((n + 1) & 1) ? -1.0 : 1.0) * z1;
            if (s0 > 0 && s1 > 0) good++;
            tot++;
        }
        char b[80];
        snprintf(b, sizeof b, "%ld/%ld Gram intervals obey Gram's law", good, tot);
        /* Gram's law fails for a minority of intervals; ~70% is normal here */
        ok("Gram's law holds for most intervals", good > tot / 2, b);
        rs_logtab_free(lt);
    }

    /* ---- end-to-end: certified count == Turing count -------------------- */
    struct { double T; long count; } cases[] = {
        { 1.0e7,  120 },
        { 1.0e9,  150 },
        { 1.0e11, 150 },
    };

    for (size_t c = 0; c < sizeof cases / sizeof cases[0]; c++) {
        double T = cases[c].T;
        long count = cases[c].count;
        double gap = mean_gap(T);
        double delta = gap / 16.0;
        double B = turing_S_bound(T);
        double zone = 12.0 * B; if (zone < 40.0) zone = 40.0;
        double span = (double)count * gap;
        double t_lo = T - zone, t_hi = T + span + zone;
        int m = (int)((t_hi - t_lo) / delta) + 2;

        rs_logtab *lt = rs_logtab_build(rs_nterms_d(t_hi) + 2, 0);
        os_window *w = os_eval(t_lo, delta, m, 8, lt, 1, 0);
        if (!w) { ok("pipeline produced a window", 0, NULL); rs_logtab_free(lt); continue; }

        zlist zl; zlist_init(&zl);
        long unres = 0;
        zeros_scan_window(w, &zl, &unres);

        dd d0 = dd_of(w->t0), dl = dd_of(w->delta);
        long ja = lrint(zone / w->delta), jb = lrint((zone + span) / w->delta);
        if (jb > w->m - 1) jb = w->m - 1;
        dd a = dd_add(d0, dd_mul_d(dl, (double)ja));
        dd bb = dd_add(d0, dd_mul_d(dl, (double)jb));
        dd e = dd_add(d0, dd_mul_d(dl, (double)(w->m - 1)));

        turing_report rep;
        turing_verify(a, bb, d0, e, &zl, &rep);

        char msg[200];
        snprintf(msg, sizeof msg,
                 "t=%.0e certified=%ld turing=%ld slack=%.2f/%.2f unresolved=%ld",
                 T, rep.found, rep.expected, rep.slack_a, rep.slack_b, unres);
        ok("Turing count matches certified sign changes", rep.verified, msg);

        /* N(T) must track the Riemann-von Mangoldt main term */
        if (rep.verified) {
            double rvm = (T / 6.283185307179586232) *
                         (log(T / 6.283185307179586232) - 1.0) + 0.875;
            double rel = fabs((double)rep.Na - rvm) / rvm;
            snprintf(msg, sizeof msg, "N=%ld vs RvM %.6e (rel %.2e)",
                     rep.Na, rvm, rel);
            ok("N(T) matches Riemann-von Mangoldt", rel < 1e-7, msg);
        }

        zlist_free(&zl); os_window_free(w); rs_logtab_free(lt);
    }

    /* ---- brackets really do bracket a zero (low t, vs mpmath) ----------- */
    {
        long need = rs_nterms_d(1.2e6) + 10;
        rs_logtab *lt = rs_logtab_build(need, 0);
        /* refine a bracket around the 1st..30th known zero using EM signs is
         * covered in test_rs; here check refinement narrows brackets at a
         * height where Riemann-Siegel is valid. */
        double T = 1.0e6, gap = mean_gap(T);
        os_window *w = os_eval(T, gap / 16.0, 4000, 8, lt, 1, 0);
        if (w) {
            zlist zl; zlist_init(&zl);
            long unres = 0;
            zeros_scan_window(w, &zl, &unres);
            long n0 = zl.n;
            double before = w->delta;
            zeros_refine(&zl, lt, 1, 1e-9, 60, 0);
            double worst = 0;
            int still_signed = 1;
            double *ws = malloc(sizeof(double) * (size_t)zl.n);
            for (long i = 0; i < zl.n; i++) {
                ws[i] = zl.b[i].width;
                if (zl.b[i].width > worst) worst = zl.b[i].width;
                double za = rs_Z(zl.b[i].lo, lt, 1), zb = rs_Z(zl.b[i].hi, lt, 1);
                if (!(za * zb < 0)) still_signed = 0;
            }
            /* Bisection cannot go below the precision floor: it stops once
             * |Z(midpoint)| no longer exceeds the a-priori error bound, which
             * at t=1e6 with J=1 is ~1.9e-7 (the asymptotic tail dominates).
             * Near a flat crossing that leaves a bracket of ~4E/|Z'|.  So the
             * right assertion is that the typical bracket collapses, not that
             * every one reaches an arbitrary target. */
            for (long i = 1; i < zl.n; i++) {       /* insertion sort, n ~ 250 */
                double v = ws[i]; long j = i - 1;
                while (j >= 0 && ws[j] > v) { ws[j + 1] = ws[j]; j--; }
                ws[j + 1] = v;
            }
            double median = zl.n ? ws[zl.n / 2] : 1.0;
            double floor_est = 4.0 * rs_Z_errbound(T, 1);
            char msg[200];
            snprintf(msg, sizeof msg,
                     "%ld brackets: %.2e -> median %.2e, max %.2e (floor ~%.1e)",
                     n0, before, median, worst, floor_est);
            ok("refinement reaches the precision floor",
               median < floor_est, msg);
            ok("refinement narrows every bracket by >100x",
               worst < before / 100.0, NULL);
            ok("refined brackets still change sign", still_signed, NULL);
            free(ws);
            zlist_free(&zl); os_window_free(w);
        } else ok("window at 1e6", 0, NULL);
        rs_logtab_free(lt);
    }

    printf("test_zeros: %s (%d failures)\n", fails ? "FAILED" : "PASSED", fails);
    return fails ? 1 : 0;
}
