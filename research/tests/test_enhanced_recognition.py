
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.enhanced_simulator_recognition import (
    EnhancedSimulatorCardRecognizer
)


DATASET_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/heldout_v1"
)

TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

BASELINE_FILE = (
    PROJECT_ROOT
    / "test_output/baselines/heldout_validation_v1.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output/enhanced_recognition_report.json"
)


def load_json(path):

    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def create_counters():

    return {
        "total_slots": 0,
        "occupied_slots": 0,
        "empty_slots": 0,
        "correct_ranks": 0,
        "correct_suits": 0,
        "correct_cards": 0,
        "rejected_cards": 0,
        "incorrect_accepted_cards": 0,
        "empty_slots_rejected": 0,
        "empty_slots_false_positive": 0,
        "fallback_attempts": 0,
        "fallback_recovered": 0
    }


def evaluate(expected, actual, counters):

    counters["total_slots"] += 1

    if actual.get("rank_fallback_used"):

        counters["fallback_attempts"] += 1

    if actual.get("rank_fallback_recovered"):

        counters["fallback_recovered"] += 1

    if not expected["occupied"]:

        counters["empty_slots"] += 1

        if actual.get("recognized"):

            counters[
                "empty_slots_false_positive"
            ] += 1

            return "FALSE POSITIVE"

        counters["empty_slots_rejected"] += 1

        return "PASS"

    counters["occupied_slots"] += 1

    rank_correct = (
        actual.get("rank") == expected["rank"]
    )

    suit_correct = (
        actual.get("suit") == expected["suit"]
    )

    if rank_correct:
        counters["correct_ranks"] += 1

    if suit_correct:
        counters["correct_suits"] += 1

    if not actual.get("recognized"):

        counters["rejected_cards"] += 1

        return "REJECTED"

    if rank_correct and suit_correct:

        counters["correct_cards"] += 1

        return "PASS"

    counters["incorrect_accepted_cards"] += 1

    return "WRONG"


def calculate_metrics(counters):

    result = counters.copy()

    occupied = counters["occupied_slots"]

    empty = counters["empty_slots"]

    total = counters["total_slots"]

    result["rank_accuracy"] = (
        counters["correct_ranks"] / occupied
        if occupied else None
    )

    result["suit_accuracy"] = (
        counters["correct_suits"] / occupied
        if occupied else None
    )

    result["card_accuracy"] = (
        counters["correct_cards"] / occupied
        if occupied else None
    )

    result["empty_rejection_rate"] = (
        counters["empty_slots_rejected"] / empty
        if empty else None
    )

    result["overall_slot_accuracy"] = (
        (
            counters["correct_cards"]
            + counters["empty_slots_rejected"]
        ) / total
        if total else None
    )

    result["passed"] = (
        counters["correct_cards"] == occupied
        and counters["empty_slots_rejected"] == empty
        and counters["incorrect_accepted_cards"] == 0
        and counters["empty_slots_false_positive"] == 0
    )

    return result


def main():

    print("=" * 75)
    print("ENHANCED SIMULATOR RECOGNITION VALIDATION")
    print("=" * 75)

    dataset = load_json(
        DATASET_DIR / "expected.json"
    )

    baseline = load_json(
        BASELINE_FILE
    )

    records = dataset["records"]

    if len(records) != 168:

        raise ValueError(
            f"Expected 168 images, found "
            f"{len(records)}."
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

        image = cv2.imread(
            str(image_path)
        )

        if image is None:

            raise FileNotFoundError(
                f"Cannot load {image_path}"
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

        fallback_label = (
            " | FALLBACK"
            if actual.get("rank_fallback_used")
            else ""
        )

        total_elapsed = (
            time.perf_counter() - total_start
        )

        average = total_elapsed / index

        remaining = (
            average * (len(records) - index)
        )

        print(
            f"[{index:03}/{len(records)}] "
            f"{status:14} | "
            f"{filename:28} | "
            f"{elapsed:.2f}s"
            f"{fallback_label} | "
            f"ETA: {remaining / 60:.1f}m"
        )

    summary = calculate_metrics(
        counters
    )

    summary["total_time_seconds"] = round(
        time.perf_counter() - total_start,
        4
    )

    summary["failed_images"] = len(
        failures
    )

    summary_by_variant = {
        variant: calculate_metrics(values)
        for variant, values
        in variant_counters.items()
    }

    baseline_summary = baseline["summary"]

    comparison = {
        "baseline_card_accuracy": (
            baseline_summary["card_accuracy"]
        ),
        "enhanced_card_accuracy": (
            summary["card_accuracy"]
        ),
        "accuracy_improvement_percentage_points": round(
            (
                summary["card_accuracy"]
                - baseline_summary["card_accuracy"]
            ) * 100,
            4
        ),
        "baseline_correct_cards": (
            baseline_summary["correct_cards"]
        ),
        "enhanced_correct_cards": (
            summary["correct_cards"]
        ),
        "baseline_rejected_cards": (
            baseline_summary["rejected_cards"]
        ),
        "enhanced_rejected_cards": (
            summary["rejected_cards"]
        ),
        "incorrect_accepted_cards": (
            summary["incorrect_accepted_cards"]
        )
    }

    report = {
        "summary": summary,
        "summary_by_variant": summary_by_variant,
        "baseline_comparison": comparison,
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
    print("ENHANCED RECOGNITION SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print("\nBASELINE COMPARISON")

    print(json.dumps(comparison, indent=4))

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

