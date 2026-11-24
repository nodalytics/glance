# AGENTS

## Project

`glance` is a C++ (CMake, C++20) screen-scraping and control tool: OpenCV
template matching + tesseract OCR on a grab of a window (first target:
[ACR Poker](https://www.acrpoker.eu/) tables), served over cpp-httplib. The C++
project lives in `glance/`; the old Python prototype is preserved in
`research/`.

## Commands

(all from the repo root; the CMake list lives in `glance/`)

- Configure: `cmake -B glance/build -S glance -DCMAKE_BUILD_TYPE=Release`
- Build: `cmake --build glance/build -j$(nproc)`
- Test: `ctest --test-dir glance/build` (runs `glance-selftest`) or
  `glance/build/glance-selftest [--fixtures <dir>]`
- Run: `glance/build/glance-server path/to/mapping.json [port]`

## Setup (first time)

1. CMake >= 3.24, a C++20 compiler (g++ 13 verified).
2. Optional: `apt install tesseract-ocr` (build falls back to no-OCR without it).
3. `cmake -B build && cmake --build build -j$(nproc)` — FetchContent pulls
   nlohmann/json v3.11.3, cpp-httplib v0.67.0, and OpenCV 5.1.0 from source
   (minimal modules: core;imgproc;imgcodecs).

## Layout

```
glance/              # repo root
├── glance/          # the C++ project
│   ├── CMakeLists.txt     # single build file: FetchContent deps + all targets
│   ├── core/              # generic engine (screen-scraping, no ACR knowledge)
│   │   ├── include/       #   mapping.h, template_match.h, ocr.h, scraper.h, server.h
│   │   └── src/
│   ├── acr/               # ACR-specific scraper (thin wrapper over core)
│   ├── server/main.cpp    # HTTP entry point
│   ├── tools/selftest.cpp # synthesized-scenario end-to-end test
│   ├── testdata/          # example table mapping
│   └── docs/              # README.md (vision + roadmap), acr.md (technique)
└── research/          # original Python prototype + scripts/ (lab setup)
```

- New generic scraping/control code goes in `glance/core/`; ACR-only stuff in
  `glance/acr/`.
- The table-mapping JSON contract is documented in
  `glance/core/include/mapping.h` (header comment) and `glance/docs/acr.md` —
  keep both in sync when it changes.
- Docs live in `glance/docs/` — start there (`glance/docs/README.md`) for what
  glance is and where it is headed.

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
  machine. To prepare a fresh machine/labs state, run
  `research/scripts/install_deps.sh` (idempotent; installs tesseract-ocr +
  build tooling via apt, with sudo). `.secrets/` is gitignored — never commit
  it.

## Where to build: lab first, local is fallback

- **The lab machine is the primary build and compute target.** It is
  faster and already has the dependencies; source syncs to the lab with
  rsync, builds there, and results rsync back. Access details live in
  `.secrets/` (gitignored), not in the docs.
- **Local computation/build is the fallback only.** Use it when the lab is
  unreachable (or for a quick sanity check), and prefer the same
  `install_deps.sh` to bring a local machine up to the required toolchain
  state.

## References

- [dickreuter/Poker](https://github.com/dickreuter/Poker/) — technique reference
- [ACR Poker](https://www.acrpoker.eu/)
