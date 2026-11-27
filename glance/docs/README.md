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
3. **Bot control (the full loop, milestone M1).** Because the mapping
   already records every field's rectangle, the action targets (call button,
   raise bar, chips input) come from the same file: glance reads the table
   *and* clicks the answer. A decision loop that watches state and injects
   inputs is a thin client of the same HTTP surface.
4. **Multi-table awareness (M3).** One process, many window grabs (one skin
   per table, different coordinates): a cross-table view of where action is,
   used for switching, for correlated reads, or simply for tracking.
5. **Verification & replay (M5).** The event log makes every machine
   decision auditable: given a grab and the mapping, the parse is
   deterministic, so any action the bot took can be replayed and checked
   afterwards.

The first three work or nearly work today (1–2 are a client script away;
3 is milestone M1); 4–5 are on the roadmap below.

## Reading order

- [architecture.md](architecture.md) — **start here**: the layer diagram, a
  request traced end to end, the "who knows what" layering contract, and the
  design invariants.
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
- **Control (sending actions back to the screen)** — on the roadmap.

## Roadmap: from screen-reading to screen-controlling

**M1 — Control loop (poker actions).**
Keyboard/mouse injection against the poker window: click-by-coordinate
(determinable from the mapping, since we already know the rectangles) and key
input for chat/raise amounts. This closes the loop: glance *reads* the table
and then *plays* on it — a minimal bot with zero platform access. The mapping
gains an `actions` section (coordinate + click type per action) — same schema
extension pattern as before, generic in `core/`, ACR-specific targets in
`acr/`.

**M2 — Generic control primitives in `core/`.**
A small, platform-safe mouse/keyboard abstraction (X11 `XTEST`, Windows
SendInput, fallback to cliclick/input on macOS), injected through the service
so the HTTP layer can drive it: `POST /click`, `POST /key`, `POST /sequence`.
The service becomes the control surface any client can use, not just the
poker scraper.

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
  linked in; the same pattern will apply to X11/SendInput for control, so the
  headroom of "it builds" is preserved on every machine.
