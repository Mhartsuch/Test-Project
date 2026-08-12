/* turing.h -- Turing's method: a rigorous count of the zeros in an interval.
 *
 * Write N(T) for the number of zeros of zeta with 0 < Im(rho) <= T, and
 *   S(T) = N(T) - 1 - theta(T)/pi.
 * Sign changes give a LOWER bound on N; Turing's insight is that the mean of
 * S over an interval is small, which converts that into an UPPER bound too.
 *
 * Using only that certified sign changes are genuine zeros (never that we
 * found all of them), for any b > a:
 *
 *   N(a) <= 1 + [ (1/pi) Int_a^b theta + B - Sum_{gamma in (a,b]} (b-gamma) ] / (b-a)
 *
 * and symmetrically, for c < a:
 *
 *   N(a) >= 1 + [ (1/pi) Int_c^a theta + Sum_{gamma in (c,a]} (gamma-c) - B ] / (a-c)
 *
 * where B bounds |Int S|.  Both hold unconditionally.  When the two bounds
 * trap a single integer, N(a) is pinned.  Doing this at both ends of a range
 * gives the true zero count there; if it equals the number of certified sign
 * changes, then every zero in the range is simple and on the critical line.
 *
 * The constant B is the one input taken from the literature; see docs/RIGOR.md.
 */
#ifndef ZETA_TURING_H
#define ZETA_TURING_H

#include "zeros.h"

/* |Int_{t1}^{t2} S(t) dt| <= 2.30 + 0.128 log(t2 / 2pi)   for t2 >= 2pi.
 * Lehman, "On the distribution of zeros of the Riemann zeta-function",
 * Proc. London Math. Soc. (3) 20 (1970), Theorem 2. */
double turing_S_bound(double t2);

/* Antiderivative of theta, for the (1/pi) Int theta terms above. */
dd turing_theta_integral(dd t);

typedef struct {
    int    verified;      /* 1 iff both endpoints pinned and counts agree   */
    long   Na, Nb;        /* N(a), N(b) -- valid only when verified         */
    double slack_a;       /* width of the integer window at a (<1 = pinned) */
    double slack_b;
    long   found;         /* certified sign changes in (a, b]               */
    long   expected;      /* Nb - Na                                        */
    double zone;          /* length of each Turing zone actually used       */
    const char *why;      /* explanation when not verified                  */
} turing_report;

/* zl must hold certified brackets covering [c, e] with c < a < b < e.
 * The zones [c,a] and [b,e] are what pins N(a) and N(b). */
int turing_verify(dd a, dd b, dd c, dd e, const zlist *zl, turing_report *rep);

#endif /* ZETA_TURING_H */
