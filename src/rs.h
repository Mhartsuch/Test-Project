/* rs.h -- Riemann-Siegel machinery and an independent Euler-Maclaurin path.
 *
 * Z(t) = e^{i theta(t)} zeta(1/2 + it) is real for real t, and its sign
 * changes are the zeros of zeta on the critical line.  Two evaluators:
 *
 *   Riemann-Siegel   cost O(sqrt(t)), used everywhere at height.
 *   Euler-Maclaurin  cost O(t), rigorous to arbitrary order, used as an
 *                    independent oracle and below the RS threshold.
 *
 * Conventions (validated against mpmath in tests/):
 *   tau = sqrt(t / 2pi),  N = floor(tau),  p = tau - N in [0,1)
 *   Z(t) = 2 sum_{k=1}^{N} k^{-1/2} cos(theta(t) - t log k)
 *          + (-1)^{N-1} tau^{-1/2} ( C_0(p) + C_1(p)/tau + ... )
 *   Psi(p) = cos(2pi(p^2 - p - 1/16)) / cos(2pi p)
 *   C_0 = Psi,   C_1 = -Psi'''/(96 pi^2)
 */
#ifndef ZETA_RS_H
#define ZETA_RS_H

#include "dd.h"
#include "interval.h"

/* ---- table of log k in double-double, k = 1..nmax ----------------------- */
typedef struct {
    long   nmax;
    dd    *log;        /* log[k] for k <= nmax; log[0] unused */
    double err;        /* rigorous bound on |log[k] - log(k)| for every k */
} rs_logtab;

rs_logtab *rs_logtab_build(long nmax, int verbose);
void       rs_logtab_free(rs_logtab *lt);

/* ---- Riemann-Siegel theta -----------------------------------------------
 *
 * NOTE ON THE ARGUMENT TYPE.  Everything that consumes a height takes a dd,
 * not a double.  At t = 1e15 one ulp of a double is 0.125, while the mean
 * spacing between zeros is 2 pi / log(t/2pi) = 0.19 -- consecutive zeros are
 * less than two ulps apart, so a double cannot even name them.  The grid,
 * the zero locations and every phase must be carried in double-double. */
dd     rs_theta(dd t);                /* full value (huge); dd-accurate      */
double rs_theta_err(double t);        /* rigorous bound on the above         */
double rs_theta_mod2pi(dd t);
double rs_theta_prime(double t);      /* = (1/2) log(t/2pi)                  */
double rs_theta_inv(double target);   /* solve theta(t) = target for t       */

/* log of a dd argument, with a rigorous absolute error bound. */
dd     dd_log_full_pub(dd x, double *err);

/* ---- main sum size ------------------------------------------------------ */
long   rs_nterms(dd t);               /* N = floor(sqrt(t/2pi))              */

/* ---- correction terms --------------------------------------------------- */
dd     rs_psi(dd p);                  /* Psi(p), stable near p = 1/4, 3/4    */
double rs_correction(dd t, int J);    /* (-1)^{N-1} tau^{-1/2} sum_{j<=J} .. */
double rs_trunc_bound(double t, int J);/* bound on the omitted RS tail       */

/* ---- evaluation --------------------------------------------------------- */
/* Fast path: O(N) with dd phases, double accumulation. */
double rs_Z(dd t, const rs_logtab *lt, int J);
/* Rigorous a-priori bound on |rs_Z - Z_exact|, valid for the fast path. */
double rs_Z_errbound(double t, int J);
/* Fully rigorous evaluation: interval arithmetic per term.  Slow. */
iv     rs_Z_iv(dd t, const rs_logtab *lt, int J);

/* ---- Euler-Maclaurin (independent, rigorous) ---------------------------- */
/* Z(t) via zeta(1/2+it) with M split terms and K Bernoulli terms.
 * Pass M = 0 to let it choose.  Returns an enclosure. */
iv     em_Z_iv(double t, long M, int K);

/* Convenience wrappers for callers working at heights where a double is
 * plenty (tests, low-t validation). */
static inline double rs_Z_d(double t, const rs_logtab *lt, int J)
{ return rs_Z(dd_of(t), lt, J); }
static inline long rs_nterms_d(double t) { return rs_nterms(dd_of(t)); }
static inline double rs_theta_mod2pi_d(double t) { return rs_theta_mod2pi(dd_of(t)); }

#endif /* ZETA_RS_H */
