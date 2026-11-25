
import sys
import json
import time
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from test_rank_diagnostics import (
    create_variants,
    recognize_variant
)

from poker_apis.vision.enhanced_simulator_recognition import (
    EnhancedSimulatorCardRecognizer
)


DATASET_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/independent_v1"
)

TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

BASELINE_FILE = (
    PROJECT_ROOT
    / "test_output/baselines/independent_recognition_v1.json"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output/rank_conflict"
)


def main():

    print("=" * 75)
    print("OFFLINE SYNTHETIC RANK CONFLICT DIAGNOSTICS")
    print("=" * 75)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    baseline = json.loads(
        BASELINE_FILE.read_text(
            encoding="utf-8-sig"
        )
    )

    failures = baseline["failures"]

    if not failures:

        print("No failed images found.")

        return

    recognizer = EnhancedSimulatorCardRecognizer(
        suit_template_dir=TEMPLATE_DIR
    )

    report_results = []

    total_start = time.perf_counter()

    for failure in failures:

        filename = failure["file"]

        expected = failure["expected"]

        image_path = (
            DATASET_DIR / "cards" / filename
        )

        image = cv2.imread(str(image_path))

        if image is None:

            raise FileNotFoundError(
                f"Cannot load: {image_path}"
            )

        print("\n" + "-" * 75)

        print(f"Image: {filename}")

        print(
            f"Expected: "
            f"{expected['rank']} of "
            f"{expected['suit']}"
        )

        print("\nPREVIOUS PREDICTION")

        print(
            json.dumps(
                failure["actual"],
                indent=4
            )
        )

        actual = recognizer.recognize_card(
            image
        )

        print("\nCURRENT PREDICTION")

        print(json.dumps(actual, indent=4))

        variants = create_variants(image)

        variant_results = {}

        correct_variants = 0
        wrong_variants = 0
        rejected_variants = 0

        print("\nDEDICATED RANK VERIFICATION")

        for name, variant in variants.items():

            debug_path = (
                OUTPUT_DIR
                / f"{image_path.stem}_{name}.png"
            )

            if not cv2.imwrite(
                str(debug_path),
                variant
            ):

                raise IOError(
                    f"Cannot save: {debug_path}"
                )

            prediction = recognize_variant(
                recognizer.ocr,
                variant
            )

            if not prediction["accepted"]:

                status = "REJECTED"

                rejected_variants += 1

            elif (
                prediction["rank"]
                == expected["rank"]
            ):

                status = "PASS"

                correct_variants += 1

            else:

                status = "WRONG"

                wrong_variants += 1

            variant_results[name] = {
                **prediction,
                "status": status
            }

            print(
                f"{status:10} | "
                f"{name:20} | "
                f"Rank: "
                f"{str(prediction['rank']):4} | "
                f"Confidence: "
                f"{prediction['confidence']:.6f}"
            )

        report_results.append({
            "file": filename,
            "expected": expected,
            "previous_prediction": (
                failure["actual"]
            ),
            "current_prediction": actual,
            "correct_variants": correct_variants,
            "wrong_variants": wrong_variants,
            "rejected_variants": rejected_variants,
            "variants": variant_results
        })

    summary = {
        "failed_images_tested": len(failures),
        "correct_variant_predictions": sum(
            item["correct_variants"]
            for item in report_results
        ),
        "wrong_variant_predictions": sum(
            item["wrong_variants"]
            for item in report_results
        ),
        "rejected_variant_predictions": sum(
            item["rejected_variants"]
            for item in report_results
        ),
        "total_time_seconds": round(
            time.perf_counter() - total_start,
            4
        )
    }

    report = {
        "summary": summary,
        "results": report_results
    }

    output_file = (
        OUTPUT_DIR / "rank_conflict_report.json"
    )

    output_file.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("RANK CONFLICT SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print(f"\nReport saved: {output_file}")


if __name__ == "__main__":
    main()
