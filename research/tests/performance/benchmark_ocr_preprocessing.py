
import json
import statistics
import sys
import time
import unicodedata

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from paddleocr import PaddleOCR

from validate_lightweight_ocr import (
    create_document,
    extract_text,
    DOCUMENTS,
)


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "test_output" / "performance"

OUTPUT_FILE = (
    OUTPUT_DIR / "ocr_preprocessing_benchmark.json"
)

CONFIGURATIONS = [
    "original",
    "grayscale",
    "clahe",
    "gaussian",
    "otsu",
    "nlm",
]

RUNS = 3

MODEL_PREFIX = "PP-OCRv6_tiny"


def elapsed_ms(start):

    return (
        time.perf_counter_ns() - start
    ) / 1_000_000


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


def normalize_strict(text):

    return " ".join(
        text.lower().split()
    )


def normalize_adjusted(text):

    text = unicodedata.normalize(
        "NFKC",
        text,
    ).lower()

    return "".join(text.split())


def evaluate(expected, recognized, normalizer):

    expected_counter = Counter(
        normalizer(text)
        for text in expected
    )

    recognized_counter = Counter(
        normalizer(text)
        for text in recognized
    )

    matched = sum(
        (
            expected_counter
            & recognized_counter
        ).values()
    )

    expected_count = len(expected)

    recognized_count = len(recognized)

    return {
        "expected_count": expected_count,

        "recognized_count": recognized_count,

        "matched_count": matched,

        "recall_percent": round(
            matched / max(expected_count, 1)
            * 100,
            3,
        ),

        "precision_percent": round(
            matched / max(recognized_count, 1)
            * 100,
            3,
        ),

        "exact_match": (
            expected_counter
            == recognized_counter
        ),

        "missing_lines": list(
            (
                expected_counter
                - recognized_counter
            ).elements()
        ),

        "unexpected_lines": list(
            (
                recognized_counter
                - expected_counter
            ).elements()
        ),
    }


def preprocess(image, configuration):

    if configuration == "original":

        return image.copy()

    if configuration == "gaussian":

        return cv2.GaussianBlur(
            image,
            (3, 3),
            0,
        )

    if configuration == "nlm":

        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            5,
            5,
            7,
            21,
        )

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    if configuration == "grayscale":

        processed = gray

    elif configuration == "clahe":

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8),
        )

        processed = clahe.apply(gray)

    elif configuration == "otsu":

        _, processed = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY
            + cv2.THRESH_OTSU,
        )

    else:

        raise ValueError(
            f"Unknown configuration: {configuration}"
        )

    return cv2.cvtColor(
        processed,
        cv2.COLOR_GRAY2BGR,
    )


def benchmark_document(
    engine,
    image,
    expected,
    configuration,
):

    runs = []

    for run_index in range(RUNS):

        start = time.perf_counter_ns()

        processed = preprocess(
            image,
            configuration,
        )

        preprocessing_ms = elapsed_ms(start)

        start = time.perf_counter_ns()

        results = list(
            engine.predict(processed)
        )

        inference_ms = elapsed_ms(start)

        start = time.perf_counter_ns()

        recognized = extract_text(results)

        extraction_ms = elapsed_ms(start)

        strict = evaluate(
            expected,
            recognized,
            normalize_strict,
        )

        adjusted = evaluate(
            expected,
            recognized,
            normalize_adjusted,
        )

        total_ms = (
            preprocessing_ms
            + inference_ms
            + extraction_ms
        )

        runs.append({
            "run": run_index + 1,

            "preprocessing_ms": round(
                preprocessing_ms, 6
            ),

            "inference_ms": round(
                inference_ms, 6
            ),

            "extraction_ms": round(
                extraction_ms, 6
            ),

            "total_ms": round(
                total_ms, 6
            ),

            "strict_accuracy": strict,

            "adjusted_accuracy": adjusted,

            "recognized_text": recognized,
        })

    return runs


