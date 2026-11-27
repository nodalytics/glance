
import argparse
import hashlib
import json
import statistics
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
)

DEFAULT_IMAGE = (
    PROJECT_ROOT
    / "test_images"
    / "ss.jpeg"
)

REFERENCE_STATE = (
    OUTPUT_DIR
    / "profiled_table_state.json"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "baseline_benchmark_v1.json"
)

MIB = 1024 ** 2


def elapsed_ms(started):

    return round(
        (time.perf_counter_ns() - started)
        / 1_000_000,
        3,
    )


def normalize_state(state):

    if hasattr(state, "model_dump"):

        return state.model_dump(
            mode="json"
        )

    return state


def extract_recognition_values(state):

    state = normalize_state(state)

    cards = state.get("cards", {})
    game = state.get("game", {})
    validation = state.get("validation", {})

    card_slots = (
        cards.get("board_slots", [])
        + cards.get("hero_slots", [])
    )

    return {
        "status": state.get("status"),

        "table": state.get("table", {}),

        "street": game.get("street"),

        "cards": [
            {
                "slot": card.get("slot"),
                "rank": card.get("rank"),
                "suit": card.get("suit"),
                "recognized": card.get(
                    "recognized"
                ),
                "occupied": card.get(
                    "occupied"
                ),
            }
            for card in card_slots
        ],

        "players": [
            {
                "seat": player.get("seat"),
                "name": player.get("name"),
                "stack": player.get("stack"),
                "bounty_display": player.get(
                    "bounty_display"
                ),
            }
            for player in state.get(
                "players",
                [],
            )
        ],

        "validation": {
            "valid": validation.get("valid"),

            "error_count": validation.get(
                "error_count"
            ),

            "warning_count": validation.get(
                "warning_count"
            ),
        },
    }


def compare_results(reference, current):

    expected = extract_recognition_values(
        reference
    )

    actual = extract_recognition_values(
        current
    )

    differences = []

    for key in expected:

        if expected[key] != actual[key]:

            differences.append({
                "field": key,
                "expected": expected[key],
                "actual": actual[key],
            })

    return {
        "matches_reference": (
            len(differences) == 0
        ),

        "difference_count": len(
            differences
        ),

        "differences": differences,
    }


def get_resource_snapshot():

    process = psutil.Process()

    memory = process.memory_info()

    system = psutil.virtual_memory()

    return {
        "process_rss_mib": round(
            memory.rss / MIB,
            3,
        ),

        "system_available_memory_mib": round(
            system.available / MIB,
            3,
        ),

        "system_memory_percent": (
            system.percent
        ),

        "process_threads": (
            process.num_threads()
        ),
    }


def calculate_statistics(values):

    if not values:
        return None

    return {
        "count": len(values),

        "minimum_ms": min(values),

        "maximum_ms": max(values),

        "mean_ms": round(
            statistics.mean(values),
            3,
        ),

        "median_ms": round(
            statistics.median(values),
            3,
        ),

        "standard_deviation_ms": round(
            statistics.pstdev(values),
            3,
        ),
    }


