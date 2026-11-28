# acr — glance package for ACR Poker

Default package shipped with glance. It teaches the engine the ACR Poker
6-max table: anchor, card slots, action buttons, dealer button, number
fields and named click targets (`mappings/6max.json`; the mapping format is
documented in `core/include/mapping.h` and `research/acr.md`).

```bash
glance serve --package acr          # default mapping (6max)
glance serve --package acr:6max     # explicit mapping
```

**Status:** the mapping geometry is a starter; the template PNGs it
references (`mappings/templates/`, `mappings/cards/`) still have to be
captured from a real ACR client (see "Producing template PNGs" in
`research/acr.md`). For template-free cards, add a `card_vision` section with
suit/rank glyphs harvested from ACR crops (`glance-cardvision harvest`).
