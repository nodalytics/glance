
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.recognition_profiles import (
    RecognitionProfileManager
)


DATASET_ROOT = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/optimized_recognition_report.json"
)


# --------------------------------------------------
# LOAD SYNTHETIC DATASETS
# --------------------------------------------------

def load_records():

    manifest = json.loads(
        (DATASET_ROOT / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    records = []

    for entry in manifest["datasets"]:

        if entry["type"] != "synthetic":
            continue

        if not entry.get("enabled", True):
            continue

        expected = json.loads(
            (
                DATASET_ROOT
                / entry["expected_file"]
            ).read_text(encoding="utf-8")
        )

        cards_dir = (
            DATASET_ROOT
            / entry["cards_directory"]
        )

        for slot, card in expected["cards"].items():

            image = cv2.imread(
                str(cards_dir / f"{slot}.png")
            )

            if image is None:

                raise FileNotFoundError(
                    f"{entry['id']}/{slot}"
                )

            records.append({
                "dataset": entry["id"],
                "street": entry["street"],
                "slot": slot,
                "expected": card,
                "image": image
            })

    if not records:

        raise RuntimeError(
            "No synthetic records found."
        )

    return records


# --------------------------------------------------
# BENCHMARK RECOGNIZER
# --------------------------------------------------

def benchmark(recognizer, records, profile):

    print("\n" + "=" * 75)
    print(f"BENCHMARK: {profile}")
    print("=" * 75)

    counters = {
        "total_slots": len(records),
        "occupied_slots": 0,
        "empty_slots": 0,
        "correct_cards": 0,
        "rejected_cards": 0,
        "incorrect_accepted_cards": 0,
        "empty_slots_rejected": 0,
        "empty_false_positives": 0,
        "ocr_skipped_slots": 0,
        "false_empty": 0
    }

    results = []

    start_time = time.perf_counter()

    for index, record in enumerate(
        records,
        start=1
    ):

        expected = record["expected"]

        card_start = time.perf_counter()

        actual = recognizer.recognize_card(
            record["image"],
            card_name=record["slot"]
        )

        elapsed = (
            time.perf_counter() - card_start
        )

        occupied = expected.get(
            "occupied",
            True
        )

        recognized = actual["recognized"]

        skipped = actual.get(
            "ocr_skipped",
            False
        )

        counters["ocr_skipped_slots"] += int(
            skipped
        )

        if occupied:

            counters["occupied_slots"] += 1

            if skipped:

                counters["false_empty"] += 1

            correct = (
                recognized
                and actual["rank"] == expected["rank"]
                and actual["suit"] == expected["suit"]
            )

            if correct:

                counters["correct_cards"] += 1

                status = "PASS"

            elif not recognized:

                counters["rejected_cards"] += 1

                status = "REJECTED"

            else:

                counters[
                    "incorrect_accepted_cards"
                ] += 1

                status = "WRONG"

        else:

            counters["empty_slots"] += 1

            if recognized:

                counters[
                    "empty_false_positives"
                ] += 1

                status = "FALSE POSITIVE"

            else:

                counters[
                    "empty_slots_rejected"
                ] += 1

                status = "PASS"

        results.append({
            "dataset": record["dataset"],
            "street": record["street"],
            "slot": record["slot"],
            "expected": expected,
            "actual": actual,
            "status": status,
            "time_seconds": round(elapsed, 4)
        })

        print(
            f"[{index:02}/{len(records):02}] "
            f"{status:15} | "
            f"{record['street']:8} | "
            f"{record['slot']:15} | "
            f"OCR skipped: {str(skipped):5} | "
            f"{elapsed:.4f}s",
            flush=True
        )

    total_time = (
        time.perf_counter() - start_time
    )

    summary = counters.copy()

    summary["card_accuracy"] = (
        counters["correct_cards"]
        / counters["occupied_slots"]
        if counters["occupied_slots"]
        else None
    )

    summary["overall_slot_accuracy"] = (
        (
            counters["correct_cards"]
            + counters["empty_slots_rejected"]
        ) / len(records)
    )

    summary["total_time_seconds"] = round(
        total_time,
        4
    )

    summary["average_time_per_slot_seconds"] = round(
        total_time / len(records),
        4
    )

    summary["ocr_skip_rate"] = (
        counters["ocr_skipped_slots"]
        / len(records)
    )

    summary["passed"] = (
        counters["correct_cards"]
        == counters["occupied_slots"]

        and counters["empty_false_positives"] == 0

        and counters["false_empty"] == 0
    )

    return {
        "profile": profile,
        "summary": summary,
        "results": results
    }


# --------------------------------------------------
# COMPARE RECOGNITION RESULTS
# --------------------------------------------------

def compare_results(baseline, optimized):

    mismatches = []

    for old, new in zip(
        baseline["results"],
        optimized["results"]
    ):

        fields = [
            "rank",
            "suit",
            "recognized"
        ]

        differences = {}

        for field in fields:

            old_value = old["actual"].get(field)
            new_value = new["actual"].get(field)

            if old_value != new_value:

                differences[field] = {
                    "baseline": old_value,
                    "optimized": new_value
                }

        if differences:

            mismatches.append({
                "dataset": old["dataset"],
                "slot": old["slot"],
                "differences": differences
            })

    return mismatches


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("OPTIMIZED OFFLINE RECOGNITION BENCHMARK")
    print("=" * 75)

    records = load_records()

    print(f"Total slots: {len(records)}")

    manager = RecognitionProfileManager(
        project_root=PROJECT_ROOT
    )

    baseline_recognizer = (
        manager.get_recognizer("synthetic")
    )

    optimized_recognizer = (
        manager.get_recognizer(
            "synthetic_optimized"
        )
    )

    # Warm up both OCR pipelines before timing.

    warmup_image = next(
        record["image"]
        for record in records
        if record["expected"].get(
            "occupied",
            True
        )
    )

    print("\nWarming up recognition pipelines...")

    baseline_recognizer.recognize_card(
        warmup_image
    )

    optimized_recognizer.recognize_card(
        warmup_image
    )

    optimized_recognizer.reset_statistics()

    baseline = benchmark(
        baseline_recognizer,
        records,
        "simulator"
    )

    optimized = benchmark(
        optimized_recognizer,
        records,
        "simulator_optimized"
    )

    old_summary = baseline["summary"]
    new_summary = optimized["summary"]

    old_time = old_summary[
        "total_time_seconds"
    ]

    new_time = new_summary[
        "total_time_seconds"
    ]

    mismatches = compare_results(
        baseline,
        optimized
    )

    comparison = {
        "baseline_time_seconds": old_time,
        "optimized_time_seconds": new_time,

        "time_saved_seconds": round(
            old_time - new_time,
            4
        ),

        "time_reduction_percent": round(
            (old_time - new_time)
            / old_time * 100,
            4
        ),

        "speedup_factor": round(
            old_time / new_time,
            4
        ),

        "baseline_card_accuracy": (
            old_summary["card_accuracy"]
        ),

        "optimized_card_accuracy": (
            new_summary["card_accuracy"]
        ),

        "ocr_skipped_slots": (
            new_summary["ocr_skipped_slots"]
        ),

        "ocr_skip_rate": (
            new_summary["ocr_skip_rate"]
        ),

        "false_empty": (
            new_summary["false_empty"]
        ),

        "recognition_mismatches": len(
            mismatches
        )
    }

    comparison["passed"] = (
        old_summary["passed"]

        and new_summary["passed"]

        and len(mismatches) == 0

        and new_summary["ocr_skipped_slots"]
        == new_summary["empty_slots"]
    )

    report = {
        "baseline": baseline,
        "optimized": optimized,
        "comparison": comparison,
        "recognition_mismatches": mismatches,
        "recognizer_statistics": (
            optimized_recognizer.get_statistics()
        )
    }

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("BENCHMARK COMPARISON")
    print("=" * 75)

    print(
        json.dumps(
            comparison,
            indent=4
        )
    )

    print(f"\nReport saved: {REPORT_FILE}")

    if comparison["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
