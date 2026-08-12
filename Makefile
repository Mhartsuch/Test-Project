CC      ?= gcc
# -ffp-contract=off is REQUIRED: the interval arithmetic assumes every written
# floating-point operation is individually correctly rounded.
CFLAGS  ?= -O2 -march=native -ffp-contract=off -fno-fast-math -std=c11 -Wall -Wextra \
           -Wno-unused-parameter -pthread
LDFLAGS ?= -lm -pthread

SRC  := src/interval.c src/fft.c src/rs.c src/os.c src/zeros.c src/turing.c
OBJ  := $(SRC:.c=.o)
HDR  := $(wildcard src/*.h)

TESTS := tests/test_dd tests/test_interval tests/test_fft tests/test_rs \
         tests/test_os tests/test_zeros

all: zeta $(TESTS)

zeta: src/main.c $(OBJ) $(HDR)
	$(CC) $(CFLAGS) -o $@ src/main.c $(OBJ) $(LDFLAGS)

%.o: %.c $(HDR)
	$(CC) $(CFLAGS) -c -o $@ $<

tests/%: tests/%.c $(OBJ) $(HDR)
	$(CC) $(CFLAGS) -Isrc -o $@ $< $(OBJ) $(LDFLAGS)

check: all
	@bash tests/run_tests.sh

clean:
	rm -f zeta $(OBJ) $(TESTS) tests/*.o

.PHONY: all check clean
