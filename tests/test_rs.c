/* test_rs.c -- Riemann-Siegel and Euler-Maclaurin against an mpmath oracle. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "rs.h"
#include "oracle.h"

static int fails = 0;
static void ok(const char *what, int cond, const char *extra) {
    if (!cond) fails++;
    printf("  %-40s %s %s\n", what, cond ? "ok  " : "FAIL", extra ? extra : "");
}

int main(void) {
    printf("test_rs\n");
    iv_init_constants();

    long need = rs_nterms_d(1.1e7) + 10;
    rs_logtab *lt = rs_logtab_build(need, 0);
    if (!lt) { printf("  log table alloc FAILED\n"); return 1; }

    /* --- theta ---------------------------------------------------------- */
    {
        double worst = 0;
        for (int i = 0; i < ORACLE_N; i++) {
            double got = rs_theta_mod2pi_d(ORACLE[i].t);
            double want = ORACLE[i].theta_mod2pi;
            double d = fabs(got - want);
            if (d > 3.0) d = fabs(d - 2.0 * 3.141592653589793);  /* wrap */
            if (d > worst) worst = d;
        }
        char b[64]; snprintf(b, sizeof b, "max err %.2e", worst);
        ok("theta mod 2pi vs mpmath", worst < 1e-12, b);
    }

    /* --- theta inverse --------------------------------------------------- */
    {
        double worst = 0;
        for (double target = 10; target < 1e9; target *= 3.3) {
            double t = rs_theta_inv(target);
            dd th = rs_theta(dd_of(t));
            double d = fabs((th.hi + th.lo) - target);
            if (d > worst) worst = d;
        }
        char b[64]; snprintf(b, sizeof b, "max residual %.2e", worst);
        ok("rs_theta_inv round trip", worst < 1e-6, b);
    }

    /* --- Psi ------------------------------------------------------------- */
    {
        /* Psi is real-analytic through p = 1/4 and 3/4; check continuity by
         * comparing against the naive formula away from those points. */
        double worst = 0;
        for (int i = 1; i < 1000; i++) {
            double p = (double)i / 1000.0;
            if (fabs(p - 0.25) < 0.02 || fabs(p - 0.75) < 0.02) continue;
            double naive = cos(2 * 3.14159265358979323846 * (p * p - p - 1.0 / 16.0)) / cos(2 * 3.14159265358979323846 * p);
            dd got = rs_psi(dd_of(p));
            double d = fabs((got.hi + got.lo) - naive);
            if (d > worst) worst = d;
        }
        char b[64]; snprintf(b, sizeof b, "max dev %.2e", worst);
        ok("rs_psi matches naive formula", worst < 1e-12, b);

        /* and that it stays finite and smooth across the removable poles */
        int smooth = 1;
        for (double p = 0.24; p <= 0.26; p += 0.0005) {
            dd v = rs_psi(dd_of(p));
            if (!(fabs(v.hi) < 2.0)) smooth = 0;
        }
        ok("rs_psi finite across p = 1/4", smooth, NULL);
    }

    /* --- Z via Riemann-Siegel ------------------------------------------- */
    {
        double worst = 0; double worst_t = 0;
        for (int i = 0; i < ORACLE_N; i++) {
            double t = ORACLE[i].t;
            double got = rs_Z_d(t, lt, 1);
            double d = fabs(got - ORACLE[i].Z);
            if (d > worst) { worst = d; worst_t = t; }
        }
        char b[96]; snprintf(b, sizeof b, "max err %.2e at t=%g", worst, worst_t);
        /* J=1 truncation dominates at the low end (t=100 gives ~1e-4) */
        ok("rs_Z vs mpmath siegelz", worst < 2e-4, b);
    }

    /* --- the a-priori error bound must actually hold --------------------- */
    {
        int held = 1; double worst_ratio = 0;
        for (int i = 0; i < ORACLE_N; i++) {
            double t = ORACLE[i].t;
            double got = rs_Z_d(t, lt, 1);
            double e = rs_Z_errbound(t, 1);
            double d = fabs(got - ORACLE[i].Z);
            if (d > e) held = 0;
            double r = d / e;
            if (r > worst_ratio) worst_ratio = r;
        }
        char b[64]; snprintf(b, sizeof b, "worst actual/bound = %.3f", worst_ratio);
        ok("rs_Z_errbound holds on oracle", held, b);
    }

    /* --- fully rigorous interval path ------------------------------------ */
    {
        int enclosed = 1; double worst_w = 0;
        for (int i = 0; i < ORACLE_N && ORACLE[i].t <= 2e5; i++) {
            iv z = rs_Z_iv(dd_of(ORACLE[i].t), lt, 1);
            if (!(z.lo <= ORACLE[i].Z && ORACLE[i].Z <= z.hi)) enclosed = 0;
            if (iv_wid(z) > worst_w) worst_w = iv_wid(z);
        }
        char b[64]; snprintf(b, sizeof b, "max width %.2e", worst_w);
        ok("rs_Z_iv encloses true Z", enclosed, b);
    }

    /* --- Euler-Maclaurin, independent path ------------------------------- */
    {
        int enclosed = 1; double worst_w = 0; double worst_err = 0;
        for (int i = 0; i < ORACLE_N && ORACLE[i].t <= 6e4; i++) {
            iv z = em_Z_iv(ORACLE[i].t, 0, 14);
            if (!(z.lo <= ORACLE[i].Z && ORACLE[i].Z <= z.hi)) enclosed = 0;
            double d = fabs(iv_mid(z) - ORACLE[i].Z);
            if (d > worst_err) worst_err = d;
            if (iv_wid(z) > worst_w) worst_w = iv_wid(z);
        }
        char b[96]; snprintf(b, sizeof b, "max width %.2e, max err %.2e", worst_w, worst_err);
        ok("em_Z_iv encloses true Z", enclosed, b);
    }

    /* --- RS and EM must agree with each other (independent algorithms) ----
     * At these heights the J=1 asymptotic truncation is the whole story
     * (~1e-6 at t=5000), so the meaningful assertion is that the two paths
     * agree to within the a-priori RS bound, not to some absolute figure. */
    {
        double worst = 0, worst_ratio = 0; int held = 1;
        for (double t = 5000.0; t < 20000.0; t += 137.7) {
            double a = rs_Z_d(t, lt, 1);
            iv b_ = em_Z_iv(t, 0, 14);
            double d = fabs(a - iv_mid(b_));
            double e = rs_Z_errbound(t, 1);
            if (d > e) held = 0;
            if (d > worst) worst = d;
            if (d / e > worst_ratio) worst_ratio = d / e;
        }
        char b[96];
        snprintf(b, sizeof b, "max diff %.2e, worst diff/bound %.3f", worst, worst_ratio);
        ok("RS vs Euler-Maclaurin within RS bound", held, b);
    }

    /* --- known zeros: a *certified* sign change across each ----------------
     * The first zeros sit at t ~ 14..100, where the RS main sum has only a
     * handful of terms and the asymptotic remainder is useless; Euler-
     * Maclaurin is the right tool there.  Requiring iv_sign to be rigorously
     * determined and opposite on the two sides certifies a zero of odd order
     * strictly between them. */
    {
        int good = 1; double eps = 1e-3;
        for (int i = 0; i < ORACLE_ZEROS_N; i++) {
            double g = ORACLE_ZEROS[i];
            iv a = em_Z_iv(g - eps, 0, 14), b_ = em_Z_iv(g + eps, 0, 14);
            int sa = iv_sign(a), sb = iv_sign(b_);
            if (sa == 0 || sb == 0 || sa == sb) good = 0;
        }
        ok("certified sign change at 30 known zeros", good, NULL);
    }

    /* --- RS reproduces EM's sign pattern where RS is valid ---------------- */
    {
        int good = 1; int n = 0;
        for (double t = 1e5; t < 1e5 + 8.0; t += 0.043) {
            double a = rs_Z_d(t, lt, 1);
            iv b_ = em_Z_iv(t, 0, 14);
            if (fabs(a) > 1e-3 && iv_sign(b_) != 0) {
                if ((a > 0) != (iv_sign(b_) > 0)) good = 0;
                n++;
            }
        }
        char b[64]; snprintf(b, sizeof b, "%d points compared", n);
        ok("RS and EM signs agree at t~1e5", good, b);
    }

    rs_logtab_free(lt);
    printf("test_rs: %s (%d failures)\n", fails ? "FAILED" : "PASSED", fails);
    return fails ? 1 : 0;
}
