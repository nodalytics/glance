# glance — architecture

How everything works, layer by layer. Keep this in sync with the code: if a
box below stops matching the source, the doc is stale.

## 1. The one-line picture

A screenshot goes in as image bytes; parsed table state comes out as JSON —
and, since milestone M1, the same HTTP surface drives the platform back:
`POST /click`, `/key`, `/sequence` turn client coordinates and named actions
(defined in the mapping JSON) into screen-absolute input injected by the
platform backend (X11/XTest on Linux, SendInput on Windows, CGEvent on
macOS), or by a null backend on machines without a display. **glance is the screen's replacement API** — for platforms
that expose no programming interface at all, it manufactures one from pixels,
in both directions.

```
                 +-----------------------------------------------------------+
                 |              client (bot / research / curl)               |
                 +-----------------------------------+-----------------------+
                                                     |
                     POST /capture (PNG/JPEG bytes)  |  GET /state, /health
                                                     v
   +---------------------------------------------------------------------+
   |  glance serve / glance-server  (core/app_server.cpp, cpp-httplib) |
   |  - owns the HTTP surface (+ dashboard, /info, /packages)           |
   |  - resolves the package -> mapping, builds the TableScraper        |
   |  - wires it into the ScreenshotService and the ControlService      |
   +---------------------------------+-----------------------------------+
                                     | .update(img_bytes)
                                     v
   +---------------------------------------------------------------------+
   |  ScreenshotService  (core/server.cpp)  -- stateful glue            |
   |  decodes image (imdecode), calls scraper->scrape(), keeps last     |
   |  frame + state_json for GET /state. No platform knowledge.         |
   +---------------------------------+-----------------------------------+
                                     | .scrape(cv::Mat)
                                     v
    +---------------------------------------------------------------------+
    |  ControlRoutes / ControlService  (core/server_control.cpp,         |
    |                                   control_service.cpp)  -- M1      |
    |  HTTP control routes; records every capture as the INPUT-SPACE     |
    |  reference; resolves mapping "actions" to screen-absolute centres; |
    |  converts client coordinates to screen-absolute. No platform       |
    |  knowledge — the platform is the Backend behind it.                |
    +---------------------------------+-----------------------------------+
                                      | Screen::grab / Input::click / key
                                      v
    +---------------------------------------------------------------------+
    |  control backend  (core/src/screen_{x11,win,mac}.cpp or null)      |
    |  Screen (pixel grab) + Input (synthetic mouse/keys) + name;        |
    |  make_default() picks the platform backend compiled in at          |
    |  configure time, else null (same optional pattern as tesseract).   |
    +---------------------------------------------------------------------+
   +---------------------------------------------------------------------+
   |  package  (packages/<name>/, e.g. packages/acr)  -- the app "skin" |
   |  glance-package.json + mappings + templates: DATA, no code.        |
   |  A new application = a new package (`glance pkg install`).         |
   +---------------------------------+-----------------------------------+
                                     | (composition)
                                     v
   +---------------------------------------------------------------------+
   |  TableScraper  (core/scraper.cpp)  -- the generic engine          |
   |  mapping.json + screenshot  ->  TableState                         |
   |  uses only the primitives below; no UI, no network                 |
   +-------+------------------------------+------------------------------+
           |                              |
           v                              v
   +-----------------------+    +----------------------+
   | template_match.cpp    |    | ocr.cpp              |
   | find_template,        |    | ocr_number,          |
   | find_template_in_area,|    | prepare_for_ocr      |
   | has_template_in_area, |    | (tesseract via       |
   | count_template_hits   |    |  subprocess,         |
   | (TM_SQDIFF_NORMED)    |    |  optional dependency)|
   +-----------------------+    +----------------------+
           |
           v
   +-----------------------+
   | mapping.cpp           |
   | parses the skin JSON: |
   | anchor, cards,        |
   | buttons, dealer,      |
   | stacks -> structs     |
   +-----------------------+
```

