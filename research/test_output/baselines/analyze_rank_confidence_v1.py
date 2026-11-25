
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = PROJECT_ROOT / "test_output"

REPORTS = {
    "enhanced": (
        OUTPUT_DIR
        / "enhanced_recognition_report.json"
    ),
    "independent": (
        OUTPUT_DIR
        / "independent_recognition_report.json"
    )
}

THRESHOLDS = [
    0.75,
    0.85,
    0.90,
    0.95,
    0.98,
    0.99
]


def load_json(path):

    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def analyze_report(report):

    occupied = [
        item
        for item in report["results"]
        if item["expected"]["occupied"]
    ]

    threshold_results = []

    for threshold in THRESHOLDS:

        correct_accepted = 0
        incorrect_accepted = 0
        rejected = 0

        for item in occupied:

            actual = item["actual"]
            expected = item["expected"]

            confidence = actual.get(
                "rank_confidence", 0.0
            )

            accepted = (
                actual.get("recognized", False)
                and confidence >= threshold
            )

            if not accepted:

                rejected += 1
                continue

            correct = (
                actual.get("rank")
                == expected["rank"]
                and actual.get("suit")
                == expected["suit"]
            )

            if correct:

                correct_accepted += 1

            else:

                incorrect_accepted += 1

        threshold_results.append({
            "threshold": threshold,
            "occupied_cards": len(occupied),
            "correct_accepted": correct_accepted,
            "incorrect_accepted": incorrect_accepted,
            "rejected": rejected,
            "acceptance_rate": (
                (
                    correct_accepted
                    + incorrect_accepted
                ) / len(occupied)
                if occupied else None
            )
        })

    low_confidence_cards = []

    for item in occupied:

        actual = item["actual"]

        confidence = actual.get(
            "rank_confidence", 0.0
        )

        if confidence < 0.95:

            low_confidence_cards.append({
                "file": item["file"],
                "expected_rank": (
                    item["expected"]["rank"]
                ),
                "actual_rank": actual.get("rank"),
                "rank_confidence": confidence,
                "rank_source": actual.get(
                    "rank_source"
                ),
                "status": item["status"]
            })

    return {
        "occupied_cards": len(occupied),
        "threshold_analysis": threshold_results,
        "low_confidence_cards": (
            low_confidence_cards
        ),
        "low_confidence_count": len(
            low_confidence_cards
        )
    }


def main():

    print("=" * 75)
    print("OFFLINE RANK CONFIDENCE ANALYSIS")
    print("=" * 75)

    final_report = {}

    for name, path in REPORTS.items():

        if not path.is_file():

            raise FileNotFoundError(
                f"Missing report: {path}"
            )

        report = load_json(path)

        analysis = analyze_report(report)

        final_report[name] = analysis

        print("\n" + "-" * 75)
        print(f"DATASET: {name.upper()}")
        print("-" * 75)

        print(
            f"{'Threshold':12}"
            f"{'Correct':12}"
            f"{'Wrong':12}"
            f"{'Rejected':12}"
        )

        for result in analysis[
            "threshold_analysis"
        ]:

            print(
                f"{result['threshold']:<12.2f}"
                f"{result['correct_accepted']:<12}"
                f"{result['incorrect_accepted']:<12}"
                f"{result['rejected']:<12}"
            )

        print("\nLOW CONFIDENCE CARDS")

        print(
            json.dumps(
                analysis["low_confidence_cards"],
                indent=4
            )
        )

    output_path = (
        OUTPUT_DIR
        / "rank_confidence_analysis.json"
    )

    output_path.write_text(
        json.dumps(
            final_report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print(f"\nReport saved: {output_path}")


if __name__ == "__main__":
    main()
