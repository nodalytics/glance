
import argparse
import json
import subprocess
import sys

from pathlib import Path

import benchmark_ocr_onednn as benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "ocr_model_benchmark.json"
)

MODEL_CONFIGURATIONS = {
    "v6_medium": {
        "text_detection_model_name":
            "PP-OCRv6_medium_det",

        "text_recognition_model_name":
            "PP-OCRv6_medium_rec",
    },

    "v6_small": {
        "text_detection_model_name":
            "PP-OCRv6_small_det",

        "text_recognition_model_name":
            "PP-OCRv6_small_rec",
    },

    "v6_tiny": {
        "text_detection_model_name":
            "PP-OCRv6_tiny_det",

        "text_recognition_model_name":
            "PP-OCRv6_tiny_rec",
    },

    "v5_mobile": {
        "text_detection_model_name":
            "PP-OCRv5_mobile_det",

        "text_recognition_model_name":
            "en_PP-OCRv5_mobile_rec",
    },

    "v4_mobile": {
        "text_detection_model_name":
            "PP-OCRv4_mobile_det",

        "text_recognition_model_name":
            "en_PP-OCRv4_mobile_rec",
    },
}


def get_model_size(model_name):

    directory = (
        Path.home()
        / ".paddlex"
        / "official_models"
        / model_name
    )

    if not directory.exists():
        return None

    total_bytes = sum(
        file.stat().st_size
        for file in directory.rglob("*")
        if file.is_file()
    )

    return round(
        total_bytes / (1024 ** 2),
        3,
    )


def configure_benchmark():

    benchmark.CONFIGURATIONS = (
        MODEL_CONFIGURATIONS
    )


def run_worker(configuration, runs):

    configure_benchmark()

    return benchmark.run_worker(
        configuration,
        runs,
    )


def run_benchmark(configurations, runs):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "benchmark_version": "1.0.0",

        "input_type":
            "synthetic_text_document",

        "runs_per_configuration": runs,

        "configurations": [],
    }

    for configuration in configurations:

        print("\n" + "=" * 65)

        print(
            f"MODEL CONFIGURATION: {configuration}",
            flush=True,
        )

        print("=" * 65)

        worker_file = (
            benchmark.worker_path(
                configuration
            )
        )

        if worker_file.exists():
            worker_file.unlink()

        command = [
            sys.executable,

            str(
                Path(__file__).resolve()
            ),

            "--worker",
            configuration,

            "--runs",
            str(runs),
        ]

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
                    "configuration": configuration,
                    "success": False,
                    "error": {
                        "message":
                            "Worker produced no report."
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
                        "message":
                            "Worker exited unsuccessfully."
                    },
                )

        except subprocess.TimeoutExpired:

            result = {
                "configuration": configuration,
                "success": False,
                "error": {
                    "message":
                        "Worker exceeded 900 seconds."
                },
            }

        models = MODEL_CONFIGURATIONS[
            configuration
        ]

        detection_model = models[
            "text_detection_model_name"
        ]

        recognition_model = models[
            "text_recognition_model_name"
        ]

        detection_size = get_model_size(
            detection_model
        )

        recognition_size = get_model_size(
            recognition_model
        )

        result["models"] = {
            "detection": detection_model,

            "recognition": recognition_model,

            "detection_size_mib":
                detection_size,

            "recognition_size_mib":
                recognition_size,

            "total_size_mib": (
                round(
                    detection_size
                    + recognition_size,
                    3,
                )
                if detection_size is not None
                and recognition_size is not None
                else None
            ),
        }

        report["configurations"].append(
            result
        )

        benchmark.save_json(
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

    baseline = next(
        (
            item["summary"]["warm_mean_ms"]

            for item in eligible

            if item["configuration"]
            == "v6_medium"
        ),
        None,
    )

    ranking = []

    for item in eligible:

        duration = item["summary"][
            "warm_mean_ms"
        ]

        entry = {
            "configuration":
                item["configuration"],

            "warm_mean_ms":
                duration,

            "cold_inference_ms":
                item["summary"][
                    "cold_inference_ms"
                ],

            "initialization_ms":
                item["initialization_ms"],

            "maximum_sampled_rss_mib":
                item["summary"][
                    "maximum_sampled_rss_mib"
                ],

            "model_size_mib":
                item["models"][
                    "total_size_mib"
                ],

            "all_lines_matched": True,
        }

        if baseline is not None and duration > 0:

            entry["speedup"] = round(
                baseline / duration,
                3,
            )

            entry["reduction_percent"] = round(
                (1 - duration / baseline)
                * 100,
                3,
            )

        ranking.append(entry)

    report["ranking"] = ranking

    report["failed_configurations"] = [
        {
            "configuration":
                item["configuration"],

            "error":
                item.get("error"),
        }

        for item in report["configurations"]

        if not item.get("success")
    ]

    report["accuracy_failed_configurations"] = [
        {
            "configuration":
                item["configuration"],

            "missing_lines": [
                {
                    "run": run["run"],

                    "missing_lines":
                        run["accuracy"][
                            "missing_lines"
                        ],
                }

                for run in item.get("runs", [])

                if run["accuracy"][
                    "line_match_percent"
                ] < 100
            ],
        }

        for item in report["configurations"]

        if item.get("success")

        and not item.get("summary", {}).get(
            "all_lines_matched"
        )
    ]

    benchmark.save_json(
        OUTPUT_FILE,
        report,
    )

    print("\n" + "=" * 65)
    print("FINAL MODEL BENCHMARK RESULTS")
    print("=" * 65)

    print(
        json.dumps(
            {
                "ranking": ranking,

                "failed_configurations":
                    report[
                        "failed_configurations"
                    ],

                "accuracy_failed_configurations":
                    report[
                        "accuracy_failed_configurations"
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
        choices=MODEL_CONFIGURATIONS,
    )

    parser.add_argument(
        "--configs",
        nargs="+",
        choices=MODEL_CONFIGURATIONS,
        default=list(MODEL_CONFIGURATIONS),
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
