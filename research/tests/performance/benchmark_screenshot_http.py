
import json
import time

from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]

IMAGE_PATH = ROOT / "test_images" / "ss.jpeg"

API_URL = (
    "http://127.0.0.1:8000"
    "/api/v1/analyze/screenshot"
)


def to_ms(seconds):

    if seconds is None:
        return None

    return round(seconds * 1000, 3)


def main():

    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(IMAGE_PATH)

    content = IMAGE_PATH.read_bytes()

    print("=" * 60)
    print("SCREENSHOT HTTP LATENCY")
    print("=" * 60)

    print(f"Image: {IMAGE_PATH.name}")
    print(f"Size: {len(content)} bytes")

    with httpx.Client(timeout=600.0) as client:

        start = time.perf_counter_ns()

        response = client.post(
            API_URL,
            files={
                "file": (
                    IMAGE_PATH.name,
                    content,
                    "image/jpeg",
                )
            },
        )

        response.raise_for_status()

        state = response.json()

        http_ms = (
            time.perf_counter_ns() - start
        ) / 1_000_000

    metadata = state.get("metadata", {})
    timings = metadata.get("timings", {})

    service_ms = to_ms(
        metadata.get(
            "service_processing_seconds"
        )
    )

    summary = {
        "http_total_ms": round(http_ms, 3),

        "service_processing_ms": service_ms,

        "outside_service_timer_ms": (
            round(http_ms - service_ms, 3)
            if service_ms is not None
            else None
        ),

        "pipeline_processing_ms": to_ms(
            metadata.get(
                "processing_time_seconds"
            )
        ),

        "pipeline_timings_ms": {
            key.replace("_seconds", "_ms"):
                to_ms(value)
            for key, value in timings.items()
            if key.endswith("_seconds")
            and isinstance(value, (int, float))
        },

        "response_size_bytes": len(
            response.content
        ),

        "state_status": state.get("status"),

        "validation_errors": state.get(
            "validation", {}
        ).get("error_count"),

        "validation_warnings": state.get(
            "validation", {}
        ).get("warning_count"),
    }

    output = (
        ROOT
        / "test_output"
        / "performance"
        / "screenshot_http_latency.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(summary, indent=4),
        encoding="utf-8",
    )

    print("\nFINAL SUMMARY")

    print(
        json.dumps(summary, indent=4)
    )

    print(f"\nReport saved: {output}")


if __name__ == "__main__":
    main()
