
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "ocr_thread_benchmark.json"
)

THREAD_CONFIGURATIONS = [
    "default",
    "1",
    "2",
    "4",
    "8",
    "12",
]

EXPECTED_LINES = [
    "DOCUMENT RECOGNITION TEST",
    "Reference Number: 123456",
    "Invoice Total: 47500",
    "Quantity: 2500",
    "Average Value: 83333",
    "Department: Research",
    "Status: Complete",
    "Date: 2026-11-26",
]


def elapsed_ms(started):

    return round(
        (time.perf_counter_ns() - started)
        / 1_000_000,
        3,
    )


def create_test_image():

    import cv2
    import numpy as np

    image = np.full(
        (900, 1600, 3),
        255,
        dtype=np.uint8,
    )

    for index, line in enumerate(
        EXPECTED_LINES
    ):

        cv2.putText(
            image,
            line,
            (80, 100 + index * 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )

    return image


def normalize_text(value):

    return "".join(
        str(value).lower().split()
    )


def evaluate_text(results):

    recognized = []

    for result in results:

        payload = result.json

        if not isinstance(payload, dict):
            continue

        data = payload.get(
            "res",
            payload,
        )

        recognized.extend(
            str(text)
            for text in data.get(
                "rec_texts",
                [],
            )
        )

    normalized = {
        normalize_text(text)
        for text in recognized
    }

    matched = [
        line
        for line in EXPECTED_LINES
        if normalize_text(line)
        in normalized
    ]

    missing = [
        line
        for line in EXPECTED_LINES
        if normalize_text(line)
        not in normalized
    ]

    return {
        "expected_lines": len(
            EXPECTED_LINES
        ),

        "recognized_lines": len(
            recognized
        ),

        "matched_lines": len(
            matched
        ),

        "line_match_percent": round(
            len(matched)
            / len(EXPECTED_LINES)
            * 100,
            2,
        ),

        "recognized_text": recognized,

        "missing_lines": missing,
    }


def resource_snapshot():

    import psutil

    process = psutil.Process()

    return {
        "rss_mib": round(
            process.memory_info().rss
            / (1024 ** 2),
            3,
        ),

        "process_threads": (
            process.num_threads()
        ),

        "available_memory_mib": round(
            psutil.virtual_memory().available
            / (1024 ** 2),
            3,
        ),
    }


def run_worker(configuration, runs):

    report = {
        "configuration": configuration,
        "success": False,
        "runs": [],
    }

    try:

        started = time.perf_counter_ns()

        from paddleocr import PaddleOCR

        report["import_ms"] = (
            elapsed_ms(started)
        )

        image = create_test_image()

        options = {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "engine": "paddle",
        }

        if configuration != "default":

            options["cpu_threads"] = int(
                configuration
            )

        report["options"] = options

        report["resources_before"] = (
            resource_snapshot()
        )

        started = time.perf_counter_ns()

        engine = PaddleOCR(
            **options
        )

        report["initialization_ms"] = (
            elapsed_ms(started)
        )

        for index in range(runs):

            started = time.perf_counter_ns()

            results = list(
                engine.predict(image)
            )

            duration = elapsed_ms(
                started
            )

            accuracy = evaluate_text(
                results
            )

            report["runs"].append({
                "run": index + 1,

                "type": (
                    "cold"
                    if index == 0
                    else "warm"
                ),

                "inference_ms": duration,

                "accuracy": accuracy,

                "resources": (
                    resource_snapshot()
                ),
            })

        warm_times = [
            run["inference_ms"]
            for run in report["runs"]
            if run["type"] == "warm"
        ]

        report["summary"] = {
            "cold_inference_ms": (
                report["runs"][0][
                    "inference_ms"
                ]
            ),

            "warm_mean_ms": round(
                statistics.mean(
                    warm_times
                ),
                3,
            ),

            "warm_median_ms": round(
                statistics.median(
                    warm_times
                ),
                3,
            ),

            "warm_minimum_ms": min(
                warm_times
            ),

            "warm_maximum_ms": max(
                warm_times
            ),

            "all_lines_matched": all(
                run["accuracy"][
                    "line_match_percent"
                ] == 100
                for run in report["runs"]
            ),
        }

        report["success"] = True

    except Exception as error:

        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    worker_file = (
        OUTPUT_DIR
        / f"ocr_threads_{configuration}.json"
    )

    worker_file.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            indent=4,
        )
    )

    return 0 if report["success"] else 1


