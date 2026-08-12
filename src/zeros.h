/* zeros.h -- certified sign changes, Gram points, and zero isolation. */
#ifndef ZETA_ZEROS_H
#define ZETA_ZEROS_H

#include "rs.h"
#include "os.h"

/* A certified bracket: Z(lo) and Z(hi) have rigorously determined and
 * opposite signs, so Z has a zero of odd order in (lo, hi).  Since Z is real
 * on the critical line, that is a zero of zeta with real part exactly 1/2. */
typedef struct {
    dd  lo, hi;
    int sign_lo;          /* +1 or -1, rigorously determined */
    double width;
} zbracket;

typedef struct {
    zbracket *b;
    long n, cap;
} zlist;

void zlist_init(zlist *z);
void zlist_free(zlist *z);
int  zlist_push(zlist *z, zbracket br);

/* Gram points: theta(g_n) = n*pi.  Computed in dd -- at t = 1e15 the Gram
 * index is ~5e15, so n*pi itself needs more than a double. */
dd   gram_point(long n);
long gram_index(dd t);          /* floor(theta(t)/pi) */

/* Scan an O-S window for certified sign changes.  A sign change counts only
 * when |Z| exceeds the window's error bound at BOTH ends, so the sign is
 * rigorously determined.  Returns the number appended to `out`.
 * `unresolved` receives the number of adjacent grid pairs where at least one
 * endpoint could not be signed -- those need refinement before any counting
 * claim can be made. */
long zeros_scan_window(const os_window *w, zlist *out, long *unresolved);

/* Bisect each bracket until it is narrower than `target` (absolute in t) or
 * `maxit` steps are used.  Every step re-certifies the sign with the direct
 * Riemann-Siegel evaluator and its a-priori bound, so brackets stay valid. */
int zeros_refine(zlist *zl, const rs_logtab *lt, int J,
                 double target, int maxit, int verbose);

#endif /* ZETA_ZEROS_H */
