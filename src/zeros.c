#include "zeros.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* exact dd from a 64-bit integer (|n| can exceed 2^53) */
static dd dd_of_ll(long long n) {
    double hi = (double)n;
    double lo = (double)(n - (long long)hi);
    return dd_quick_two_sum(hi, lo);
}

void zlist_init(zlist *z) { z->b = NULL; z->n = 0; z->cap = 0; }
void zlist_free(zlist *z) { free(z->b); z->b = NULL; z->n = z->cap = 0; }

int zlist_push(zlist *z, zbracket br) {
    if (z->n == z->cap) {
        long nc = z->cap ? z->cap * 2 : 256;
        zbracket *nb = (zbracket *)realloc(z->b, sizeof(zbracket) * (size_t)nc);
        if (!nb) return 0;
        z->b = nb; z->cap = nc;
    }
    z->b[z->n++] = br;
    return 1;
}

/* ---- Gram points -------------------------------------------------------- */

dd gram_point(long n) {
    dd target = dd_mul(DD_PI, dd_of_ll(n));
    /* start from the double-precision inverse, then Newton in dd */
    double t = rs_theta_inv(target.hi);
    dd x = dd_of(t);
    for (int i = 0; i < 60; i++) {
        dd f = dd_sub(rs_theta(x), target);
        double fp = rs_theta_prime(x.hi);
        if (!(fp > 1e-12)) break;
        dd step = dd_div(f, dd_of(fp));
        x = dd_sub(x, step);
        if (fabs(step.hi) < 1e-18 * fabs(x.hi)) break;
    }
    return x;
}

long gram_index(dd t) {
    dd r = dd_div(rs_theta(t), DD_PI);
    dd f = dd_floor(r);
    return (long)(f.hi + f.lo);
}

/* ---- scanning ----------------------------------------------------------- */

long zeros_scan_window(const os_window *w, zlist *out, long *unresolved) {
    long added = 0, unres = 0;
    double E = w->err;
    dd d0 = dd_of(w->t0), dl = dd_of(w->delta);

    for (int j = 0; j + 1 < w->m; j++) {
        double a = w->Z[j], b = w->Z[j + 1];
        int sa = (a > E) ? 1 : ((a < -E) ? -1 : 0);
        int sb = (b > E) ? 1 : ((b < -E) ? -1 : 0);
        if (sa == 0 || sb == 0) { unres++; continue; }
        if (sa == sb) continue;
        zbracket br;
        br.lo = dd_add(d0, dd_mul_d(dl, (double)j));
        br.hi = dd_add(d0, dd_mul_d(dl, (double)(j + 1)));
        br.sign_lo = sa;
        br.width = w->delta;
        if (!zlist_push(out, br)) return -1;
        added++;
    }
    if (unresolved) *unresolved = unres;
    return added;
}

/* ---- refinement --------------------------------------------------------- */

int zeros_refine(zlist *zl, const rs_logtab *lt, int J,
                 double target, int maxit, int verbose) {
    long stuck = 0;
    for (long i = 0; i < zl->n; i++) {
        zbracket *br = &zl->b[i];
        for (int it = 0; it < maxit; it++) {
            dd wdt = dd_sub(br->hi, br->lo);
            double wd = wdt.hi + wdt.lo;
            if (wd <= target) break;
            dd mid = dd_mul_d(dd_add(br->lo, br->hi), 0.5);
            double zm = rs_Z(mid, lt, J);
            double E = rs_Z_errbound(mid.hi, J);
            int sm = (zm > E) ? 1 : ((zm < -E) ? -1 : 0);
            if (sm == 0) { stuck++; break; }   /* too close to the zero to sign */
            if (sm == br->sign_lo) br->lo = mid;
            else                   br->hi = mid;
        }
        dd wdt = dd_sub(br->hi, br->lo);
        br->width = wdt.hi + wdt.lo;
    }
    if (verbose && stuck)
        fprintf(stderr, "  refine: %ld brackets hit the precision floor "
                        "(|Z| below the error bound at the midpoint)\n", stuck);
    return 1;
}