## 2. One request, end to end

```
  client                          glance-server                 core
    |                                  |                        |
    |  POST /capture  <raw bytes>      |                        |
    |--------------------------------->|                        |
    |                                  |  decode PNG/JPEG       |
    |                                  |  (cv::imdecode)        |
    |                                  |----------------------->|
    |                                  |                        | 1. ANCHOR
    |                                  |                        |    find_template(
    |                                  |                        |      shot,
    |                                  |                        |      anchor.png)
    |                                  |                        |    -> origin (ox,oy)
    |                                  |                        |       or 422
    |                                  |                        | 2. CROP
    |                                  |                        |    window =
    |                                  |                        |      shot[
    |                                  |                        |      oy..oy+h,
    |                                  |                        |      ox..ox+w]
    |                                  |                        | 3. BUTTONS
    |                                  |                        |    has_template_
    |                                  |                        |      in_area(call)
    |                                  |                        |      -> my_turn
    |                                  |                        | 4. CARDS
    |                                  |                        |    per slot:
    |                                  |                        |      try whole
    |                                  |                        |      card library
    |                                  |                        | 5. NUMBERS
    |                                  |                        |    ocr_number()
    |                                  |                        |      per stack/
    |                                  |                        |      bet/pot box
    |                                  |                        | 6. DEALER
    |                                  |                        |    dealer chip
    |                                  |                        |      per seat
    |                                  |   TableState           | 7. DERIVE
    |                                  |                       |    stage from
    |                                  |                       |    board count
    |                                  |                       | 8. VALIDATE
    |                                  |                       |    validate_table_
    |                                  |<----------------------|    state(); "validation"
    |                                  |   to_json(state +     |    block in the JSON
    |                                  |   validation)         |
    |   200 {table state JSON}         |                        |
    |<---------------------------------|                        |
```

Step-by-step in the code (`TableScraper::scrape`, `core/src/scraper.cpp`):

1. **Anchor** — `find_template` for `topleft` with `anchor_threshold`. No
   hit → `nullopt` from the server as 422. One hit pins the whole table.
2. **Crop** — fixed `crop` size at the anchor → `window`; every later
   coordinate is relative to it (that is why a moved window is re-found with
   a single 32×32-ish template match).
3. **Action state** — each `buttons` entry: `has_template_in_area`. Any hit →
   `my_turn = true`.
4. **Cards** — each slot in `cards` × each template in `card_templates`:
   first template matching inside the slot's area sets the card; `covered`
   means "opponent in the hand, unknown"; no match means empty slot.
5. **Numbers** — for each `stacks` key (pots, per-seat stacks/bets, call,
   raise): crop the region, `prepare_for_ocr` (resize/grayscale/binarize),
   `ocr_number` → optional double. When tesseract is absent these fields are
   simply absent from the JSON — the rest of the state still works.
6. **Dealer button** — which seat area the dealer template sits in.
7. **Derived state** — game stage from board-card count (0/3/4/5 →
    PreFlop/Flop/Turn/River).
8. **Validation** — `validate_table_state` (core/include/state_validation.h)
   sanity-checks the parsed state for internal consistency: a card face
   appearing in more than one slot (DUPLICATE_CARD — a pocket pair like A♠+A♥
   is *legal*; only identical rank+suit is flagged), board gaps, board
   overflow, stage/board-count mismatch, and negative amounts. It never
   mutates the state and never blocks the response; it produces a
   `validation` block (`{valid, errors[], warnings[]}`) added to the JSON so
   clients can distrust a broken state. No OCR, no pixels — pure logic, so it
   runs on every build. Ported from the Python research prototype
   (research/poker_apis/validation/card_state_validator.py).
Then `to_json` serializes the state with empty fields omitted (seat 0 in the
engine, the bot, becomes seat 1 in the JSON) and appends the validation
report from step 8 as a `validation` key.

## 3. Who knows what (the layering contract)

