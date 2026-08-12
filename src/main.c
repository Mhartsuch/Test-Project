/* main.c -- driver for the Odlyzko-Schoenhage zero computation.
 *
 *   zeta selftest                     arithmetic and constant checks
 *   zeta eval   T [J]                 Z(T) by direct Riemann-Siegel
 *   zeta window T COUNT [opts]        O-S grid, report timings
 *   zeta zeros  T COUNT [opts]        locate and certify zeros near T
 *   zeta verify T COUNT [opts]        as `zeros', plus Turing verification
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "turing.h"

int iv_verify_constants(int verbose);

static double now_s(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

static void usage(void) {
    fprintf(stderr,
      "usage:\n"
      "  zeta selftest\n"
      "  zeta eval   T [J]\n"
      "  zeta window T COUNT [--delta D] [--over K] [--J j]\n"
      "  zeta zeros  T COUNT [--delta D] [--over K] [--J j] [--refine W] [--list]\n"
      "  zeta verify T COUNT [--zone L] [--delta D] [--over K] [--J j] [--list]\n"
      "\n"
      "  T      height (accepts 1e15)\n"
      "  COUNT  approximate number of zeros to cover\n"
      "  --delta   grid spacing (default: mean zero gap / 16)\n"
      "  --over    FFT oversampling Q/M (default 8)\n"
      "  --J       Riemann-Siegel correction terms, 0 or 1 (default 1)\n"
      "  --zone    Turing zone length in t on each side (default: auto)\n"
      "  --refine  bisect brackets to this width (default: no refinement)\n"
      "  --list    print each certified zero\n");
}

/* mean spacing between zeros at height t */
static double mean_gap(double t) {
    return 6.283185307179586232 / log(t / 6.283185307179586232);
}

static void print_dd(const char *pre, dd x, const char *post) {
    /* print enough digits that a dd height is unambiguous */
    printf("%s%.6f%+.17e%s", pre, x.hi, x.lo, post);
}

