// Unit tests for the ported Slumbot action-string parser (slumbot_action.h).
// Drives parse_action against the reference's example, the all-in cases, the
// optional-trailing-slash rule, and every error path, asserting the exact
// machine state the reference ParseAction computes.

#include <cstdio>
#include <string>

#include "slumbot_action.h"

using glance::slumbot::parse_action;
using glance::slumbot::ParsedAction;

static int failures = 0;

#define CHECK(cond, msg)                \
  do {                                  \
    if (cond) {                         \
      std::printf("  ok: %s\n", msg);   \
    } else {                            \
      std::printf("  FAIL: %s\n", msg); \
      ++failures;                       \
    }                                   \
    std::fflush(stdout);                \
  } while (0)

// Assert a parse succeeds and reaches the expected machine state.
static void expect_ok(const char* action, int st, int pos, int slbt, int tlbt, int lbs, int lbettor) {
  const ParsedAction r = parse_action(action);
  char msg[256];
  if (!r.ok) {
    std::snprintf(msg, sizeof(msg), "'%s' parses ok (got error '%s')", action, r.error.c_str());
    CHECK(false, msg);
    return;
  }
  const bool match = r.st == st && r.pos == pos && r.street_last_bet_to == slbt &&
                     r.total_last_bet_to == tlbt && r.last_bet_size == lbs && r.last_bettor == lbettor;
  std::snprintf(msg, sizeof(msg),
                "'%s' -> st=%d pos=%d slbt=%d tlbt=%d lbs=%d lbettor=%d (got st=%d pos=%d slbt=%d "
                "tlbt=%d lbs=%d lbettor=%d)",
                action, st, pos, slbt, tlbt, lbs, lbettor, r.st, r.pos, r.street_last_bet_to,
                r.total_last_bet_to, r.last_bet_size, r.last_bettor);
  CHECK(match, msg);
}

// Assert a parse fails with exactly the expected error string.
static void expect_err(const char* action, const char* want) {
  const ParsedAction r = parse_action(action);
  char msg[256];
  std::snprintf(msg, sizeof(msg), "'%s' is rejected with '%s' (got %s '%s')", action, want,
                r.ok ? "ok" : "error", r.ok ? "" : r.error.c_str());
  CHECK(!r.ok && r.error == want, msg);
}

int main() {
  std::printf("slumbottest: defaults + the canonical example\n");
  // Empty string: the preflop start.
  expect_ok("", 0, 1, 100, 100, 50, 0);
  // A single preflop raise to 200 (SB), still preflop, BB to act.
  expect_ok("b200", 0, 0, 200, 200, 100, 1);
  // Raise to 200, called: on to the flop, big blind (pos 0) to act first.
  expect_ok("b200c", 1, 0, 0, 200, 0, -1);
  // The slumbot.md example: raise-call preflop, checks on flop and turn, a
  // river bet to 200. Ends on the river facing a 200 bet, BB (pos 0) to act.
  expect_ok("b200c/kk/kk/kb200", 3, 0, 200, 400, 200, 1);

  std::printf("slumbottest: trailing slash is optional\n");
  // "ck" and "ck/" reach the same flop state (SB limp, BB check).
  expect_ok("ck", 1, 0, 0, 100, 0, -1);
  expect_ok("ck/", 1, 0, 0, 100, 0, -1);

  std::printf("slumbottest: all-in handling\n");
  // All-in call with NO trailing slashes: hand over at the river.
  expect_ok("b20000c", 3, -1, 20000, 20000, 0, 1);
  // All-in call with empty streets up to the river: same terminal state.
  expect_ok("b20000c///", 3, -1, 20000, 20000, 0, 1);
  // An all-in bet alone is preflop, not terminal (opponent still to act).
  expect_ok("b20000", 0, 0, 20000, 20000, 19900, 1);

  std::printf("slumbottest: fold terminates the hand\n");
  // A preflop fold (BB facing the SB's blind-sized bet): hand over, pos -1.
  expect_ok("f", 0, -1, 100, 100, 50, 0);
  expect_ok("b200f", 0, -1, 200, 200, 100, 1);

  std::printf("slumbottest: error paths\n");
  expect_err("k", "Illegal check");             // a bet (the BB) is outstanding preflop
  expect_err("ck/c", "Illegal call");           // nothing to call on a fresh flop
  expect_err("ck/f", "Illegal fold");           // nothing to fold to on a fresh flop
  expect_err("b", "Missing bet size");          // 'b' with no digits
  expect_err("bc", "Missing bet size");         // 'b' followed by a non-digit
  expect_err("b150", "Bet too small");          // raise to 150 is a 50 raise, < big blind
  expect_err("b20001", "Bet too big");          // more than the remaining stack
  expect_err("x", "Unexpected character in action");
  expect_err("b200ck", "Missing slash");        // street-ending call, next token not '/'
  expect_err("b20000c/", "Missing slash (end of string)");  // partial all-in slashes
  expect_err("fc", "Extra characters at end of action");    // action after a terminal fold
  expect_err("b20000c/k", "Missing slash");     // all-in call then a non-slash

  // The emitted-action validator use (slumbot.md): a full legal hand parses.
  std::printf("slumbottest: a full check-through hand parses\n");
  expect_ok("ck/kk/kk/kk", 3, -1, 0, 100, 0, -1);

  std::printf("slumbottest: %s (%d failure%s)\n", failures ? "FAILED" : "passed", failures,
              failures == 1 ? "" : "s");
  return failures ? 1 : 0;
}
