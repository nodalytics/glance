# acr — glance package for ACR Poker

Default package shipped with glance. It teaches the engine a real ACR Poker
table (`mappings/6max.json`): the star-icon anchor, the five community-card
slots and the hero's two hole-card slots, the Fold/Call action buttons, the
dealer button, the pot and per-seat stacks, and the named click targets. The
mapping format is documented in `core/include/mapping.h` and `research/acr.md`.

```bash
glance serve --package acr          # default mapping (6max)
glance serve --package acr:6max     # explicit mapping
```

## What the mapping targets

Cut from two real 1600×899 ACR grabs (`research/test_images/ss.jpeg`, a river,
and `img.jpeg`, a preflop action frame on another table of the same client).
All field rectangles are absolute image coordinates; the scraper anchors the
window at the star icon's matched top-left (here `(0,0)`) and crops `1600×899`
down-right from there.

- **Anchor** (`templates/anchor.png`) — the ACR app star icon at the very
  top-left. The title-bar text varies per tournament, so the anchor is just the
  fixed badge. It is a unique hit at `anchor_threshold` 0.02 on both samples.
- **Window title** (`window_title`) — `"Hold'em"`. ACR table titles look like
  `"$0.11 - Lightning PKO - … - No Limit - 2,500 / 5,000 Hold'em (36514215)"`;
  they carry no literal "ACR", so `"Hold'em"` is the stable substring the
  server's `POST /grab` window search matches.
- **Cards** — `board1..board5` and `my1`/`my2`. No per-card templates: the
  board and hero cards are read template-free by `card_vision` (see below).
- **Buttons** — `fold` / `call` (`templates/fold.png`, `call.png`, cut from
  img.jpeg). A match inside the button area means it is our turn.
- **Dealer** — `templates/dealer.png` (the white "D" chip). The chip moves per
  hand, so `dealer.areas` holds one rectangle per seat's chip spot (p1 = hero,
  p2 = the lower-left seat, so far).
- **Stacks** — `pot` plus per-seat `p1..p6` stacks (green numbers), read with
  OCR when tesseract is present.
- **Actions** — `call → button:call`, `fold → button:fold`.

The sample screenshots are 9-max tournament tables, so the mapping sizes for
`max_players: 9`; six seat stacks are mapped so far and more can be added by
measuring the remaining plates the same way.

## Template-free card reading (`card_vision`)

Board and hero cards are read with the engine's card-vision recognizer
(`simulator` profile) instead of a 52-card template library:

```json
"card_vision": {
  "suit_templates": "cards/suits",
  "rank_templates": "cards/ranks",
  "profile": "simulator",
  "occupancy": true
}
```

- `cards/suits/` — the committed `suits_simulator` set **plus** ACR suit
  symbols harvested from the real cards (`*_acr_*`). Both are kept: the ACR
  symbols give a clean, high-margin self-match on ACR's own heart/diamond/
  spade/club shapes (the simulator set alone left A♥ hearts-vs-diamonds too
  close to accept), while the simulator set keeps general coverage.
- `cards/ranks/` — ACR corner rank glyphs harvested from the real cards:
  **A, 2, 8, 10, J, Q, K** (`<rank>_acr_*`). **Gap:** 3, 4, 5, 6, 7, 9 have no
  ACR sample yet — a card of one of those ranks reads its suit but not its rank
  until a template is harvested.

On the river sample this reads the whole board **A♥ 8♠ J♥ J♦ 2♥** and the
greyed showdown hero cards **Q♣ 10♣**; on the preflop sample it reads the hero
**K♠ J♦** (`glance/tools/acrtest.cpp`, ctest `acrtest`).

### Regenerating the templates

Templates are cut from the real screenshots. Crop each card to its mapping slot
rectangle into a labelled dataset (`expected.json` + `cards/<slot>.png`; see the
`"cards"` shape in `tools/cardvision.cpp`), then:

```bash
glance-cardvision harvest       <dataset> cards/ranks            # <rank>_<stem>.png
glance-cardvision harvest-suits <dataset> cards/suits --profile simulator
glance-cardvision eval          <dataset> --suits cards/suits --ranks cards/ranks --profile simulator
```

`harvest` writes the normalized rank glyph from the first rank region that
yields one (the padded corner box for ACR's large glyphs); `harvest-suits`
writes the normalized suit symbols. `eval` reports per-card accuracy.
