
import sys
import json
from pathlib import Path
from copy import deepcopy


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.validation.card_state_validator import (
    CardStateValidator
)


REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/card_state_validation_report.json"
)


# --------------------------------------------------
# CARD FIXTURES
# --------------------------------------------------

def make_card(rank, suit):

    return {
        "rank": rank,
        "suit": suit,
        "recognized": True,
        "occupied": True,
        "occupancy_state": "occupied"
    }


def make_empty():

    return {
        "rank": None,
        "suit": None,
        "recognized": False,
        "occupied": False,
        "occupancy_state": "empty"
    }


def make_unknown():

    return {
        "rank": None,
        "suit": None,
        "recognized": False,
        "occupied": None,
        "occupancy_state": "unknown"
    }


def create_table(board_count):

    board_cards = [
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

            rank, suit = board_cards[index]

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
# BUILD TEST CASES
# --------------------------------------------------

def build_test_cases():

    cases = []

    # Valid poker streets.

    for count, street in [
        (0, "preflop"),
        (3, "flop"),
        (4, "turn"),
        (5, "river")
    ]:

        cases.append({
            "name": f"valid_{street}",
            "cards": create_table(count),
            "expected_valid": True,
            "expected_street": street,
            "expected_errors": []
        })

    # Duplicate community card.

    cards = create_table(5)

    cards["board_2"] = deepcopy(
        cards["board_1"]
    )

    cases.append({
        "name": "duplicate_board_card",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "DUPLICATE_CARD"
        ]
    })

    # Duplicate hero card.

    cards = create_table(0)

    cards["hero_card_2"] = deepcopy(
        cards["hero_card_1"]
    )

    cases.append({
        "name": "duplicate_hero_card",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "DUPLICATE_CARD"
        ]
    })

    # Duplicate between board and hero.

    cards = create_table(3)

    cards["hero_card_1"] = deepcopy(
        cards["board_1"]
    )

    cases.append({
        "name": "duplicate_board_and_hero",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "DUPLICATE_CARD"
        ]
    })

    # Invalid board count: one card.

    cases.append({
        "name": "invalid_board_count_one",
        "cards": create_table(1),
        "expected_valid": False,
        "expected_errors": [
            "INVALID_BOARD_COUNT"
        ]
    })

    # Invalid board count: two cards.

    cases.append({
        "name": "invalid_board_count_two",
        "cards": create_table(2),
        "expected_valid": False,
        "expected_errors": [
            "INVALID_BOARD_COUNT"
        ]
    })

    # Gap between board cards.

    cards = create_table(4)

    cards["board_2"] = make_empty()

    cases.append({
        "name": "community_card_gap",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "BOARD_GAP"
        ]
    })

    # Missing hero card.

    cards = create_table(3)

    cards["hero_card_2"] = make_empty()

    cases.append({
        "name": "missing_hero_card",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "INVALID_HERO_COUNT"
        ]
    })

    # Invalid rank.

    cards = create_table(3)

    cards["board_1"]["rank"] = "15"

    cases.append({
        "name": "invalid_rank",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "INVALID_RANK"
        ]
    })

    # Invalid suit.

    cards = create_table(3)

    cards["board_1"]["suit"] = "stars"

    cases.append({
        "name": "invalid_suit",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "INVALID_SUIT"
        ]
    })

    # Unrecognized occupied card.

    cards = create_table(3)

    cards["board_1"] = {
        "rank": None,
        "suit": None,
        "recognized": False,
        "occupied": True
    }

    cases.append({
        "name": "unrecognized_occupied_card",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "UNRECOGNIZED_CARD"
        ]
    })

    # Unknown occupancy.

    cards = create_table(3)

    cards["board_2"] = make_unknown()

    cases.append({
        "name": "unknown_occupancy",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "UNKNOWN_OCCUPANCY"
        ]
    })

    # Required slot missing.

    cards = create_table(3)

    del cards["board_5"]

    cases.append({
        "name": "missing_required_slot",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "MISSING_SLOT"
        ]
    })

    # Inconsistent empty slot.

    cards = create_table(3)

    cards["board_4"] = make_card(
        "K",
        "diamonds"
    )

    cards["board_4"]["occupied"] = False

    cases.append({
        "name": "inconsistent_empty_slot",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "INCONSISTENT_EMPTY_SLOT"
        ]
    })

    # Unexpected card slot.

    cards = create_table(3)

    cards["board_6"] = make_card(
        "K",
        "diamonds"
    )

    cases.append({
        "name": "unexpected_slot",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "UNEXPECTED_SLOT"
        ]
    })

    # Malformed slot.

    cards = create_table(3)

    cards["board_1"] = None

    cases.append({
        "name": "malformed_slot",
        "cards": cards,
        "expected_valid": False,
        "expected_errors": [
            "INVALID_SLOT"
        ]
    })

    return cases


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("CARD STATE CONSISTENCY VALIDATION")
    print("=" * 75)

    validator = CardStateValidator()

    cases = build_test_cases()

    results = []

    passed_count = 0

    for index, case in enumerate(
        cases,
        start=1
    ):

        actual = validator.validate(
            case["cards"]
        )

        actual_codes = {
            error["code"]
            for error in actual["errors"]
        }

        expected_codes = set(
            case["expected_errors"]
        )

        valid_correct = (
            actual["valid"]
            == case["expected_valid"]
        )

        errors_correct = (
            expected_codes.issubset(
                actual_codes
            )
        )

        street_correct = (
            "expected_street" not in case

            or actual["street"]
            == case["expected_street"]
        )

        passed = (
            valid_correct
            and errors_correct
            and street_correct
        )

        if passed:
            passed_count += 1

        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        results.append({
            "name": case["name"],
            "expected_valid": (
                case["expected_valid"]
            ),
            "expected_errors": (
                case["expected_errors"]
            ),
            "actual": actual,
            "passed": passed
        })

        print(
            f"[{index:02}/{len(cases):02}] "
            f"{status:5} | "
            f"{case['name']:32} | "
            f"Errors: {sorted(actual_codes)}"
        )

    summary = {
        "total_tests": len(cases),
        "passed_tests": passed_count,
        "failed_tests": (
            len(cases) - passed_count
        ),
        "accuracy": (
            passed_count / len(cases)
        ),
        "passed": (
            passed_count == len(cases)
        )
    }

    report = {
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
    print("VALIDATION SUMMARY")
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
