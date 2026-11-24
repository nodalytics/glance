# Slumbot integration blueprint

Status: **design doc, not implemented.** glance's control-side API is built on
this blueprint (the user named it the blueprint, Nov 2026). The read side
(`/capture` → table JSON) already works; the control side is milestone **M1** in
[README.md](README.md#roadmap-from-screen-reading-to-screen-controlling).
This document pins the wire contract so M1 can be built without re-deriving it,
and defines the *extras* (things Slumbot does not do) that glance adds on top.
The rule: **the Slumbot protocol is the standard; anything glance adds is an
extra, never a deviation.**

## The Slumbot standard (mirror of the official spec)

HTTPS POSTs to `slumbot.com` with a JSON body; `Content-Type: application/json`
is required. Three endpoints:

| Endpoint               | Purpose                                        | Body                                                        |
| ---------------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| `/slumbot/api/login`   | authenticate; required for leaderboard play    | `{"username": ..., "password": ...}` → `{token, ...}`       |
| `/slumbot/api/new_hand`| start a hand; the response may carry an action | `{"token": ...}` (token optional only on the very first call)|
| `/slumbot/api/act`     | take an action in the current hand             | `{"token": ..., "incr": <action string>}`                   |

Game constants: blinds **50/100**, stack **20,000 chips (200 BB)**, stacks
reset every hand. You start the session in the less favorable position (big
blind); play an even number of hands so the button is split evenly.

### Token rules

- Every request carries a `token`; the only exception is the first-ever
  `/api/new_hand`, where it may be omitted.
- A response may return a **new** token (usually only after a long pause).
  Always read `token` out of the previous response and use it in the next
  request — never cache one across hands.
- Errors arrive as `error_msg` inside an otherwise-200 JSON body, so parse the
  body, not just the status code.

### Action strings (the core vocabulary)

An `action` in a response is the **full action history of the hand so far**,
street by street, separated by `/`; an `incr` in a request is the
**incremental** action you are taking now.

| Token        | Meaning                                              |
| ------------ | ---------------------------------------------------- |
| `k`          | check                                                |
| `c`          | call                                                 |
| `f`          | fold                                                 |
| `b<number>`  | bet (or raise) to `<number>` **chips total for that street only** |
| `/`          | street transition (preflop → flop → turn → river)   |

- Bet sizes are counts of chips put in **on that street (only)**.
  `b200c/kb400` means the flop bet is to 400 total because preflop left 400 in
  the pot; called, the total becomes 600.
- An all-in can carry empty streets: `b20000c///`.
- `client_pos`: `0` = big blind (second to act preflop, first postflop);
  `1` = small blind.

### Response shape

```json
{
  "old_action": "",
  "action": "b200",
  "client_pos": 0,
  "hole_cards": ["Ac", "9d"],
  "board": [],
  "token": "a2f42f44-7ff6-40dd-906b-4c2f03fcee57"
}
```

`winnings` (plus `baseline_winnings`, `session_num_hands`, `session_total`,
`session_baseline_total`) appear on the terminal response of a hand. If the bot
is first to act, the `/api/new_hand` response already contains its initial
action.

### Action-string parser (canonical, ported 1:1)

The reference implementation's `ParseAction` is the ground truth for turning an
`action` string into machine state. Port it **verbatim** into
`glance/core/src/slumbot_action.cpp` (C++) when M1 lands, and unit-test it
against the reference's cases, including:

- `""` → pre-flop default: `st=0`, `pos=1`, `street_last_bet_to=100`,
  `total_last_bet_to=100`, `last_bet_size=50`, `last_bettor=0`.
- `ck` and `ck/` — a trailing slash is optional.
- `b200c/...` — a check/call that **ends the street** must be followed by `/`
  or end-of-string (except the river check/call, which ends the hand).
- `b20000c///` — an all-in call on the button: any number of trailing empty
  streets up to the river, then the hand is over (`pos=-1`).
- Bet validation: minimum bet is `max(last_bet_size, BIG_BLIND)` (or the
  remaining stack, whichever is smaller); `street_last_bet_to`/`total_last_bet_to`
  advance accordingly; `last_bettor` = the bettor's position; `pos` advances.
- Errors (return an `error` key, do not crash): illegal check (a bet is
  outstanding), illegal call (nothing to call), illegal fold (nothing to fold),
  missing bet size / non-integer, bet too small / too big, unexpected
  character, missing street separators, overrunning the four streets.

## How a glance client maps the standard to screen reality

The loop for a Slumbot-backed bot where **Slumbot is the table** (research /
benchmarking, no real platform window):

```
POST /slumbot/api/new_hand {token}                    ──┐
POST /slumbot/api/act    {token, incr}                 │  the standard
                                                         ▼
      response {action, client_pos, hole_cards, board, token, winnings}
                      │
                      ▼
      ParseAction(action)  ──► TableState (seats, board, pot, street, my_turn)
                      │
                      ▼
      strategy (equity, CFR, ...)  ──► incr
```

The mapping from the parsed state to the action-string vocabulary is what glance
owns:

| TableState (parsed)                          | Standard concept          |
| -------------------------------------------- | ------------------------- |
| `seats[*].bet` on this street                | `street_last_bet_to`      |
| `seats[*].bet` accumulated, all streets      | `total_last_bet_to`       |
| largest current-street bet                   | `last_bet_size`           |
| who made that bet (seat index)               | `last_bettor`             |
| `board.size()`                               | `st` (street)             |
| `my_turn` + position of the to-act seat      | `pos`                     |
| hand over (fold / showdown terminal)         | `pos = -1`                |
| `total_pot`                                  | pot (display/research)    |

Conversely, `incr` generation: `k`/`c` when the street context allows
(`last_bettor < 0` for check), otherwise `b<number>` with the **street-total**
target — never the delta. The parser's validation rules above are also the
validator for the action *we emit*; run `ParseAction(old + "/" + incr)` before
sending to catch illegal outputs locally.

### What glance provides that Slumbot does not (extras, additive only)

- **`client_pos` from a 6-max seat layout**, not just HU big/small-blind: the
  button seat is the parsed `dealer_position`; "position" in the general case
  is derived from the button → to-act distance. Slumbot's binary `client_pos`
  stays as-is for the HU standard; glance reports the richer `dealer`/`seats`
  in the same JSON payload.
- **Real-window mode (the actual product).** ACR (or any skin) where the table
  is a window, not a bot: the same `/act {incr}` vocabulary drives M1
  (button clicks + chip input from the mapping's rectangles). Slumbot strings
  become the *internal* action language even when no Slumbot server is
  involved, so one strategy layer serves both benches.
- **State-diff + event log** (M4/M5): every response/action pair is logged
  with timestamp and the raw action string, for replay/audit — the standard
  never forbids extras on the client side.

## Out of scope here

- The actual `login`/`new_hand`/`act` HTTP client (C++ `httplib` POSTs) — M1,
  once the action vocabulary + parser exist and are tested.
- Strategy (equity/CFR) — not glance's job; glance supplies the parsed state,
  a strategy client consumes it. [Gongsta/Poker-AI](https://github.com/Gongsta/Poker-AI/)
  is a reference for the strategy side (CFR + card abstraction; its roadmap
  lists a CV card recognizer — the consumer of exactly what glance produces).
