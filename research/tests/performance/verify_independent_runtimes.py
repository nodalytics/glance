
import json
import platform
import sys

from datetime import datetime, timezone
from pathlib import Path

from verify_inference_runtimes import (
    verify_import,
    create_test_model,
    verify_onnxruntime,
    verify_openvino,
)


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "test_output" / "performance"

OUTPUT_FILE = (
    OUTPUT_DIR
    / "independent_runtime_verification.json"
)


def save_report(report):

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


def execute_test(function):

    try:

        return function()

    except Exception as error:

        return {
            "success": False,
            "error_type": type(error).__name__,
            "error": str(error),
        }


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        },

        "imports": {},
        "model": {},
        "runtimes": {},

        "converter_status": "deferred",

        "success": False,
    }

    packages = {
        "numpy": "numpy",
        "onnx": "onnx",
        "onnxruntime": "onnxruntime",
        "openvino": "openvino",
    }

    print("=" * 60)
    print("INDEPENDENT INFERENCE RUNTIME VERIFICATION")
    print("=" * 60)

    for module_name, package_name in packages.items():

        result = verify_import(
            module_name,
            package_name,
        )

        report["imports"][module_name] = result

        status = (
            "PASS"
            if result["success"]
            else "FAIL"
        )

        print(
            f"Import {module_name}: {status}"
        )

    save_report(report)

    required_imports = [
        "numpy",
        "onnx",
    ]

    if not all(
        report["imports"][name]["success"]
        for name in required_imports
    ):

        print("Required model dependencies failed.")

        return 1

    report["model"] = execute_test(
        create_test_model
    )

    save_report(report)

    if not report["model"]["success"]:

        print("Model creation failed.")

        return 1

    print("ONNX model creation: PASS")

    runtime_tests = {
        "onnxruntime": verify_onnxruntime,
        "openvino": verify_openvino,
    }

    for runtime_name, test_function in runtime_tests.items():

        print(
            f"\nTesting {runtime_name}..."
        )

        if not report["imports"][runtime_name]["success"]:

            result = {
                "success": False,
                "error": "Runtime import failed",
            }

        else:

            result = execute_test(
                test_function
            )

        report["runtimes"][runtime_name] = result

        status = (
            "PASS"
            if result["success"]
            else "FAIL"
        )

        print(
            f"{runtime_name}: {status}"
        )

        save_report(report)

    report["success"] = all(
        result["success"]
        for result in report["runtimes"].values()
    )

    report["summary"] = {
        "runtime_count": len(
            report["runtimes"]
        ),

        "passed_runtimes": sum(
            result["success"]
            for result in report["runtimes"].values()
        ),

        "failed_runtimes": sum(
            not result["success"]
            for result in report["runtimes"].values()
        ),

        "converter_required": False,
    }

    save_report(report)

    print("\nFINAL VERIFICATION REPORT")

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

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
