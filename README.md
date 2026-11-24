# Glance

**For poker platforms without APIs, Glance is the way in.** A C++ (CMake,
OpenCV, cpp-httplib) screen-scraping tool that turns a grab of the
[ACR Poker](https://www.acrpoker.eu/) table window into clean JSON — template
match for the fixed elements, OCR for the numbers — exposed over a small HTTP
API, with a roadmap toward sending controls back to the screen.
[docs/README.md](glance/docs/README.md) has the vision, roadmap and
architecture.

## Prerequisites

- CMake >= 3.24
- C++20 compiler (tested with g++ 13 on Ubuntu 24.04)
- Optional: `tesseract-ocr` — enables reading pot/stack/bet numbers (the build
  auto-disables OCR when the binary is missing)

OpenCV (from source, minimal modules), nlohmann/json, and cpp-httplib are
fetched by CMake at configure time (FetchContent) — nothing else to install.

## Build

```sh
cd glance
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

Targets:

- `glance-server` — the HTTP API
- `glance-selftest` — synthesized-scenario end-to-end test (`ctest --test-dir build` runs it)

## Run the server

```sh
build/glance-server path/to/mapping.json [port]   # default port 8000
```

- `GET /health` — liveness
- `POST /capture` — body: raw PNG/JPEG bytes of the poker window → parses and
  returns the table state JSON (422 when the table anchor is not found)
- `GET /state` — last successfully parsed state (404 until the first capture)

Example:

```sh
curl -s -X POST -H 'Content-Type: application/octet-stream' \
     --data-binary @screenshot.png http://127.0.0.1:8000/capture | jq
```

## Selftest

```sh
build/glance-selftest
# optional: leave generated mapping + screenshot around for server smoke tests
build/glance-selftest --fixtures /tmp/acr-fixtures
```

The selftest synthesizes its own scenario (anchor, cards, button, dealer, a
screenshot with text numbers), writes a real mapping file and image to disk, and
runs the full pipeline. Numeric checks are skipped when tesseract is absent.

## Table mapping

The server is driven by a table-mapping JSON (the "table skin" descriptor):
which template PNGs to look for and where each field sits. See
[docs/acr.md](docs/acr.md) for the format and the scraping technique, and
`testdata/acr.example.json` for a starter.

## Layout

```
glance/              # repo root
├── glance/          # the C++ project
│   ├── CMakeLists.txt
│   ├── core/                      # generic engine: mapping, template match,
│   │   ├── include/               #   OCR, scraper, service (no poker knowledge)
│   │   └── src/
│   ├── acr/                       # ACR-specific scraper (wraps the core engine)
│   ├── server/main.cpp            # HTTP entry point (cpp-httplib)
│   ├── tools/selftest.cpp
│   ├── testdata/                  # example table mapping
│   └── docs/                      # README.md (vision + roadmap),
│                                  #   architecture.md, acr.md (technique)
└── research/                      # the original Python prototype + scripts/
```

## Development

- Dependencies are pinned in `CMakeLists.txt` via FetchContent — bump a tag/URL
  there to update, no lockfile.
- The OpenCV build from source is large (~15 GB during build); build with
  `-j$(nproc)` on a machine with headroom.
- No linter/format tooling yet.

## References

- [dickreuter/Poker](https://github.com/dickreuter/Poker/) — screen-scraping technique reference
- [ACR Poker](https://www.acrpoker.eu/)
