# poker-apis

C++ (CMake, OpenCV, cpp-httplib) tool for screen-scraping [ACR Poker](https://www.acrpoker.eu/)
6-max tables: template match + OCR on a grab of the poker window, exposed over a small HTTP API.

## Prerequisites

- CMake >= 3.24
- C++20 compiler (tested with g++ 13 on Ubuntu 24.04)
- Optional: `tesseract-ocr` — enables reading pot/stack/bet numbers (the build
  auto-disables OCR when the binary is missing)

OpenCV (from source, minimal modules), nlohmann/json, and cpp-httplib are
fetched by CMake at configure time (FetchContent) — nothing else to install.

## Build

```sh
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

Targets:

- `poker-apis-server` — the HTTP API
- `poker-selftest` — synthesized-scenario end-to-end test (`ctest --test-dir build` runs it)

## Run the server

```sh
build/poker-apis-server path/to/mapping.json [port]   # default port 8000
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
build/poker-selftest
# optional: leave generated mapping + screenshot around for server smoke tests
build/poker-selftest --fixtures /tmp/acr-fixtures
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
poker-apis/
├── CMakeLists.txt
├── core/              # generic engine: mapping, template match, OCR, scraper, service
│   ├── include/
│   └── src/
├── acr/               # ACR-specific scraper (wraps the core engine)
├── server/            # HTTP entry point (cpp-httplib)
├── tools/selftest.cpp
├── testdata/          # example mapping
└── docs/acr.md        # ACR scraping docs + technique
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