def save_report(report):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--image",
        type=Path,
        default=DEFAULT_IMAGE,
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=4,
    )

    args = parser.parse_args()

    if args.runs < 2:
        parser.error(
            "At least two runs are required."
        )

    image = args.image.resolve()

    if not image.is_file():
        raise FileNotFoundError(image)

    if not REFERENCE_STATE.is_file():
        raise FileNotFoundError(
            f"Reference missing: "
            f"{REFERENCE_STATE}"
        )

    reference = json.loads(
        REFERENCE_STATE.read_text(
            encoding="utf-8"
        )
    )

    print("=" * 70)

    print(
        "PHASE 7.3 - COLD AND WARM BENCHMARK"
    )

    print("=" * 70)

    print(f"Screenshot: {image.name}")
    print(f"Total runs: {args.runs}")

    report = {
        "benchmark_version": "1.0.0",

        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "screenshot": image.name,

        "screenshot_sha256": hashlib.sha256(
            image.read_bytes()
        ).hexdigest(),

        "requested_runs": args.runs,

        "profiling_enabled": False,

        "initial_resources": (
            get_resource_snapshot()
        ),

        "runs": [],

        "success": False,
    }

    total_started = time.perf_counter_ns()

    try:

        print(
            "\nImporting pipeline...",
            flush=True,
        )

        started = time.perf_counter_ns()

        from poker_apis.pipeline.screenshot_pipeline import (
            ScreenshotPipeline,
        )

        report["import_ms"] = (
            elapsed_ms(started)
        )

        print(
            f"Import: {report['import_ms']} ms"
        )

        print(
            "\nCreating pipeline instance...",
            flush=True,
        )

        started = time.perf_counter_ns()

        pipeline = ScreenshotPipeline()

        report["constructor_ms"] = (
            elapsed_ms(started)
        )

        print(
            "Constructor: "
            f"{report['constructor_ms']} ms"
        )

        for index in range(args.runs):

            run_number = index + 1

            run_type = (
                "cold"
                if index == 0
                else "warm"
            )

            print(
                f"\nRUN {run_number}/{args.runs}"
                f" - {run_type.upper()}",
                flush=True,
            )

            before = get_resource_snapshot()

            started = time.perf_counter_ns()

            state = pipeline.process_file(
                image
            )

            processing_ms = elapsed_ms(
                started
            )

            after = get_resource_snapshot()

            state = normalize_state(state)

            comparison = compare_results(
                reference,
                state,
            )

            metadata = state.get(
                "metadata",
                {},
            )

            game = state.get("game", {})

            validation = state.get(
                "validation",
                {},
            )

            run = {
                "run": run_number,

                "type": run_type,

                "processing_ms": (
                    processing_ms
                ),

                "backend_timings": (
                    metadata.get(
                        "timings",
                        {},
                    )
                ),

                "recognized_cards": game.get(
                    "recognized_card_count"
                ),

                "player_count": len(
                    state.get("players", [])
                ),

                "status": state.get(
                    "status"
                ),

                "validation_valid": (
                    validation.get("valid")
                ),

                "reference_comparison": (
                    comparison
                ),

                "resources_before": before,

                "resources_after": after,
            }

            report["runs"].append(run)

            print(
                f"Processing: "
                f"{processing_ms:,.3f} ms"
            )

            print(
                f"Recognized cards: "
                f"{run['recognized_cards']}"
            )

            print(
                f"Players: "
                f"{run['player_count']}"
            )

            print(
                "Reference match: "
                f"{comparison['matches_reference']}"
            )

            print(
                "Memory: "
                f"{after['process_rss_mib']} MiB"
            )

            # Preserve completed runs even
            # if a subsequent run fails.

            save_report(report)

        cold = report["runs"][0]

        warm = [
            run["processing_ms"]
            for run in report["runs"]
            if run["type"] == "warm"
        ]

        warm_statistics = (
            calculate_statistics(warm)
        )

        warm_mean = warm_statistics[
            "mean_ms"
        ]

        report["summary"] = {
            "cold_processing_ms": (
                cold["processing_ms"]
            ),

            "cold_total_ms": round(
                report["import_ms"]
                + report["constructor_ms"]
                + cold["processing_ms"],
                3,
            ),

            "warm_statistics": (
                warm_statistics
            ),

            "cold_to_warm_speedup": round(
                cold["processing_ms"]
                / warm_mean,
                3,
            ),

            "cold_to_warm_reduction_percent": round(
                (
                    1
                    - warm_mean
                    / cold["processing_ms"]
                ) * 100,
                3,
            ),

            "all_runs_match_reference": all(
                run["reference_comparison"][
                    "matches_reference"
                ]
                for run in report["runs"]
            ),

            "all_runs_valid": all(
                run["validation_valid"] is True
                and run["status"] == "valid"
                for run in report["runs"]
            ),

            "completed_runs": len(
                report["runs"]
            ),
        }

        report["success"] = (
            report["summary"][
                "all_runs_match_reference"
            ]
            and report["summary"][
                "all_runs_valid"
            ]
        )

    except Exception as error:

        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    finally:

        report["total_benchmark_ms"] = (
            elapsed_ms(total_started)
        )

        report["final_resources"] = (
            get_resource_snapshot()
        )

        save_report(report)

    print("\n" + "=" * 70)

    print("BENCHMARK RESULTS")

    print("=" * 70)

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        )
    )

    print(f"\nReport saved: {OUTPUT_FILE}")

    if not report["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
