# glance-admin

A Qt6 Widgets desktop admin client for `glance-server`. It talks to the server
over HTTP only (QtNetwork), and links QtWidgets + QtNetwork and nothing else.
It does not link OpenCV or `glance_core`, so it builds on machines that have no
OpenCV.

Pages:

| Page | What it does |
|---|---|
| **Overview** | Polls `GET /health` and `GET /info`. Shows tiles for server, latency, control backend, OCR, mapping and card vision, plus a latency sparkline and the raw `/info` tree. |
| **Live table** | Polls `GET /state` (live toggle and interval) and paints it as a table: seats, stacks, bets, hole cards, dealer, board, pot, stage and my_turn. It also lists the server's `validation` errors and warnings, and outlines the flagged board slots. |
| **Capture** | Pick or drop a screenshot and send it with `POST /capture` (raw bytes). Shows `GET /frame.png`. Clicking the frame sends that point to Control as a raw click point. |
| **Card lab** | `POST /recognize-card[?slot=]` with a card crop. Shows the rank and suit, their confidences, margins and sources, rank verification, a score bar per suit, and occupancy metrics. A 409 means card vision is not configured. |
| **Control** | `POST /grab` (mapping window, title or region), `/click` (named actions or a raw point), `/key` (keysym or typed text) and `/sequence` (a JSON editor). Asks for confirmation before injecting input, and keeps an activity log. |
| **Inspector** | Every response as a JSON tree, raw text, the request, or an image. Polls are collapsed to the latest response per endpoint. |
| **Settings** | Theme (dark, light or system), poll intervals, timeout, auto-connect, input confirmation, and auto-fetching the frame. Saved with QSettings. |

Routes the server lacks (older builds without `/info`, `/frame.png` or
`/recognize-card`) show up as "no route" or "unknown". They are not treated as
errors.

## Build

You need Qt ≥ 6.2 (Widgets, Network), e.g. `apt install qt6-base-dev`.

Standalone (no OpenCV needed):

```sh
cmake -S glance/app -B build-app -DCMAKE_BUILD_TYPE=Release
cmake --build build-app -j$(nproc)
```

As part of the main build, `glance/CMakeLists.txt` adds this directory when
`GLANCE_APP=ON` (the default) and Qt6 is found. Otherwise it prints a STATUS
line and skips it. Turn it off with `-DGLANCE_APP=OFF`.

## Run

```sh
build-app/glance-admin                              # connects to the saved URL (default http://127.0.0.1:8080)
build-app/glance-admin --url http://lab:8080 --page table
build-app/glance-admin --demo                       # sample data, no server
```

| Flag | Meaning |
|---|---|
| `--url <url>` | Server base URL (also saved to settings) |
| `--theme dark\|light\|system` | Theme for this run (the saved default is changed in Settings) |
| `--page <key>` | Start page: `overview`, `table`, `capture`, `cards`, `control`, `inspector`, `settings` |
| `--demo` | Fill every page with sample data and do not connect |
| `--no-connect` | Do not auto-connect on start-up |
| `--screenshot <dir>` | Save a PNG of every page (dark, then light) into `<dir>` and exit. Uses demo data. Works headless with `QT_QPA_PLATFORM=offscreen` |
| `--live` | With `--screenshot`: connect to `--url` and capture real data instead of demo data |

Shortcuts: `Ctrl+1`…`Ctrl+7` switch pages, and `F5` refreshes the table.
