
import sys
import json
import time
from pathlib import Path

import cv2


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.recognition_profiles import (
    RecognitionProfileManager
)


DATASET_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/heldout_v1"
)

CARDS_DIR = DATASET_DIR / "cards"

EXPECTED_FILE = DATASET_DIR / "expected.json"

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/heldout_validation_report.json"
)


# --------------------------------------------------
# COUNTERS
# --------------------------------------------------

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
        "empty_slots_false_positive": 0
    }


# --------------------------------------------------
# METRICS
# --------------------------------------------------

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
        total > 0
        and counters["correct_cards"] == occupied
        and counters["empty_slots_rejected"] == empty
    )

    return result


# --------------------------------------------------
# EVALUATE INDIVIDUAL CARD
# --------------------------------------------------

def evaluate_card(expected, actual, counters):

    counters["total_slots"] += 1

    occupied = expected["occupied"]

    recognized = bool(
        actual.get("recognized", False)
    )

    if not occupied:

        counters["empty_slots"] += 1

        if recognized:

            counters[
                "empty_slots_false_positive"
            ] += 1

            return "FALSE POSITIVE"

        counters["empty_slots_rejected"] += 1

        return "PASS"

    counters["occupied_slots"] += 1

    rank_correct = (
        actual["rank"] == expected["rank"]
    )

    suit_correct = (
        actual["suit"] == expected["suit"]
    )

    counters["correct_ranks"] += int(
        rank_correct
    )

    counters["correct_suits"] += int(
        suit_correct
    )

    if (
        recognized
        and rank_correct
        and suit_correct
    ):

        counters["correct_cards"] += 1

        return "PASS"

    if not recognized:

        counters["rejected_cards"] += 1

        return "REJECTED"

    counters["incorrect_accepted_cards"] += 1

    return "WRONG"


# --------------------------------------------------
# DISPLAY CARD
# --------------------------------------------------

def format_card(card):

    rank = card.get("rank")
    suit = card.get("suit")

    suit_symbols = {
        "hearts": "H",
        "diamonds": "D",
        "clubs": "C",
        "spades": "S"
    }

    if rank is None and suit is None:
        return "NOT RECOGNIZED"

    return (
        f"{rank or '?'}"
        f"{suit_symbols.get(suit, '?')}"
    )


# --------------------------------------------------
# GROUP METRICS
# --------------------------------------------------

def update_group(groups, key, expected, actual):

    if key not in groups:

        groups[key] = create_counters()

    evaluate_card(
        expected,
        actual,
        groups[key]
    )


def summarize_groups(groups):

    return {
        key: calculate_metrics(counters)
        for key, counters in groups.items()
    }


# --------------------------------------------------
# PRINT GROUP RESULTS
# --------------------------------------------------

