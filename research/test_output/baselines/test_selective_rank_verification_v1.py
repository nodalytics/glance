
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.verified_simulator_recognition import (
    VerifiedSimulatorCardRecognizer
)


OUTPUT_DIR = PROJECT_ROOT / "test_output"

TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

ANALYSIS_FILE = (
    OUTPUT_DIR / "rank_confidence_analysis.json"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "selective_rank_verification_report.json"
)

DATASET_DIRECTORIES = {
    "enhanced": (
        PROJECT_ROOT
        / "test_assets/validation/heldout_v1/cards"
    ),
    "independent": (
        PROJECT_ROOT
        / "test_assets/validation/independent_v1/cards"
    )
}

BASELINE_REPORTS = {
    "enhanced": (
        OUTPUT_DIR
        / "enhanced_recognition_report.json"
    ),
    "independent": (
        OUTPUT_DIR
        / "independent_recognition_report.json"
    )
}

VERIFICATION_TRIGGER = 0.90


def load_json(path):

    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def main():

    print("=" * 75)
    print("SELECTIVE RANK VERIFICATION TEST")
    print("=" * 75)

    analysis = load_json(ANALYSIS_FILE)

    recognizer = VerifiedSimulatorCardRecognizer(
        suit_template_dir=TEMPLATE_DIR,
        verification_trigger=0.90,
        verification_threshold=0.95
    )

    results = []

    total_start = time.perf_counter()

    for dataset_name, directory in (
        DATASET_DIRECTORIES.items()
    ):

        baseline = load_json(
            BASELINE_REPORTS[dataset_name]
        )

        baseline_records = {
            item["file"]: item
            for item in baseline["results"]
        }

        candidates = [
            item
            for item in analysis[dataset_name][
                "low_confidence_cards"
            ]
            if item["rank_confidence"]
            < VERIFICATION_TRIGGER
        ]

        print("\n" + "-" * 75)
        print(f"DATASET: {dataset_name.upper()}")
        print(f"Candidates: {len(candidates)}")

        for candidate in candidates:

            filename = candidate["file"]

            baseline_record = (
                baseline_records[filename]
            )

            expected = baseline_record[
                "expected"
            ]

            previous = baseline_record[
                "actual"
            ]

            image_path = directory / filename

            image = cv2.imread(
                str(image_path)
            )

            if image is None:

                raise FileNotFoundError(
                    f"Cannot load: {image_path}"
                )

            start = time.perf_counter()

            actual = recognizer.recognize_card(
                image
            )

            elapsed = (
                time.perf_counter() - start
            )

            correct = (
                actual.get("recognized")
                and actual.get("rank")
                == expected["rank"]
                and actual.get("suit")
                == expected["suit"]
            )

            verification_used = actual.get(
                "rank_verification_used", False
            )

            passed = (
                correct and verification_used
            )

            status = (
                "PASS" if passed
                else "FAIL"
            )

            print("\n" + filename)

            print(
                f"Expected: "
                f"{expected['rank']} "
                f"{expected['suit']}"
            )

            print(
                f"Previous rank: "
                f"{previous['rank']} | "
                f"Confidence: "
                f"{previous['rank_confidence']:.6f}"
            )

            print(
                f"Verified rank: "
                f"{actual.get('rank')} | "
                f"Confidence: "
                f"{actual['rank_confidence']:.6f}"
            )

            print(
                "Verification status: "
                + actual[
                    "rank_verification_status"
                ]
            )

            print(
                f"Result: {status} | "
                f"{elapsed:.2f}s"
            )

            results.append({
                "dataset": dataset_name,
                "file": filename,
                "expected": expected,
                "previous": previous,
                "actual": actual,
                "status": status,
                "time_seconds": round(
                    elapsed, 4
                )
            })

    passed_count = sum(
        item["status"] == "PASS"
        for item in results
    )

    incorrect_accepted = sum(
        bool(item["actual"].get("recognized"))
        and (
            item["actual"].get("rank")
            != item["expected"]["rank"]
            or item["actual"].get("suit")
            != item["expected"]["suit"]
        )
        for item in results
    )

    summary = {
        "total_candidates": len(results),
        "passed_candidates": passed_count,
        "failed_candidates": (
            len(results) - passed_count
        ),
        "incorrect_accepted_cards": (
            incorrect_accepted
        ),
        "total_time_seconds": round(
            time.perf_counter() - total_start,
            4
        ),
        "passed": (
            len(results) == 3
            and passed_count == len(results)
            and incorrect_accepted == 0
        )
    }

    report = {
        "summary": summary,
        "verification_statistics": (
            recognizer.get_verification_statistics()
        ),
        "results": results
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("VERIFICATION SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print("\nVERIFICATION STATISTICS")

    print(
        json.dumps(
            report["verification_statistics"],
            indent=4
        )
    )

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