int main(int argc, char **argv) {
    if (argc < 2) { usage(); return 2; }
    iv_init_constants();

    const char *cmd = argv[1];

    if (!strcmp(cmd, "selftest")) {
        int bad = iv_self_test();
        bad += iv_verify_constants(1);
        printf("selftest: %s\n", bad ? "FAILED" : "PASSED");
        return bad ? 1 : 0;
    }

    if (argc < 3) { usage(); return 2; }
    double T = strtod(argv[2], NULL);
    if (!(T > 100.0)) { fprintf(stderr, "T must exceed 100\n"); return 2; }

    if (!strcmp(cmd, "eval")) {
        int J = (argc > 3) ? atoi(argv[3]) : 1;
        long N = rs_nterms_d(T);
        fprintf(stderr, "building log table for N = %ld ...\n", N);
        rs_logtab *lt = rs_logtab_build(N + 2, 1);
        if (!lt) { fprintf(stderr, "out of memory\n"); return 1; }
        double t0 = now_s();
        double z = rs_Z_d(T, lt, J);
        double t1 = now_s();
        printf("t          = %.17g\n", T);
        printf("N terms    = %ld\n", N);
        printf("theta mod 2pi = %.17g\n", rs_theta_mod2pi_d(T));
        printf("Z(t)       = %.15g\n", z);
        printf("error bd   = %.3e\n", rs_Z_errbound(T, J));
        printf("time       = %.3f s\n", t1 - t0);
        rs_logtab_free(lt);
        return 0;
    }

    long count = (argc > 3) ? strtol(argv[3], NULL, 10) : 100;
    if (count < 1) count = 1;

    double delta = -1, zone = -1, refine = -1;
    int over = 8, J = 1, list = 0;
    for (int i = 4; i < argc; i++) {
        if (!strcmp(argv[i], "--delta") && i + 1 < argc) delta = strtod(argv[++i], NULL);
        else if (!strcmp(argv[i], "--over") && i + 1 < argc) over = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--J") && i + 1 < argc) J = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--zone") && i + 1 < argc) zone = strtod(argv[++i], NULL);
        else if (!strcmp(argv[i], "--refine") && i + 1 < argc) refine = strtod(argv[++i], NULL);
        else if (!strcmp(argv[i], "--list")) list = 1;
        else { fprintf(stderr, "unknown option %s\n", argv[i]); usage(); return 2; }
    }

    double gap = mean_gap(T);
    /* Each certified bracket is one grid cell wide, and Turing's sums can
     * only use the conservative end of each bracket -- so every zero in a
     * zone loses up to delta, and the slack picks up delta/gap per zone
     * (independent of the zone length).  delta = gap/16 keeps that near 6%. */
    if (delta <= 0) delta = gap / 16.0;

    int verify = !strcmp(cmd, "verify");
    if (verify && zone <= 0) {
        /* the zone must be long enough that 2B/L < 1 with margin */
        /* slack ~ B/zone (each side) + delta/gap (each side); aim well under 1 */
        double B = turing_S_bound(T);
        zone = 12.0 * B;
        if (zone < 40.0) zone = 40.0;
    }
    if (!verify) zone = 0.0;

    /* total span: the requested zeros plus a Turing zone on each side */
    double span = (double)count * gap;
    double t_lo = T - zone, t_hi = T + span + zone;
    int m = (int)((t_hi - t_lo) / delta) + 2;

    fprintf(stderr, "height t = %.17g   mean zero gap = %.6f\n", T, gap);
    fprintf(stderr, "span %.3f in t (%ld zeros requested), zone %.3f each side\n",
            span, count, zone);
    fprintf(stderr, "grid: %d points at spacing ~%.6g\n", m, delta);

    long N = rs_nterms_d(t_hi);
    fprintf(stderr, "main sum length N = %ld\n", N);
    double tb0 = now_s();
    rs_logtab *lt = rs_logtab_build(N + 2, 1);
    if (!lt) { fprintf(stderr, "out of memory building log table\n"); return 1; }
    fprintf(stderr, "log table built in %.2f s\n", now_s() - tb0);

    os_window *w = os_eval(t_lo, delta, m, over, lt, J, 1);
    if (!w) {
        fprintf(stderr, "os_eval failed (N not constant across the window, "
                        "or allocation failure)\n");
        rs_logtab_free(lt); return 1;
    }

    if (!strcmp(cmd, "window")) {
        printf("grid points  = %d\n", w->m);
        printf("spacing      = %.17g\n", w->delta);
        printf("N            = %ld\n", w->N);
        printf("FFT length   = %d,  bins = %d,  blocks = %d\n",
               w->fft_len, w->nbins, w->nblocks);
        printf("Taylor depth = %d  (rho = %.4f)\n", w->taylor_d, w->rho);
        printf("error bound  = %.3e\n", w->err);
        printf("time: coef %.2fs  fft %.2fs  total %.2fs\n",
               w->secs_coef, w->secs_fft, w->secs_total);
        printf("equivalent direct cost = %.1f s (%d evals x %ld terms)\n",
               w->secs_coef * (double)w->m, w->m, w->N);
        os_window_free(w); rs_logtab_free(lt);
        return 0;
    }

    /* ---- certified sign changes ---------------------------------------- */
    zlist zl; zlist_init(&zl);
    long unresolved = 0;
    long found = zeros_scan_window(w, &zl, &unresolved);
    printf("certified sign changes : %ld\n", found);
    printf("unresolved grid pairs  : %ld  (|Z| below the error bound)\n", unresolved);
    printf("O-S error bound        : %.3e\n", w->err);

    if (refine > 0) {
        double tr0 = now_s();
        zeros_refine(&zl, lt, J, refine, 200, 1);
        double worst = 0;
        for (long i = 0; i < zl.n; i++) if (zl.b[i].width > worst) worst = zl.b[i].width;
        printf("refined %ld brackets to <= %.3e in %.2f s\n",
               zl.n, worst, now_s() - tr0);
    }

    if (verify) {
        /* Pin a and b to actual grid points, so that no certified bracket
         * straddles an endpoint (which would drop it from both counts). */
        dd d0 = dd_of(w->t0), dl = dd_of(w->delta);
        long ja = lrint(zone / w->delta);
        long jb = lrint((zone + span) / w->delta);
        if (jb > w->m - 1) jb = w->m - 1;
        dd a = dd_add(d0, dd_mul_d(dl, (double)ja));
        dd b = dd_add(d0, dd_mul_d(dl, (double)jb));
        dd c = d0;
        dd e = dd_add(d0, dd_mul_d(dl, (double)(w->m - 1)));
        turing_report rep;
        turing_verify(a, b, c, e, &zl, &rep);
        printf("\nTuring verification\n");
        printf("  zone length        : %.3f each side\n", rep.zone);
        printf("  |Int S| bound      : %.4f\n", turing_S_bound(t_hi));
        printf("  slack at a, b      : %.4f, %.4f  (must be < 1)\n",
               rep.slack_a, rep.slack_b);
        if (rep.verified) {
            printf("  N(a)               : %ld\n", rep.Na);
            printf("  N(b)               : %ld\n", rep.Nb);
            printf("  zeros expected     : %ld\n", rep.expected);
            printf("  zeros certified    : %ld\n", rep.found);
            printf("  RESULT             : VERIFIED -- %s\n", rep.why);
        } else {
            printf("  RESULT             : NOT VERIFIED -- %s\n", rep.why);
        }
    }

    if (list) {
        printf("\n# certified zero brackets (t = hi + lo, width)\n");
        for (long i = 0; i < zl.n; i++) {
            dd mid = dd_mul_d(dd_add(zl.b[i].lo, zl.b[i].hi), 0.5);
            print_dd("", mid, "");
            printf("  width %.3e\n", zl.b[i].width);
        }
    }

    zlist_free(&zl);
    os_window_free(w);
    rs_logtab_free(lt);
    return 0;
}
