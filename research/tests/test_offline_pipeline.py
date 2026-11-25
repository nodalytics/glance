
import sys
import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.pipeline.offline_pipeline import (
    OfflineProcessingPipeline
)


DATASET_ROOT = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output/offline_pipeline"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/offline_pipeline_report.json"
)


# --------------------------------------------------
# SYNTHETIC TABLE INFORMATION
# --------------------------------------------------

def create_table_data():

    return {
        "small_blind": 2500,
        "big_blind": 5000,
        "pot": 47500,
        "prize_pool_display": "$1.12",
        "first_place_prize_display": "$1.12",
        "average_stack": 83333,
        "tournament_position": "12 of 18",

        "players": [
            {
                "seat": "top",
                "name": "SimulatorPlayer1",
                "stack": 92500,
                "bounty_display": "$0.03"
            },
            {
                "seat": "upper_left",
                "name": "SimulatorPlayer2",
                "stack": 85000,
                "bounty_display": "$0.04"
            }
        ]
    }


# --------------------------------------------------
# LOAD JSON
# --------------------------------------------------

def load_json(path):

    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


# --------------------------------------------------
# VALIDATE CARD IDENTITIES
# --------------------------------------------------

def compare_cards(expected_cards, state):

    actual_cards = {}

    all_slots = (
        state["cards"]["board_slots"]
        + state["cards"]["hero_slots"]
    )

    for card in all_slots:

        actual_cards[card["slot"]] = card

    mismatches = []

    for slot, expected in expected_cards.items():

        actual = actual_cards.get(slot)

        if actual is None:

            mismatches.append({
                "slot": slot,
                "reason": "Missing output slot"
            })

            continue

        occupied = expected.get(
            "occupied",
            True
        )

        if occupied:

            correct = (
                actual["recognized"] is True

                and actual["occupied"] is True

                and actual["rank"]
                == expected["rank"]

                and actual["suit"]
                == expected["suit"]
            )

        else:

            correct = (
                actual["recognized"] is False

                and actual["occupied"] is False

                and actual["rank"] is None

                and actual["suit"] is None
            )

        if not correct:

            mismatches.append({
                "slot": slot,
                "expected": expected,
                "actual": actual
            })

    return mismatches


# --------------------------------------------------
# VALIDATE DATASET
# --------------------------------------------------

def validate_dataset(pipeline, entry):

    dataset_id = entry["id"]

    print("\n" + "=" * 75)

    print(f"DATASET: {dataset_id}")

    print("=" * 75)

    expected = load_json(
        DATASET_ROOT / entry["expected_file"]
    )

    cards_directory = (
        DATASET_ROOT
        / entry["cards_directory"]
    )

    table_data = create_table_data()

    state = pipeline.process_directory(
        table_data=table_data,
        cards_directory=cards_directory,
        dataset_type=entry["type"]
    )

    mismatches = compare_cards(
        expected["cards"],
        state
    )

    expected_empty_slots = sum(
        not card.get("occupied", True)
        for card in expected["cards"].values()
    )

    statistics = state["metadata"][
        "recognition_statistics"
    ]

    expected_skips = (
        expected_empty_slots
        if entry["type"] == "synthetic"
        else 0
    )

    checks = {

        "state_valid": (
            state["status"] == "valid"
        ),

        "validation_passed": (
            state["validation"]["valid"] is True
        ),

        "street_correct": (
            state["game"]["street"]
            == entry["street"]
        ),

        "card_identities_correct": (
            len(mismatches) == 0
        ),

        "duplicate_count_zero": (
            state["validation"][
                "card_validation"
            ]["duplicate_count"] == 0
        ),

        "seven_slots_preserved": (
            len(state["cards"]["board_slots"])
            + len(state["cards"]["hero_slots"])
            == 7
        ),

        "ocr_skips_correct": (
            statistics["ocr_skipped_slots"]
            == expected_skips
        ),

        "profile_correct": (
            state["metadata"]["recognition_profile"]
            == (
                "calibration"
                if entry["type"] == "calibration"
                else "simulator_optimized"
            )
        ),

        "json_serializable": (
            isinstance(
                json.dumps(
                    state,
                    allow_nan=False
                ),
                str
            )
        )
    }

    passed = all(checks.values())

    output_file = (
        OUTPUT_DIR / f"{dataset_id}.json"
    )

    output_file.write_text(
        json.dumps(
            state,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print(f"Street: {state['game']['street']}")

    print(f"State: {state['status']}")

    print(
        f"Profile: "
        f"{state['metadata']['recognition_profile']}"
    )

    print(
        f"Recognized cards: "
        f"{state['game']['recognized_card_count']}"
    )

    print(
        f"OCR skipped: "
        f"{statistics['ocr_skipped_slots']}"
    )

    print(
        f"Card mismatches: {len(mismatches)}"
    )

    print(
        f"Processing time: "
        f"{state['metadata']['processing_time_seconds']:.3f}s"
    )

    for name, result in checks.items():

        status = "PASS" if result else "FAIL"

        print(f"  {status} | {name}")

    print(f"Output saved: {output_file}")

    return {
        "dataset_id": dataset_id,
        "dataset_type": entry["type"],
        "street": entry["street"],
        "checks": checks,
        "mismatches": mismatches,
        "statistics": statistics,
        "processing_time_seconds": (
            state["metadata"]["processing_time_seconds"]
        ),
        "passed": passed
    }


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)

    print("END-TO-END OFFLINE PIPELINE VALIDATION")

    print("=" * 75)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    manifest = load_json(
        DATASET_ROOT / "manifest.json"
    )

    entries = [
        entry
        for entry in manifest["datasets"]
        if entry.get("enabled", True)
    ]

    if not entries:

        raise RuntimeError(
            "No enabled datasets found."
        )

    pipeline = OfflineProcessingPipeline(
        project_root=PROJECT_ROOT
    )

    results = []

    start_time = time.perf_counter()

    for entry in entries:

        result = validate_dataset(
            pipeline,
            entry
        )

        results.append(result)

    elapsed = (
        time.perf_counter() - start_time
    )

    passed_count = sum(
        result["passed"]
        for result in results
    )

    summary = {
        "total_datasets": len(results),

        "passed_datasets": passed_count,

        "failed_datasets": (
            len(results) - passed_count
        ),

        "total_slots": sum(
            result["statistics"]["total_slots"]
            for result in results
        ),

        "total_recognized_cards": sum(
            result["statistics"]["recognized_cards"]
            for result in results
        ),

        "total_ocr_skipped": sum(
            result["statistics"]["ocr_skipped_slots"]
            for result in results
        ),

        "total_card_mismatches": sum(
            len(result["mismatches"])
            for result in results
        ),

        "total_time_seconds": round(
            elapsed,
            4
        ),

        "loaded_profiles": (
            pipeline.profile_manager.loaded_profiles
        ),

        "passed": (
            passed_count == len(results)
        )
    }

    report = {
        "summary": summary,
        "datasets": results
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)

    print("PIPELINE VALIDATION SUMMARY")

    print("=" * 75)

    print(
        json.dumps(
            summary,
            indent=4
        )
    )

    print(f"\nReport saved: {REPORT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