def print_group_results(title, groups):

    print("\n" + "=" * 75)
    print(title)
    print("=" * 75)

    for name, summary in groups.items():

        accuracy = summary[
            "overall_slot_accuracy"
        ]

        accuracy_display = (
            f"{accuracy:.2%}"
            if accuracy is not None
            else "N/A"
        )

        print(
            f"{name:15} | "
            f"Cards: "
            f"{summary['correct_cards']:3}/"
            f"{summary['occupied_slots']:3} | "
            f"Rejected: "
            f"{summary['rejected_cards']:3} | "
            f"Wrong: "
            f"{summary['incorrect_accepted_cards']:3} | "
            f"Accuracy: {accuracy_display}"
        )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("HELD-OUT OFFLINE CARD VALIDATION")
    print("=" * 75)

    if not EXPECTED_FILE.is_file():

        raise FileNotFoundError(
            f"Dataset missing: {EXPECTED_FILE}"
        )

    expected_data = json.loads(
        EXPECTED_FILE.read_text(
            encoding="utf-8"
        )
    )

    records = expected_data["records"]

    total_images = len(records)

    if total_images != expected_data["total_images"]:

        raise ValueError(
            "Dataset image count mismatch."
        )

    if total_images == 0:

        raise ValueError(
            "Dataset is empty."
        )

    filenames = [
        record["file"]
        for record in records
    ]

    if len(filenames) != len(set(filenames)):

        raise ValueError(
            "Duplicate filenames in dataset."
        )

    for filename in filenames:

        if not (CARDS_DIR / filename).is_file():

            raise FileNotFoundError(
                f"Missing image: {filename}"
            )

    manager = RecognitionProfileManager(
        project_root=PROJECT_ROOT
    )

    recognizer = manager.get_recognizer(
        "synthetic"
    )

    profile_info = manager.get_profile_info(
        "synthetic"
    )

    print(
        f"\nDataset: "
        f"{expected_data['dataset_id']}"
    )

    print(
        f"Total images: {total_images}"
    )

    print(
        f"Recognizer: "
        f"{profile_info['recognizer']}"
    )

    print(
        f"Templates: "
        f"{profile_info['template_count']}"
    )

    overall_counters = create_counters()

    counters_by_variant = {}
    counters_by_rank = {}
    counters_by_suit = {}

    results = []
    failures = []

    start_time = time.perf_counter()

    # ----------------------------------------------
    # PROCESS ALL IMAGES
    # ----------------------------------------------

    for index, expected in enumerate(
        records,
        start=1
    ):

        filename = expected["file"]

        image = cv2.imread(
            str(CARDS_DIR / filename)
        )

        if image is None:

            raise IOError(
                f"Cannot read image: {filename}"
            )

        card_start = time.perf_counter()

        actual = recognizer.recognize_card(
            image
        )

        card_elapsed = (
            time.perf_counter() - card_start
        )

        status = evaluate_card(
            expected,
            actual,
            overall_counters
        )

        update_group(
            counters_by_variant,
            expected["variant"],
            expected,
            actual
        )

        if expected["occupied"]:

            update_group(
                counters_by_rank,
                expected["rank"],
                expected,
                actual
            )

            update_group(
                counters_by_suit,
                expected["suit"],
                expected,
                actual
            )

        result = {
            "file": filename,
            "variant": expected["variant"],
            "expected": expected,
            "actual": actual,
            "status": status,
            "recognition_time_seconds": round(
                card_elapsed,
                4
            )
        }

        results.append(result)

        if status != "PASS":

            failures.append(result)

        expected_display = (
            format_card(expected)
            if expected["occupied"]
            else "EMPTY"
        )

        actual_display = format_card(
            actual
        )

        elapsed = (
            time.perf_counter() - start_time
        )

        average = elapsed / index

        remaining = (
            total_images - index
        ) * average

        print(
            f"[{index:03}/{total_images:03}] "
            f"{status:15} | "
            f"{filename:32} | "
            f"Expected: {expected_display:5} | "
            f"Actual: {actual_display:15} | "
            f"ETA: {remaining / 60:.1f} min",
            flush=True
        )

    # ----------------------------------------------
    # FINAL METRICS
    # ----------------------------------------------

    elapsed = (
        time.perf_counter() - start_time
    )

    summary = calculate_metrics(
        overall_counters
    )

    summary["total_time_seconds"] = round(
        elapsed,
        3
    )

    summary["average_time_per_image_seconds"] = round(
        elapsed / total_images,
        4
    )

    summary["failed_images"] = len(
        failures
    )

    summary_by_variant = summarize_groups(
        counters_by_variant
    )

    summary_by_rank = summarize_groups(
        counters_by_rank
    )

    summary_by_suit = summarize_groups(
        counters_by_suit
    )

    # ----------------------------------------------
    # SAVE REPORT
    # ----------------------------------------------

    report = {
        "dataset_id": expected_data["dataset_id"],
        "recognition_profile": profile_info,
        "summary": summary,
        "summary_by_variant": summary_by_variant,
        "summary_by_rank": summary_by_rank,
        "summary_by_suit": summary_by_suit,
        "failures": failures,
        "results": results
    }

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8"
    )

    # ----------------------------------------------
    # PRINT SUMMARY
    # ----------------------------------------------

    print("\n" + "=" * 75)
    print("HELD-OUT VALIDATION SUMMARY")
    print("=" * 75)

    print(
        json.dumps(
            summary,
            indent=4
        )
    )

    print_group_results(
        "RESULTS BY IMAGE VARIANT",
        summary_by_variant
    )

    print_group_results(
        "RESULTS BY RANK",
        summary_by_rank
    )

    print_group_results(
        "RESULTS BY SUIT",
        summary_by_suit
    )

    print("\n" + "=" * 75)
    print("FAILED IMAGES")
    print("=" * 75)

    if not failures:

        print("No failed images.")

    else:

        for failure in failures:

            print(
                f"{failure['status']:15} | "
                f"{failure['file']}"
            )

    print(
        f"\nReport saved: {REPORT_FILE}"
    )

    print(
        f"Total time: "
        f"{elapsed / 60:.2f} minutes"
    )

    if summary["passed"]:

        print(
            "\nFINAL RESULT: "
            "ALL HELD-OUT TESTS PASSED"
        )

        return 0

    print(
        "\nFINAL RESULT: "
        "VALIDATION COMPLETED WITH FAILURES"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
