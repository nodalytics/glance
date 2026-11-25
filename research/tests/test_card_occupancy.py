
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.card_occupancy import (
    CardOccupancyDetector
)


DATASET_ROOT = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
)

HELDOUT_ROOT = (
    PROJECT_ROOT
    / "test_assets/validation/heldout_v1"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/occupancy_validation_report.json"
)


# --------------------------------------------------
# LOAD DATASETS
# --------------------------------------------------

def load_test_records():

    records = []

    manifest = json.loads(
        (DATASET_ROOT / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

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

            records.append({
                "dataset": entry["id"],
                "file": str(
                    cards_dir / f"{slot}.png"
                ),
                "occupied": card.get(
                    "occupied",
                    True
                )
            })

    heldout_file = (
        HELDOUT_ROOT / "expected.json"
    )

    if heldout_file.exists():

        heldout = json.loads(
            heldout_file.read_text(
                encoding="utf-8"
            )
        )

        for record in heldout["records"]:

            records.append({
                "dataset": "heldout_v1",
                "file": str(
                    HELDOUT_ROOT
                    / "cards"
                    / record["file"]
                ),
                "occupied": record["occupied"]
            })

    else:

        print(
            "WARNING: Held-out dataset unavailable."
        )

    return records


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("CARD OCCUPANCY VALIDATION")
    print("=" * 75)

    detector = CardOccupancyDetector()

    records = load_test_records()

    if not records:

        raise RuntimeError(
            "No test records found."
        )

    counters = {
        "total_slots": 0,
        "occupied_slots": 0,
        "empty_slots": 0,
        "correct_occupied": 0,
        "correct_empty": 0,
        "false_empty": 0,
        "false_occupied": 0,
        "unknown_slots": 0,
        "ocr_skipped_slots": 0
    }

    results = []
    failures = []

    start_time = time.perf_counter()

    for index, record in enumerate(
        records,
        start=1
    ):

        image = cv2.imread(
            record["file"]
        )

        if image is None:

            raise FileNotFoundError(
                record["file"]
            )

        actual = detector.detect(image)

        expected = record["occupied"]

        state = actual["state"]

        counters["total_slots"] += 1

        if expected:

            counters["occupied_slots"] += 1

        else:

            counters["empty_slots"] += 1

        if actual["skip_ocr"]:

            counters["ocr_skipped_slots"] += 1

        if state == "unknown":

            counters["unknown_slots"] += 1

            status = "UNKNOWN"

        elif expected and state == "occupied":

            counters["correct_occupied"] += 1

            status = "PASS"

        elif not expected and state == "empty":

            counters["correct_empty"] += 1

            status = "PASS"

        elif expected and state == "empty":

            counters["false_empty"] += 1

            status = "FALSE EMPTY"

        else:

            counters["false_occupied"] += 1

            status = "FALSE OCCUPIED"

        result = {
            "dataset": record["dataset"],
            "file": record["file"],
            "expected_occupied": expected,
            "actual": actual,
            "status": status
        }

        results.append(result)

        if status != "PASS":

            failures.append(result)

        print(
            f"[{index:03}/{len(records):03}] "
            f"{status:15} | "
            f"{Path(record['file']).name:35} | "
            f"State: {state}"
        )

    elapsed = (
        time.perf_counter() - start_time
    )

    total = counters["total_slots"]

    summary = counters.copy()

    summary["occupancy_accuracy"] = (
        (
            counters["correct_occupied"]
            + counters["correct_empty"]
        ) / total
    )

    summary["ocr_skip_rate"] = (
        counters["ocr_skipped_slots"] / total
    )

    summary["total_time_seconds"] = round(
        elapsed,
        4
    )

    summary["average_time_per_slot_ms"] = round(
        elapsed / total * 1000,
        4
    )

    summary["safe_to_skip"] = (
        counters["false_empty"] == 0
    )

    summary["passed"] = (
        len(failures) == 0
    )

    report = {
        "summary": summary,
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

    print("\n" + "=" * 75)
    print("OCCUPANCY VALIDATION SUMMARY")
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
