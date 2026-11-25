
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


CARD_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
    / "calibration_sample_001/cards"
)
EXPECTED_FILE = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
    / "calibration_sample_001/expected.json"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/card_regression_report.json"
)


# --------------------------------------------------
# LOAD EXPECTED RESULTS
# --------------------------------------------------

def load_expected_results():

    if not EXPECTED_FILE.exists():
        raise FileNotFoundError(
            f"Expected results not found: {EXPECTED_FILE}"
        )

    with open(
        EXPECTED_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# --------------------------------------------------
# LOAD CARD IMAGES
# --------------------------------------------------

def load_card_images(expected_cards):

    images = {}

    for card_name in expected_cards:

        path = CARD_DIR / f"{card_name}.png"

        image = cv2.imread(str(path))

        if image is None:
            raise FileNotFoundError(
                f"Could not load card image: {path}"
            )

        images[card_name] = image

        print(
            f"Loaded: {path.name} | "
            f"Dimensions: {image.shape}"
        )

    return images


# --------------------------------------------------
# CARD FORMATTING
# --------------------------------------------------

def format_card(rank, suit):

    suit_symbols = {
        "hearts": "H",
        "diamonds": "D",
        "clubs": "C",
        "spades": "S"
    }

    rank = rank or "?"
    suit = suit_symbols.get(suit, "?")

    return f"{rank}{suit}"


# --------------------------------------------------
# VALIDATE RECOGNITION RESULTS
# --------------------------------------------------

def validate_results(expected_cards, actual_cards):

    report = []

    correct_ranks = 0
    correct_suits = 0
    correct_cards = 0
    rejected_cards = 0
    incorrect_accepted_cards = 0

    print("\nREGRESSION TEST RESULTS")
    print("=" * 65)

    for card_name, expected in expected_cards.items():

        actual = actual_cards.get(card_name, {})

        expected_rank = expected["rank"]
        expected_suit = expected["suit"]

        actual_rank = actual.get("rank")
        actual_suit = actual.get("suit")

        rank_correct = (
            actual_rank == expected_rank
        )

        suit_correct = (
            actual_suit == expected_suit
        )

        recognized = bool(
            actual.get("recognized", False)
        )

        card_correct = (
            rank_correct
            and suit_correct
            and recognized
        )

        if rank_correct:
            correct_ranks += 1

        if suit_correct:
            correct_suits += 1

        if card_correct:
            correct_cards += 1

        if not recognized:
            rejected_cards += 1

        elif not card_correct:
            incorrect_accepted_cards += 1

        status = (
            "PASS" if card_correct else "FAIL"
        )

        expected_display = format_card(
            expected_rank,
            expected_suit
        )

        actual_display = format_card(
            actual_rank,
            actual_suit
        )

        print(
            f"{status:4} | "
            f"{card_name:15} | "
            f"Expected: {expected_display:4} | "
            f"Actual: {actual_display:4}"
        )

        report.append({
            "card_name": card_name,
            "expected": expected,
            "actual": actual,
            "rank_correct": rank_correct,
            "suit_correct": suit_correct,
            "card_correct": card_correct,
            "status": status
        })

    total = len(expected_cards)

    summary = {
        "total_cards": total,
        "correct_ranks": correct_ranks,
        "correct_suits": correct_suits,
        "correct_cards": correct_cards,
        "rejected_cards": rejected_cards,
        "incorrect_accepted_cards": (
            incorrect_accepted_cards
        ),
        "rank_accuracy": (
            correct_ranks / total if total else 0.0
        ),
        "suit_accuracy": (
            correct_suits / total if total else 0.0
        ),
        "card_accuracy": (
            correct_cards / total if total else 0.0
        ),
        "passed": (
            total > 0 and correct_cards == total
        )
    }

    return summary, report


# --------------------------------------------------
# MAIN TEST
# --------------------------------------------------

def main():

    print("=" * 65)
    print("OFFLINE CARD RECOGNITION REGRESSION TEST")
    print("=" * 65)

    dataset = load_expected_results()

    expected_cards = dataset["cards"]

    if not expected_cards:
        raise ValueError("Validation dataset is empty.")

    print(
        f"\nDataset: {dataset['sample_name']}"
    )

    print("\nLoading card images...")

    card_images = load_card_images(
        expected_cards
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

    print("\nRunning recognition...")

    start_time = time.perf_counter()

    actual_cards = recognizer.recognize_cards(
        card_images
    )

    elapsed_time = (
        time.perf_counter() - start_time
    )

    summary, details = validate_results(
        expected_cards,
        actual_cards
    )

    summary["recognition_time_seconds"] = (
        round(elapsed_time, 3)
    )

    summary["average_time_per_card_seconds"] = (
        round(
            elapsed_time / len(card_images),
            3
        )
    )

    # ----------------------------------------------
    # SAVE REPORT
    # ----------------------------------------------

    final_report = {
        "sample_name": dataset["sample_name"],
        "summary": summary,
        "cards": details
    }

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
    # PRINT SUMMARY
    # ----------------------------------------------

    print("\n" + "=" * 65)
    print("VALIDATION SUMMARY")
    print("=" * 65)

    print(
        f"Total cards: "
        f"{summary['total_cards']}"
    )

    print(
        f"Correct ranks: "
        f"{summary['correct_ranks']}"
    )

    print(
        f"Correct suits: "
        f"{summary['correct_suits']}"
    )

    print(
        f"Correct complete cards: "
        f"{summary['correct_cards']}"
    )

    print(
        f"Rejected cards: "
        f"{summary['rejected_cards']}"
    )

    print(
        f"Incorrect accepted cards: "
        f"{summary['incorrect_accepted_cards']}"
    )

    print(
        f"Rank accuracy: "
        f"{summary['rank_accuracy']:.2%}"
    )

    print(
        f"Suit accuracy: "
        f"{summary['suit_accuracy']:.2%}"
    )

    print(
        f"Complete card accuracy: "
        f"{summary['card_accuracy']:.2%}"
    )

    print(
        f"Recognition time: "
        f"{elapsed_time:.3f} seconds"
    )

    print(f"\nReport saved: {REPORT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: REGRESSION TEST FAILED")

    return 1


if __name__ == "__main__":
    sys.exit(main())