| Layer                | Knows about                  | Must NOT know about            |
|----------------------|------------------------------|--------------------------------|
| `app_server.cpp`     | HTTP verbs, exit codes       | card faces, seat numbers       |
| `ScreenshotService`  | "last frame + last state"    | what a table *is*              |
| `ControlService`     | "last frame's input space",  | pixels, the platform, what an  |
|                      | action->coordinate           |   action *means*               |
| `control backend`    | the platform's pixels &      | tables, mappings, card faces   |
|                      | input device (x11/win32/     |                                |
|                      | macos/null)                  |                                |
| package (data)       | one app's layout & mapping   | HTTP, OpenCV details, code     |
| `TableScraper`       | anchors, slots, thresholds   | ACR specifically (any skin)    |
| `template_match.cpp` | pixel similarity             | games, tables, cards           |
| `ocr.cpp`            | digits in a region           | poker, money, seats            |
| `state_validation`   | internal consistency of a    | pixels, OCR, the HTTP layer    |
|                      | parsed state                 |                                |

Two rules make this hold:

- **The mapping JSON is the only platform-specific input.** Everything a
  scraper does comes from `name/crop/topleft/cards/buttons/dealer/stacks`
  (contract in `core/include/mapping.h` and `research/acr.md`). A new application is
  data only: a package (`core/include/packages.h`).
- **Control attaches to the same seam (milestone M1, landed).** The
  `ControlService` (core/control_service.cpp, routes in
  core/server_control.cpp) is another `core/` service driven by the *same*
  `TableScraper`: it records every capture — a server-side grab, a located
  window, or a frame POSTed to /capture — as the **input-space reference**
  (client coordinates are re-based to screen-absolute with that frame's
  origin), and resolves the mapping's `actions` names to the centre of the
  existing `buttons`/`stacks` rectangles. The platform itself is a
  `Screen`+`Input` *backend* behind it (X11, Win32 or macOS — see below —
  when compiled in at configure time, null otherwise — the same
  configure-time-optional pattern as tesseract), so the arrow direction is
  unchanged: the service is platform-ignorant, the backend is game-ignorant.

### Control backends (per platform)

One `Screen`+`Input` pair per OS (`core/include/control.h`), each in its own
file, each compiled only on its OS and only when its CMake option is ON
(default ON); `make_default()` in `core/src/control.cpp` returns whichever was
compiled in, else `make_null()`. Every backend fails its *calls* (grab returns
false, input is dropped), never its construction, when there is no usable
display or permission — so the server always starts.

| Backend (`backend_name`) | Option / file | Grab | Window lookup | Input |
|---|---|---|---|---|
| `x11` | `GLANCE_X11`, `screen_x11.cpp` (needs libx11-dev libxext-dev libxtst-dev) | `XGetImage` on the root window | `_NET_WM_NAME`/`WM_NAME` walk of the window tree; client-window geometry | XTest fake motion/button/key events |
| `win32` | `GLANCE_WIN32`, `screen_win.cpp` (system libs user32/gdi32/dwmapi) | GDI `BitBlt` (`SRCCOPY\|CAPTUREBLT`) of the virtual desktop into a 32-bit top-down DIB section | `EnumWindows` + `GetWindowTextW` (UTF-16 → lower-case substring; visible, non-minimized, non-cloaked); client area via `GetClientRect`+`ClientToScreen`, falling back to `DWMWA_EXTENDED_FRAME_BOUNDS`/`GetWindowRect` | `SendInput`: absolute moves normalized 0..65535 with `MOUSEEVENTF_VIRTUALDESK`; named keys → VK codes (extended-key flag, scancode filled), characters via `VkKeyScanW`; `type_text` via `KEYEVENTF_UNICODE` |
| `macos` | `GLANCE_MACOS`, `screen_mac.cpp` (CoreGraphics + CoreFoundation frameworks) | `CGWindowListCreateImage` (fallback `CGDisplayCreateImageForRect`) drawn into a BGRA bitmap context | `CGWindowListCopyWindowInfo`, layer-0 on-screen windows front to back, `kCGWindowName` then `kCGWindowOwnerName` (case-insensitive `CFStringFind`); frame = `kCGWindowBounds` (includes the title bar) | `CGEventCreateMouseEvent` / `CGEventCreateKeyboardEvent` posted at the HID tap; text via `CGEventKeyboardSetUnicodeString` |
| `null` | always (`control.cpp`) | deterministic checkerboard | unsupported | recorded, no-op |

