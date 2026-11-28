---
name: glance-bug-hunt
description: Hunt for bugs in the glance C++ engine (OpenCV scraping, card vision, X11/Win32/macOS control backends, cpp-httplib server, packages, CLI). Use when asked to find bugs, review glance code, audit a diff or a module, or before merging glance changes. Checks the bug classes this codebase has actually shipped, then proves each finding with a test.
---

# glance bug hunt

Find real, reproducible bugs in `glance/`, prove each one, and report or fix
them. A finding without a reproduction (failing check, crafted input, or a
concrete trace through the code) is a suspicion, not a bug — label it so.

## 0. Scope

- A diff: `git diff main...HEAD -- glance/` (or the files the user names).
- A module: read its header contract first (`glance/core/include/*.h`),
  then the source. The mapping contract lives in `mapping.h` + `research/acr.md`,
  packages in `packages.h`, card vision in `card_vision.h`.
- Whole engine: go module by module in the order of the request path in
  `docs/engine.md`.

## 1. Known bug classes (check every one that applies)

These all happened here before. Grep for them, then read the hits.

**OpenCV**
- Element type punning: `at<double>` / `at<float>` / `at<int>` must match
  `Mat::type()`. `matchTemplate` returns `CV_32F`; connectedComponents stats
  are `CV_32S`. (Real bug: `at<double>` on a CV_32F result → "4e40" scores.)
  `grep -n "at<" glance/`
- `cv::Mat(rows, cols, ...)`: rows = height first. Transposed images still
  "work" on square data. `grep -n "Mat(" glance/`
- ROI assignment is a no-op: `img(rect) = other;` only reassigns a header —
  use `other.copyTo(img(rect))`.
- ROIs out of bounds: every `cv::Rect` built from mapping/JSON/HTTP input must
  be intersected with the image (`r & cv::Rect(0,0,cols,rows)`) or checked.
- Channel assumptions: `cvtColor(BGR2…)` on a 1- or 4-channel input throws.
  HTTP/disk images can be gray or BGRA.
- `cv::imwrite`/`imencode` pick the codec by extension: temp paths need a real
  extension (real bug: extensionless `mkstemp` path → CI abort).
- Python-port drift: the research prototype (`research/poker_apis/vision`)
  uses `int()` truncation for crops and banker's rounding in `round()`;
  numpy slicing clamps silently, OpenCV ROIs throw.

**X11 / platform backends** (`core/src/screen_*.cpp`)
- Xlib `Status` functions (`XGetWindowAttributes`, `XQueryTree`,
  `XGetGeometry`, `XTranslateCoordinates`) return NONZERO on success;
  `XGetWindowProperty` returns `Success` (0). Comparing the former to
  `Success` inverts them (real bug).
- `unsigned long` is 64-bit on LP64: never read 32-bit pixels through it.
- `XWarpPointer(dpy, None, None, …)` moves RELATIVE; absolute needs dest=root.
- X headers `#define` `Complex`, `COUNT`, `None`, `Status`, `Bool`, `True`,
  `Success` — they must not leak into OpenCV/other headers parsed later.
- Typing: keysyms needing Shift, non-ASCII text, keys absent from the keymap.
- Win32: DPI awareness, virtual-desktop origin (can be negative), `SendInput`
  absolute coordinates normalized to 0..65535. macOS: points vs pixels
  (Retina), permissions.

**HTTP server** (`core/src/server*.cpp`, `app_server.cpp`)
- Body limits: `set_payload_max_length` AND the form-urlencoded compile-time
  limit (real bug: silent 413 on multi-MB POSTs).
- Concurrency: httplib runs handlers on a thread pool. Shared state
  (`ScreenshotService`, `ControlService`, scraper) read/written from several
  routes needs a lock — look for unsynchronized access.
- Untrusted input: query params, JSON bodies (type checks before `get<>`),
  image bytes (`imdecode` → empty), path traversal in asset/file routes.
- Network exposure: control routes inject real input; check bind host and
  what a remote caller can do. Packages are never installable over HTTP.

**Shell / filesystem**
- `popen`/`system` with interpolated strings: quoting per platform, user
  input reaching the command (tesseract whitelist, `git clone` URLs).
- Temp files: unique names, cleanup on every error path.
- Package paths: manifests must not reference files outside the package
  (`weakly_canonical` prefix check); names validated before use in paths.

**Card vision / scraping logic**
- Accept/reject gates: a wrong card accepted is worse than a rejection —
  check thresholds AND margins, and that "unknown" never becomes a card.
- Slot naming: `my<n>`, `board<n>`, `p<n>_hand<m>` (1-based); calibration
  hero regions also accept `hero_card_1/2`.
- Reload: calling `load_mapping` twice must not duplicate buttons/slots.

**Build / docs drift**
- A new `.cpp` not in `CMakeLists.txt`; a target configured before the
  `-Wall -Wextra` block references it; options silently falling back
  (X11/OCR/Qt) so the code is never compiled — check configure output.
- Contract changed in code but not in `mapping.h` header comment +
  `research/acr.md` (AGENTS.md requires both).

## 2. Prove it

For each candidate:
1. Write the smallest reproduction: a CHECK in `glance/tools/selftest.cpp`
   (or `pkgtest.cpp` / `webtest.cpp`), a crafted image/mapping/HTTP request,
   or a `glance-cardvision eval` run showing the wrong output.
2. Run it on the lab (see the `glance-verify` skill) — the reproduction must
   FAIL before the fix.
3. Fix minimally, rerun: the check passes and nothing else regresses
   (full `ctest`, including the `cardvision_*` accuracy gates).

## 3. Report

Per finding: file:line, the bug class, the concrete failure (input →
wrong output/crash), the reproduction, and status (fixed + verified /
reproduced, not fixed / suspected, not reproduced). Do not report style
nits as bugs. If the user wants tracking, file GitHub issues on
`nodalytics/glance` with the reproduction in the body.
