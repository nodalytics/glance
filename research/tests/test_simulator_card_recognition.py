
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.simulator_card_recognition import (
    SimulatorCardRecognizer
)


DATASET_ROOT = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
)

TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/simulator_validation_report.json"
)


def main():

    print("=" * 75)
    print("OFFLINE SIMULATOR CARD RECOGNITION TEST")
    print("=" * 75)

    manifest = json.loads(
        (DATASET_ROOT / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    datasets = [
        entry
        for entry in manifest["datasets"]
        if entry["type"] == "synthetic"
        and entry.get("enabled", True)
    ]

    if not datasets:
        raise RuntimeError(
            "No enabled synthetic datasets found."
        )

    recognizer = SimulatorCardRecognizer(
        suit_template_dir=TEMPLATE_DIR
    )

    print(
        f"\nSuit categories: "
        f"{len(recognizer.suit_templates)}"
    )

    print(
        f"Total templates: "
        f"{recognizer.template_count}"
    )

    for suit, templates in (
        recognizer.suit_templates.items()
    ):

        print(
            f"  {suit:10}: "
            f"{len(templates)} templates"
        )

    counters = {
        "occupied_cards": 0,
        "correct_ranks": 0,
        "correct_suits": 0,
        "correct_cards": 0,
        "rejected_cards": 0,
        "incorrect_accepted_cards": 0,
        "empty_slots": 0,
        "empty_slots_rejected": 0,
        "empty_false_positives": 0
    }

    results = []

    start_time = time.perf_counter()

    for dataset in datasets:

        dataset_id = dataset["id"]

        cards_dir = (
            DATASET_ROOT
            / dataset["cards_directory"]
        )

        expected_data = json.loads(
            (
                DATASET_ROOT
                / dataset["expected_file"]
            ).read_text(encoding="utf-8")
        )

        print("\n" + "=" * 75)
        print(f"DATASET: {dataset_id}")
        print("=" * 75)

        for slot, expected in (
            expected_data["cards"].items()
        ):

            image = cv2.imread(
                str(cards_dir / f"{slot}.png")
            )

            if image is None:
                raise FileNotFoundError(
                    f"Cannot load {dataset_id}/{slot}"
                )

            actual = recognizer.recognize_card(
                image,
                card_name=slot
            )

            occupied = expected.get(
                "occupied",
                True
            )

            recognized = actual["recognized"]

            if occupied:

                counters["occupied_cards"] += 1

                rank_correct = (
                    actual["rank"]
                    == expected["rank"]
                )

                suit_correct = (
                    actual["suit"]
                    == expected["suit"]
                )

                counters["correct_ranks"] += int(
                    rank_correct
                )

                counters["correct_suits"] += int(
                    suit_correct
                )

                if (
                    rank_correct
                    and suit_correct
                    and recognized
                ):

                    status = "PASS"

                    counters["correct_cards"] += 1

                elif not recognized:

                    status = "REJECTED"

                    counters["rejected_cards"] += 1

                else:

                    status = "WRONG"

                    counters[
                        "incorrect_accepted_cards"
                    ] += 1

            else:

                counters["empty_slots"] += 1

                if recognized:

                    status = "FALSE POSITIVE"

                    counters[
                        "empty_false_positives"
                    ] += 1

                else:

                    status = "PASS"

                    counters[
                        "empty_slots_rejected"
                    ] += 1

            expected_display = (
                f"{expected['rank']} "
                f"{expected['suit']}"
                if occupied
                else "EMPTY"
            )

            actual_display = (
                f"{actual['rank']} "
                f"{actual['suit']}"
            )

            print(
                f"{status:15} | "
                f"{slot:15} | "
                f"Expected: {expected_display:12} | "
                f"Actual: {actual_display:12} | "
                f"Score: "
                f"{actual['suit_confidence']:.3f}"
            )

            results.append({
                "dataset": dataset_id,
                "slot": slot,
                "expected": expected,
                "actual": actual,
                "status": status
            })

    elapsed = (
        time.perf_counter() - start_time
    )

    occupied = counters["occupied_cards"]

    summary = counters.copy()

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

    summary["recognition_time_seconds"] = round(
        elapsed,
        3
    )

    summary["passed"] = (
        occupied > 0
        and counters["correct_cards"] == occupied
        and counters["empty_false_positives"] == 0
    )

    report = {
        "profile": "offline_simulator",
        "template_count": recognizer.template_count,
        "summary": summary,
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

    print("\n" + "=" * 75)
    print("SIMULATOR VALIDATION SUMMARY")
    print("=" * 75)

    print(
        json.dumps(summary, indent=4)
    )

    print(f"\nReport saved: {REPORT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
