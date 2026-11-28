# glance — documentation

**glance** is the screen-grabbing platform of last resort: for platforms with
**no SDK, no event feed and no API at all**, the screen is the interface, and
we turn it into one. For poker platforms without APIs, that makes glance the
only option that works at all: template match + OCR on a grab of the window,
turned into clean JSON plus an HTTP control surface — so a bot reads the table
the way a human does: it looks.

The design principle: **the engine never knows what it is looking at.**
`core/` is a generic screen-scraping + control engine (it does not even know
that poker exists); every platform is a thin skin: a mapping file plus a few
hundred lines (`acr/`). Adding a new platform — poker, blackjack, dice,
crash, a game you play to farm a bonus — is a mapping file and some template
PNGs, not new code.

## The ultimate test: any desktop app, no human

Poker tables are the first target, not the finish line. **glance's ultimate
test is to navigate any desktop application it comes across, understand it,
and operate it without human assistance.** The bar is **hands-off desktop control**: once
started, nobody touches the mouse or keyboard. Pointed at an app it has never
seen — no mapping file, no templates, no SDK — glance should be able to:

1. **See** it: grab the window, find its controls, text, images and state;
2. **Understand** it: work out what the app is for, what each control does
   and what state the app is in (a learned, platform-free model of UIs, not
   a hand-written mapping per app);
3. **Operate** it: pick the actions that reach a goal, inject them through
   the same `Screen`/`Input` backends (X11, Windows, macOS), and check from
   the next grab that each action had the intended effect, recovering when
   it did not.

Getting there is open research, and we are prepared to do it ourselves:
when off-the-shelf models do not see or reason about arbitrary UIs well
enough (or cheaply/locally enough), **we research and train our own
foundation models** for screen understanding and action — trained on the
grabs, structured states and verified action traces glance itself produces
(use cases 1, 2 and 5 below are exactly that data pipeline). Nothing about
the model side is fixed: how screens are tokenized and arranged (pixel
patches, UI-element tokens, OCR text tokens, interleaved state/action
sequences), which encoders and decoders, and which architectures are all
research questions to try and measure, not settle up front. **This is where glance should evolve to** — see
[models.md](models.md) for the direction, borrowed ideas (Kronos) and the
research axes. The C++ engine
stays the fast, deterministic runtime; models plug in behind the same
`Screen`/`Input` + state-JSON contracts.

Everything below is a step towards that. Mapping files and template PNGs are
the scaffolding that gets one app working today; the template-free card
reader (`core/include/card_vision.h`), the generic engine/skin split, the
cross-platform control backends and the verify-after-act loop (M4/M5) are
the pieces that generalize. A feature that only works because a human
pre-mapped the screen is useful, but it does not pass the test; prefer
designs that move a step closer to "never seen it, operated it anyway".

## Use cases: what we can do with this

For platforms that expose nothing — no API, no hand-history file, no event
feed — the screen is the only interface, and glance turns it into one:

1. **Table logging / state recording.** Poll `/capture` (or later a cadence
   loop) and append every parsed state to a durable log. For a poker platform
   without a history export, this *is* the hand history: stack, bet, pot and
   card states per street, with timestamps, enough to reconstruct every hand.
2. **Research data source.** The JSON lines feed straight into the analysis
   stack in `research/` — distributions, timing stats, opponent tendencies,
   model training. The structured output exists so the research side never
   has to touch images.
3. **Bot control (the full loop, milestone M1 — landed).** Because the
   mapping already records every field's rectangle, the action targets (call
   button, raise bar, chips input) come from the same file: glance reads the
   table *and* clicks the answer. A decision loop that watches state and
   injects inputs is a thin client of the same HTTP surface — today
   `POST /click {"action": "call"}` does exactly that (see the control
   section in `architecture.md` and the HTTP routes in
   `core/include/server_control.h`).
4. **Multi-table awareness (M3).** One process, many window grabs (one skin
   per table, different coordinates): a cross-table view of where action is,
   used for switching, for correlated reads, or simply for tracking.
5. **Verification & replay (M5).** The event log makes every machine
   decision auditable: given a grab and the mapping, the parse is
   deterministic, so any action the bot took can be replayed and checked
   afterwards.

The first three all work today (1–2 are a client script away; 3 is a one-line
`POST /click` away); 4–5 are on the roadmap below.

## Reading order

- [architecture.md](architecture.md) — **start here**: the layer diagram, a
  request traced end to end, the "who knows what" layering contract, and the
  design invariants.
- [models.md](models.md) — where we evolve to: our own foundation model for
  understanding and operating any desktop app (direction, not built yet).
- [acr.md](acr.md) — the complete ACR Poker technique: anchor, crop, template
  matching, OCR, the mapping-JSON contract, and how to produce template PNGs.

## Where glance is today

