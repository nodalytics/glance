# ACR Poker Screen Scraping

Screen scraping for [ACR Poker](https://www.acrpoker.eu/) — a web poker client.
Because it is a web client, the "screenshot" is a grab of the poker window. The
engine in `core/` is generic (no ACR knowledge); ACR is a **package**
(`packages/acr/`: `glance-package.json` + `mappings/6max.json` + template
PNGs), the default one shipped with glance (`glance serve --package acr`).

All ACR-specific knowledge lives in that package — data, not code.

## Conventions

- New generic scraping code goes in `core/`; ACR-only stuff in `packages/acr/`.
- Use OpenCV for image processing (`imread`/`imdecode`, `matchTemplate`,
  `cvtColor`, `threshold`). No GUI.
- OCR is optional: `glance::ocr_available()` gates every numeric read. The
  selftest passes without tesseract.

## Technique

This mirrors the approach of
[dickreuter/Poker](https://github.com/dickreuter/Poker/) (a screen-scraping
poker bot): anchor-based cropping, per-field template matching for
symbolic UI (cards, buttons, dealer button), and OCR for the varying
numbers.

### 1. Anchor

The table window is first located in the screenshot by matching the
`topleft` anchor template with `TM_SQDIFF_NORMED` (0.0 = perfect). The match
must be found (and the crop must fit in the image). The bot's rule is "exactly
one top-left corner" — a unique anchor hit is what makes the fixed-size crop
below trustworthy. `count_template_hits` (in `template_match.h`) counts
positions at/below the threshold; `scrape` currently relies on the best hit +
the crop-bounds check, and can be hardened to require `== 1`.

### 2. Fixed crop + relative fields

Once the top-left corner `(ox, oy)` is known, a fixed-size window
(`crop.x` × `crop.y`) is cropped at that corner. **Every other field is then
specified in coordinates relative to that corner.** This is the key
simplification: you only ever re-anchor when the window moves; you never
re-search the whole screen per field.

### 3. Per-field template matching (symbolic fields)

- **Action buttons** (`buttons`): e.g. "Call". A template is matched inside
  the button's search `area`. If present, it means it's our turn
  (`my_turn = true`).
- **Cards** (`cards` + `card_templates`): for each card slot, the whole
  `card_templates` library is tried against the slot's `area`. The first
  template that matches identifies the card; the template's file stem is the
  card id (e.g. `Ah`). A `covered` template means the slot holds face-down
  cards (opponent in the hand, identity unknown). A slot with no match is
  treated as empty.
- **Dealer button** (`dealer`): which seat area the button template sits in
  → `dealer_position`.

Template matching is used for **anything fixed on screen** (a card, a
button, the button chip). The threshold (`template_threshold`) is on
`TM_SQDIFF_NORMED`, so lower is better and we test `best <= threshold`.

### 4. OCR for numbers

Numbers (stacks, per-seat bets, `pot`, `call`, `raise`) **vary** and cannot be
template-matched, so they are read with tesseract:

- The region is prepared: resized to a fixed width (300 px), converted to
  grayscale, and binarized (`THRESH_BINARY_INV` with an adaptive fallback for
  low-contrast text) — see `prepare_for_ocr`.
- tesseract runs with PSM 7 (single line) and a digits/decimal/comma/`$`
  whitelist; only parseable, non-negative numbers are kept.
- If OCR is unavailable, numeric fields are simply omitted from the output —
  everything else (cards, turn, stage, dealer) still works.

### 5. Derived state

- **Game stage** from board-card count: 0 → PreFlop, 3 → Flop, 4 → Turn,
  5 → River.
- **`my_cards`** = seat 0's hole cards. Seat 0 is the bot's own seat.

## Table mapping JSON

The server is configured with a table-mapping JSON describing the ACR skin.
Paths are relative to the mapping file's directory. Full contract is in
`core/include/mapping.h`. Fields:

```json
{
  "name": "acr-6max",
  "crop": {"x": 1600, "y": 900},
  "topleft": "templates/anchor.png",
  "anchor_threshold": 0.01,
  "template_threshold": 0.07,
  "card_templates": ["cards/Ah.png", "cards/2c.png", "cards/covered.png"],
  "cards": {
    "my1": [x1, y1, x2, y2],
    "board1": [x1, y1, x2, y2],
    "p3_hand1": [x1, y1, x2, y2]
  },
  "buttons": {
    "call": { "template": "templates/call.png", "area": [x1, y1, x2, y2] }
  },
  "dealer": {
    "template": "templates/dealer.png",
    "areas": { "p1": [x1, y1, x2, y2], "p2": [x1, y1, x2, y2] }
  },
  "stacks": {
    "p1": [x1, y1, x2, y2],
    "p1_bet": [x1, y1, x2, y2],
    "pot": [x1, y1, x2, y2],
    "call": [x1, y1, x2, y2],
    "raise": [x1, y1, x2, y2]
  },
  "max_players": 6,
  "actions": { "call": "button:call", "raise_bar": "stack:raise" },
  "window_title": "ACR Poker"
}
```

### Card-slot grammar

Slot names in `cards` are parsed with a fixed grammar (see `scraper.cpp`):

- `my<n>` — the bot's own hole card `n` (seat index 0).
- `board<n>` — community card `n` (1-based).
- `p<n>_hand<m>` — hole card `m` of opponent `n` (1-based; seat `n-1`).

All indices are 1-based. `n`/`m` are parsed as integers and must be >= 1.

### Number keys (`stacks`)

- `pot`, `call`, `raise` — table-level numbers.
- `p<n>` — seat `n`'s stack.
- `p<n>_bet` — seat `n`'s current bet.

### Action targets (`actions`)

`actions` (optional; control, milestone M1) maps names a client can POST to
`POST /click` to **existing** geometry:

- `"button:<name>"` — references a `buttons` entry by name;
- `"stack:<key>"` — references a `stacks` entry by key.

At request time the name is resolved, using the anchor position found in the
last capture, to the **screen-absolute centre** of the referenced rectangle —
a `button:` target's rectangle and a `stack:` target's rectangle already live
in the mapping, so `actions` never carries geometry of its own. Example:

```json
"actions": {
  "call": "button:call",
  "fold": "button:fold",
  "raise_amount": "stack:call",
  "raise_bar": "stack:raise"
}
```

Unknown names, unknown target names, or malformed targets are rejected (a
clean 422, never a click on a guess); a grab whose anchor was not found
resolves no action at all.

### Template-free cards (`card_vision`)

Optional. For slots where no `card_templates` entry matches, the scraper reads
the card from its crop with the card-vision engine (`core/include/card_vision.h`,
ported from the research prototype): occupancy check → suit by symbol shape
(Dice + Hu moments against `<suit>.png` / `<suit>_*.png`, colour-gated in the
`simulator` profile) → rank by glyph template (`<rank>_*.png`; Dice, accepted
only with a clear lead over the runner-up) → optional tesseract cross-check.
A skin then needs a handful of glyph PNGs instead of 52 card images.

```json
"card_vision": {
  "suit_templates": "suits/",
  "rank_templates": "ranks/",
  "profile": "simulator",
  "occupancy": true
}
```

`rank_templates` omitted → built-in Hershey glyphs (only good for synthetic
tests). Glyph templates are per-font: cut them from the platform's own
rendering with `glance-cardvision harvest <labelled-dataset> <out-dir>`, and
measure with `glance-cardvision eval` (see `tools/cardvision.cpp`). Profiles:
`simulator` (several templates per suit, colour-gated) and `calibration`
(one template per suit; slot names `my1`/`my2` select hero-card regions).

### Window title (`window_title`)

`window_title` (optional; control) is the title substring of the platform
window the *server itself* grabs with `POST /grab` (window search via the
X11 backend) when no client capture stream feeds it; it also names the
window for the `ControlService`'s input-space bookkeeping.

### Seats

Seat 0 is the bot. A seat label `pX` maps to seat index `X-1`. The API
re-numbers seats from 1 (so the bot is seat 1 in JSON output).

### Thresholds

- `anchor_threshold` — how tight the topleft anchor match must be.
- `template_threshold` — how tight card/button/dealer matches must be.

Both are on `TM_SQDIFF_NORMED` (lower = better).

## Producing template PNGs

Templates are small crops of the **actual ACR window** at your resolution:

1. Grab the ACR window at a fixed window size.
2. Crop the top-left corner region → `templates/anchor.png`.
3. For every card that can appear in a slot, crop that card → `cards/<id>.png`
   (id = the stem you want, e.g. `Ah.png`, `2c.png`). Add a `covered.png` crop
   for face-down cards.
4. Crop each action button you care about → `templates/<button>.png`.
5. Crop the dealer chip → `templates/dealer.png`.
6. Record each field's on-screen rectangle relative to the window top-left.

Because matching is per-slot and per-template, you only need the card
templates for cards you actually want to identify — but covering the full
deck gives the most robust result.

## Reference

- [dickreuter/Poker](https://github.com/dickreuter/Poker/) — screen-scraping technique
- [Gongsta/Poker-AI](https://github.com/Gongsta/Poker-AI/) — solves heads-up no-limit hold'em with CFR + equity-based card abstraction (game-strategy side; benchmarked vs Slumbot in BB/100). Complements the recognition work: its roadmap explicitly includes a CV/deep-learning card recognizer (the consumer of what glance produces).
- [ACR Poker](https://www.acrpoker.eu/)
