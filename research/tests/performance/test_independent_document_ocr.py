
import json
import random
import statistics
import sys
import time

from pathlib import Path
from collections import Counter

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT))


from document_research.optimized_ocr import (
    OptimizedDocumentOCR,
)

from document_research.text_normalizer import (
    DocumentTextNormalizer,
)


SEED = 20261127

DOCUMENT_COUNT = 30

VARIANTS = [
    "standard",
    "small_text",
    "low_contrast",
    "noisy",
    "dark",
    "dense",
]


def create_document(index):

    rng = random.Random(SEED + index)

    variant = VARIANTS[
        index % len(VARIANTS)
    ]

    expected = [
        "Warehouse Inspection",
        f"Reference: WX{rng.randint(100000, 999999)}",
        f"Quantity: {rng.randint(10, 9999)}",
        f"Total: {rng.randint(10000, 999999)}",
        f"Batch Number: {rng.randint(10000, 99999)}",
        f"Location: Building {rng.randint(1, 99)}",
        f"Inspector: {rng.choice(['Alice', 'David', 'Sarah', 'James'])}",
        f"Status: {rng.choice(['Approved', 'Pending', 'Rejected'])}",
    ]

    background = 255
    foreground = 20
    font_scale = 1.3
    thickness = 2
    spacing = 85

    if variant == "small_text":

        font_scale = 0.65
        thickness = 1

    elif variant == "low_contrast":

        background = 205
        foreground = 145

    elif variant == "dark":

        background = 25
        foreground = 235

    elif variant == "dense":

        font_scale = 0.8
        thickness = 1
        spacing = 42

        expected.extend([
            f"Order Number: {rng.randint(100000, 999999)}",
            f"Units Received: {rng.randint(100, 999)}",
            f"Units Remaining: {rng.randint(1, 99)}",
            "Department: Logistics",
            "Category: Equipment",
            "Delivery: Scheduled",
            "Condition: Acceptable",
            "Review: Completed",
        ])

    image = np.full(
        (900, 1600, 3),
        background,
        dtype=np.uint8,
    )

    for line_index, text in enumerate(expected):

        y = 65 + line_index * spacing

        cv2.putText(
            image,
            text,
            (50, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (
                foreground,
                foreground,
                foreground,
            ),
            thickness,
            cv2.LINE_AA,
        )

    if variant == "noisy":

        noise_rng = np.random.default_rng(
            SEED + index
        )

        noise = noise_rng.normal(
            0,
            12,
            image.shape,
        )

        image = np.clip(
            image.astype(np.float32) + noise,
            0,
            255,
        ).astype(np.uint8)

    return image, expected, variant


def main():

    print("=" * 60)
    print("INDEPENDENT DOCUMENT OCR VALIDATION")
    print("=" * 60)

    engine = OptimizedDocumentOCR()

    # Exclude initial inference from warm measurements.

    image, expected, _ = create_document(-1)

    engine.recognize(image, expected)

    results = []

    for index in range(DOCUMENT_COUNT):

        image, expected, variant = (
            create_document(index)
        )

        start = time.perf_counter_ns()

        result = engine.recognize(
            image,
            expected,
            preprocessing="gaussian",
        )

        raw = result["recognized_text"]

        formatted = (
            DocumentTextNormalizer.normalize_lines(
                raw
            )
        )

        total_ms = (
            time.perf_counter_ns() - start
        ) / 1_000_000

        expected_counter = Counter(expected)
        actual_counter = Counter(formatted)

        matched = sum(
            (
                expected_counter
                & actual_counter
            ).values()
        )

        entry = {
            "document": index + 1,
            "variant": variant,
            "total_ms": total_ms,

            "expected_count": len(expected),
            "recognized_count": len(formatted),
            "matched_count": matched,

            "exact_match": (
                expected_counter == actual_counter
            ),

            "ordered_match": (
                formatted == expected
            ),

            "missing_lines": list(
                (
                    expected_counter
                    - actual_counter
                ).elements()
            ),

            "unexpected_lines": list(
                (
                    actual_counter
                    - expected_counter
                ).elements()
            ),

            "raw_text": raw,
            "formatted_text": formatted,
            "expected_text": expected,
        }

        results.append(entry)

        status = (
            "PASS"
            if entry["ordered_match"]
            else "FAIL"
        )

        print(
            f"Document {index + 1:02d} | "
            f"{variant:15s} | "
            f"{total_ms:9.3f} ms | "
            f"{matched}/{len(expected)} | "
            f"{status}"
        )

        if status == "FAIL":

            print(
                "  Missing:",
                entry["missing_lines"],
            )

            print(
                "  Unexpected:",
                entry["unexpected_lines"],
            )

    latencies = [
        item["total_ms"]
        for item in results
    ]

    expected_count = sum(
        item["expected_count"]
        for item in results
    )

    recognized_count = sum(
        item["recognized_count"]
        for item in results
    )

    matched_count = sum(
        item["matched_count"]
        for item in results
    )

    summary = {
        "total_documents": len(results),

        "expected_lines": expected_count,

        "recognized_lines": recognized_count,

        "matched_lines": matched_count,

        "recall_percent": round(
            matched_count / expected_count * 100,
            3,
        ),

        "precision_percent": round(
            matched_count
            / max(recognized_count, 1)
            * 100,
            3,
        ),

        "exact_document_matches": sum(
            item["exact_match"]
            for item in results
        ),

        "ordered_document_matches": sum(
            item["ordered_match"]
            for item in results
        ),

        "failed_documents": sum(
            not item["ordered_match"]
            for item in results
        ),

        "warm_mean_ms": round(
            statistics.mean(latencies), 3
        ),

        "warm_median_ms": round(
            statistics.median(latencies), 3
        ),

        "warm_p95_ms": round(
            float(np.percentile(latencies, 95)),
            3,
        ),

        "warm_max_ms": round(
            max(latencies), 3
        ),

        "under_1000ms": sum(
            value < 1000
            for value in latencies
        ),

        "under_200ms": sum(
            value < 200
            for value in latencies
        ),
    }

    output = (
        ROOT
        / "test_output"
        / "performance"
        / "independent_document_validation.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            {
                "seed": SEED,
                "summary": summary,
                "results": results,
            },
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nFINAL SUMMARY")

    print(
        json.dumps(summary, indent=4)
    )

    print(f"\nReport saved: {output}")

    return 0 if (
        summary["failed_documents"] == 0
        and summary["warm_mean_ms"] < 1000
    ) else 1


if __name__ == "__main__":

    sys.exit(main())
