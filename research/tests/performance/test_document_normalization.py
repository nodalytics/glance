
import json
import sys
import time

from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT))


from document_research.text_normalizer import (
    DocumentTextNormalizer,
)

from validate_lightweight_ocr import (
    create_document,
)


def main():

    report_path = (
        ROOT
        / "test_output"
        / "performance"
        / "optimized_document_engine.json"
    )

    report = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    results = []

    for item in report["results"]:

        _, expected = create_document(
            item["document"]
        )

        raw = item["recognized_text"]

        start = time.perf_counter_ns()

        formatted = (
            DocumentTextNormalizer.normalize_lines(
                raw
            )
        )

        normalization_ms = (
            time.perf_counter_ns() - start
        ) / 1_000_000

        raw_match = (
            Counter(raw) == Counter(expected)
        )

        formatted_match = (
            Counter(formatted) == Counter(expected)
        )

        ordered_match = (
            formatted == expected
        )

        results.append({
            "document": item["document"],
            "run": item["run"],
            "raw_match": raw_match,
            "formatted_match": formatted_match,
            "ordered_match": ordered_match,
            "normalization_ms": normalization_ms,
            "raw_text": raw,
            "formatted_text": formatted,
            "expected_text": expected,
        })

        print(
            f"{item['document']} | "
            f"Run {item['run']} | "
            f"Match: {formatted_match} | "
            f"Ordered: {ordered_match} | "
            f"{normalization_ms:.6f} ms"
        )

    total = len(results)

    summary = {
        "total_runs": total,

        "raw_exact_matches": sum(
            r["raw_match"] for r in results
        ),

        "formatted_exact_matches": sum(
            r["formatted_match"] for r in results
        ),

        "ordered_exact_matches": sum(
            r["ordered_match"] for r in results
        ),

        "formatted_failures": sum(
            not r["formatted_match"]
            for r in results
        ),

        "mean_normalization_ms": (
            sum(
                r["normalization_ms"]
                for r in results
            ) / max(total, 1)
        ),
    }

    output = (
        ROOT
        / "test_output"
        / "performance"
        / "document_normalization_validation.json"
    )

    output.write_text(
        json.dumps(
            {
                "summary": summary,
                "results": results,
            },
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nFINAL SUMMARY")

    print(
        json.dumps(summary, indent=4)
    )

    print(f"\nReport saved: {output}")

    return 0 if (
        total > 0
        and summary["formatted_failures"] == 0
        and summary["ordered_exact_matches"] == total
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