- **Capture → state (poker)** — done. HTTP server, table mapping, template
  match for static elements, optional OCR for numbers (build passes without
  tesseract; numeric fields are just omitted), end-to-end selftest
  (`glance-selftest`).
- **State validation** — done. Every parsed state is sanity-checked
  (`core/include/state_validation.h`, port of the Python research
  prototype's card/table validators): duplicate card faces, board gaps,
  stage/board mismatches and negative amounts surface in the state JSON as a
  `validation` block (`{valid, errors[], warnings[]}`) so clients can
  distrust a broken read. Pure logic; no OCR required.
- **Generic engine** — done. `core/` (mapping, template_match, ocr, scraper,
  ScreenshotService) is platform-free and ready to be reused elsewhere.
- **Control (sending actions back to the screen)** — done (milestone M1).
  `POST /grab`, `POST /click`, `POST /key`, `POST /sequence` on the same
  HTTP surface: the server can grab the desktop/a window (X11 `XGetImage`),
  click a named mapping `action` (resolved to the centre of its
  `buttons`/`stacks` rectangle in screen-absolute coordinates) or raw
  coordinates in the last capture's space, and inject keys/text (X11 `XTest`).
  The mapping gained `actions` (name → `button:<name>` | `stack:<key>`, no
  own rectangles) and `window_title` (see `core/include/mapping.h`); the
  platform is a `Screen`/`Input` backend chosen at configure time
  (`GLANCE_X11`), with a null fallback on headless machines — the same
  optional pattern as tesseract.

## Roadmap: from screen-reading to screen-controlling

**M1 — Control loop (poker actions) — done.**
Keyboard/mouse injection against the poker window: click-by-coordinate
(determinable from the mapping, since we already know the rectangles) and key
input for chat/raise amounts. The mapping gains an `actions` section — named
targets that reference the *existing* `buttons`/`stacks` geometry
(`"call": "button:call"`), resolved to screen-absolute centres at scrape
time — same schema extension pattern as before. The loop is closed: glance
*reads* the table and then *plays* on it, a minimal bot with zero platform
access. Selftest drives the whole surface in-process on fake backends
(resolution cases, input-space conversion, HTTP round-trips through the real
route handlers), so no window is needed to prove it.

**M2 — Generic control primitives in `core/` — landed in part.**
The platform-safe mouse/keyboard abstraction exists: `Screen` + `Input` +
`Backend` in `core/` (`control.h`), injected through the `ControlService` so
the HTTP layer (`/click`, `/key`, `/sequence`, `/grab`) drives it. The Linux
X11 backend (XGetImage + XTest) is in; Windows SendInput and macOS
CGEvent/cliclick backends are still to come when glance moves off Linux —
the configure-time-optional pattern means each is an additive option
(`GLANCE_X11`, and future flags) with the null backend as fallback.

**M3 — Multi-platform skins.**
Every new game is a skin: mapping file + templates + (optional) a thin
scraper subclass, exactly how `acr/` sits on `core/`. Poker is the first
skin; the design is deliberately not poker-shaped. A skin registry in the
server (one process, several platforms at different coordinates) is a
straightforward extension of `ScreenshotService`.

**M4 — Reliability & timing.**
Capture cadence and jitter (so grabs land at stable moments in the game
loop), debouncing of state changes, and a state-diff log: glance reports what
changed since the last grab rather than re-sending the whole table. Cheap
latency measurement per grab (template-match timing is already in the hot
path; OCR is the slow one) with an "OCR only when something moved" mode.

**M5 — Observability.**
A JSON-lines event log (every grab, every state diff, every control action,
with timestamps and match scores) and a `GET /events` tail. This is also
what makes glance *verifiable*: every decision a bot makes can be replayed
against the grabs that led to it.

The bar at each milestone is the same one the selftest sets: a synthesized
end-to-end scenario, run by `ctest`, that proves the new capability without a
real window attached.

## Design notes (why glance is shaped this way)

- **Screenshot-in, JSON-out.** The HTTP boundary is raw image bytes → parsed
  state. Nothing platform-specific crosses the wire; clients stay dumb.
- **Anchoring beats coordinates.** A single "top-left corner" template pins
  the whole window; every other field is relative to it. When the window
  moves, only the anchor moves. This is what makes a fixed-res, no-GUI
  pipeline robust enough for a real table.
- **Symbolic vs. numeric.** What does not change (cards, buttons, dealer
  chip) is template-matched; what changes (stacks, bets, pot) is read with
  OCR, and OCR is optional — degrade to "no numbers", never to "doesn't
  work".
- **Optional heavy dependencies.** tesseract is found at configure time, not
  linked in; the same pattern was applied to X11 for control (`GLANCE_X11`),
  so the headroom of "it builds" is preserved on every machine — headless
  hosts run the null backend and every control route degrades to a clean
  422 "no display" instead of failing at startup.
