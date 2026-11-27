
import importlib.util
import json
import platform
import sys

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_FILE = (
    ROOT
    / "test_output"
    / "performance"
    / "inference_runtime_inspection.json"
)

CACHE_ROOT = (
    Path.home()
    / ".paddlex"
    / "official_models"
)

MODELS = [
    "PP-OCRv6_tiny_det",
    "PP-OCRv6_tiny_rec",
    "PP-OCRv6_small_det",
    "PP-OCRv6_small_rec",
    "PP-OCRv6_medium_det",
    "PP-OCRv6_medium_rec",
]

PACKAGES = [
    "paddlepaddle",
    "paddleocr",
    "paddlex",
    "onnx",
    "onnxruntime",
    "onnxruntime-directml",
    "openvino",
    "paddle2onnx",
    "numpy",
    "protobuf",
    "opencv-python",
    "opencv-contrib-python",
    "opencv-python-headless",
]


def package_version(name):

    try:
        return version(name)

    except Exception:
        return None


def module_available(name):

    try:
        return (
            importlib.util.find_spec(name)
            is not None
        )

    except Exception:
        return False


def inspect_model(model_name):

    directory = CACHE_ROOT / model_name

    result = {
        "model": model_name,
        "exists": directory.exists(),
        "files": [],
        "formats": {},
        "total_size_mib": 0,
    }

    if not directory.exists():
        return result

    total_bytes = 0

    for file in sorted(
        directory.rglob("*")
    ):

        if not file.is_file():
            continue

        size = file.stat().st_size

        total_bytes += size

        result["files"].append({
            "name": str(
                file.relative_to(directory)
            ),

            "extension": file.suffix.lower(),

            "size_mib": round(
                size / (1024 ** 2),
                4,
            ),
        })

    extensions = {
        item["extension"]
        for item in result["files"]
    }

    result["formats"] = {
        "paddle_parameters":
            ".pdiparams" in extensions,

        "paddle_legacy_graph":
            ".pdmodel" in extensions,

        "json_files":
            ".json" in extensions,

        "onnx_graph":
            ".onnx" in extensions,

        "openvino_xml":
            ".xml" in extensions,

        "binary_files":
            ".bin" in extensions,
    }

    result["total_size_mib"] = round(
        total_bytes / (1024 ** 2),
        3,
    )

    return result


def inspect_paddlex_runtime_support():

    result = {
        "package_found": False,
        "runtime_references": {},
    }

    spec = importlib.util.find_spec(
        "paddlex"
    )

    if spec is None:
        return result

    if not spec.submodule_search_locations:
        return result

    package_root = Path(
        next(
            iter(
                spec.submodule_search_locations
            )
        )
    )

    result["package_found"] = True

    keywords = [
        "onnxruntime",
        "openvino",
        "paddle2onnx",
        "paddle_static",
        "enable_hpi",
    ]

    references = {
        keyword: []
        for keyword in keywords
    }

    for file in package_root.rglob("*.py"):

        try:

            content = file.read_text(
                encoding="utf-8",
                errors="ignore",
            ).lower()

        except OSError:
            continue

        for keyword in keywords:

            if keyword in content:

                references[keyword].append(
                    str(
                        file.relative_to(
                            package_root
                        )
                    )
                )

    for keyword, files in references.items():

        result["runtime_references"][
            keyword
        ] = {
            "source_count": len(files),

            "example_sources": sorted(
                files
            )[:8],
        }

    return result


def main():

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "environment": {
            "python_version":
                platform.python_version(),

            "python_executable":
                sys.executable,

            "platform":
                platform.platform(),

            "architecture":
                platform.machine(),

            "virtual_environment": (
                sys.prefix != sys.base_prefix
            ),
        },

        "packages": {
            name: package_version(name)
            for name in PACKAGES
        },

        "runtime_modules": {
            name: module_available(name)

            for name in [
                "paddle",
                "onnx",
                "onnxruntime",
                "openvino",
                "paddle2onnx",
            ]
        },

        "cached_models": [
            inspect_model(model)
            for model in MODELS
        ],

        "paddlex_runtime_support": (
            inspect_paddlex_runtime_support()
        ),
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