def run_benchmark(configurations, runs):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "benchmark_version": "1.0.0",

        "input_type": (
            "synthetic_text_document"
        ),

        "runs_per_configuration": runs,

        "configurations": [],
    }

    for configuration in configurations:

        print(
            "\n" + "=" * 65,
            flush=True,
        )

        print(
            f"TESTING CPU THREADS: "
            f"{configuration}",
            flush=True,
        )

        worker_file = (
            OUTPUT_DIR
            / f"ocr_threads_{configuration}.json"
        )

        if worker_file.exists():
            worker_file.unlink()

        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            configuration,
            "--runs",
            str(runs),
        ]

        started = time.perf_counter_ns()

        try:

            process = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                timeout=900,
            )

            if worker_file.exists():

                result = json.loads(
                    worker_file.read_text(
                        encoding="utf-8"
                    )
                )

            else:

                result = {
                    "configuration": (
                        configuration
                    ),

                    "success": False,

                    "error": {
                        "message": (
                            "Worker did not "
                            "produce a report."
                        )
                    },
                }

            result["return_code"] = (
                process.returncode
            )

        except subprocess.TimeoutExpired:

            result = {
                "configuration": (
                    configuration
                ),

                "success": False,

                "error": {
                    "message": (
                        "Worker timed out."
                    )
                },
            }

        result["total_worker_ms"] = (
            elapsed_ms(started)
        )

        report["configurations"].append(
            result
        )

        OUTPUT_FILE.write_text(
            json.dumps(
                report,
                indent=4,
            ),
            encoding="utf-8",
        )

    eligible = [
        item
        for item in report[
            "configurations"
        ]
        if item.get("success")
        and item.get("summary", {}).get(
            "all_lines_matched"
        )
    ]

    eligible.sort(
        key=lambda item: item["summary"][
            "warm_mean_ms"
        ]
    )

    report["ranking"] = [
        {
            "configuration": item[
                "configuration"
            ],

            "warm_mean_ms": item["summary"][
                "warm_mean_ms"
            ],

            "initialization_ms": item[
                "initialization_ms"
            ],
        }
        for item in eligible
    ]

    control = next(
        (
            item
            for item in eligible
            if item["configuration"]
            == "default"
        ),
        None,
    )

    if eligible and control:

        baseline = control["summary"][
            "warm_mean_ms"
        ]

        best = eligible[0]["summary"][
            "warm_mean_ms"
        ]

        report["comparison"] = {
            "best_configuration": (
                eligible[0]["configuration"]
            ),

            "baseline_ms": baseline,

            "best_ms": best,

            "speedup": round(
                baseline / best,
                3,
            ),

            "reduction_percent": round(
                (1 - best / baseline) * 100,
                3,
            ),
        }

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 65)

    print("FINAL BENCHMARK SUMMARY")

    print("=" * 65)

    print(
        json.dumps(
            {
                "ranking": report["ranking"],

                "comparison": report.get(
                    "comparison"
                ),

                "failed_configurations": [
                    {
                        "configuration": item[
                            "configuration"
                        ],

                        "error": item.get(
                            "error"
                        ),
                    }
                    for item in report[
                        "configurations"
                    ]
                    if not item.get(
                        "success"
                    )
                ],
            },
            indent=4,
        )
    )

    print(
        f"\nReport saved: {OUTPUT_FILE}"
    )

    return 0 if eligible else 1


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--worker",
        choices=THREAD_CONFIGURATIONS,
    )

    parser.add_argument(
        "--configs",
        nargs="+",
        choices=THREAD_CONFIGURATIONS,
        default=THREAD_CONFIGURATIONS,
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=3,
    )

    args = parser.parse_args()

    if args.runs < 2:

        parser.error(
            "At least two runs are required."
        )

    if args.worker:

        return run_worker(
            args.worker,
            args.runs,
        )

    return run_benchmark(
        args.configs,
        args.runs,
    )


if __name__ == "__main__":
    sys.exit(main())
