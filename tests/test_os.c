/* test_os.c -- Odlyzko-Schoenhage multi-evaluation vs direct Riemann-Siegel.
 *
 * The O-S grid values must agree with rs_Z at every grid point to within the
 * error bound the window reports, at several heights and grid geometries. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "os.h"
#include "fft.h"

static int fails = 0;
static void ok(const char *what, int cond, const char *extra) {
    if (!cond) fails++;
    printf("  %-46s %s %s\n", what, cond ? "ok  " : "FAIL", extra ? extra : "");
}

/* ---- FFT sanity --------------------------------------------------------- */
static void test_fft(void) {
    for (int n = 8; n <= 4096; n <<= 2) {
        fft_plan *p = fft_plan_new(n);
        double complex *a = malloc(sizeof(double complex) * n);
        double complex *b = malloc(sizeof(double complex) * n);
        unsigned long long s = 12345;
        for (int i = 0; i < n; i++) {
            s ^= s << 13; s ^= s >> 7; s ^= s << 17;
            double re = (double)(s >> 11) / 9007199254740992.0 - 0.5;
            s ^= s << 13; s ^= s >> 7; s ^= s << 17;
            double im = (double)(s >> 11) / 9007199254740992.0 - 0.5;
            a[i] = re + im * I; b[i] = a[i];
        }
        fft_forward(p, b);
        fft_inverse(p, b);
        double worst = 0;
        for (int i = 0; i < n; i++) {
            double d = cabs(a[i] - b[i]);
            if (d > worst) worst = d;
        }
        char msg[80]; snprintf(msg, sizeof msg, "n=%d round-trip err %.2e", n, worst);
        ok("fft forward/inverse round trip", worst < 1e-13, msg);

        /* against a direct DFT at a few frequencies */
        fft_forward(p, b = memcpy(b, a, sizeof(double complex) * n));
        double wd = 0;
        for (int kk = 0; kk < n; kk += (n / 4 ? n / 4 : 1)) {
            double complex acc = 0;
            for (int i = 0; i < n; i++)
                acc += a[i] * cexp(-2.0 * I * 3.14159265358979323846 * kk * i / n);
            double d = cabs(acc - b[kk]);
            if (d > wd) wd = d;
        }
        snprintf(msg, sizeof msg, "n=%d vs direct DFT %.2e", n, wd);
        ok("fft matches direct DFT", wd < 1e-11, msg);
        free(a); free(b); fft_plan_free(p);
    }
}

int main(void) {
    printf("test_os\n");
    iv_init_constants();
    test_fft();

    struct { double t; int m; int over; double dtarget; } cases[] = {
        { 1.0e6,  512, 8,  0.02 },
        { 1.0e7,  512, 8,  0.02 },
        { 1.0e8,  400, 16, 0.01 },
        { 1.0e9,  300, 8,  0.03 },
    };

    long need = rs_nterms_d(1.1e9) + 10;
    rs_logtab *lt = rs_logtab_build(need, 0);
    if (!lt) { printf("  log table alloc FAILED\n"); return 1; }

    for (size_t c = 0; c < sizeof cases / sizeof cases[0]; c++) {
        double t0 = cases[c].t;
        os_window *w = os_eval(t0, cases[c].dtarget, cases[c].m,
                               cases[c].over, lt, 1, 0);
        if (!w) { ok("os_eval returned a window", 0, NULL); continue; }

        /* compare against direct RS at every grid point */
        double worst = 0; int within = 1;
        for (int j = 0; j < w->m; j++) {
            dd tj = dd_add(dd_of(w->t0), dd_mul_d(dd_of(w->delta), (double)j));
            double zd = rs_Z(tj, lt, 1);
            double d = fabs(zd - w->Z[j]);
            if (d > worst) worst = d;
            if (d > w->err) within = 0;
        }
        char msg[160];
        snprintf(msg, sizeof msg,
                 "t=%.0e max|OS-direct|=%.2e bound=%.2e ratio=%.3f",
                 t0, worst, w->err, worst / w->err);
        ok("O-S agrees with direct RS within bound", within, msg);

        /* the window must actually contain sign changes (sanity) */
        int changes = 0;
        for (int j = 1; j < w->m; j++)
            if (w->Z[j - 1] * w->Z[j] < 0) changes++;
        snprintf(msg, sizeof msg, "%d sign changes over %g in t",
                 changes, w->m * w->delta);
        ok("window contains sign changes", changes > 0, msg);

        os_window_free(w);
    }

    /* speed-up check: one O-S window vs m direct evaluations, at 1e9 */
    {
        double t0 = 1.0e9;
        int m = 2000;
        os_window *w = os_eval(t0, 0.02, m, 8, lt, 1, 0);
        if (w) {
            char msg[160];
            snprintf(msg, sizeof msg,
                     "%d points in %.2fs (coef %.2fs + fft %.2fs)",
                     m, w->secs_total, w->secs_coef, w->secs_fft);
            ok("O-S evaluates a large grid quickly", w->secs_total < 20.0, msg);
            os_window_free(w);
        } else ok("O-S large grid", 0, NULL);
    }

    rs_logtab_free(lt);
    printf("test_os: %s (%d failures)\n", fails ? "FAILED" : "PASSED", fails);
    return fails ? 1 : 0;
}
