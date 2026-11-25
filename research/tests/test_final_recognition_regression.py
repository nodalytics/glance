
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from test_enhanced_recognition import (
    create_counters,
    evaluate,
    calculate_metrics
)

from poker_apis.vision.verified_simulator_recognition import (
    VerifiedSimulatorCardRecognizer
)


OUTPUT_DIR = PROJECT_ROOT / "test_output"

TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "final_recognition_regression_report.json"
)

DATASETS = {
    "enhanced": {
        "directory": (
            PROJECT_ROOT
            / "test_assets/validation/heldout_v1"
        ),
        "expected_count": 168,
        "baseline": (
            OUTPUT_DIR
            / "baselines/enhanced_recognition_v1.json"
        )
    },
    "independent": {
        "directory": (
            PROJECT_ROOT
            / "test_assets/validation/independent_v1"
        ),
        "expected_count": 116,
        "baseline": (
            OUTPUT_DIR
            / "baselines/independent_recognition_v1.json"
        )
    }
}


def load_json(path):

    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def validate_dataset(
    name,
    configuration,
    recognizer,
    global_counters
):

    directory = configuration["directory"]

    dataset = load_json(
        directory / "expected.json"
    )

    baseline = load_json(
        configuration["baseline"]
    )

    records = dataset["records"]

    expected_count = configuration[
        "expected_count"
    ]

    if len(records) != expected_count:

        raise ValueError(
            f"{name}: expected {expected_count} "
            f"images, found {len(records)}."
        )

    filenames = [
        record["file"]
        for record in records
    ]

    if len(filenames) != len(set(filenames)):

        raise ValueError(
            f"{name}: duplicate filenames."
        )

    baseline_records = {
        item["file"]: item
        for item in baseline["results"]
    }

    if set(filenames) != set(baseline_records):

        raise ValueError(
            f"{name}: baseline records mismatch."
        )

    counters = create_counters()

    variant_counters = {}

    results = []

    failures = []

    changed_predictions = []

    verification_attempts = 0

    recognizer.reset_fallback_statistics()

    recognizer.reset_verification_statistics()

    dataset_start = time.perf_counter()

    print("\n" + "=" * 75)

    print(f"DATASET: {name.upper()}")

    print(f"Images: {len(records)}")

    print("=" * 75)

    for index, expected in enumerate(records, 1):

        filename = expected["file"]

        variant = expected["variant"]

        image_path = (
            directory / "cards" / filename
        )

        image = cv2.imread(
            str(image_path)
        )

        if image is None:

            raise FileNotFoundError(
                f"Cannot load: {image_path}"
            )

        previous_record = baseline_records[
            filename
        ]

        previous = previous_record["actual"]

        start = time.perf_counter()

        actual = recognizer.recognize_card(
            image
        )

        elapsed = (
            time.perf_counter() - start
        )

        status = evaluate(
            expected,
            actual,
            counters
        )

        evaluate(
            expected,
            actual,
            global_counters
        )

        if variant not in variant_counters:

            variant_counters[variant] = (
                create_counters()
            )

        evaluate(
            expected,
            actual,
            variant_counters[variant]
        )

        verification_used = actual.get(
            "rank_verification_used",
            False
        )

        if verification_used:

            verification_attempts += 1

        prediction_changed = any(
            actual.get(field)
            != previous.get(field)
            for field in (
                "rank",
                "suit",
                "recognized"
            )
        )

        result = {
            "dataset": name,
            "file": filename,
            "variant": variant,
            "expected": expected,
            "previous": previous,
            "actual": actual,
            "status": status,
            "prediction_changed": (
                prediction_changed
            ),
            "recognition_time_seconds": round(
                elapsed, 4
            )
        }

        results.append(result)

        if status != "PASS":

            failures.append(result)

        if prediction_changed:

            changed_predictions.append(
                result
            )

        labels = []

        if actual.get("rank_fallback_used"):

            labels.append("FALLBACK")

        if verification_used:

            labels.append("VERIFIED")

        if prediction_changed:

            labels.append("CHANGED")

        label_text = (
            " | " + ", ".join(labels)
            if labels else ""
        )

        total_elapsed = (
            time.perf_counter()
            - dataset_start
        )

        average = total_elapsed / index

        remaining = (
            average * (len(records) - index)
        )

        print(
            f"[{index:03}/{len(records)}] "
            f"{status:14} | "
            f"{filename:38} | "
            f"{elapsed:.2f}s"
            f"{label_text} | "
            f"ETA: {remaining / 60:.1f}m"
        )

    summary = calculate_metrics(
        counters
    )

    summary["verification_attempts"] = (
        verification_attempts
    )

    summary["changed_predictions"] = len(
        changed_predictions
    )

    summary["failed_images"] = len(
        failures
    )

    summary["total_time_seconds"] = round(
        time.perf_counter() - dataset_start,
        4
    )

    summary_by_variant = {
        variant: calculate_metrics(values)
        for variant, values
        in variant_counters.items()
    }

    comparison = {
        "baseline_correct_cards": (
            baseline["summary"]["correct_cards"]
        ),
        "verified_correct_cards": (
            summary["correct_cards"]
        ),
        "baseline_incorrect_accepted": (
            baseline["summary"][
                "incorrect_accepted_cards"
            ]
        ),
        "verified_incorrect_accepted": (
            summary["incorrect_accepted_cards"]
        ),
        "baseline_card_accuracy": (
            baseline["summary"]["card_accuracy"]
        ),
        "verified_card_accuracy": (
            summary["card_accuracy"]
        )
    }

    return {
        "dataset": name,
        "summary": summary,
        "summary_by_variant": (
            summary_by_variant
        ),
        "baseline_comparison": comparison,
        "fallback_statistics": (
            recognizer.get_fallback_statistics()
        ),
        "verification_statistics": (
            recognizer.get_verification_statistics()
        ),
        "changed_predictions": (
            changed_predictions
        ),
        "failures": failures,
        "results": results
    }


