
import argparse
import json
import statistics
import subprocess
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

from benchmark_ocr_threads import (
    create_test_image,
    evaluate_text,
    resource_snapshot,
    elapsed_ms,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "ocr_onednn_benchmark.json"
)

CONFIGURATIONS = {
    "default": {},
    "onednn_enabled": {
        "enable_mkldnn": True,
    },
    "onednn_disabled": {
        "enable_mkldnn": False,
    },
}


def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def worker_path(configuration):

    return (
        OUTPUT_DIR
        / f"ocr_{configuration}.json"
    )


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

        options.update(
            CONFIGURATIONS[configuration]
        )

        report["options"] = options

        report["resources_before"] = (
            resource_snapshot()
        )

        print(
            f"\nInitializing: {configuration}",
            flush=True,
        )

        started = time.perf_counter_ns()

        engine = PaddleOCR(**options)

        report["initialization_ms"] = (
            elapsed_ms(started)
        )

        for index in range(runs):

            run_type = (
                "cold"
                if index == 0
                else "warm"
            )

            print(
                f"\nRun {index + 1}/{runs}"
                f" - {run_type.upper()}",
                flush=True,
            )

            started = time.perf_counter_ns()

            results = list(
                engine.predict(image)
            )

            duration = elapsed_ms(started)

            accuracy = evaluate_text(
                results
            )

            report["runs"].append({
                "run": index + 1,
                "type": run_type,
                "inference_ms": duration,
                "accuracy": accuracy,
                "resources": (
                    resource_snapshot()
                ),
            })

            print(
                f"Inference: {duration:,.3f} ms"
            )

            print(
                "Expected line matches:",
                accuracy["line_match_percent"],
                "%",
            )

            save_json(
                worker_path(configuration),
                report,
            )

        warm_times = [
            item["inference_ms"]
            for item in report["runs"]
            if item["type"] == "warm"
        ]

        report["summary"] = {
            "cold_inference_ms": (
                report["runs"][0][
                    "inference_ms"
                ]
            ),

            "warm_mean_ms": round(
                statistics.mean(warm_times),
                3,
            ),

            "warm_median_ms": round(
                statistics.median(warm_times),
                3,
            ),

            "warm_minimum_ms": min(
                warm_times
            ),

            "warm_maximum_ms": max(
                warm_times
            ),

            "all_lines_matched": all(
                item["accuracy"][
                    "line_match_percent"
                ] == 100
                for item in report["runs"]
            ),

            "maximum_sampled_rss_mib": max(
                item["resources"]["rss_mib"]
                for item in report["runs"]
            ),

            "minimum_sampled_available_memory_mib": min(
                item["resources"][
                    "available_memory_mib"
                ]
                for item in report["runs"]
            ),
        }

        report["success"] = True

    except Exception as error:

        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    finally:

        save_json(
            worker_path(configuration),
            report,
        )

    return 0 if report["success"] else 1


def run_benchmark(configurations, runs):

    started = time.perf_counter_ns()

    report = {
        "benchmark_version": "1.0.0",

        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "input_type": (
            "synthetic_text_document"
        ),

        "runs_per_configuration": runs,

        "configurations": [],
    }

    for configuration in configurations:

        print("\n" + "=" * 65)

        print(
            f"CONFIGURATION: {configuration}",
            flush=True,
        )

        print("=" * 65, flush=True)

        path = worker_path(configuration)

        if path.exists():
            path.unlink()

        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            configuration,
            "--runs",
            str(runs),
        ]

        worker_started = (
            time.perf_counter_ns()
        )

        try:

            process = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                timeout=900,
            )

            if path.exists():

                result = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

            else:

                result = {
                    "configuration": configuration,
                    "success": False,
                    "error": {
                        "message": (
                            "Worker produced no report."
                        ),
                    },
                }

            result["return_code"] = (
                process.returncode
            )

            if process.returncode != 0:

                result["success"] = False

                result.setdefault(
                    "error",
                    {
                        "message": (
                            "Worker exited unsuccessfully."
                        ),
                    },
                )

        except subprocess.TimeoutExpired:

            result = {
                "configuration": configuration,
                "success": False,
                "error": {
                    "message": (
                        "Worker exceeded 900 seconds."
                    ),
                },
            }

        result["total_worker_ms"] = (
            elapsed_ms(worker_started)
        )

        report["configurations"].append(
            result
        )

        save_json(
            OUTPUT_FILE,
            report,
        )

    eligible = [
        item
        for item in report["configurations"]
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

    control = next(
        (
            item
            for item in eligible
            if item["configuration"] == "default"
        ),
        None,
    )

    ranking = []

    for item in eligible:

        duration = item["summary"][
            "warm_mean_ms"
        ]

        entry = {
            "configuration": item[
                "configuration"
            ],

            "warm_mean_ms": duration,

            "initialization_ms": item[
                "initialization_ms"
            ],

            "maximum_sampled_rss_mib": (
                item["summary"][
                    "maximum_sampled_rss_mib"
                ]
            ),
        }

        if control and duration > 0:

            baseline = control["summary"][
                "warm_mean_ms"
            ]

            entry["speedup"] = round(
                baseline / duration,
                3,
            )

            entry["reduction_percent"] = round(
                (1 - duration / baseline) * 100,
                3,
            )

        ranking.append(entry)

    report["ranking"] = ranking

    report["failed_configurations"] = [
        {
            "configuration": item[
                "configuration"
            ],

            "error": item.get("error"),
        }
        for item in report["configurations"]
        if not item.get("success")
    ]

    report["accuracy_failed_configurations"] = [
        item["configuration"]
        for item in report["configurations"]
        if item.get("success")
        and not item.get("summary", {}).get(
            "all_lines_matched"
        )
    ]

    report["total_benchmark_ms"] = (
        elapsed_ms(started)
    )

    save_json(
        OUTPUT_FILE,
        report,
    )

    print("\n" + "=" * 65)
    print("FINAL ONEDNN BENCHMARK RESULTS")
    print("=" * 65)

    print(
        json.dumps(
            {
                "ranking": ranking,

                "failed_configurations": (
                    report[
                        "failed_configurations"
                    ]
                ),

                "accuracy_failed_configurations": (
                    report[
                        "accuracy_failed_configurations"
                    ]
                ),

                "total_benchmark_ms": (
                    report["total_benchmark_ms"]
                ),
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
        choices=CONFIGURATIONS,
    )

    parser.add_argument(
        "--configs",
        nargs="+",
        choices=CONFIGURATIONS,
        default=list(CONFIGURATIONS),
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
