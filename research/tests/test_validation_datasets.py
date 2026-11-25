
import sys
import json
import time
from pathlib import Path

import cv2


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.card_recognition import CardRecognizer


DATASET_ROOT = (
    PROJECT_ROOT / "test_assets/validation/datasets"
)

MANIFEST_FILE = DATASET_ROOT / "manifest.json"

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/multi_dataset_validation_report.json"
)


# --------------------------------------------------
# JSON LOADING
# --------------------------------------------------

def load_json(path):

    if not path.is_file():
        raise FileNotFoundError(
            f"JSON file not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# --------------------------------------------------
# FORMAT CARD
# --------------------------------------------------

def format_card(rank, suit):

    symbols = {
        "hearts": "H",
        "diamonds": "D",
        "clubs": "C",
        "spades": "S"
    }

    return (
        f"{rank or '?'}"
        f"{symbols.get(suit, '?')}"
    )


# --------------------------------------------------
# INITIALIZE COUNTERS
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
# CALCULATE METRICS
# --------------------------------------------------

def calculate_metrics(counters):

    summary = counters.copy()

    occupied = counters["occupied_slots"]
    empty = counters["empty_slots"]
    total = counters["total_slots"]

    summary["rank_accuracy"] = (
        counters["correct_ranks"] / occupied
        if occupied else None
    )

    summary["suit_accuracy"] = (
        counters["correct_suits"] / occupied
        if occupied else None
    )

    summary["card_accuracy"] = (
        counters["correct_cards"] / occupied
        if occupied else None
    )

    summary["empty_rejection_rate"] = (
        counters["empty_slots_rejected"] / empty
        if empty else None
    )

    summary["overall_slot_accuracy"] = (
        (
            counters["correct_cards"]
            + counters["empty_slots_rejected"]
        ) / total
        if total else None
    )

    summary["passed"] = (
        total > 0
        and counters["correct_cards"] == occupied
        and counters["empty_slots_rejected"] == empty
    )

    return summary


# --------------------------------------------------
# VALIDATE INDIVIDUAL SLOT
# --------------------------------------------------

def validate_slot(
    slot_name,
    expected,
    actual,
    counters
):

    counters["total_slots"] += 1

    occupied = expected.get(
        "occupied",
        True
    )

    recognized = bool(
        actual.get("recognized", False)
    )

    actual_rank = actual.get("rank")
    actual_suit = actual.get("suit")

    # ----------------------------------------------
    # OCCUPIED CARD
    # ----------------------------------------------

    if occupied:

        counters["occupied_slots"] += 1

        rank_correct = (
            actual_rank == expected["rank"]
        )

        suit_correct = (
            actual_suit == expected["suit"]
        )

        card_correct = (
            rank_correct
            and suit_correct
            and recognized
        )

        if rank_correct:
            counters["correct_ranks"] += 1

        if suit_correct:
            counters["correct_suits"] += 1

        if card_correct:

            counters["correct_cards"] += 1

            status = "PASS"

        elif not recognized:

            counters["rejected_cards"] += 1

            status = "REJECTED"

        else:

            counters["incorrect_accepted_cards"] += 1

            status = "WRONG"

        expected_display = format_card(
            expected["rank"],
            expected["suit"]
        )

        actual_display = format_card(
            actual_rank,
            actual_suit
        )

        passed = card_correct

    # ----------------------------------------------
    # EMPTY SLOT
    # ----------------------------------------------

    else:

        counters["empty_slots"] += 1

        rank_correct = None
        suit_correct = None

        expected_display = "EMPTY"

        if not recognized:

            counters["empty_slots_rejected"] += 1

            status = "PASS"

            actual_display = "NOT RECOGNIZED"

            passed = True

        else:

            counters[
                "empty_slots_false_positive"
            ] += 1

            status = "FALSE POSITIVE"

            actual_display = format_card(
                actual_rank,
                actual_suit
            )

            passed = False

    print(
        f"{status:15} | "
        f"{slot_name:15} | "
        f"Expected: {expected_display:6} | "
        f"Actual: {actual_display}"
    )

    return {
        "slot_name": slot_name,
        "expected": expected,
        "actual": actual,
        "rank_correct": rank_correct,
        "suit_correct": suit_correct,
        "passed": passed,
        "status": status
    }


# --------------------------------------------------
# VALIDATE DATASET
# --------------------------------------------------

def validate_dataset(entry, recognizer):

    dataset_id = entry["id"]

    cards_dir = (
        DATASET_ROOT
        / entry["cards_directory"]
    )

    expected_file = (
        DATASET_ROOT
        / entry["expected_file"]
    )

    expected_data = load_json(
        expected_file
    )

    expected_cards = expected_data["cards"]

    if not expected_cards:
        raise ValueError(
            f"Dataset is empty: {dataset_id}"
        )

    counters = create_counters()

    details = []

    print("\n" + "=" * 75)
    print(f"DATASET: {dataset_id}")
    print(f"TYPE: {entry['type']}")
    print(f"STREET: {entry['street']}")
    print("=" * 75)

    start_time = time.perf_counter()

    for slot_name, expected in expected_cards.items():

        image_path = (
            cards_dir / f"{slot_name}.png"
        )

        image = cv2.imread(
            str(image_path)
        )

        if image is None:

            raise FileNotFoundError(
                f"Cannot load image: {image_path}"
            )

        actual = recognizer.recognize_card(
            image,
            card_name=slot_name
        )

        result = validate_slot(
            slot_name,
            expected,
            actual,
            counters
        )

        details.append(result)

    elapsed_time = (
        time.perf_counter() - start_time
    )

    summary = calculate_metrics(
        counters
    )

    summary["recognition_time_seconds"] = (
        round(elapsed_time, 3)
    )

    print("\nDataset summary:")

    print(
        f"Correct cards: "
        f"{summary['correct_cards']}/"
        f"{summary['occupied_slots']}"
    )

    print(
        f"Rejected occupied cards: "
        f"{summary['rejected_cards']}"
    )

    print(
        f"Incorrect accepted cards: "
        f"{summary['incorrect_accepted_cards']}"
    )

    print(
        f"Empty slots rejected: "
        f"{summary['empty_slots_rejected']}/"
        f"{summary['empty_slots']}"
    )

    print(
        f"Empty false positives: "
        f"{summary['empty_slots_false_positive']}"
    )

    print(
        f"Recognition time: "
        f"{elapsed_time:.3f} seconds"
    )

    print(
        "Dataset result: "
        + ("PASS" if summary["passed"] else "FAIL")
    )

    return {
        "dataset_id": dataset_id,
        "type": entry["type"],
        "street": entry["street"],
        "summary": summary,
        "slots": details
    }


# --------------------------------------------------
# PRINT PERCENTAGE
# --------------------------------------------------

def print_percentage(label, value):

    if value is None:
        print(f"{label}: N/A")

    else:
        print(f"{label}: {value:.2%}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("MULTI-DATASET OFFLINE VALIDATION")
    print("=" * 75)

    manifest = load_json(
        MANIFEST_FILE
    )

    datasets = [
        entry
        for entry in manifest["datasets"]
        if entry.get("enabled", True)
    ]

    if not datasets:
        raise RuntimeError(
            "No enabled datasets found."
        )

    print(
        f"\nEnabled datasets: {len(datasets)}"
    )

    print("\nInitializing recognizer...")

    recognizer = CardRecognizer(
        suit_template_dir=(
            PROJECT_ROOT
            / "test_assets/card_templates/suits"
        )
    )

    print(
        f"Suit templates loaded: "
        f"{len(recognizer.suit_templates)}"
    )

    if len(recognizer.suit_templates) != 4:

        raise RuntimeError(
            "All four suit templates are required."
        )

    overall_counters = create_counters()

    counters_by_type = {}

    dataset_reports = []

    passed_datasets = 0

    start_time = time.perf_counter()

    # ----------------------------------------------
    # PROCESS ALL DATASETS
    # ----------------------------------------------

    for entry in datasets:

        result = validate_dataset(
            entry,
            recognizer
        )

        dataset_reports.append(result)

        summary = result["summary"]

        dataset_type = result["type"]

        if dataset_type not in counters_by_type:

            counters_by_type[dataset_type] = (
                create_counters()
            )

        for key in overall_counters:

            overall_counters[key] += summary[key]

            counters_by_type[dataset_type][key] += (
                summary[key]
            )

        if summary["passed"]:
            passed_datasets += 1

    elapsed_time = (
        time.perf_counter() - start_time
    )

    # ----------------------------------------------
    # OVERALL SUMMARY
    # ----------------------------------------------

    overall_summary = calculate_metrics(
        overall_counters
    )

    overall_summary["total_datasets"] = (
        len(datasets)
    )

    overall_summary["passed_datasets"] = (
        passed_datasets
    )

    overall_summary["failed_datasets"] = (
        len(datasets) - passed_datasets
    )

    overall_summary["total_time_seconds"] = (
        round(elapsed_time, 3)
    )

    summaries_by_type = {
        dataset_type: calculate_metrics(counters)
        for dataset_type, counters
        in counters_by_type.items()
    }

    final_report = {
        "summary": overall_summary,
        "summary_by_type": summaries_by_type,
        "datasets": dataset_reports
    }

    # ----------------------------------------------
    # SAVE REPORT
    # ----------------------------------------------

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            final_report,
            file,
            indent=4
        )

    # ----------------------------------------------
    # PRINT FINAL RESULTS
    # ----------------------------------------------

    print("\n" + "=" * 75)
    print("OVERALL VALIDATION SUMMARY")
    print("=" * 75)

    for key, value in overall_counters.items():

        label = key.replace("_", " ").title()

        print(f"{label}: {value}")

    print_percentage(
        "Rank accuracy",
        overall_summary["rank_accuracy"]
    )

    print_percentage(
        "Suit accuracy",
        overall_summary["suit_accuracy"]
    )

    print_percentage(
        "Complete card accuracy",
        overall_summary["card_accuracy"]
    )

    print_percentage(
        "Empty rejection rate",
        overall_summary["empty_rejection_rate"]
    )

    print_percentage(
        "Overall slot accuracy",
        overall_summary["overall_slot_accuracy"]
    )

    print("\nRESULTS BY DATASET TYPE")

    for dataset_type, summary in summaries_by_type.items():

        print(f"\nType: {dataset_type}")

        print(
            f"Correct cards: "
            f"{summary['correct_cards']}/"
            f"{summary['occupied_slots']}"
        )

        print_percentage(
            "Card accuracy",
            summary["card_accuracy"]
        )

    print(
        f"\nPassed datasets: "
        f"{passed_datasets}/{len(datasets)}"
    )

    print(
        f"Total recognition time: "
        f"{elapsed_time:.3f} seconds"
    )

    print(f"\nReport saved: {REPORT_FILE}")

    if overall_summary["passed"]:

        print("\nFINAL RESULT: ALL DATASETS PASSED")

        return 0

    print(
        "\nFINAL RESULT: "
        "VALIDATION COMPLETED WITH FAILURES"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