Coordinate space is the same everywhere: **screen-absolute pixels with 0,0 at
the top-left of the virtual desktop** (the bounding box of all monitors).

- **Windows**: physical pixels. The process is made per-monitor DPI aware
  (`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`, falling back to
  `SetProcessDPIAware`) when the backend is created, so GDI and SendInput are
  not DPI-virtualized. The Win32 virtual-screen origin
  (`SM_XVIRTUALSCREEN`/`SM_YVIRTUALSCREEN`, negative with a monitor left of or
  above the primary) is subtracted, so glance coordinates never go negative.
  `SendInput` obeys UIPI: input aimed at an elevated window is dropped unless
  glance runs elevated too. Session-0 services have no desktop to grab.
- **macOS**: Quartz works in *points*; glance space is *pixels* = (global
  point − top-left of the union of active displays) × the main display's
  backing scale factor (2 on Retina). Grabs come back at native Retina
  resolution and the same numbers fed to `/click` land on the same pixels.
  With mixed-scale displays the secondary ones are resampled to the main
  display's scale. **Permissions** (System Settings → Privacy & Security, for
  the binary or the terminal launching it): *Screen Recording* — without it
  grabs show only the desktop/own windows and other apps' window titles are
  hidden (lookup then matches only owner/app names); *Accessibility* —
  without it posted events are silently dropped. `CGWindowListCreateImage` and
  `CGDisplayCreateImageForRect` are deprecated (macOS 14) and *obsoleted* in
  the macOS 15 SDK (a hard compile error at deployment target ≥ 15), so they
  are resolved at runtime with `dlsym` and the file builds against any SDK.
  Future work: a ScreenCaptureKit (`SCScreenshotManager`, Objective-C++)
  grab path for OS releases that drop those symbols.

## 4. Design invariants

1. **Screenshot-in / JSON-out.** Nothing platform-specific crosses the HTTP
   wire; clients stay dumb and reusable.
2. **Anchoring beats coordinates.** One unique anchor hit + relative
   rectangles = robustness under window moves without per-field search.
3. **Symbolic vs numeric.** Fixed pixels (cards, buttons, chips) are
   template-matched; varying digits are OCR'd — and only that second class is
   optional, so the failure mode of "no tesseract" is "no numbers", never
   "no server".
4. **Configure-time, not link-time, optionals.** `GLANCE_OCR` is decided
   by `find_program(tesseract)` at configure time and burned in as a compiled
   default; `ocr_available()` still re-checks the binary at runtime. The same
   pattern exists for the control backends (`GLANCE_X11`, `GLANCE_WIN32`,
   `GLANCE_MACOS`): the platform's dev packages/SDK decide whether its
   screen/input backend is compiled in, and `backend_name()` reports
   `null` at runtime on machines without one — the build never breaks and a
   headless machine degrades to "no display", never to "no server".
5. **Synth-proof correctness.** `glance-selftest` generates its own
   anchor/cards/screenshots and runs this whole path; a change that breaks
   the pipeline is caught by `ctest` without a browser window open.

## 5. What runs where (process picture)