def main():

    print("=" * 75)

    print("FINAL OFFLINE RECOGNITION REGRESSION")

    print("=" * 75)

    recognizer = VerifiedSimulatorCardRecognizer(
        suit_template_dir=TEMPLATE_DIR,
        verification_trigger=0.90,
        verification_threshold=0.95
    )

    global_counters = create_counters()

    dataset_reports = {}

    all_failures = []

    all_changes = []

    verification_totals = {
        "total_cards": 0,
        "verification_attempts": 0,
        "confirmed_ranks": 0,
        "changed_ranks": 0,
        "rejected_ranks": 0
    }

    total_start = time.perf_counter()

    for name, configuration in DATASETS.items():

        report = validate_dataset(
            name,
            configuration,
            recognizer,
            global_counters
        )

        dataset_reports[name] = report

        all_failures.extend(
            report["failures"]
        )

        all_changes.extend(
            report["changed_predictions"]
        )

        for key in verification_totals:

            verification_totals[key] += (
                report["verification_statistics"][
                    key
                ]
            )

    summary = calculate_metrics(
        global_counters
    )

    summary["total_datasets"] = len(
        dataset_reports
    )

    summary["passed_datasets"] = sum(
        report["summary"]["passed"]
        for report in dataset_reports.values()
    )

    summary["failed_images"] = len(
        all_failures
    )

    summary["changed_predictions"] = len(
        all_changes
    )

    summary["total_time_seconds"] = round(
        time.perf_counter() - total_start,
        4
    )

    summary["average_time_per_image_seconds"] = (
        round(
            summary["total_time_seconds"]
            / summary["total_slots"],
            4
        )
    )

    summary["passed"] = (
        summary["passed"]
        and summary["total_slots"] == 284
        and summary["occupied_slots"] == 260
        and summary["empty_slots"] == 24
        and summary["passed_datasets"] == 2
    )

    final_report = {
        "recognizer": (
            "VerifiedSimulatorCardRecognizer"
        ),
        "configuration": {
            "verification_trigger": 0.90,
            "verification_threshold": 0.95
        },
        "summary": summary,
        "verification_statistics": (
            verification_totals
        ),
        "changed_predictions": all_changes,
        "failures": all_failures,
        "datasets": dataset_reports
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            final_report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)

    print("FINAL REGRESSION SUMMARY")

    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print("\nVERIFICATION STATISTICS")

    print(
        json.dumps(
            verification_totals,
            indent=4
        )
    )

    print("\nDATASET COMPARISON")

    for name, report in dataset_reports.items():

        print(f"\n{name.upper()}")

        print(
            json.dumps(
                report["baseline_comparison"],
                indent=4
            )
        )

    print("\nCHANGED PREDICTIONS")

    for item in all_changes:

        print(
            f"{item['dataset']} | "
            f"{item['file']} | "
            f"{item['previous'].get('rank')} "
            f"-> {item['actual'].get('rank')} | "
            f"{item['status']}"
        )

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
