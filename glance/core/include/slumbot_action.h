#pragma once

#include <string>

// Slumbot action-string parser (the control plane's "ground truth").
//
// This is a 1:1 C++ port of the `ParseAction` state machine from Slumbot's
// published `sample_api.py` (slumbot.com). It is PURE LOGIC — no I/O, no
// network, no poker strategy: given an action string it reports the machine
// state of the hand (current street, bet-to amounts, who bet last, whose turn
// it is) and every error path the reference defines.
//
// The grammar (see research/slumbot.md):
//   k            check
//   c            call
//   f            fold
//   b<number>    bet or raise TO <number> chips total for THIS street only
//   /            street transition (preflop -> flop -> turn -> river)
// e.g. "b200c/kk/kk/kb200" is a full four-street history.
//
// Game constants are Slumbot's house rules: blinds 50/100, stack 200 BB
// (20,000 chips). `client_pos` elsewhere is 0 = big blind, 1 = small blind;
// here `pos` is the position (0/1) next to act, or -1 when the hand is over.
namespace glance::slumbot {

inline constexpr int kNumStreets = 4;
inline constexpr int kSmallBlind = 50;
inline constexpr int kBigBlind = 100;
inline constexpr int kStackSize = 20000;  // 200 big blinds

// The result of parsing an action string.
//
// When `ok` is false, `error` holds the reason (one of the reference's error
// strings) and the numeric fields are left at whatever the walk reached — read
// `error` first. When `ok` is true the fields mirror the reference dict:
//   st                  current street index, 0..3 (preflop..river)
//   pos                 position (0/1) next to act, or -1 if the hand is over
//                       (fold, river check/call, or an all-in call)
//   street_last_bet_to  chips bet TO on the current street only
//   total_last_bet_to   chips put in across all streets (the pot's bet-to)
//   last_bet_size       size of the last bet/raise (0 after a check/call)
//   last_bettor         position of the last bettor (-1 after a check/call)
struct ParsedAction {
  bool ok = false;
  std::string error;
  int st = 0;
  int pos = 1;
  int street_last_bet_to = kBigBlind;
  int total_last_bet_to = kBigBlind;
  int last_bet_size = kBigBlind - kSmallBlind;
  int last_bettor = 0;
};

// Parse a full action-history string. The empty string is the valid preflop
// start (st=0, pos=1, street_last_bet_to=100, total_last_bet_to=100,
// last_bet_size=50, last_bettor=0). A trailing '/' is optional ("ck" == "ck/").
ParsedAction parse_action(const std::string& action);

}  // namespace glance::slumbot