```
  +---------------------------  one machine  --------------------+
  |                                                               |
  |  +----------------+   HTTP   +--------------------------+   |
  |  | capture source | --------> | glance-server            |   |
  |  | (screenshotter |  :8000   |   - ScreenshotService     |   |
  |  |  tool / window |          |     + TableScraper        |   |
  |  |  grab)         | <-------- (JSON)  + templates in mem |   |
  |  +----------------+          |   + tesseract (spawned   |   |
  |                              |     per number read)     |   |
  |  +----------------+   HTTP   +--------------------------+   |
  |  | bot / research | --------> (JSON)  + ControlService  |   |
  |  | client         | <----  POST (state)   + control     |   |
  |  +----------------+              /click /key   backend  |   |
  |                                    /sequence  (x11/win32 |   |
  |                                               /macos)   |   |
  +-----------------------------------------------------------+
```

Nothing here is a daemon: `glance-server` holds state only "last frame" and
"last input-space reference" — the capture cadence lives in whatever posts to
it, which is what keeps the server boring.

## 6. Control API (HTTP)

All routes are plain, flat paths — `/grab`, `/click`, `/key`, `/sequence`,
`/health`, `/info`, `/login`, `/new_hand`, `/act` — never nested (`/api/...`
or `/slumbot/...`). Bodies and responses are JSON unless noted. Routes are
registered by `ControlRoutes` (`core/src/server_control.cpp`),
`DashboardRoutes` (`/info`, `core/src/server_dashboard.cpp`) and
`SlumbotRoutes` (`core/src/server_slumbot.cpp`).

### Coordinate spaces (read this first)

There are two spaces, and the control layer converts between them
(`ControlService::to_screen`, `core/src/control_service.cpp`):

- **Screen-absolute**: pixels with `0,0` at the top-left of the virtual
  desktop. This is what the platform backend injects, and it is the space of
  the `x`/`y` a `/click` response reports.
- **Last-capture space**: pixels relative to the top-left of the *last frame
  glance captured*. Every `/click` request coordinate and every named action
  is expressed here. How the frame was obtained decides the conversion:
  - a `POST /grab` of a **region** or **window** carries that region/window's
    screen origin, so a request coordinate `(x,y)` is injected at
    `(x + origin_x, y + origin_y)`;
  - a whole-desktop grab has origin `(0,0)`, so its space already *is*
    screen-absolute;
  - a frame a client sent to `POST /capture` is used **as given** — no origin
    is added (clients are expected to POST whole-desktop grabs; for a
    window-relative frame use `POST /grab` with a title instead).

