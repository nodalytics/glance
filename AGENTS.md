# AGENTS

## Project

`glance` is a C++ (CMake, C++20) screen-scraping and control tool: OpenCV
template matching + tesseract OCR on a grab of a window (first target:
[ACR Poker](https://www.acrpoker.eu/) tables), served over cpp-httplib. The C++
project lives in `glance/`; the old Python prototype is preserved in
`research/`.

**North star (the ultimate test):** glance must be able to navigate any
desktop application it comes across — understand it and operate it without
human assistance (no per-app mapping, no SDK). Poker is the first target, not
the goal. When choosing between designs, prefer the one that generalizes to
apps glance has never seen (template-free recognition, generic control
primitives, verify-after-act) over per-app special cases. See
`docs/README.md` ("The ultimate test").

## Commands

(all from the repo root; the CMake list lives in `glance/`)

- Configure: `cmake -B glance/build -S glance -DCMAKE_BUILD_TYPE=Release`
- Build: `cmake --build glance/build -j$(nproc)`
- Test: `ctest --test-dir glance/build` (runs `glance-selftest`) or
  `glance/build/glance-selftest [--fixtures <dir>]`
- Run: `glance/build/glance-server path/to/mapping.json [port]`
- Windows (MSVC, multi-config generator): add `-DOpenCV_DIR=<opencv>\build\x64\vc16\lib`
  to configure, build with `--config Release`, test with
  `ctest --test-dir glance/build -C Release`; the OpenCV `bin\` dir
  (`opencv_world*.dll`) must be on `PATH` to run anything.
- macOS: add `-DCMAKE_PREFIX_PATH="$(brew --prefix)"` to configure; build
  with `-j$(sysctl -n hw.ncpu)`.
- CI: `.github/workflows/ci.yml` builds + runs ctest on ubuntu-24.04,
  windows-latest (MSVC) and macos-latest (Apple clang), **with tesseract
  installed** — the only place the OCR numeric checks (pot/stack/bet) ever
  run, because the lab host has no tesseract — and with each OS's control
  backend compiled in (X11 / Win32 / macOS). It is the canonical full test;
  the lab remains the primary build/compute host. Windows/macOS code can only
  be compiler-checked there (or with a mingw cross compiler / clang + a macOS
  SDK for syntax only).

## Setup (first time)

1. `bash research/scripts/install_deps.sh` (or manually): a C++20 compiler,
   CMake >= 3.24, and **`libopencv-dev`** (the distro's prebuilt OpenCV 4.x),
   plus `libx11-dev libxext-dev libxtst-dev` for the X11 control backend
   (optional: without them control falls back to the null backend).
   - **Windows**: Visual Studio 2022 (C++ workload) + CMake, and the
     *prebuilt* OpenCV Windows package (`choco install opencv`, or the
     official installer); point `OpenCV_DIR` at `build\x64\vc16\lib` and put
     `build\x64\vc16\bin` on `PATH`. Optional OCR: `choco install tesseract`
     and add `C:\Program Files\Tesseract-OCR` to `PATH` before configuring.
     The Win32 control backend needs nothing extra.
   - **macOS**: Xcode command line tools + `brew install cmake opencv`
     (optional `tesseract`). Running the control backend needs the Screen
     Recording and Accessibility permissions for the binary or its terminal
     (see `docs/engine.md`, "Control backends").
2. Optional: `apt install tesseract-ocr` (build falls back to no-OCR without it).
3. `cmake -B build && cmake --build build -j$(nproc)` — the build compiles
   glance's sources and Fetches two single-header deps (nlohmann/json v3.11.3,
   cpp-httplib v0.67.0). **OpenCV is never built from source**: the host's
   system package is linked (see CMakeLists `find_package(OpenCV 4.5 ...)`;
   on Windows/macOS that means the prebuilt choco/Homebrew packages, never
   vcpkg-from-source).
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
│   ├── packages/          # installable app packages; acr/ = default ACR Poker package
│   ├── server/main.cpp    # glance-server (compat entry; = `glance serve`)
│   ├── tools/             # glance CLI, selftest, webtest, pkgtest, cardvision
│   ├── web/               # dashboard (embedded into the server binary)
│   ├── app/               # Qt admin app (optional)
│   └── testdata/          # card-vision glyph templates
├── docs/              # architecture.md (system), engine.md, README.md (vision),
│                      #   models.md
└── research/          # original Python prototype + scripts/ (lab setup)
```

- New generic scraping/control code goes in `glance/core/`; app-specific
  knowledge goes in a package (`glance/packages/<name>/`: manifest
  `glance-package.json` + mappings + templates; contract in
  `glance/core/include/packages.h`). ACR is the default package `acr`.
  Packages are data-only; users add more with `glance pkg install`.
- The table-mapping JSON contract is documented in
  `glance/core/include/mapping.h` (header comment) and `research/acr.md` —
  keep both in sync when it changes.
- Docs live in `docs/` (repo root) — start there (`docs/README.md`) for what
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
- Portable code only (Linux, Windows/MSVC, macOS): no `unistd.h`, `popen`,
  `mkstemp`/`mkdtemp`, hard-coded `/tmp`, `fs::path::c_str()` into printf
  (it is `wchar_t*` on Windows) — use `std::filesystem::temp_directory_path()`
  and `.string()`. Shelling out goes through `ocr.cpp`'s per-OS quoting
  (`popen`+single quotes vs `_popen`+cmd.exe double quotes). Platform APIs
  live only in the `core/src/screen_*.cpp` backends, behind `#if` guards.
- To prepare a fresh machine, run `research/scripts/install_deps.sh`
  (idempotent; installs the C++ toolchain, `libopencv-dev` and optional
  tesseract-ocr via apt, with sudo). `.secrets/` is gitignored — never commit
  it.

## Skills

Project skills live in `.claude/skills/`: `glance-bug-hunt` (find and prove
bugs, built from the bug classes this repo has actually shipped) and
`glance-verify` (lab build + ctest + CI). Use them for reviews and before
claiming a change works.

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
