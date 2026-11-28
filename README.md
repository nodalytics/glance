# Glance

**glance turns the screen into an API.** For software with no SDK, no event
feed and no API, the screen is the only interface — so glance grabs the
window, reads what is on it (OpenCV template matching + card vision + optional
OCR), serves that as JSON over a small HTTP API, and drives the app back with
synthetic mouse and keyboard input. The engine never knows what it is looking
at; each application is an installable **package** of mappings and templates.

The first target is poker (ACR Poker), shipped as the built-in `acr` package.
The north star is to operate **any desktop app, hands-off** — no per-app SDK,
no human at the keyboard. See [docs/README.md](docs/README.md) for the vision
and roadmap, and [docs/models.md](docs/models.md) for where it evolves to.

- [docs/architecture.md](docs/architecture.md) — the whole-system map (engine,
  packages, the three front ends, platform backends).
- [docs/engine.md](docs/engine.md) — engine internals, a request end to end.
- Poker, the ACR scraping technique and the Slumbot control-plane spec live in
  [research/README.md](research/README.md) (`research/acr.md`,
  `research/slumbot.md`).

## Prerequisites

- CMake >= 3.24 and a C++20 compiler (g++ 13 on Ubuntu 24.04 is the reference)
- `libopencv-dev` — the distro's prebuilt OpenCV 4.x. glance links it; it is
  never built from source. (`bash research/scripts/install_deps.sh` installs
  the toolchain + OpenCV in one go.)
- Optional: `tesseract-ocr` — enables reading numbers (pot/stack/bet); the
  build auto-disables OCR when the binary is missing.
- Optional: `libx11-dev libxext-dev libxtst-dev` (Linux) — the X11 screen-grab
  / synthetic-input backend. Like OCR it is configure-time: without the headers
  the build still succeeds on the null backend. Windows (GDI + SendInput) and
  macOS (CoreGraphics) backends build on their own platforms.
- Optional: `qt6-base-dev` — the `glance-admin` desktop app.

nlohmann/json and cpp-httplib are single-header deps fetched by CMake.

## Build

```sh
cd glance
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
ctest --test-dir build        # selftest, webtest, pkgtest, card-vision gates
```

Targets: `glance` (the CLI + server), `glance-server` (compat entry),
`glance-admin` (Qt app, when Qt6 is found), and the test tools.

## The `glance` command and packages

Support for one application ships as a **package**: a directory with a
`glance-package.json` manifest plus table mappings and template PNGs — data
only, so it installs the same way on Linux, Windows and macOS with no compiler.

```sh
glance serve --package acr            # serve the built-in ACR package
glance serve --mapping path/to.json   # or a bare mapping file
glance pkg list                       # built-in + user packages
glance pkg install ./my-app-package   # or a git URL; --force to upgrade
glance pkg remove my-app

glance health | info | state | packages      # API client commands
glance capture shot.png                       # POST a screenshot, print state
glance read-card card.png [--slot board1]     # recognize one card crop
```

## HTTP API

`glance serve` (and `glance-server`) exposes the API and a read-only web
dashboard on the same port (default 8000).

| Endpoint | What it does |
| --- | --- |
| `GET /` | the web dashboard (read-only: live table, capture, card lab, system, JSON) |
| `GET /health` | liveness + control backend name |
| `GET /info` | version, OCR availability, control backend, active package/mapping, card-vision config |
| `GET /packages` | installed packages and the active one |
| `POST /capture` | body: raw PNG/JPEG bytes of the window (≤ 16 MB) → parses and returns the state JSON (422 when the anchor is not found) |
| `GET /state` | last successfully parsed state (404 until the first capture) |
| `GET /frame.png` | the last captured frame (404 until the first capture) |
| `POST /recognize-card[?slot=]` | body: a card-crop image → the card-vision reading (409 when the mapping has no `card_vision`) |
| `POST /grab` `/click` `/key` `/sequence` | control: grab a window/region, click a named action or coordinates, inject keys/text |
| `POST /login` `/new_hand` `/act` | the Slumbot-mirroring control plane (plain flat paths): mint a token, read the hand's state, and take an action (`{token, incr}`) that maps to a click |

The control routes (`/grab`…`/act`) are a thin control + translation surface,
not a game engine; their request/response JSON, status codes and coordinate
spaces are documented in [docs/engine.md](docs/engine.md), and the
Slumbot-grammar contract (bodies, tokens, `ParseAction` errors) in
[research/slumbot.md](research/slumbot.md). Every path is plain and flat — no
`/api` or `/slumbot` nesting.

```sh
curl -s -X POST --data-binary @screenshot.png http://127.0.0.1:8000/capture | jq
```

State shape (field presence is data-driven — a seat's `cards`/`stack`/`bet`
and the board/stage/pot appear only when actually read):

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

Every state carries a `validation` block (duplicate card faces, board gaps,
stage/board mismatches, negative amounts, each with a `code`, `message` and
affected `slots`), so a client can distrust any state that is not
`"valid": true`.

## Front ends

Three, all clients of the HTTP API above, which is also the integration point
for anything else (bots, loggers, research pipelines):

- **Web dashboard** — read-only, served by `glance serve` itself (embedded in
  the binary). Live table, capture, card lab, system info, JSON inspector.
- **`glance-admin`** — the Qt6 desktop app, the only front end with the
  **control** surface (grab/click/key/sequence) behind a confirm dialog.
- **`glance` CLI** — `serve`, `pkg …`, and the client commands above.

## Table mapping

A package's mappings are table-mapping JSON files: which template PNGs to look
for and where each field sits, plus named `actions` and the `window_title` to
drive. The contract is documented in `glance/core/include/mapping.h`; the
scraping technique and a worked ACR example are in
[research/acr.md](research/acr.md).

## Footprint

glance is meant to stay small, nimble, efficient and effective: the `glance`
binary is ~1.2 MB stripped, a card reads in ~2 ms, and CI enforces a size
budget. See the footprint section in
[docs/architecture.md](docs/architecture.md).

## Layout

```
.
├── docs/            # architecture.md (system map), engine.md (internals),
│                    #   README.md (vision + roadmap), models.md (where we evolve to)
├── glance/          # the C++ project
│   ├── core/              # generic engine (include/ + src/): mapping, template
│   │                      #   match, card vision, OCR, scraper, validation,
│   │                      #   control backends, packages, server
│   ├── packages/acr/      # default package: ACR Poker mapping (+ templates)
│   ├── server/            # glance-server (compat entry)
│   ├── tools/             # glance CLI, selftest, webtest, pkgtest, cardvision
│   ├── web/               # dashboard (embedded into the server binary)
│   ├── app/               # Qt admin desktop app (optional)
│   └── testdata/          # card-vision glyph templates
└── research/        # Python prototype, datasets, frontend prototype;
                     #   poker/ACR/Slumbot material (acr.md, slumbot.md)
```

## Development

- OpenCV comes from the distro (`libopencv-dev`, >= 4.5); json + httplib are
  pinned in `glance/CMakeLists.txt` via FetchContent — bump versions there.
- The lab is the primary build host; CI (`.github/workflows/ci.yml`) is the
  canonical full test across Linux, Windows and macOS, and the only place OCR
  runs. Project skills `glance-verify` and `glance-bug-hunt` are in
  `.claude/skills/`.

Prior art and related projects: see
[research/README.md](research/README.md#references).
