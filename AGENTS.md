# AGENTS

## Project

`glance` is a C++ (CMake, C++20) screen-scraping and control tool: OpenCV
template matching + tesseract OCR on a grab of a window (first target:
[ACR Poker](https://www.acrpoker.eu/) tables), served over cpp-httplib. The C++
project lives in `glance/`. `research/` holds a Python notebook
environment and the host setup scripts.

## Commands

(all from the repo root; the CMake list lives in `glance/`)

- Configure: `cmake -B glance/build -S glance -DCMAKE_BUILD_TYPE=Release`
- Build: `cmake --build glance/build -j$(nproc)`
- Test: `ctest --test-dir glance/build` (runs `glance-selftest`) or
  `glance/build/glance-selftest [--fixtures <dir>]`
- Run: `glance/build/glance-server path/to/mapping.json [port]`
- CI: `.github/workflows/ci.yml` builds + runs the selftest on ubuntu-24.04
  **with tesseract installed** — it is the only place the OCR numeric checks
  (pot/stack/bet) ever run, because the lab host has no tesseract. It is the
  canonical full test; the lab remains the primary build/compute host.

## Setup (first time)

1. `bash research/scripts/install_deps.sh` (or manually): a C++20 compiler,
   CMake >= 3.24, and **`libopencv-dev`** (the distro's prebuilt OpenCV 4.x).
2. Optional: `apt install tesseract-ocr` (build falls back to no-OCR without it).
3. `cmake -B build && cmake --build build -j$(nproc)` — the build compiles
   glance's sources and Fetches two single-header deps (nlohmann/json v3.11.3,
   cpp-httplib v0.67.0). **OpenCV is never built from source**: the host's
   system package is linked (see CMakeLists `find_package(OpenCV 4.5 ...)`).
   Do not reintroduce a source build — it dominated build time/disk for no
   benefit; OpenCV 5.1.0 from source once aborted our selftest, but a correct
   probe proved that was our test code, not OpenCV (see global memory).

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
└── research/          # notebook environment + host setup scripts
```

- New generic scraping/control code goes in `glance/core/`; ACR-only stuff in
  `glance/acr/`.
- The table-mapping JSON contract is documented in
  `glance/core/include/mapping.h` (header comment) and `glance/docs/acr.md` —
  keep both in sync when it changes.
- Docs live in `glance/docs/` — start there (`glance/docs/README.md`) for what
  glance is and where it is headed.

## Conventions

- C++20. Deps: the distro's OpenCV 4.x (linked, never built), plus
  nlohmann/json v3.11.3 and cpp-httplib v0.67.0 which `CMakeLists.txt`
  Fetches. Pin versions there; there is no lockfile.
- The LSP/clangd in this workspace reports "file not found" for
  `nlohmann/json.hpp` and headers in sibling subdirs — those include paths
  only exist after a CMake configure. The real compile check is the build
  (`cmake --build build`).
- OCR must stay optional: `ocr_available()` gates every numeric read, and the
  selftest passes (minus the numeric checks) on machines without tesseract.
- To prepare a fresh machine, run `research/scripts/install_deps.sh`
  (idempotent; installs the C++ toolchain, `libopencv-dev` and optional
  tesseract-ocr via apt, with sudo). `.secrets/` is gitignored — never commit
  it.

## Memory (always keep current)

- **After meaningful work, update global memory before ending the session.**
  Cross-session findings — bugs found/fixed and their state, what builds
  where, lab quirks, workflow or infra changes, current commit state — go to
  `~/.config/opencode/AGENTS.md` (global, machine-level). Don't let
  discoveries die in a transcript: the next session starts from memory and
  must know where things stand. Record conclusions with confidence levels,
  not just observations.
- Repo-local conventions stay in this file; machine/session-spanning facts
  (lab behavior, environment quirks, project state) go to global memory.
  Keep both in sync when one references the other.

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
- [Gongsta/Poker-AI](https://github.com/Gongsta/Poker-AI/) — CFR + equity-based card abstraction for heads-up no-limit hold'em (game-strategy side; complements the recognition work)
- [ACR Poker](https://www.acrpoker.eu/)
