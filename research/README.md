# research

The Python side of glance: the original PaddleOCR vision-pipeline prototype
(`poker_apis/`, FastAPI), its test suite and labelled datasets
(`tests/`, `test_assets/validation/`), the React dashboard prototype
(`frontend/`), notebooks (`notebooks/`) and lab setup scripts (`scripts/`).

The C++ engine in `../glance/` is the product; this folder is where ideas are
tried first. The card-vision engine (`glance/core/include/card_vision.h`) was
ported from `poker_apis/vision/`, and its accuracy gates run on
`test_assets/validation/` (see `glance-cardvision eval`).

## Docs here

- [acr.md](acr.md) — the ACR Poker scraping technique and the table-mapping
  JSON contract (kept in sync with `glance/core/include/mapping.h`).
- [slumbot.md](slumbot.md) — the Slumbot API blueprint for the control-side
  surface.

## References

- [Slumbot](https://slumbot.com/) — the bot API standard glance's control
  plane mirrors; `sample_api.py` is the reference action-string parser
- [dickreuter/Poker](https://github.com/dickreuter/Poker/) — screen-scraping technique reference
- [Gongsta/Poker-AI](https://github.com/Gongsta/Poker-AI/) — CFR + equity-based strategy reference (the consumer side of glance's parsed state)
- [ACR Poker](https://www.acrpoker.eu/)
- [Kronos](https://github.com/shiyu-coder/Kronos) — decoder-only foundation
  model for financial K-lines; tokenizer/architecture ideas for glance's own
  models (see `docs/models.md`)
