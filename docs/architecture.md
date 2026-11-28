# glance — system architecture

The whole system on one page: what the parts are, how they connect, and
where each one lives. For the engine internals (one request traced through
every layer, the layering contract, the design invariants), see
[docs/engine.md](engine.md). For the vision
and roadmap, see [docs/README.md](README.md).

## 1. What glance is

glance turns the **screen into an API**. It is built for software that has no
SDK, no event feed and no API: it grabs the window, works out what is on
screen, serves that as JSON, and drives the app back with synthetic mouse and
keyboard input. Poker (ACR) is the first target. The north star is to operate
**any desktop app it comes across, hands-off** ([docs](README.md),
[models](models.md)).

## 2. The big picture

```
  ┌──────────── three front ends (API clients) ─────────────┐   ┌── integrations ──┐
  │  web dashboard          Qt admin app        glance CLI  │   │ bots, loggers,   │
  │  (read-only, served     (glance/app, admin  (tools/     │   │ research         │
  │   by the server)         controls)           glance_cli)│   │ pipelines, …     │
  └───────────┬───────────────────┬──────────────────┬──────┘   └────────┬─────────┘
              └───────────────────┴──────── HTTP/JSON ───┴────────────────────┘
                                             │
  ┌──────────────────────────────────────────▼─────────────────────────────────────────┐
  │  glance serve  (core/app_server.cpp + cpp-httplib)                                 │
  │   state:   POST /capture · GET /state · GET /frame.png · POST /recognize-card      │
  │   control: POST /grab /click /key /sequence            (ControlRoutes)             │
  │   system:  GET /health /info /packages · GET / (dashboard, embedded in the binary) │
  └───────┬───────────────────────────────┬──────────────────────────────┬─────────────┘
          │ image bytes                   │ named action / coordinates   │ package spec
  ┌───────▼────────────┐        ┌─────────▼───────────┐        ┌─────────▼────────────┐
  │ ScreenshotService  │        │ ControlService      │        │ packages             │
  │ decode → scrape →  │        │ action → screen     │        │ (core/packages.cpp)  │
  │ keep frame + state │        │ coords, input space │        │ find / install /     │
  └───────┬────────────┘        └─────────┬───────────┘        │ resolve mapping      │
          │                               │                    └─────────┬────────────┘
  ┌───────▼───────────────────────────────┼──────────────────────────────▼────────────┐
  │  TableScraper (core/scraper.cpp) — the generic engine: mapping + image → state    │
  │   anchor → crop → buttons/dealer (template match) → cards (templates, else card   │
  │   vision) → numbers (OCR) → derived state → validation                            │
  ├───────────────┬──────────────────┬─────────────────┬─────────────────┬────────────┤
  │ template_match│ card_vision      │ ocr             │ state_validation│ mapping    │
  │ (OpenCV)      │ occupancy, suit  │ (tesseract,     │ (impossible     │ (JSON      │
  │               │ shapes, rank     │  optional)      │  states → JSON  │  contract) │
  │               │ glyphs           │                 │  errors)        │            │
  └───────────────┴──────────────────┴─────────────────┴─────────────────┴────────────┘
                                          │
  ┌───────────────────────────────────────▼───────────────────────────────────────────┐
  │  platform backends (core/control.h: Screen + Input), chosen at configure time     │
  │   X11 (XGetImage + XTest) · Windows (GDI + SendInput) · macOS (CoreGraphics) ·    │
  │   null (headless fallback)                                                        │
  └───────────────────────────────────────────────────────────────────────────────────┘
```

## 3. The parts

### Engine (`glance/core/`)
Generic and platform-free: it never knows what it is looking at.
- **mapping**: the JSON contract describing where things are in a window
  and what they look like (`core/include/mapping.h`, `research/acr.md`).
- **scraper**: mapping + image → `TableState`. Template matching for
  symbolic fields, OCR for numbers, card vision for cards no template
  matched.
- **card vision**: reads cards without per-card templates. It checks
  occupancy, matches suit symbol shapes (Dice + Hu moments) and rank glyph
  templates, with tesseract as an optional cross-check. Ported from the
  Python research prototype; accuracy is gated in ctest on the research
  datasets.
- **ocr**: an optional tesseract subprocess. `ocr_available()` gates every
  read, so the build and tests work without it.
- **state validation**: flags impossible states (duplicate cards, board
  gaps, stage mismatch, negative amounts) in every state JSON.
- **control**: `Screen` (grab) + `Input` (mouse/keys) interfaces with a
  backend per OS, picked at configure time, with a null fallback.
- **server**: cpp-httplib routes; `serve()` wires everything together.
- **packages**: discovery, validation, install and removal of app packages.

