
import json
import re

from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version

import paddlex


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
    / "available_ocr_models.json"
)

PACKAGE_ROOT = Path(
    paddlex.__file__
).resolve().parent

CACHE_ROOT = (
    Path.home()
    / ".paddlex"
    / "official_models"
)

MODEL_PATTERN = re.compile(
    r"[A-Za-z0-9_-]*PP-OCRv[456]"
    r"[A-Za-z0-9_.-]*",
    re.IGNORECASE,
)


def get_package_version(name):

    try:
        return version(name)

    except Exception:
        return None


def inspect_cached_models():

    models = []

    if not CACHE_ROOT.exists():
        return models

    for directory in sorted(
        CACHE_ROOT.iterdir()
    ):

        if not directory.is_dir():
            continue

        if "ocr" not in directory.name.lower():
            continue

        total_bytes = 0

        for file in directory.rglob("*"):

            if file.is_file():
                total_bytes += file.stat().st_size

        models.append({
            "name": directory.name,

            "size_mib": round(
                total_bytes / (1024 ** 2),
                3,
            ),
        })

    return models


def inspect_package_models():

    discovered = {}

    supported_extensions = {
        ".py",
        ".yaml",
        ".yml",
        ".json",
    }

    for file in PACKAGE_ROOT.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in supported_extensions:
            continue

        try:

            content = file.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        except OSError:
            continue

        matches = MODEL_PATTERN.findall(
            content
        )

        for model in matches:

            model = model.rstrip(".")

            if not model.lower().endswith(
                ("_det", "_rec")
            ):
                continue

            relative_path = str(
                file.relative_to(
                    PACKAGE_ROOT
                )
            )

            discovered.setdefault(
                model,
                set(),
            ).add(relative_path)

    return [
        {
            "name": name,

            "type": (
                "detection"
                if name.lower().endswith("_det")
                else "recognition"
            ),

            "lightweight_candidate": any(
                keyword in name.lower()
                for keyword in (
                    "mobile",
                    "small",
                    "tiny",
                    "lite",
                )
            ),

            "source_count": len(sources),

            "example_sources": sorted(
                sources
            )[:3],
        }

        for name, sources in sorted(
            discovered.items()
        )
    ]


def main():

    discovered = inspect_package_models()

    lightweight = [
        model
        for model in discovered
        if model["lightweight_candidate"]
    ]

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "versions": {
            "paddlepaddle": get_package_version(
                "paddlepaddle"
            ),

            "paddleocr": get_package_version(
                "paddleocr"
            ),

            "paddlex": get_package_version(
                "paddlex"
            ),
        },

        "cached_models": (
            inspect_cached_models()
        ),

        "discovered_model_count": len(
            discovered
        ),

        "lightweight_candidate_count": len(
            lightweight
        ),

        "lightweight_candidates": lightweight,

        "all_discovered_models": discovered,
    }

    OUTPUT_FILE.parent.mkdir(
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
