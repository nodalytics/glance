
import json
import statistics
import sys

from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT))


from document_research.optimized_ocr import (
    OptimizedDocumentOCR,
)

from validate_lightweight_ocr import (
    create_document,
    DOCUMENTS,
)


def main():

    print("=" * 60)
    print("OPTIMIZED DOCUMENT OCR VALIDATION")
    print("=" * 60)

    engine = OptimizedDocumentOCR()

    print(
        f"Initialization: "
        f"{engine.initialization_ms:.3f} ms"
    )

    image, expected = create_document(
        "standard"
    )

    cold = engine.recognize(
        image,
        expected,
    )

    print(
        "Cold inference: "
        f"{cold['timings']['total_request_ms']:.3f} ms"
    )

    results = []

    for name in DOCUMENTS:

        image, expected = create_document(name)

        for run in range(3):

            result = engine.recognize(
                image,
                expected,
                preprocessing="gaussian",
            )

            result["document"] = name
            result["run"] = run + 1

            results.append(result)

            latency = result["timings"][
                "total_request_ms"
            ]

            recall = result["accuracy"][
                "adjusted"
            ]["recall_percent"]

            print(
                f"{name} | "
                f"Run {run + 1} | "
                f"{latency:.3f} ms | "
                f"Recall: {recall:.3f}% | "
                f"{result['validation_status']}"
            )

    latencies = [
        item["timings"]["total_request_ms"]
        for item in results
    ]

    normalized_passes = sum(
        item["accuracy"]["adjusted"]["exact_match"]
        for item in results
    )

    strict_passes = sum(
        item["accuracy"]["strict"]["exact_match"]
        for item in results
    )

    literal_passes = sum(
        item["accuracy"]["literal_line_match"]
        for item in results
    )

    summary = {
        "total_runs": len(results),

        "initialization_ms": round(
            engine.initialization_ms, 3
        ),

        "cold_request_ms": cold["timings"][
            "total_request_ms"
        ],

        "warm_mean_ms": round(
            statistics.mean(latencies), 3
        ),

        "warm_median_ms": round(
            statistics.median(latencies), 3
        ),

        "warm_p95_ms": round(
            float(np.percentile(latencies, 95)),
            3,
        ),

        "warm_min_ms": round(
            min(latencies), 3
        ),

        "warm_max_ms": round(
            max(latencies), 3
        ),

        "normalized_passes": normalized_passes,

        "strict_passes": strict_passes,

        "literal_passes": literal_passes,

        "normalized_failures": (
            len(results) - normalized_passes
        ),

        "under_1000ms_runs": sum(
            value < 1000
            for value in latencies
        ),

        "under_200ms_runs": sum(
            value < 200
            for value in latencies
        ),

        "normalized_accuracy_target_met": (
            normalized_passes == len(results)
        ),

        "mean_latency_target_met": (
            statistics.mean(latencies) < 1000
        ),
    }

    report = {
        "summary": summary,
        "cold_run": cold,
        "results": results,
    }

    output = (
        ROOT
        / "test_output"
        / "performance"
        / "optimized_document_engine.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nFINAL SUMMARY")

    print(
        json.dumps(
            summary,
            indent=4,
        )
    )

    print(f"\nReport saved: {output}")

    return 0 if (
        summary["normalized_accuracy_target_met"]
        and summary["mean_latency_target_met"]
    ) else 1


if __name__ == "__main__":

    sys.exit(main())
