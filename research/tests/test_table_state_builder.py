
import sys
import json
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.state.table_state_builder import (
    TableStateBuilder
)


REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/table_state_builder_report.json"
)

SAMPLE_FILE = (
    PROJECT_ROOT
    / "test_output/sample_table_state.json"
)


# --------------------------------------------------
# TABLE FIXTURE
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
                "name": "Player1",
                "stack": 92500,
                "bounty_display": "$0.03"
            },
            {
                "seat": "upper_left",
                "name": "Player2",
                "stack": 85000,
                "bounty_display": "$0.04"
            }
        ]
    }


# --------------------------------------------------
# CARD FIXTURES
# --------------------------------------------------

def make_card(rank, suit):

    return {
        "rank": rank,
        "suit": suit,
        "rank_confidence": 0.99,
        "suit_confidence": 0.98,
        "suit_margin": 0.12,
        "recognized": True,
        "occupied": True,
        "occupancy_state": "occupied",
        "ocr_skipped": False
    }


def make_empty():

    return {
        "rank": None,
        "suit": None,
        "recognized": False,
        "occupied": False,
        "occupancy_state": "empty",
        "ocr_skipped": True
    }


def create_cards(board_count):

    identities = [
        ("A", "hearts"),
        ("8", "spades"),
        ("J", "hearts"),
        ("J", "diamonds"),
        ("2", "hearts")
    ]

    cards = {}

    for index in range(5):

        slot = f"board_{index + 1}"

        if index < board_count:

            rank, suit = identities[index]

            cards[slot] = make_card(
                rank,
                suit
            )

        else:

            cards[slot] = make_empty()

    cards["hero_card_1"] = make_card(
        "Q",
        "clubs"
    )

    cards["hero_card_2"] = make_card(
        "10",
        "clubs"
    )

    return cards


# --------------------------------------------------
# TEST CASES
# --------------------------------------------------

def build_test_cases():

    cases = []

    for count, street in [
        (0, "preflop"),
        (3, "flop"),
        (4, "turn"),
        (5, "river")
    ]:

        cases.append({
            "name": f"valid_{street}",
            "table": create_table_data(),
            "cards": create_cards(count),
            "expected_status": "valid",
            "expected_street": street,
            "expected_board_count": count
        })

    # Duplicate card.

    cards = create_cards(5)

    cards["hero_card_1"] = deepcopy(
        cards["board_1"]
    )

    cases.append({
        "name": "duplicate_card",
        "table": create_table_data(),
        "cards": cards,
        "expected_status": "invalid",
        "expected_error": "DUPLICATE_CARD"
    })

    # Missing pot.

    table = create_table_data()

    del table["pot"]

    cases.append({
        "name": "missing_pot",
        "table": table,
        "cards": create_cards(3),
        "expected_status": "partial"
    })

    # Negative pot.

    table = create_table_data()

    table["pot"] = -100

    cases.append({
        "name": "negative_pot",
        "table": table,
        "cards": create_cards(3),
        "expected_status": "invalid",
        "expected_error": "INVALID_TABLE_VALUE"
    })

    # Invalid blind order.

    table = create_table_data()

    table["small_blind"] = 10000

    cases.append({
        "name": "invalid_blind_order",
        "table": table,
        "cards": create_cards(3),
        "expected_status": "invalid",
        "expected_error": "INVALID_BLIND_ORDER"
    })

    # Zero blind.

    table = create_table_data()

    table["small_blind"] = 0

    cases.append({
        "name": "zero_blind",
        "table": table,
        "cards": create_cards(3),
        "expected_status": "invalid",
        "expected_error": "INVALID_BLIND"
    })

    # Missing hero card.

    cards = create_cards(3)

    cards["hero_card_2"] = make_empty()

    cases.append({
        "name": "missing_hero_card",
        "table": create_table_data(),
        "cards": cards,
        "expected_status": "invalid",
        "expected_error": "INVALID_HERO_COUNT"
    })

    # Unknown occupancy.

    cards = create_cards(3)

    cards["board_2"] = {
        "rank": None,
        "suit": None,
        "recognized": False,
        "occupied": None
    }

    cases.append({
        "name": "unknown_occupancy",
        "table": create_table_data(),
        "cards": cards,
        "expected_status": "invalid",
        "expected_error": "UNKNOWN_OCCUPANCY"
    })

    # Empty table information.

    cases.append({
        "name": "missing_table_information",
        "table": {},
        "cards": create_cards(3),
        "expected_status": "partial"
    })

    return cases


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("STRUCTURED TABLE STATE VALIDATION")
    print("=" * 75)

    builder = TableStateBuilder()

    cases = build_test_cases()

    results = []

    passed_count = 0

    for index, case in enumerate(
        cases,
        start=1
    ):

        original_table = deepcopy(
            case["table"]
        )

        original_cards = deepcopy(
            case["cards"]
        )

        state = builder.build(
            table_data=case["table"],
            recognized_cards=case["cards"],
            source="offline_simulator",
            recognition_profile="simulator_optimized"
        )

        actual_errors = {
            error["code"]
            for error in state["validation"]["errors"]
        }

        checks = {
            "status_correct": (
                state["status"]
                == case["expected_status"]
            ),

            "schema_version_correct": (
                state["schema_version"]
                == "1.0.0"
            ),

            "street_correct": (
                "expected_street" not in case
                or state["game"]["street"]
                == case["expected_street"]
            ),

            "board_count_correct": (
                "expected_board_count" not in case
                or len(state["cards"]["community"])
                == case["expected_board_count"]
            ),

            "error_correct": (
                "expected_error" not in case
                or case["expected_error"]
                in actual_errors
            ),

            "board_slots_preserved": (
                len(state["cards"]["board_slots"]) == 5
            ),

            "hero_slots_preserved": (
                len(state["cards"]["hero_slots"]) == 2
            ),

            "input_not_modified": (
                case["table"] == original_table
                and case["cards"] == original_cards
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

        passed_count += int(passed)

        results.append({
            "name": case["name"],
            "expected_status": (
                case["expected_status"]
            ),
            "actual_status": state["status"],
            "checks": checks,
            "errors": sorted(actual_errors),
            "passed": passed
        })

        status = "PASS" if passed else "FAIL"

        print(
            f"[{index:02}/{len(cases):02}] "
            f"{status:5} | "
            f"{case['name']:32} | "
            f"State: {state['status']}"
        )

    summary = {
        "total_tests": len(cases),
        "passed_tests": passed_count,
        "failed_tests": len(cases) - passed_count,
        "accuracy": passed_count / len(cases),
        "passed": passed_count == len(cases)
    }

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    report = {
        "summary": summary,
        "results": results
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    sample_state = builder.build(
        table_data=create_table_data(),
        recognized_cards=create_cards(5),
        source="offline_simulator",
        recognition_profile="simulator_optimized"
    )

    SAMPLE_FILE.write_text(
        json.dumps(
            sample_state,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("VALIDATION SUMMARY")
    print("=" * 75)

    print(
        json.dumps(summary, indent=4)
    )

    print(f"\nReport saved: {REPORT_FILE}")

    print(f"Sample state saved: {SAMPLE_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
