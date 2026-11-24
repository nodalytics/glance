# AGENTS

## Project

`poker-apis` is a C++ (CMake, C++20) poker screen-scraping tool for
[ACR Poker](https://www.acrpoker.eu/): OpenCV template matching + tesseract OCR
on a grab of the poker window, served over cpp-httplib.

## Commands

- Configure: `cmake -B build -DCMAKE_BUILD_TYPE=Release`
- Build: `cmake --build build -j$(nproc)`
- Test: `ctest --test-dir build` (runs `poker-selftest`) or
  `build/poker-selftest [--fixtures <dir>]`
- Run: `build/poker-apis-server path/to/mapping.json [port]`

## Setup (first time)

1. CMake >= 3.24, a C++20 compiler (g++ 13 verified).
2. Optional: `apt install tesseract-ocr` (build falls back to no-OCR without it).
3. `cmake -B build && cmake --build build -j$(nproc)` — FetchContent pulls
   nlohmann/json v3.11.3, cpp-httplib v0.67.0, and OpenCV 5.1.0 from source
   (minimal modules: core;imgproc;imgcodecs).

## Layout

```
poker-apis/
├── CMakeLists.txt     # single build file: FetchContent deps + all targets
├── core/              # generic engine (screen-scraping, no ACR knowledge)
│   ├── include/       #   mapping.h, template_match.h, ocr.h, scraper.h, server.h
│   └── src/
├── acr/               # ACR-specific scraper (thin wrapper over core)
├── server/main.cpp    # HTTP entry point
├── tools/selftest.cpp # synthesized-scenario end-to-end test
├── testdata/          # example table mapping
└── docs/acr.md        # ACR scraping docs + technique analysis
```

- New generic scraping code goes in `core/`; ACR-only stuff in `acr/`.
- The table-mapping JSON contract is documented in `core/include/mapping.h`
  (header comment) and `docs/acr.md` — keep both in sync when it changes.

## Conventions

- C++20, no external deps beyond what `CMakeLists.txt` already Fetches (json,
  httplib, OpenCV). Pin versions there; there is no lockfile.
- The LSP/clangd in this workspace reports "file not found" for `opencv2/...`,
  `nlohmann/json.hpp`, and headers in sibling subdirs — that's because the
  include paths only exist after a CMake configure (FetchContent). The real
  compile check is the build (`cmake --build build`).
- OCR must stay optional: `ocr_available()` gates every numeric read, and the
  selftest passes (minus the numeric checks) on machines without tesseract.
- Heavy builds (the OpenCV-from-source configure is large) run on the lab
  machine: source `.secrets/lab.env`, then rsync + ssh per the lab workflow in
  the repo README of that project. `.secrets/` is gitignored — never commit it.

## References

- [dickreuter/Poker](https://github.com/dickreuter/Poker/) — technique reference
- [ACR Poker](https://www.acrpoker.eu/)
