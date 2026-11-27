# glance — architecture

How everything works, layer by layer. Keep this in sync with the code: if a
box below stops matching the source, the doc is stale.

## 1. The one-line picture

A screenshot goes in as image bytes; parsed table state comes out as JSON.
**glance is the screen's replacement API** — for platforms that expose no
programming interface at all, it manufactures one from pixels.

```
                 +-----------------------------------------------------------+
                 |              client (bot / research / curl)               |
                 +-----------------------------------+-----------------------+
                                                     |
                     POST /capture (PNG/JPEG bytes)  |  GET /state, /health
                                                     v
   +---------------------------------------------------------------------+
   |  glance-server  (server/main.cpp, cpp-httplib)                     |
   |  - owns the HTTP surface                                            |
   |  - wires the platform scraper into the ScreenshotService           |
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
   |  AcrScraper  (acr/acr_scraper.cpp)  -- the platform "skin"         |
   |  owns the ACR mapping; delegates everything to the core engine.    |
   |  A new platform = a new thin layer like this one.                  |
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
| `server/main.cpp`    | HTTP verbs, exit codes       | card faces, seat numbers       |
| `ScreenshotService`  | "last frame + last state"    | what a table *is*              |
| `acr/` (skin)        | ACR's skin layout & mapping  | HTTP, OpenCV details           |
| `TableScraper`       | anchors, slots, thresholds   | ACR specifically (any skin)    |
| `template_match.cpp` | pixel similarity             | games, tables, cards           |
| `ocr.cpp`            | digits in a region           | poker, money, seats            |
| `state_validation`   | internal consistency of a    | pixels, OCR, the HTTP layer    |
|                      | parsed state                 |                                |

Two rules make this hold:

- **The mapping JSON is the only platform-specific input.** Everything a
  scraper does comes from `name/crop/topleft/cards/buttons/dealer/stacks`
  (contract in `core/include/mapping.h` and `docs/acr.md`). A new platform is
  data plus, at most, a ~40-line wrapper like `AcrScraper`.
- **Control (roadmap) attaches to the same seam.** Input injection
  (`POST /click`, `/key`) will be another `core/` primitive driven by
  `ScreenshotService`, with per-skin *action targets* living in the same
  mapping JSON — so the "who knows what" table gains a row but no new
  direction of arrows.

## 4. Design invariants

1. **Screenshot-in / JSON-out.** Nothing platform-specific crosses the HTTP
   wire; clients stay dumb and reusable.
2. **Anchoring beats coordinates.** One unique anchor hit + relative
   rectangles = robustness under window moves without per-field search.
3. **Symbolic vs numeric.** Fixed pixels (cards, buttons, chips) are
   template-matched; varying digits are OCR'd — and only that second class is
   optional, so the failure mode of "no tesseract" is "no numbers", never
   "no server".
4. **Configuration-time, not link-time, optionals.** `GLANCE_OCR` is decided
   by `find_program(tesseract)` at configure time and burned in as a compiled
   default; `ocr_available()` still re-checks the binary at runtime. Same
   pattern for any future optional dependency.
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
  |  | bot / research | --------> (future: POST /click,       |   |
  |  | client         |        /key -- control primitives,    |   |
  |  +----------------+        milestone M1/M2)               |   |
  +-----------------------------------------------------------+
```

Nothing here is a daemon: `glance-server` holds state only "last frame" —
the capture cadence lives in whatever posts to it, which is what keeps the
server boring.
