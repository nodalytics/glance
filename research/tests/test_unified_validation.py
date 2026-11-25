
import sys
import json
import time
from pathlib import Path


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.recognition_profiles import (
    RecognitionProfileManager
)

from test_validation_datasets import (
    load_json,
    create_counters,
    calculate_metrics,
    validate_dataset,
    print_percentage
)


DATASET_ROOT = (
    PROJECT_ROOT
    / "test_assets/validation/datasets"
)

MANIFEST_FILE = (
    DATASET_ROOT / "manifest.json"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "test_output/unified_validation_report.json"
)

BASELINE_FILE = (
    PROJECT_ROOT
    / "test_output/baselines/validation_v1.json"
)


# --------------------------------------------------
# MERGE COUNTERS
# --------------------------------------------------

def merge_counters(target, source):

    for key in target:

        target[key] += source[key]


# --------------------------------------------------
# COMPARE BASELINE
# --------------------------------------------------

def compare_baseline(current_by_type):

    if not BASELINE_FILE.is_file():

        print("\nBaseline report unavailable.")

        return None

    baseline = load_json(BASELINE_FILE)

    baseline_by_type = baseline.get(
        "summary_by_type",
        {}
    )

    comparison = {}

    for dataset_type, current in (
        current_by_type.items()
    ):

        previous = baseline_by_type.get(
            dataset_type
        )

        if previous is None:
            continue

        metrics = [
            "rank_accuracy",
            "suit_accuracy",
            "card_accuracy",
            "empty_rejection_rate"
        ]

        changes = {}

        for metric in metrics:

            old_value = previous.get(metric)

            new_value = current.get(metric)

            if (
                old_value is None
                or new_value is None
            ):

                continue

            changes[metric] = {
                "baseline": old_value,
                "current": new_value,
                "improvement_percentage_points": (
                    round(
                        (new_value - old_value) * 100,
                        4
                    )
                )
            }

        comparison[dataset_type] = {
            "metrics": changes,
            "baseline_occupied_slots": (
                previous["occupied_slots"]
            ),
            "current_occupied_slots": (
                current["occupied_slots"]
            ),
            "baseline_incorrect_accepted": (
                previous["incorrect_accepted_cards"]
            ),
            "current_incorrect_accepted": (
                current["incorrect_accepted_cards"]
            )
        }

    return comparison


# --------------------------------------------------
# PRINT BASELINE COMPARISON
# --------------------------------------------------

def print_comparison(comparison):

    if not comparison:
        return

    print("\n" + "=" * 75)
    print("BASELINE COMPARISON")
    print("=" * 75)

    for dataset_type, data in comparison.items():

        print(f"\nDataset type: {dataset_type}")

        for metric, values in (
            data["metrics"].items()
        ):

            label = metric.replace(
                "_",
                " "
            ).title()

            print(
                f"{label:25} | "
                f"{values['baseline']:.2%} -> "
                f"{values['current']:.2%} | "
                f"{values['improvement_percentage_points']:+.2f} pp"
            )

        print(
            "Incorrect accepted cards: "
            f"{data['baseline_incorrect_accepted']} -> "
            f"{data['current_incorrect_accepted']}"
        )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 75)
    print("UNIFIED OFFLINE DATASET VALIDATION")
    print("=" * 75)

    manifest = load_json(MANIFEST_FILE)

    datasets = [
        entry
        for entry in manifest["datasets"]
        if entry.get("enabled", True)
    ]

    if not datasets:

        raise RuntimeError(
            "No enabled datasets found."
        )

    manager = RecognitionProfileManager(
        project_root=PROJECT_ROOT
    )

    overall_counters = create_counters()

    counters_by_type = {}

    profile_information = {}

    dataset_reports = []

    passed_datasets = 0

    start_time = time.perf_counter()

    # ----------------------------------------------
    # VALIDATE ALL DATASETS
    # ----------------------------------------------

    for entry in datasets:

        dataset_type = entry["type"]

        recognizer = manager.get_recognizer(
            dataset_type
        )

        profile_info = manager.get_profile_info(
            dataset_type
        )

        profile_name = profile_info["profile"]

        profile_information[profile_name] = (
            profile_info
        )

        print(
            f"\nSelected profile: {profile_name}"
        )

        print(
            f"Recognizer: "
            f"{profile_info['recognizer']}"
        )

        print(
            f"Templates: "
            f"{profile_info['template_count']}"
        )

        result = validate_dataset(
            entry,
            recognizer
        )

        result["recognition_profile"] = (
            profile_name
        )

        dataset_reports.append(result)

        summary = result["summary"]

        merge_counters(
            overall_counters,
            summary
        )

        if dataset_type not in counters_by_type:

            counters_by_type[dataset_type] = (
                create_counters()
            )

        merge_counters(
            counters_by_type[dataset_type],
            summary
        )

        if summary["passed"]:

            passed_datasets += 1

    # ----------------------------------------------
    # CALCULATE SUMMARY
    # ----------------------------------------------

    elapsed = (
        time.perf_counter() - start_time
    )

    overall_summary = calculate_metrics(
        overall_counters
    )

    overall_summary["total_datasets"] = (
        len(datasets)
    )

    overall_summary["passed_datasets"] = (
        passed_datasets
    )

    overall_summary["failed_datasets"] = (
        len(datasets) - passed_datasets
    )

    overall_summary["total_time_seconds"] = (
        round(elapsed, 3)
    )

    summaries_by_type = {
        dataset_type: calculate_metrics(counters)
        for dataset_type, counters
        in counters_by_type.items()
    }

    comparison = compare_baseline(
        summaries_by_type
    )

    # ----------------------------------------------
    # SAVE REPORT
    # ----------------------------------------------

    report = {
        "validation_version": 2,
        "profiles": profile_information,
        "summary": overall_summary,
        "summary_by_type": summaries_by_type,
        "baseline_comparison": comparison,
        "datasets": dataset_reports
    }

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8"
    )

    # ----------------------------------------------
    # PRINT FINAL SUMMARY
    # ----------------------------------------------

    print("\n" + "=" * 75)
    print("UNIFIED VALIDATION SUMMARY")
    print("=" * 75)

    print(
        json.dumps(
            overall_summary,
            indent=4
        )
    )

    print("\nRESULTS BY DATASET TYPE")

    for dataset_type, summary in (
        summaries_by_type.items()
    ):

        print(f"\nType: {dataset_type}")

        print(
            f"Correct cards: "
            f"{summary['correct_cards']}/"
            f"{summary['occupied_slots']}"
        )

        print_percentage(
            "Rank accuracy",
            summary["rank_accuracy"]
        )

        print_percentage(
            "Suit accuracy",
            summary["suit_accuracy"]
        )

        print_percentage(
            "Card accuracy",
            summary["card_accuracy"]
        )

    print_comparison(comparison)

    print(
        f"\nLoaded profiles: "
        f"{manager.loaded_profiles}"
    )

    print(
        f"Passed datasets: "
        f"{passed_datasets}/{len(datasets)}"
    )

    print(
        f"Total execution time: "
        f"{elapsed:.3f} seconds"
    )

    print(f"\nReport saved: {REPORT_FILE}")

    if overall_summary["passed"]:

        print("\nFINAL RESULT: ALL DATASETS PASSED")

        return 0

    print(
        "\nFINAL RESULT: "
        "VALIDATION COMPLETED WITH FAILURES"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
