
import argparse
import json
import statistics
import subprocess
import sys
import time

from collections import Counter
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "test_output" / "performance"

OUTPUT_FILE = (
    OUTPUT_DIR / "lightweight_ocr_validation.json"
)

MODELS = {
    "tiny": "PP-OCRv6_tiny",
    "small": "PP-OCRv6_small",
    "medium": "PP-OCRv6_medium",
}

DOCUMENTS = [
    "standard",
    "small_text",
    "low_contrast",
    "noisy",
    "dark",
    "dense",
]

EXPECTED_LINES = [
    "Inventory Report",
    "Reference: AB123789",
    "Quantity: 3482",
    "Total: 67219",
    "Department: Operations",
    "Status: Approved",
    "Date: 2026-11-26",
    "Location: Building 12",
]


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )


def normalize(text):
    return " ".join(
        text.lower().split()
    )


def create_document(document_type):

    background = 255
    foreground = 20
    font_scale = 1.4
    thickness = 2
    spacing = 90

    lines = EXPECTED_LINES.copy()

    if document_type == "small_text":
        font_scale = 0.65
        thickness = 1

    elif document_type == "low_contrast":
        background = 205
        foreground = 145

    elif document_type == "dark":
        background = 25
        foreground = 235

    elif document_type == "dense":
        font_scale = 0.8
        thickness = 1
        spacing = 40

        lines.extend([
            "Product Code: ZX9876",
            "Batch Number: 45019",
            "Warehouse: Central",
            "Delivery: Pending",
            "Order Number: 876543",
            "Category: Equipment",
            "Units Received: 124",
            "Units Remaining: 82",
        ])

    image = np.full(
        (900, 1600, 3),
        background,
        dtype=np.uint8,
    )

    for index, line in enumerate(lines):

        cv2.putText(
            image,
            line,
            (80, 100 + index * spacing),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (foreground,) * 3,
            thickness,
            cv2.LINE_AA,
        )

    if document_type == "noisy":

        rng = np.random.default_rng(42)

        noise = rng.normal(
            0,
            12,
            image.shape,
        )

        image = np.clip(
            image.astype(np.float32) + noise,
            0,
            255,
        ).astype(np.uint8)

    return image, lines


def extract_text(results):

    texts = []

    for result in results:

        payload = result.json

        if not isinstance(payload, dict):
            continue

        payload = payload.get(
            "res",
            payload,
        )

        texts.extend(
            str(text)
            for text in payload.get(
                "rec_texts",
                [],
            )
        )

    return texts


def evaluate(expected, recognized):

    expected_counter = Counter(
        normalize(text)
        for text in expected
    )

    recognized_counter = Counter(
        normalize(text)
        for text in recognized
    )

    matched = sum(
        (
            expected_counter
            & recognized_counter
        ).values()
    )

    missing = list(
        (
            expected_counter
            - recognized_counter
        ).elements()
    )

    unexpected = list(
        (
            recognized_counter
            - expected_counter
        ).elements()
    )

    recall = (
        matched / len(expected)
        if expected else 0
    )

    precision = (
        matched / len(recognized)
        if recognized else 0
    )

    return {
        "expected_count": len(expected),

        "recognized_count": len(recognized),

        "matched_count": matched,

        "line_recall_percent": round(
            recall * 100, 3
        ),

        "line_precision_percent": round(
            precision * 100, 3
        ),

        "exact_match": (
            expected_counter
            == recognized_counter
        ),

        "missing_lines": missing,

        "unexpected_lines": unexpected,
    }


