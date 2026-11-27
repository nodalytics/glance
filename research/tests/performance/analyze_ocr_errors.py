
import json
import re

from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    ROOT / "test_output" / "performance"
)

INPUT_FILE = (
    OUTPUT_DIR
    / "lightweight_ocr_validation.json"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "ocr_error_analysis.json"
)


def normalize(text):
    return " ".join(
        text.lower().split()
    )


def normalize_without_whitespace(text):
    return re.sub(
        r"\s+",
        "",
        text.lower(),
    )


def levenshtein(source, target):

    previous = list(
        range(len(target) + 1)
    )

    for i, source_char in enumerate(
        source, start=1
    ):

        current = [i]

        for j, target_char in enumerate(
            target, start=1
        ):

            insertion = current[j - 1] + 1

            deletion = previous[j] + 1

            substitution = (
                previous[j - 1]
                + (source_char != target_char)
            )

            current.append(
                min(
                    insertion,
                    deletion,
                    substitution,
                )
            )

        previous = current

    return previous[-1]


def analyze_document(document):

    accuracy = document["accuracy"]

    missing = accuracy.get(
        "missing_lines", []
    )

    unexpected = accuracy.get(
        "unexpected_lines", []
    )

    original_matches = accuracy[
        "matched_count"
    ]

    expected_count = accuracy[
        "expected_count"
    ]

    missing_compact = Counter(
        normalize_without_whitespace(text)
        for text in missing
    )

    unexpected_compact = Counter(
        normalize_without_whitespace(text)
        for text in unexpected
    )

    formatting_matches = sum(
        (
            missing_compact
            & unexpected_compact
        ).values()
    )

    adjusted_matches = (
        original_matches
        + formatting_matches
    )

    possible_errors = []

    for expected in missing:

        candidates = []

        for recognized in unexpected:

            expected_normalized = normalize(
                expected
            )

            recognized_normalized = normalize(
                recognized
            )

            distance = levenshtein(
                expected_normalized,
                recognized_normalized,
            )

            denominator = max(
                len(expected_normalized),
                len(recognized_normalized),
                1,
            )

            similarity = (
                1 - distance / denominator
            )

            candidates.append({
                "recognized": recognized,
                "edit_distance": distance,
                "similarity_percent": round(
                    similarity * 100,
                    3,
                ),
            })

        candidates.sort(
            key=lambda item:
                item["similarity_percent"],
            reverse=True,
        )

        possible_errors.append({
            "expected": expected,

            "closest_candidate": (
                candidates[0]
                if candidates
                else None
            ),
        })

    return {
        "document": document["document"],

        "expected_lines": expected_count,

        "recognized_lines": accuracy[
            "recognized_count"
        ],

        "original_matches": original_matches,

        "formatting_only_matches":
            formatting_matches,

        "adjusted_matches": adjusted_matches,

        "remaining_unmatched_lines": (
            expected_count
            - adjusted_matches
        ),

        "adjusted_recall_percent": round(
            adjusted_matches
            / expected_count
            * 100,
            3,
        ) if expected_count else 0,

        "possible_errors": possible_errors,
    }


def analyze_model(configuration):

    documents = [
        analyze_document(document)

        for document in configuration.get(
            "documents", []
        )
    ]

    expected = sum(
        item["expected_lines"]
        for item in documents
    )

    original = sum(
        item["original_matches"]
        for item in documents
    )

    formatting = sum(
        item["formatting_only_matches"]
        for item in documents
    )

    adjusted = original + formatting

    return {
        "model": configuration["model"],

        "summary": {
            "expected_lines": expected,

            "original_matches": original,

            "formatting_only_matches":
                formatting,

            "adjusted_matches": adjusted,

            "remaining_unmatched_lines": (
                expected - adjusted
            ),

            "original_recall_percent": round(
                original / expected * 100,
                3,
            ) if expected else 0,

            "adjusted_recall_percent": round(
                adjusted / expected * 100,
                3,
            ) if expected else 0,
        },

        "documents": documents,
    }


def main():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Missing validation report: "
            f"{INPUT_FILE}"
        )

    source = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    report = {
        "source": INPUT_FILE.name,

        "models": [
            analyze_model(configuration)

            for configuration in source[
                "configurations"
            ]

            if configuration.get("success")
        ],
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        )
    )

    print(
        f"\nReport saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
