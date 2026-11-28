# Glance

**For poker platforms without APIs, Glance is the way in.** A C++ (CMake,
OpenCV, cpp-httplib) screen-scraping and control tool that turns a grab of the
[ACR Poker](https://www.acrpoker.eu/) table window into clean JSON — template
match for the fixed elements, OCR for the numbers — exposed over a small HTTP
API. The read side works today; the control side is in progress, and its wire
contract is the [Slumbot API](https://slumbot.com/) (below) — so any engine
written against Slumbot can talk to a glance table window unmodified.

[docs/architecture.md](docs/architecture.md) is the whole-system map (engine,
packages, front ends, platforms); [docs/README.md](docs/README.md) has
the vision and roadmap; [research/slumbot.md](research/slumbot.md) pins the control-side
protocol.

## Prerequisites

- CMake >= 3.24
- C++20 compiler (tested with g++ 13 on Ubuntu 24.04)
- `libopencv-dev` — the distro's prebuilt OpenCV 4.x. glance links it; it is
  never built from source. (`bash research/scripts/install_deps.sh` installs
  all of the above in one go.)
- Optional: `tesseract-ocr` — enables reading pot/stack/bet numbers (the build
  auto-disables OCR when the binary is missing)
- Optional: `libx11-dev` + `libxext-dev` — the X11 screen-grab / synthetic-input
  backend for the control plane. Like OCR, it is a configure-time option:
  without the headers the build still succeeds, on the null backend, and the
  server reports "no display" at runtime.

nlohmann/json and cpp-httplib are single-header deps fetched by CMake at
configure time — nothing else to install.

## Build

```sh
cd glance
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

Targets:

- `glance-server` — the HTTP API
- `glance-selftest` — synthesized-scenario end-to-end test (`ctest --test-dir build` runs it)

## Server API (live today)

```sh
build/glance-server path/to/mapping.json [port]   # default port 8000
```

| Endpoint              | What it does                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------- |
| `GET /health`         | liveness                                                                                                       |
| `POST /capture`       | body: raw PNG/JPEG bytes of the poker window (any content type, ≤ 16 MB) → parses and returns the table state JSON (422 when the table anchor is not found) |
| `GET /state`          | last successfully parsed state (404 until the first capture)                                                  |

Example:

```sh
curl -s -X POST -H 'Content-Type: application/octet-stream' \
     --data-binary @screenshot.png http://127.0.0.1:8000/capture | jq
```

State shape (field presence is data-driven — a seat's `cards`/`stack`/`bet` and
the board/stage/pot appear only when actually read):

```json
{
  "max_players": 6,
  "seats": [
    { "index": 1, "cards": ["Ah", "2c"], "stack": 4800.0, "bet": 0.0, "in_hand": true },
    { "index": 2, "stack": 3100.0, "bet": 0.0, "in_hand": true }
  ],
  "dealer": 3,
  "pot": 243.5,
  "my_turn": true,
  "call": 100.0,
  "raise": 400.0,
  "stage": "Flop",
  "board": ["7d", "Ks", "Qh"],
  "my_cards": ["Ah", "2c"],
  "validation": { "valid": true, "errors": [], "warnings": [] }
}
```

Every state crosses the wire with a `validation` block — a port of the card/
table-state validators from the research prototype in `research/` (duplicate
card faces, board gaps, stage/board mismatches, negative amounts, each with a
`code`, `message` and affected `slots`). Clients can distrust any state that is
not `"valid": true`.

## Slumbot API — the control-plane spec

glance's control plane speaks the [Slumbot API](https://slumbot.com/)
verbatim. Slumbot is the de-facto standard against which poker bots are built
and benchmarked, and its sample client (`sample_api.py`, served from the
project page) ships the canonical action-string parser. The rule for glance:

> **The Slumbot protocol is the standard; anything glance adds is an extra,
> never a deviation.**

The consequence is that a bot written for slumbot.com is a drop-in client for
a glance table — and glance clients can play hands against Slumbot itself, no
code changes.

**Status.** The read side above is live and end-to-end tested. The control
plane (click-by-mapping, key input, the `/slumbot/api/*` surface) is in
progress — roadmap M1–M2 in
[docs/README.md](docs/README.md). The contract below is already pinned
in [research/slumbot.md](research/slumbot.md) — endpoints, grammar, token rules
and the parser contract — so engines can be built against it now.

### Endpoints (mirror of slumbot.com)

HTTPS POSTs, JSON bodies, `Content-Type: application/json`:

| Endpoint               | Purpose                                                    | Body                                                                  |
| ---------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------- |
| `POST /slumbot/api/login`   | authenticate; required to make the leaderboards            | `{"username": ..., "password": ...}` → `{token, ...}`                  |
| `POST /slumbot/api/new_hand`| start a new hand; the response carries the action if the bot is first to act | `{"token": ...}` — the token may be omitted on the very first call only |
| `POST /slumbot/api/act`     | take an action in the current hand                         | `{"token": ..., "incr": <action string>}`                              |

Game constants (Slumbot house rules): blinds **50/100**, stacks **200 BB**,
stacks reset every hand. A session starts in the less favorable position (big
blind); play an even number of hands so the button is split evenly.

### Token rules

- Every request carries a `token`; the sole exception is the first-ever
  `/api/new_hand`, where it may be omitted.
- A response can return a **new** token (usually only after a long pause).
  Always read `token` out of the previous response and use it in the next
  request — never cache one across hands.
- Errors arrive as an `error_msg` key inside an otherwise-200 JSON body —
  parse the body, not just the status code.

### Action strings

An `action` in a response is the **full action history of the hand so far**,
streets separated by `/`. An `incr` in a request is the **incremental** action
you are taking now.

| Token        | Meaning                                                          |
| ------------ | ---------------------------------------------------------------- |
| `k`          | check                                                            |
| `c`          | call                                                             |
| `f`          | fold                                                             |
| `b<number>`  | bet (or raise) **to `<number>` chips total for that street only** — never the delta |
| `/`          | street transition (preflop → flop → turn → river)               |

- `b200c/kk/kk/kb200` — a full hand's history: a raise to 200 (called) preflop,
  checks around on the flop and turn, a bet to 200 on the river.
- An all-in can carry streets with no action: `b20000c///`.
- `client_pos`: `0` = big blind, `1` = small blind.

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

`winnings` (plus session counters) appear on the terminal response of a hand.
If the bot is first to act, the `/api/new_hand` response already contains its
initial action.

### Extras & the in-progress surface

The reference `ParseAction` in Slumbot's `sample_api.py` is the ground truth
for turning an action string into machine state (current street, bet-to, last
bettor, position to act, and the full set of validation errors — illegal
check/call/fold, bets too small or too big, overrunning the streets, `b20000c///`
all-in handling, optional trailing `/`). glance ports it verbatim and unit-
tests it against the reference's cases; the contract, including every error
path, is pinned in [research/slumbot.md](research/slumbot.md).

What glance adds on top (additive only, documented in the same file):
real-window mode, where the table is an [ACR](https://www.acrpoker.eu/) window
rather than a benchmark server and the same `incr` vocabulary drives the
clicks; the mapping between the parsed state JSON above and the action grammar;
and a state-diff event log for replay/audit. The glance-specific helpers
(`POST /capture`, `GET /state`) stay outside the Slumbot contract — extras a
standard client simply ignores.

## Selftest

```sh
build/glance-selftest
# optional: leave generated mapping + screenshot around for server smoke tests
build/glance-selftest --fixtures /tmp/acr-fixtures
```

The selftest synthesizes its own scenario (anchor, cards, button, dealer, a
screenshot with text numbers), writes a real mapping file and image to disk,
and runs the full pipeline — including the state-validation checks and the
OCR number-parsing unit cases (thousands separators and all). The numeric
*OCR* checks are skipped when tesseract is absent; CI
(`.github/workflows/ci.yml`) runs on ubuntu-24.04 **with** tesseract
installed, so the canonical full check is the CI run — a machine without
tesseract (e.g. the lab) stays green minus those.

## Packages and the `glance` command

Support for one application ships as a **package**: a folder with
`glance-package.json` plus table mappings and template PNGs (data only, so
it installs the same way on every OS). ACR Poker is the default built-in
package `acr` (`glance/packages/acr/`).

```sh
glance pkg list                      # built-in + user packages
glance pkg install ./my-app-package  # or a git URL; --force to upgrade
glance pkg remove my-app
glance serve --package acr           # = glance-server acr
glance state | capture shot.png | read-card card.png | packages   # API client
```

The HTTP API stays the integration point: the web dashboard (read-only), the
Qt admin app and any external system are all clients of it. Contract:
`glance/core/include/packages.h`.

## Table mapping

A package's mappings are table-mapping JSON files (the "table skin"
descriptor): which template PNGs to look for and where each field sits. See
[research/acr.md](research/acr.md) for the format and the scraping technique,
and `glance/packages/acr/mappings/6max.json` for a starter. When the control plane
lands (roadmap M1–M2), the same file carries its targets — named `actions`
(e.g. `call` → a button rectangle) and the window to drive — so reading and
clicking share one source of truth.

## Layout

```
glance/              # repo root
├── glance/          # the C++ project
│   ├── CMakeLists.txt     # pinned deps (OpenCV distro pkg, json, httplib)
│   ├── core/              # generic engine: mapping, template match, OCR,
│   │   ├── include/       #   scraper, service, state validation, screen
│   │   │                  #   + input control (no poker knowledge)
│   │   └── src/           #   (incl. the optional X11 backend)
│   ├── packages/acr/      # default package: ACR Poker mapping (+ templates)
│   ├── server/main.cpp    # glance-server (compat entry; = glance serve)
│   ├── tools/             # glance CLI, selftest, webtest, pkgtest, cardvision
│   ├── web/               # dashboard (embedded into the server binary)
│   ├── app/               # Qt admin desktop app (optional)
│   └── testdata/          # card-vision glyph templates
├── docs/            # architecture.md (system map), engine.md (internals),
│                    #   README.md (vision + roadmap), models.md (where we evolve to)
└── research/        # Python side, uv-managed
    ├── notebooks/     #   YOLO card-detection experiments
    ├── poker_apis/    #   PaddleOCR vision-pipeline research prototype
    │                  #   (FastAPI; the source the state validators were
    │                  #   ported from)
    ├── frontend/      #   React dashboard prototype
    ├── tests/         #   research-prototype test suite
    └── scripts/       #   host setup (install_deps.sh, ...)
```

## Development

- Deps: OpenCV comes from the distro (`libopencv-dev`; pinned to >= 4.5 in
  CMakeLists), json + httplib are pinned in `CMakeLists.txt` via FetchContent —
  bump versions there to update, no lockfile.
- The build is small (glance's sources + two single-header deps); there is no
  OpenCV build step to wait for.
- No linter/format tooling yet.

References (prior art, related projects): see [research/README.md](research/README.md#references).
