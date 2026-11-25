
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from test_enhanced_recognition import (
    create_counters,
    evaluate,
    calculate_metrics
)

from poker_apis.vision.enhanced_simulator_recognition import (
    EnhancedSimulatorCardRecognizer
)


DATASET_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/independent_v1"
)

TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output/independent_recognition_report.json"
)


def main():

    print("=" * 75)
    print("INDEPENDENT OFFLINE RECOGNITION VALIDATION")
    print("=" * 75)

    dataset = json.loads(
        (DATASET_DIR / "expected.json").read_text(
            encoding="utf-8-sig"
        )
    )

    records = dataset["records"]

    if len(records) != 116:

        raise ValueError(
            f"Expected 116 images, "
            f"found {len(records)}."
        )

    filenames = [
        record["file"]
        for record in records
    ]

    if len(set(filenames)) != len(filenames):

        raise ValueError(
            "Duplicate filenames in dataset."
        )

    recognizer = EnhancedSimulatorCardRecognizer(
        suit_template_dir=TEMPLATE_DIR
    )

    counters = create_counters()

    variant_counters = {}

    results = []

    failures = []

    total_start = time.perf_counter()

    for index, expected in enumerate(records, 1):

        filename = expected["file"]

        variant = expected["variant"]

        image_path = (
            DATASET_DIR / "cards" / filename
        )

        image = cv2.imread(str(image_path))

        if image is None:

            raise FileNotFoundError(
                f"Cannot load: {image_path}"
            )

        start = time.perf_counter()

        actual = recognizer.recognize_card(
            image
        )

        elapsed = time.perf_counter() - start

        status = evaluate(
            expected,
            actual,
            counters
        )

        if variant not in variant_counters:

            variant_counters[variant] = (
                create_counters()
            )

        evaluate(
            expected,
            actual,
            variant_counters[variant]
        )

        result = {
            "file": filename,
            "variant": variant,
            "expected": expected,
            "actual": actual,
            "status": status,
            "recognition_time_seconds": round(
                elapsed, 4
            )
        }

        results.append(result)

        if status != "PASS":

            failures.append(result)

        total_elapsed = (
            time.perf_counter() - total_start
        )

        average = total_elapsed / index

        remaining = (
            average * (len(records) - index)
        )

        fallback_label = (
            " | FALLBACK"
            if actual.get("rank_fallback_used")
            else ""
        )

        print(
            f"[{index:03}/{len(records)}] "
            f"{status:14} | "
            f"{filename:38} | "
            f"{elapsed:.2f}s"
            f"{fallback_label} | "
            f"ETA: {remaining / 60:.1f}m"
        )

    summary = calculate_metrics(counters)

    summary["total_time_seconds"] = round(
        time.perf_counter() - total_start,
        4
    )

    summary["failed_images"] = len(failures)

    summary_by_variant = {
        variant: calculate_metrics(values)
        for variant, values
        in variant_counters.items()
    }

    report = {
        "dataset_id": dataset["dataset_id"],
        "summary": summary,
        "summary_by_variant": summary_by_variant,
        "fallback_statistics": (
            recognizer.get_fallback_statistics()
        ),
        "failures": failures,
        "results": results
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("INDEPENDENT VALIDATION SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print("\nRESULTS BY VARIANT")

    print(
        json.dumps(
            summary_by_variant,
            indent=4
        )
    )

    print("\nFALLBACK STATISTICS")

    print(
        json.dumps(
            report["fallback_statistics"],
            indent=4
        )
    )

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
