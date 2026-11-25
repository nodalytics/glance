# Development log

Tracking for independent work on this branch. Entries below are facts from the repository or Git history. No build, test, or review result is recorded unless it was actually run.

## Project objective

Keep independent contributions scoped, traceable, and reviewable on their own branch.

The repository's documented purpose, from `README.md`, is a C++ screen-scraping tool that turns a grab of an ACR Poker table window into JSON over HTTP. That statement is the project's own description, not a claim that further work has been done.

## Current baseline

- Branch: `feat/my-development-work`, created from `main` at `3decc87d78d8b34375b52f6d761176932f2edbbc`.
- `main` is 1 commit ahead of `origin/main`. That remote commit is `64a9e11b48794402129da71d24ca0608a3cbb93d` (`Fix the CI imwrite abort: extensionless mkstemp path in ocr.cpp`).
- This branch has not been pushed.
- Application source, build files, dependencies, and tests were not changed for this log.

## Work completed to date

- `3decc87d78d8b34375b52f6d761176932f2edbbc` — `docs: fix repository documentation references`
  - Author: BOLEXMAN `<belrender000@gmail.com>`
  - Date: 2026-11-25 14:12:37 -0800
  - Parent: `64a9e11b48794402129da71d24ca0608a3cbb93d`
  - Files: `README.md` and `AGENTS.md` (3 insertions and 3 deletions in each; 6 insertions and 6 deletions in the commit)
  - Local only. Not on `origin/main`.

- `ae4a5a1b5ae033241214fc7df1f1b900d46ad4fa` — `docs: add independent development log`
  - Adds this file. Local only. Not pushed.

Working tree after that commit, not committed:

- `research/batch_extract.py` — posts saved PNG/JPEG files to `POST /capture` and appends states to a timestamped JSONL file. Consecutive identical states are skipped.
- `research/format_history.py` — rewrites a glance state into street, board, pot, stacks, bets, and seat labels derived from the dealer seat.
- `research/tests/test_offline_pipeline.py` — standard-library `unittest` for dedup, image listing, non-200 filtering, seat labels, and omitted numbers.
- `README.md` — short usage notes for those scripts and the unit tests.
- `glance/core/include/ocr.h`, `glance/core/src/ocr.cpp` — number-text parsing, including thousands separators, is a separate function.
- `glance/tools/selftest.cpp` — extra synthetic checks for a distinct suit, an empty card id, an unpainted board slot, a preflop frame, and the number-text parser.

No live window capture, pointer control, or action endpoint was added.

## Current milestone

Offline saved-screenshot logging and history formatting, with extra synthetic checks. The C++ selftest has not been run for these checks.

## Pending tasks

None recorded.

## Verification evidence

- `git show 3decc87` confirms the documentation commit, its parent, and the two files above.
- `git status` before this document was created: `main`, clean, ahead of `origin/main` by 1 commit.
- No configure, build, or test command was run for the initial log entry.
- A local Python check of `format_state`, JSONL wrapping, and `canonical_state` equality passed. `glance-selftest` was not built or run.
- `python -m unittest discover -s research/tests -v` reported `Ran 7 tests` and `OK`.
- This Windows machine has no `cmake`, `g++`, or `wsl`, so the C++ selftest was not compiled here. `.github/workflows/ci.yml` is what runs that selftest on a pull request.

## Known blockers

None recorded.
