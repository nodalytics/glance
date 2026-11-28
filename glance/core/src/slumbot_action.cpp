#include "slumbot_action.h"

#include <cstdint>

// 1:1 port of Slumbot's `ParseAction` (sample_api.py from slumbot.com). The
// control flow, the branch order, and the error strings are the reference's;
// only the shape of the result differs (a struct with an `ok` flag instead of
// a Python dict that may carry an 'error' key). Keep this faithful to the
// reference so glance validates action strings exactly as the benchmark server
// does — the parser is the "ground truth" (research/slumbot.md).

namespace glance::slumbot {

namespace {

ParsedAction error(const std::string& msg) {
  ParsedAction r;
  r.ok = false;
  r.error = msg;
  return r;
}

ParsedAction done(int st, int pos, int street_last_bet_to, int total_last_bet_to, int last_bet_size,
                  int last_bettor) {
  ParsedAction r;
  r.ok = true;
  r.st = st;
  r.pos = pos;
  r.street_last_bet_to = street_last_bet_to;
  r.total_last_bet_to = total_last_bet_to;
  r.last_bet_size = last_bet_size;
  r.last_bettor = last_bettor;
  return r;
}

}  // namespace

ParsedAction parse_action(const std::string& action) {
  int st = 0;
  int street_last_bet_to = kBigBlind;
  int total_last_bet_to = kBigBlind;
  int last_bet_size = kBigBlind - kSmallBlind;
  int last_bettor = 0;
  const int sz = static_cast<int>(action.size());
  int pos = 1;
  if (sz == 0) {
    return done(st, pos, street_last_bet_to, total_last_bet_to, last_bet_size, last_bettor);
  }

  bool check_or_call_ends_street = false;
  int i = 0;
  while (i < sz) {
    if (st >= kNumStreets) return error("Unexpected error");
    char c = action[i];
    i += 1;
    if (c == 'k') {
      if (last_bet_size > 0) return error("Illegal check");
      if (check_or_call_ends_street) {
        // After a check that ends a pre-river street, expect either a '/' or
        // end of string.
        if (st < kNumStreets - 1 && i < sz) {
          if (action[i] != '/') return error("Missing slash");
          i += 1;
        }
        if (st == kNumStreets - 1) {
          // Reached showdown
          pos = -1;
        } else {
          pos = 0;
          st += 1;
        }
        street_last_bet_to = 0;
        check_or_call_ends_street = false;
      } else {
        pos = (pos + 1) % 2;
        check_or_call_ends_street = true;
      }
    } else if (c == 'c') {
      if (last_bet_size == 0) return error("Illegal call");
      if (total_last_bet_to == kStackSize) {
        // Call of an all-in bet. Either allow no slashes, or slashes
        // terminating all streets prior to the river.
        if (i != sz) {
          for (int st1 = st; st1 < kNumStreets - 1; ++st1) {
            if (i == sz) {
              return error("Missing slash (end of string)");
            } else {
              c = action[i];
              i += 1;
              if (c != '/') return error("Missing slash");
            }
          }
        }
        if (i != sz) return error("Extra characters at end of action");
        st = kNumStreets - 1;
        pos = -1;
        last_bet_size = 0;
        return done(st, pos, street_last_bet_to, total_last_bet_to, last_bet_size, last_bettor);
      }
      if (check_or_call_ends_street) {
        // After a call that ends a pre-river street, expect either a '/' or
        // end of string.
        if (st < kNumStreets - 1 && i < sz) {
          if (action[i] != '/') return error("Missing slash");
          i += 1;
        }
        if (st == kNumStreets - 1) {
          // Reached showdown
          pos = -1;
        } else {
          pos = 0;
          st += 1;
        }
        street_last_bet_to = 0;
        check_or_call_ends_street = false;
      } else {
        pos = (pos + 1) % 2;
        check_or_call_ends_street = true;
      }
      last_bet_size = 0;
      last_bettor = -1;
    } else if (c == 'f') {
      // The reference has a typo here (a set literal {'error', 'Illegal fold'}
      // instead of a dict), but the intended — and effective, via `'error' in
      // r` — semantic is an illegal-fold error: a fold with nothing to call.
      if (last_bet_size == 0) return error("Illegal fold");
      if (i != sz) return error("Extra characters at end of action");
      pos = -1;
      return done(st, pos, street_last_bet_to, total_last_bet_to, last_bet_size, last_bettor);
    } else if (c == 'b') {
      int j = i;
      while (i < sz && action[i] >= '0' && action[i] <= '9') i += 1;
      if (i == j) return error("Missing bet size");
      // The reference uses Python's arbitrary-precision int(); parse into a
      // 64-bit accumulator (saturating well above the stack size) so an absurd
      // digit run cannot overflow — it then fails the "Bet too big" check
      // below exactly as a large Python int would.
      std::int64_t new_street_last_bet_to = 0;
      for (int k = j; k < i; ++k) {
        new_street_last_bet_to = new_street_last_bet_to * 10 + (action[k] - '0');
        if (new_street_last_bet_to > static_cast<std::int64_t>(kStackSize) * 100) {
          new_street_last_bet_to = static_cast<std::int64_t>(kStackSize) * 100;
        }
      }
      std::int64_t new_last_bet_size = new_street_last_bet_to - street_last_bet_to;
      // Validate that the bet is legal.
      const int remaining = kStackSize - total_last_bet_to;
      int min_bet_size;
      if (last_bet_size > 0) {
        min_bet_size = last_bet_size;
        // Make sure minimum opening bet is the size of the big blind.
        if (min_bet_size < kBigBlind) min_bet_size = kBigBlind;
      } else {
        min_bet_size = kBigBlind;
      }
      // Can always go all-in.
      if (min_bet_size > remaining) min_bet_size = remaining;
      if (new_last_bet_size < min_bet_size) return error("Bet too small");
      const int max_bet_size = remaining;
      if (new_last_bet_size > max_bet_size) return error("Bet too big");
      last_bet_size = static_cast<int>(new_last_bet_size);
      street_last_bet_to = static_cast<int>(new_street_last_bet_to);
      total_last_bet_to += last_bet_size;
      last_bettor = pos;
      pos = (pos + 1) % 2;
      check_or_call_ends_street = true;
    } else {
      return error("Unexpected character in action");
    }
  }

  return done(st, pos, street_last_bet_to, total_last_bet_to, last_bet_size, last_bettor);
}

}  // namespace glance::slumbot