def worker(model):

    from paddleocr import PaddleOCR

    report = {
        "model": model,
        "success": False,
        "documents": [],
    }

    output = (
        OUTPUT_DIR
        / f"validation_{model}.json"
    )

    try:

        started = time.perf_counter()

        engine = PaddleOCR(
            text_detection_model_name=(
                MODELS[model] + "_det"
            ),
            text_recognition_model_name=(
                MODELS[model] + "_rec"
            ),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )

        report["initialization_ms"] = round(
            (time.perf_counter() - started)
            * 1000,
            3,
        )

        # Untimed warm-up.
        image, _ = create_document("standard")
        list(engine.predict(image))

        for document_type in DOCUMENTS:

            image, expected = create_document(
                document_type
            )

            started = time.perf_counter()

            results = list(
                engine.predict(image)
            )

            duration = round(
                (time.perf_counter() - started)
                * 1000,
                3,
            )

            recognized = extract_text(results)

            accuracy = evaluate(
                expected,
                recognized,
            )

            entry = {
                "document": document_type,
                "inference_ms": duration,
                "accuracy": accuracy,
                "recognized_text": recognized,
            }

            report["documents"].append(entry)

            print(
                f"{model} | {document_type} | "
                f"{duration:.3f} ms | "
                f"Recall: "
                f"{accuracy['line_recall_percent']}%",
                flush=True,
            )

            save_json(output, report)

        durations = [
            item["inference_ms"]
            for item in report["documents"]
        ]

        expected_count = sum(
            item["accuracy"]["expected_count"]
            for item in report["documents"]
        )

        recognized_count = sum(
            item["accuracy"]["recognized_count"]
            for item in report["documents"]
        )

        matched_count = sum(
            item["accuracy"]["matched_count"]
            for item in report["documents"]
        )

        report["summary"] = {
            "document_count": len(DOCUMENTS),

            "expected_lines": expected_count,

            "matched_lines": matched_count,

            "mean_inference_ms": round(
                statistics.mean(durations),
                3,
            ),

            "median_inference_ms": round(
                statistics.median(durations),
                3,
            ),

            "minimum_inference_ms": min(
                durations
            ),

            "maximum_inference_ms": max(
                durations
            ),

            "line_recall_percent": round(
                matched_count / expected_count
                * 100,
                3,
            ),

            "line_precision_percent": round(
                matched_count / recognized_count
                * 100,
                3,
            ) if recognized_count else 0,

            "exact_documents": sum(
                item["accuracy"]["exact_match"]
                for item in report["documents"]
            ),
        }

        report["success"] = True

    except Exception as error:

        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    finally:
        save_json(output, report)

    return 0 if report["success"] else 1


def benchmark(models):

    report = {
        "input_type": "synthetic_documents",
        "configurations": [],
    }

    for model in models:

        path = (
            OUTPUT_DIR
            / f"validation_{model}.json"
        )

        path.unlink(missing_ok=True)

        try:

            process = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    model,
                ],
                cwd=str(ROOT),
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
                    "model": model,
                    "success": False,
                    "error": "No worker report",
                }

            result["return_code"] = (
                process.returncode
            )

            if process.returncode != 0:
                result["success"] = False

        except subprocess.TimeoutExpired:

            result = {
                "model": model,
                "success": False,
                "error": "Worker timed out",
            }

        report["configurations"].append(
            result
        )

        save_json(OUTPUT_FILE, report)

    report["summary"] = [
        {
            "model": item["model"],
            "success": item["success"],
            "summary": item.get("summary"),
            "error": item.get("error"),
        }
        for item in report["configurations"]
    ]

    save_json(OUTPUT_FILE, report)

    print("\nFINAL VALIDATION RESULTS")

    print(
        json.dumps(
            report["summary"],
            indent=4,
        )
    )

    print(f"\nReport saved: {OUTPUT_FILE}")

    return 0 if all(
        item["success"]
        for item in report["configurations"]
    ) else 1


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--worker",
        choices=MODELS,
    )

    parser.add_argument(
        "--models",
        nargs="+",
        choices=MODELS,
        default=list(MODELS),
    )

    args = parser.parse_args()

    if args.worker:
        return worker(args.worker)

    return benchmark(args.models)


if __name__ == "__main__":
    sys.exit(main())
