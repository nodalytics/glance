
import sys
import json
import time
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from poker_apis.vision.ocr import PokerOCR


REPORT_PATH = (
    PROJECT_ROOT
    / "test_output/baselines/heldout_validation_v1.json"
)

CARDS_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/heldout_v1/cards"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output/rank_diagnostics"
)

VALID_RANKS = {
    "A", "K", "Q", "J", "10",
    "9", "8", "7", "6",
    "5", "4", "3", "2"
}

CONFIDENCE_THRESHOLD = 0.75


def normalize_rank(text):

    text = text.strip().upper().replace(" ", "")

    aliases = {
        "T": "10",
        "1O": "10",
        "IO": "10"
    }

    text = aliases.get(text, text)

    if text in VALID_RANKS:
        return text

    return None


def extract_rank_region(image):

    height, width = image.shape[:2]

    x1 = int(width * 0.03)
    y1 = int(height * 0.01)

    x2 = int(width * 0.43)
    y2 = int(height * 0.24)

    return image[y1:y2, x1:x2]


def add_border(image):

    color = (
        (255, 255, 255)
        if image.ndim == 3
        else 255
    )

    return cv2.copyMakeBorder(
        image,
        20,
        20,
        20,
        20,
        cv2.BORDER_CONSTANT,
        value=color
    )


def create_variants(image):

    region = extract_rank_region(image)

    if region.size == 0:
        raise ValueError("Rank region is empty.")

    enlarged = cv2.resize(
        region,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC
    )

    gray = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2GRAY
    )

    blurred = cv2.GaussianBlur(
        gray,
        (0, 0),
        1.0
    )

    sharpened = cv2.addWeighted(
        gray,
        1.8,
        blurred,
        -0.8,
        0
    )

    _, otsu = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    _, sharpened_otsu = cv2.threshold(
        sharpened,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10
    )

    return {
        "original_rank": add_border(enlarged),
        "grayscale": add_border(gray),
        "sharpened": add_border(sharpened),
        "otsu": add_border(otsu),
        "sharpened_otsu": add_border(
            sharpened_otsu
        ),
        "adaptive": add_border(adaptive)
    }


def recognize_variant(ocr, image):

    if image.ndim == 2:

        image = cv2.cvtColor(
            image,
            cv2.COLOR_GRAY2BGR
        )

    results = ocr.extract(image)

    detections = []
    candidates = []

    for item in results:

        rank = normalize_rank(item.text)

        detection = {
            "raw_text": str(item.text),
            "rank": rank,
            "confidence": float(item.confidence)
        }

        detections.append(detection)

        if rank is not None:
            candidates.append(detection)

    best = max(
        candidates,
        key=lambda item: item["confidence"],
        default=None
    )

    accepted = (
        best is not None
        and best["confidence"] >= CONFIDENCE_THRESHOLD
    )

    return {
        "rank": best["rank"] if accepted else None,
        "confidence": (
            best["confidence"] if best else 0.0
        ),
        "accepted": accepted,
        "detections": detections
    }


def main():

    print("=" * 75)
    print("OFFLINE RANK RECOGNITION DIAGNOSTICS")
    print("=" * 75)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    report = json.loads(
        REPORT_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    failures = report["failures"]

    print(f"Failed images: {len(failures)}")

    ocr = PokerOCR()

    results = []
    technique_statistics = {}

    recovered_images = 0

    total_start = time.perf_counter()

    for index, failure in enumerate(failures, 1):

        filename = failure["file"]

        expected_rank = failure["expected"]["rank"]

        image_path = CARDS_DIR / filename

        image = cv2.imread(str(image_path))

        if image is None:

            raise FileNotFoundError(
                f"Cannot load: {image_path}"
            )

        print("\n" + "-" * 75)

        print(
            f"[{index}/{len(failures)}] "
            f"{filename}"
        )

        print(f"Expected rank: {expected_rank}")

        variants = create_variants(image)

        image_results = {}

        recovered = False

        for name, variant in variants.items():

            debug_path = (
                OUTPUT_DIR
                / f"{image_path.stem}_{name}.png"
            )

            cv2.imwrite(
                str(debug_path),
                variant
            )

            start = time.perf_counter()

            actual = recognize_variant(
                ocr,
                variant
            )

            elapsed = time.perf_counter() - start

            correct = (
                actual["rank"] == expected_rank
                and actual["accepted"]
            )

            wrong = (
                actual["accepted"]
                and actual["rank"] != expected_rank
            )

            status = (
                "PASS" if correct
                else "WRONG" if wrong
                else "REJECTED"
            )

            if name not in technique_statistics:

                technique_statistics[name] = {
                    "tested": 0,
                    "correct": 0,
                    "wrong": 0,
                    "rejected": 0
                }

            statistics = technique_statistics[name]

            statistics["tested"] += 1

            if correct:

                statistics["correct"] += 1

                recovered = True

            elif wrong:

                statistics["wrong"] += 1

            else:

                statistics["rejected"] += 1

            image_results[name] = {
                **actual,
                "status": status,
                "time_seconds": round(elapsed, 4)
            }

            print(
                f"{status:8} | "
                f"{name:20} | "
                f"Rank: {str(actual['rank']):4} | "
                f"Confidence: "
                f"{actual['confidence']:.4f}"
            )

        if recovered:
            recovered_images += 1

        results.append({
            "file": filename,
            "expected_rank": expected_rank,
            "recoverable": recovered,
            "variants": image_results
        })

    summary = {
        "failed_images_tested": len(failures),
        "recoverable_images": recovered_images,
        "unresolved_images": (
            len(failures) - recovered_images
        ),
        "recovery_rate": (
            recovered_images / len(failures)
            if failures else 0.0
        ),
        "total_time_seconds": round(
            time.perf_counter() - total_start,
            4
        )
    }

    final_report = {
        "summary": summary,
        "technique_statistics": technique_statistics,
        "results": results
    }

    output_path = (
        OUTPUT_DIR / "rank_diagnostic_report.json"
    )

    output_path.write_text(
        json.dumps(
            final_report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print("\nPREPROCESSING TECHNIQUE RESULTS")

    print(
        json.dumps(
            technique_statistics,
            indent=4
        )
    )

    print(f"\nReport saved: {output_path}")


if __name__ == "__main__":
    main()
