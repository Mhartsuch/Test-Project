#!/usr/bin/env bash
# Run the whole test suite.  Every test is self-checking and exits non-zero
# on failure.
set -u
cd "$(dirname "$0")/.."

TESTS="tests/test_dd tests/test_interval tests/test_fft tests/test_os tests/test_rs tests/test_zeros"
fail=0
for t in $TESTS; do
    [ -x "$t" ] || { echo "missing $t (run make)"; fail=1; continue; }
    echo "=============================================================="
    if ! "$t"; then fail=1; fi
done
echo "=============================================================="
if [ "$fail" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit $fail
