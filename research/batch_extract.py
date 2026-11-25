#!/usr/bin/env python3
"""Post saved table screenshots to a local glance server and log states.

Reads PNG/JPEG files from a directory. Does not capture a window or send input.
Each successful `/capture` response is appended to a JSONL file. A frame whose
parsed state is identical to the previous accepted frame is not written again.

Default server is the one documented in the repository README:
http://127.0.0.1:8000/capture
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
DEFAULT_URL = "http://127.0.0.1:8000/capture"


def list_images(directory: Path) -> list[Path]:
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.name)


def canonical_state(state: object) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def post_image(url: str, image: Path, timeout: float) -> tuple[int, object]:
    request = urllib.request.Request(
        url,
        data=image.read_bytes(),
        method="POST",
        headers={"Content-Type": "application/octet-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    parsed: object
    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = {"error": "response was not JSON", "body": body}
    return status, parsed


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"session_states_{stamp}.jsonl")


def extract(directory: Path, url: str, output: Path, timeout: float) -> int:
    images = list_images(directory)
    if not images:
        print(f"no PNG or JPEG files in {directory}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    failed = 0
    previous: str | None = None

    with output.open("a", encoding="utf-8") as handle:
        for image in images:
            try:
                status, payload = post_image(url, image, timeout)
            except urllib.error.URLError as exc:
                failed += 1
                print(f"{image.name}: request failed: {exc.reason}", file=sys.stderr)
                continue
            if status != 200 or not isinstance(payload, dict) or "error" in payload:
                failed += 1
                print(f"{image.name}: HTTP {status} {payload}", file=sys.stderr)
                continue
            token = canonical_state(payload)
            if token == previous:
                skipped += 1
                continue
            previous = token
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": image.name,
                "state": payload,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(
        f"wrote {written} state(s) to {output}; "
        f"skipped {skipped} duplicate frame(s); {failed} failed"
    )
    return 0 if written or skipped else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="directory of saved PNG/JPEG frames")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"capture endpoint (default {DEFAULT_URL})")
    parser.add_argument("--output", type=Path, help="JSONL path (default session_states_<UTC>.jsonl)")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    args = parser.parse_args(argv)
    if not args.directory.is_dir():
        print(f"not a directory: {args.directory}", file=sys.stderr)
        return 2
    output = args.output or default_output_path()
    return extract(args.directory, args.url, output, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
