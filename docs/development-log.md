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

No other commits exist on this branch beyond that baseline.

## Current milestone

Branch and this tracking document. No feature milestone has been started here.

## Pending tasks

None recorded.

## Verification evidence

- `git show 3decc87` confirms the documentation commit, its parent, and the two files above.
- `git status` before this document was created: `main`, clean, ahead of `origin/main` by 1 commit.
- No configure, build, or test command was run for this entry.

## Known blockers

None recorded.