### Packages (`glance/packages/`)
Everything app-specific is a **package**: a folder holding
`glance-package.json`, table mappings and template/glyph PNGs. Packages are
data only, so they install the same way on every OS with no compiler.
- **Built in:** `acr` (ACR Poker), shipped with glance.
- **User:** installed with `glance pkg install <dir|git-url>` into the user
  package directory.
- **Search order:** `$GLANCE_PACKAGES_PATH`, then user packages, then
  built-ins. A name found earlier shadows later ones.
- **Contract:** `glance/core/include/packages.h`. Packages are never
  installed over the network API; that is CLI-only.

### Front ends
glance ships **three** front ends. All are clients of the same HTTP API, and
that API is also the integration point for anything else (bots, loggers,
research pipelines), which are consumers, not front ends.

| Front end | Where | Role |
|---|---|---|
| Web dashboard | `glance/web/` (embedded into the binary) | **Read-only**: live table, capture upload, card lab, system info, JSON inspector |
| Qt admin app | `glance/app/` (optional, Qt6) | Admin: live state, capture, card lab, **control** (grab/click/key/sequence) |
| `glance` CLI | `glance/tools/glance_cli.cpp` | `serve`, `pkg …`, and client commands (`state`, `capture`, `read-card`, …) |

Admin input injection is deliberately **not** in the web dashboard.

### Platform layer
`GLANCE_X11`, `GLANCE_WIN32` and `GLANCE_MACOS` are configure-time options,
like tesseract and Qt: a missing dependency falls back to the null backend,
and the build still succeeds.

| Backend | Status |
|---|---|
| X11 | Compiled and tested in CI and on the lab; not yet exercised on a real display (#12) |
| Windows, macOS | Code written; awaiting their CI jobs |

## 4. Data flow

1. **Read.** A frame arrives, either a client `POST /capture` or a server
   grab of the package's `window_title`. The anchor template locates the
   window, fields are read relative to it, the state is validated, and
   `GET /state` returns the JSON.
2. **Act.** A client sends a named action (`POST /click {"action":"call"}`).
   The mapping resolves it to a rectangle, its centre is converted to
   screen-absolute coordinates, and the backend injects the input.
3. **Verify** (roadmap M4/M5). The next grab confirms the action had its
   effect; every grab, state and action is logged for replay and as
   training data.

## 5. Build, test, CI

- **Build:** CMake ≥ 3.24, C++20.
  - Uses the distro's prebuilt OpenCV 4.x, which is never built from
    source.
  - nlohmann/json and cpp-httplib are fetched, pinned in
    `glance/CMakeLists.txt`.
  - Optional parts: tesseract, X11/Win32/macOS, Qt6.
- **Tests (ctest):**
  - `selftest`: end-to-end engine checks on synthetic scenarios and fake
    control backends.
  - `webtest`: dashboard routes.
  - `pkgtest`: package management.
  - `cardvision_*`: accuracy gates on `research/test_assets/validation`,
    allowing **zero** wrong cards.
- **Where it runs:** the lab is the primary build host. CI
  (`.github/workflows/ci.yml`) is the canonical full run, and the only
  place OCR runs.
- **Project skills:** `glance-verify` (build, test, CI) and
  `glance-bug-hunt` (`.claude/skills/`).

## 6. Research and models

- **`research/`:** the Python prototype (PaddleOCR pipeline, FastAPI,
  React prototype), its labelled datasets, notebooks and references
  ([research/README.md](../research/README.md)). Ideas are tried here first,
  then ported to C++ and gated.
- **Where glance evolves to:** its own foundation model for understanding
  and operating any desktop app ([docs/models.md](models.md)).
  It would be trained on glance's own grabs, states and verified action
  traces, running behind the same `Screen`/`Input` and state-JSON
  contracts. The C++ engine stays the fast, deterministic runtime.

## 7. Repository map

```
.
├── docs/                    # architecture.md (this file), engine.md, README.md (vision),
│                            #   models.md
├── AGENTS.md                # conventions for contributors and agents
├── README.md                # build, run, API
├── .claude/skills/          # glance-verify, glance-bug-hunt
├── .github/workflows/       # CI
├── glance/                  # the C++ project
│   ├── core/                #   engine (include/ + src/)
│   ├── packages/acr/        #   default package: ACR Poker
│   ├── server/              #   glance-server (compat entry)
│   ├── tools/               #   glance CLI, selftest, webtest, pkgtest, cardvision, opencv probe
│   ├── web/                 #   dashboard sources (embedded at build time)
│   ├── app/                 #   Qt admin app (optional)
│   ├── cmake/               #   build helpers (web embedding)
│   ├── testdata/            #   card-vision suit/rank templates
└── research/                # Python prototype, datasets, frontend prototype, references
```
