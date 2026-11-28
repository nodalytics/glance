---
name: glance-verify
description: Build and test glance on the lab machine (primary build host) and read CI, to verify a change or reproduce a bug. Use whenever glance C++ code changed, before claiming something works, or when a bug-hunt finding needs a reproduction run. Covers lab sync, configure/build, ctest (selftest, webtest, pkgtest, card-vision accuracy gates), and CI.
---

# glance verify

The lab is the primary build host; this workstation usually has no OpenCV.
CI (`.github/workflows/ci.yml`) is the only place tesseract OCR and other
platforms run. Never claim "works" without the output of one of them.

## Lab access

`source .secrets/lab.env` (repo root, gitignored) gives `$LAB` and `$LAB_KEY`.
Never write lab hosts/keys into committed files.

- The key path contains a space: `ssh -i "$LAB_KEY" "$LAB" '…'`, and for
  rsync `-e "ssh -i '$LAB_KEY'"` (single quotes inside).
- `pkill -f pattern` over ssh can kill the remote shell itself: use the
  bracket trick `pkill -f "[g]lance serve"`.
- No sudo without the user; no tesseract on the lab (OCR checks skip by
  design). Port 8000 is taken there — use a high port for servers.
- Use your own lab directory (e.g. `~/glance-<topic>/`) so parallel work
  does not collide.

## Build + test

```bash
source .secrets/lab.env
D=glance-verify   # your lab dir
ssh -i "$LAB_KEY" "$LAB" "mkdir -p ~/$D/research"
rsync -az --timeout=120 --delete --exclude build -e "ssh -i '$LAB_KEY'" glance/ "$LAB:$D/glance/"
rsync -az --timeout=120 -e "ssh -i '$LAB_KEY'" research/test_assets/ "$LAB:$D/research/test_assets/"
ssh -i "$LAB_KEY" "$LAB" "cd ~/$D/glance && cmake -B build -S . -DCMAKE_BUILD_TYPE=Release 2>&1 | grep -E 'glance:|Error' ;
  cmake --build build -j48 2>&1 | grep -E 'error|warning' ; ctest --test-dir build --output-on-failure 2>&1 | tail -20"
```

- Configure lines `glance: …` say which optional parts are compiled (OCR,
  X11, Qt app). A part that silently fell back is NOT verified.
- The build must have zero warnings (`-Wall -Wextra`).
- Tests: `selftest` (engine end to end, fake control backends), `webtest`
  (dashboard routes), `pkgtest` (packages), `cardvision_*` (accuracy gates on
  `research/test_assets/validation`, zero wrong cards allowed).
- Accuracy detail: `build/glance-cardvision eval <dataset> --suits … --ranks …
  --json out.json` prints per-variant accuracy and every miss.
- Server smoke test: `build/glance-selftest --fixtures /tmp/fx` then
  `build/glance serve --mapping /tmp/fx/mapping.json --port 18xxx --host 127.0.0.1`
  and the client commands (`glance state|capture|packages --url …`).

## CI

Pushes to a branch only run CI through a PR (the workflow triggers on
`pull_request` and `main`). `gh run list --repo nodalytics/glance --branch <b>`,
`gh run watch <id> --exit-status`, logs via `gh run view <id> --log`.
Commit/push only when the user asked for it.

## Reporting

Quote the actual output (test summary lines, failing checks). If a step was
skipped (no tesseract, no display, platform not built), say so explicitly.
