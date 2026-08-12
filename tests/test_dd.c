/* test_dd.c -- double-double arithmetic against exact / high-precision values. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "dd.h"

static int fails = 0;

static void chk(const char *what, dd got, const char *want_hi, const char *want_lo,
                double tol) {
    double wh = strtod(want_hi, NULL), wl = strtod(want_lo, NULL);
    dd want = dd_mk(wh, wl);
    dd d = dd_sub(got, want);
    double e = fabs(d.hi + d.lo);
    double rel = e / (fabs(wh) + 1e-300);
    int ok = rel <= tol;
    if (!ok) fails++;
    printf("  %-28s %s  rel err %8.2e (tol %.0e)\n", what, ok ? "ok  " : "FAIL", rel, tol);
}

int main(void) {
    printf("test_dd\n");

    /* exactness of the error-free transformations */
    {
        double a = 1.0 + 0x1p-30, b = 1.0 + 0x1p-25;
        dd p = dd_two_prod(a, b);
        double exact = 1.0 + 0x1p-25 + 0x1p-30 + 0x1p-55;
        if (p.hi + p.lo != exact) { printf("  two_prod                     FAIL\n"); fails++; }
        else                        printf("  two_prod exact               ok\n");
        dd s = dd_two_sum(1e17, 1.0);
        if (s.hi + s.lo != 1e17 + 1.0 && s.lo != 1.0) { printf("  two_sum   FAIL\n"); fails++; }
        else printf("  two_sum exact                ok\n");
    }

    /* pi, log 2, e -- reference digits from mpmath (50 dps) */
    chk("dd_log(2)",   dd_log(dd_of(2.0)),
        "6.931471805599452862e-01", "2.319046813846299558e-17", 1e-31);
    chk("dd_exp(1)",   dd_exp(dd_of(1.0)),
        "2.718281828459045091e+00", "1.445646891729250158e-16", 1e-31);
    chk("dd_sqrt(2)",  dd_sqrt(dd_of(2.0)),
        "1.414213562373095145e+00", "-9.667293313452913451e-17", 1e-31);
    chk("dd_log(1e7+3)", dd_log(dd_of(10000003.0)),
        "1.611809595095827419e+01", "6.008203396134321307e-16", 1e-31);

    /* round trips */
    {
        dd x = dd_mk(1.2345678901234567e1, 4.5678901234e-16);
        dd y = dd_log(dd_exp(x));
        dd d = dd_sub(y, x);
        double rel = fabs(d.hi + d.lo) / fabs(x.hi);
        int ok = rel < 1e-30;
        if (!ok) fails++;
        printf("  log(exp(x)) round trip       %s  rel err %8.2e\n", ok ? "ok  " : "FAIL", rel);
    }

    /* sin^2 + cos^2 = 1 at a large argument (exercises mod-2pi reduction) */
    {
        double worst = 0;
        for (int i = 0; i < 2000; i++) {
            dd x = dd_of(1e15 * ((double)i / 2000.0 + 0.13));
            dd s, c;
            dd_sincos(x, &s, &c);
            dd one = dd_add(dd_mul(s, s), dd_mul(c, c));
            dd d = dd_sub_d(one, 1.0);
            double e = fabs(d.hi + d.lo);
            if (e > worst) worst = e;
        }
        int ok = worst < 1e-29;
        if (!ok) fails++;
        printf("  sin^2+cos^2=1 at t~1e15      %s  max err %8.2e\n", ok ? "ok  " : "FAIL", worst);
    }

    /* mod 2pi: reducing k*2pi + a must return a.  This is the accuracy that
     * limits the Riemann-Siegel phase at t = 1e15, so measure it honestly:
     * build k*2pi in dd, add a known offset, reduce, compare. */
    {
        double worst = 0;
        for (long k = 1; k <= 4000; k++) {
            double a = 0.7 + 0.0001 * (double)(k % 100);
            dd x = dd_add_d(dd_mul_d(DD_2PI, (double)(k * 700000000L)), a);
            double r = dd_mod_2pi(x);
            double e = fabs(r - a);
            if (e > worst) worst = e;
        }
        int ok = worst < 1e-14;
        if (!ok) fails++;
        printf("  mod2pi(k*2pi+a), k~2.8e12    %s  max err %8.2e\n",
               ok ? "ok  " : "FAIL", worst);
    }

    printf("test_dd: %s (%d failures)\n", fails ? "FAILED" : "PASSED", fails);
    return fails ? 1 : 0;
}