A **named action** is a key in the mapping's `"actions"` section
(`core/include/mapping.h`). Its value is `"button:<name>"` (a rectangle from
the mapping's `"buttons"`) or `"stack:<key>"` (a rectangle from `"stacks"`);
`control::resolve_action` returns the **centre** of that rectangle, placed at
the last capture's anchored table origin, in last-capture space — then
re-based to screen-absolute exactly like a raw coordinate. An action resolves
only when the table anchor was found in the last capture; otherwise the click
is refused (422) rather than landing on a guess.

### POST /grab — server-side grab

The server grabs the screen itself; the grabbed frame becomes the
input-space reference and is parsed. Body (all fields optional):

```jsonc
{"region": {"x": 0, "y": 0, "w": 1920, "h": 1080}}  // grab a screen rectangle
{"title": "ACR"}                                     // grab the matching window
{}                                                   // grab the mapping's window_title
```

- 200: `{"table_found": bool, "state"?: {…}}` (the parsed state when the table
  was found).
- 400: no `region`/`title` and the mapping has no `window_title`, or a
  non-string/empty `title`.
- 422: the platform grab failed (no display, window not found).

### POST /click — one click

```jsonc
{"action": "call"}                       // a named action (mapping "actions")
{"action": "button:call"}                // a direct button:/stack: target
{"click": {"x": 120, "y": 40, "button": 1}}  // raw point in last-capture space
```

`button` is 1=left, 2=middle, 3=right (default 1).

- 200: `{"x", "y", "kind", "action"?}` — `x`/`y` are screen-absolute, `kind`
  is `"button"`, `"stack"` or `"raw"`, `action` echoes a named target.
- 400: body is not a JSON object, or has neither `action` nor `click`.
- 422: an action that cannot be resolved (unknown name, unknown target, or the
  table is not anchored in the last capture).

### POST /key — one key press or typed text

```jsonc
{"key": "Return"}   // one keysym (X keysym names: Return, Tab, F5, 9, a, …)
{"type": "200"}     // type a short printable string (chip amounts, chat)
```

- 200: `{}`.
- 400: body is not a JSON object, or has neither `key` nor `type`.
- 422: the backend rejected the key (unrecognised keysym).

### POST /sequence — a batch of steps

Body is a JSON **array** of steps, each one of the `/click`/`/key` shapes:
`{"action":…}`, `{"click":{…}}`, `{"key":…}` or `{"type":…}`. Steps run in
order; every step is reported whether it succeeded or not (an audit trail).

- 200: `{"steps": [{"request", "ok", "error"?, "detail"?}, …]}`.
- 400: the body is not a JSON array.

### GET /health — liveness + control state

200: `{"status": "ok", "control": {"backend": "x11"|"win32"|"macos"|"null"|…,
"window"?: {"title","x","y"}}}`. `window` appears only when the last grab was
of a located window.

### GET /info — build + configuration

200 includes `name`, `version`, `ocr_available`, `control_backend`, a
`mapping` object (`name`, `window_title`, `actions[]`), a `card_vision`
object, and a `control` object: `{"backend": …, "endpoints": ["/grab",
"/click", "/key", "/sequence", "/login", "/new_hand", "/act"]}` so a client can
discover the control surface without the docs.

### The Slumbot-mirroring control plane (POST /login, /new_hand, /act)

These mirror the Slumbot protocol's bodies, token rules and action grammar
(`research/slumbot.md`) under glance's flat paths. They are a thin
real-window **control + translation** surface over the services above — **not
a poker game engine**: glance does not deal cards or run a game, it reads the
real table and clicks it. Errors ride inside a **200** body as `error_msg`
(the Slumbot convention — parse the body, not just the status); a genuinely
malformed HTTP request (unparseable JSON) is still a 400.

What is real: the opaque session token + in-memory session map; the ported
`ParseAction` validator (`core/src/slumbot_action.cpp`) run on every `/act`;
the action → named-control-action → click mapping; and the Slumbot-shaped
state readback from the last parsed `TableState`. What is roadmap: no real
auth (any/empty credentials mint a token), no dealing or turn enforcement, no
auto-recapture after a click (call `/grab` or `/capture` again to see the
result), and no typing of a specific bet size for `b<n>` (only the `"raise"`
button is clicked).

- **POST /login** `{username?, password?}` → `{token}`. Any (or empty)
  credentials mint an opaque session token. 400 on a malformed body.
- **POST /new_hand** `{token?}` → the Slumbot-shaped response
  `{old_action:"", action:"", client_pos, hole_cards, board, token, state?}`.
  The token may be omitted **only** on the very first call (then one is
  minted); a provided token must be a known session. `client_pos` is `0`=big
  blind / `1`=small blind, derived from the parsed dealer (the hero is seat 0;
  holding the button in heads-up means small blind). `hole_cards` and `board`
  come from the last parsed state; `state` is the full glance state JSON when a
  capture is available. With no state yet: 200 with an `error_msg`.
- **POST /act** `{token, incr}` → the updated Slumbot-shaped response (plus an
  `injected` detail of the click). `incr` is validated with `ParseAction`
  (illegal strings come back as `error_msg`); its **last** action token maps to
  a named control action — `f`→`"fold"`, `c`→`"call"`, `k`→`"check"`,
  `b<n>`→`"raise"` — resolved through the mapping's `"actions"` and injected
  via the `ControlService`. A missing action in the mapping, or a click that
  cannot be resolved (table not anchored), is reported as an `error_msg`.
