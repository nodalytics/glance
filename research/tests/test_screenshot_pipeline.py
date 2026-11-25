
import sys
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.pipeline.screenshot_pipeline import (
    ScreenshotPipeline
)


IMAGE_PATH = (
    PROJECT_ROOT / "test_images/ss.jpeg"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output/screenshot_table_state.json"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/screenshot_pipeline_report.json"
)

DEBUG_DIR = (
    PROJECT_ROOT
    / "test_output/screenshot_pipeline_crops"
)


EXPECTED_TABLE = {
    "small_blind": 2500,
    "big_blind": 5000,
    "pot": 47500,
    "average_stack": 83333,
    "tournament_position": "12 of 18"
}


EXPECTED_CARDS = {
    "board_1": ("A", "hearts"),
    "board_2": ("8", "spades"),
    "board_3": ("J", "hearts"),
    "board_4": ("J", "diamonds"),
    "board_5": ("2", "hearts"),
    "hero_card_1": ("Q", "clubs"),
    "hero_card_2": ("10", "clubs")
}


def main():

    print("=" * 75)
    print("COMPLETE OFFLINE SCREENSHOT VALIDATION")
    print("=" * 75)

    print(f"Screenshot: {IMAGE_PATH}")

    if not IMAGE_PATH.is_file():

        raise FileNotFoundError(
            f"Screenshot not found: {IMAGE_PATH}"
        )

    pipeline = ScreenshotPipeline(
        project_root=PROJECT_ROOT
    )

    state = pipeline.process_file(
        screenshot_path=IMAGE_PATH,
        debug_output_dir=DEBUG_DIR
    )

    checks = {}

    table_mismatches = []

    card_mismatches = []

    # Validate extracted table information.

    print("\nTABLE INFORMATION")

    for field, expected in EXPECTED_TABLE.items():

        actual = state["table"].get(field)

        passed = actual == expected

        checks[f"table_{field}"] = passed

        if not passed:

            table_mismatches.append({
                "field": field,
                "expected": expected,
                "actual": actual
            })

        status = "PASS" if passed else "FAIL"

        print(
            f"{status} | {field}: {actual}"
        )

    # Validate recognized cards.

    print("\nCARD RECOGNITION")

    all_slots = (
        state["cards"]["board_slots"]
        + state["cards"]["hero_slots"]
    )

    actual_cards = {
        card["slot"]: card
        for card in all_slots
    }

    for slot, expected in EXPECTED_CARDS.items():

        actual = actual_cards.get(slot, {})

        identity = (
            actual.get("rank"),
            actual.get("suit")
        )

        passed = (
            identity == expected
            and actual.get("recognized") is True
            and actual.get("occupied") is True
        )

        checks[f"card_{slot}"] = passed

        if not passed:

            card_mismatches.append({
                "slot": slot,
                "expected": list(expected),
                "actual": actual
            })

        status = "PASS" if passed else "FAIL"

        print(
            f"{status} | {slot}: "
            f"{identity[0]} of {identity[1]}"
        )

    # Validate complete response.

    checks["street_correct"] = (
        state["game"]["street"] == "river"
    )

    checks["board_count_correct"] = (
        state["game"]["board_count"] == 5
    )

    checks["hero_count_correct"] = (
        state["game"]["hero_card_count"] == 2
    )

    checks["seven_cards_recognized"] = (
        state["game"]["recognized_card_count"] == 7
    )

    checks["seven_slots_preserved"] = (
        len(all_slots) == 7
    )

    checks["validation_passed"] = (
        state["validation"]["valid"] is True
    )

    checks["parser_validation_passed"] = (
        state["validation"][
            "table_parser_validation"
        ].get("valid") is True
    )

    checks["automatic_table_extraction"] = (
        state["metadata"]["table_data_origin"]
        == "screenshot_ocr"
    )

    checks["ocr_items_detected"] = (
        state["metadata"]["ocr_item_count"] > 0
    )

    checks["players_detected"] = any(
        player.get("name")
        and player.get("stack") is not None
        for player in state["players"]
    )

    checks["json_serializable"] = isinstance(
        json.dumps(state, allow_nan=False),
        str
    )

    print("\nINTEGRATION CHECKS")

    for name, passed in checks.items():

        status = "PASS" if passed else "FAIL"

        print(f"{status} | {name}")

    passed_count = sum(checks.values())

    summary = {
        "total_checks": len(checks),
        "passed_checks": passed_count,
        "failed_checks": len(checks) - passed_count,
        "state_status": state["status"],
        "street": state["game"]["street"],
        "recognized_cards": state["game"][
            "recognized_card_count"
        ],
        "player_slots": len(state["players"]),
        "ocr_items": state["metadata"][
            "ocr_item_count"
        ],
        "table_mismatches": len(table_mismatches),
        "card_mismatches": len(card_mismatches),
        "validation_errors": state["validation"][
            "error_count"
        ],
        "validation_warnings": state["validation"][
            "warning_count"
        ],
        "processing_time_seconds": state["metadata"][
            "processing_time_seconds"
        ],
        "passed": all(checks.values())
    }

    report = {
        "summary": summary,
        "checks": checks,
        "table_mismatches": table_mismatches,
        "card_mismatches": card_mismatches,
        "validation": state["validation"]
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            state,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("SCREENSHOT PIPELINE SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print(f"\nTable state saved: {OUTPUT_FILE}")
    print(f"Report saved: {REPORT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