def summarize(documents):

    runs = [
        run
        for document in documents
        for run in document["runs"]
    ]

    if not runs:

        return {}

    expected_count = sum(
        run["adjusted_accuracy"]
        ["expected_count"]
        for run in runs
    )

    recognized_count = sum(
        run["adjusted_accuracy"]
        ["recognized_count"]
        for run in runs
    )

    strict_matches = sum(
        run["strict_accuracy"]
        ["matched_count"]
        for run in runs
    )

    adjusted_matches = sum(
        run["adjusted_accuracy"]
        ["matched_count"]
        for run in runs
    )

    totals = [
        run["total_ms"]
        for run in runs
    ]

    return {
        "document_count": len(documents),

        "total_runs": len(runs),

        "expected_lines": expected_count,

        "recognized_lines": recognized_count,

        "strict_matches": strict_matches,

        "adjusted_matches": adjusted_matches,

        "strict_recall_percent": round(
            strict_matches
            / max(expected_count, 1)
            * 100,
            3,
        ),

        "adjusted_recall_percent": round(
            adjusted_matches
            / max(expected_count, 1)
            * 100,
            3,
        ),

        "adjusted_precision_percent": round(
            adjusted_matches
            / max(recognized_count, 1)
            * 100,
            3,
        ),

        "mean_preprocessing_ms": round(
            statistics.mean(
                run["preprocessing_ms"]
                for run in runs
            ),
            6,
        ),

        "mean_inference_ms": round(
            statistics.mean(
                run["inference_ms"]
                for run in runs
            ),
            6,
        ),

        "mean_total_ms": round(
            statistics.mean(totals),
            6,
        ),

        "median_total_ms": round(
            statistics.median(totals),
            6,
        ),

        "p95_total_ms": round(
            float(np.percentile(totals, 95)),
            6,
        ),

        "maximum_total_ms": max(totals),

        "exact_adjusted_runs": sum(
            run["adjusted_accuracy"]
            ["exact_match"]
            for run in runs
        ),
    }


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "python_executable": sys.executable,

        "model": MODEL_PREFIX,

        "runs_per_document": RUNS,

        "configurations": [],

        "success": False,
    }

    print("=" * 60)
    print("DOCUMENT OCR PREPROCESSING BENCHMARK")
    print("=" * 60)

    try:

        start = time.perf_counter_ns()

        engine = PaddleOCR(
            text_detection_model_name=(
                MODEL_PREFIX + "_det"
            ),

            text_recognition_model_name=(
                MODEL_PREFIX + "_rec"
            ),

            use_doc_orientation_classify=False,

            use_doc_unwarping=False,

            use_textline_orientation=False,

            engine="paddle",
        )

        report["initialization_ms"] = round(
            elapsed_ms(start),
            6,
        )

        warmup_image, _ = create_document(
            "standard"
        )

        list(engine.predict(warmup_image))

        datasets = {
            name: create_document(name)
            for name in DOCUMENTS
        }

        for configuration in CONFIGURATIONS:

            print(
                f"\nCONFIGURATION: {configuration}"
            )

            entry = {
                "configuration": configuration,

                "documents": [],

                "success": False,
            }

            report["configurations"].append(
                entry
            )

            try:

                for name in DOCUMENTS:

                    image, expected = datasets[name]

                    runs = benchmark_document(
                        engine,
                        image,
                        expected,
                        configuration,
                    )

                    entry["documents"].append({
                        "document": name,
                        "runs": runs,
                    })

                    mean_latency = statistics.mean(
                        run["total_ms"]
                        for run in runs
                    )

                    mean_recall = statistics.mean(
                        run["adjusted_accuracy"]
                        ["recall_percent"]
                        for run in runs
                    )

                    print(
                        f"{name}: "
                        f"{mean_latency:.3f} ms | "
                        f"Recall: {mean_recall:.2f}%"
                    )

                    save_report(report)

                entry["summary"] = summarize(
                    entry["documents"]
                )

                entry["success"] = True

            except Exception as error:

                entry["error_type"] = (
                    type(error).__name__
                )

                entry["error"] = str(error)

                print(
                    f"FAILED: {error}"
                )

            save_report(report)

        successful = [
            entry
            for entry in report["configurations"]
            if entry["success"]
        ]

        baseline = next(
            (
                entry["summary"]
                for entry in successful
                if entry["configuration"]
                == "original"
            ),
            None,
        )

        ranking = []

        for entry in successful:

            summary = entry["summary"]

            item = {
                "configuration": (
                    entry["configuration"]
                ),

                **summary,
            }

            if baseline is not None:

                baseline_ms = (
                    baseline["mean_total_ms"]
                )

                current_ms = (
                    summary["mean_total_ms"]
                )

                item["speedup_vs_original"] = round(
                    baseline_ms / current_ms,
                    4,
                )

                item["reduction_percent"] = round(
                    (
                        1 - current_ms / baseline_ms
                    ) * 100,
                    3,
                )

                item["accuracy_preserved"] = (
                    summary["adjusted_matches"]
                    >= baseline["adjusted_matches"]

                    and summary[
                        "adjusted_precision_percent"
                    ]
                    >= baseline[
                        "adjusted_precision_percent"
                    ]
                )

            ranking.append(item)

        ranking.sort(
            key=lambda item: (
                item["mean_total_ms"]
            )
        )

        report["ranking"] = ranking

        report["summary"] = {
            "configurations_tested": len(
                report["configurations"]
            ),

            "configurations_passed": len(
                successful
            ),

            "configurations_failed": (
                len(report["configurations"])
                - len(successful)
            ),
        }

        report["success"] = (
            len(successful)
            == len(CONFIGURATIONS)
        )

    except Exception as error:

        report["error_type"] = (
            type(error).__name__
        )

        report["error"] = str(error)

    finally:

        save_report(report)

    print("\nFINAL BENCHMARK SUMMARY")

    print(
        json.dumps(
            {
                "success": report["success"],

                "summary": report.get(
                    "summary"
                ),

                "ranking": report.get(
                    "ranking"
                ),

                "error": report.get(
                    "error"
                ),
            },
            indent=4,
            ensure_ascii=False,
        )
    )

    print(
        f"\nReport saved: {OUTPUT_FILE}"
    )

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
