
import json
import statistics
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openvino as ov


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "test_output" / "performance"

MODEL_FILE = OUTPUT_DIR / "runtime_smoke_test.onnx"

OUTPUT_FILE = (
    OUTPUT_DIR / "openvino_device_verification.json"
)

WARMUP_RUNS = 10
BENCHMARK_RUNS = 100


def elapsed_ms(start):

    return (
        time.perf_counter_ns() - start
    ) / 1_000_000


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


def verify_device(core, model, device):

    result = {
        "device": device,
        "success": False,
    }

    try:

        result["device_name"] = core.get_property(
            device,
            "FULL_DEVICE_NAME",
        )

        start = time.perf_counter_ns()

        compiled_model = core.compile_model(
            model,
            device,
        )

        result["compilation_ms"] = round(
            elapsed_ms(start),
            6,
        )

        result["execution_devices"] = list(
            compiled_model.get_property(
                "EXECUTION_DEVICES"
            )
        )

        output_port = compiled_model.output(0)

        data = np.array(
            [[1.0, 2.0, 3.0, 4.0]],
            dtype=np.float32,
        )

        expected = data * 2 + 3

        def inference():

            outputs = compiled_model([data])

            return outputs[output_port]

        start = time.perf_counter_ns()

        actual = inference()

        result["first_inference_ms"] = round(
            elapsed_ms(start),
            6,
        )

        result["expected_output"] = (
            expected.tolist()
        )

        result["actual_output"] = (
            actual.tolist()
        )

        result["numerically_correct"] = bool(
            np.allclose(
                actual,
                expected,
                rtol=1e-5,
                atol=1e-5,
            )
        )

        for _ in range(WARMUP_RUNS):

            inference()

        timings = []

        for _ in range(BENCHMARK_RUNS):

            start = time.perf_counter_ns()

            inference()

            timings.append(
                elapsed_ms(start)
            )

        result["benchmark"] = {
            "warmup_runs": WARMUP_RUNS,
            "benchmark_runs": BENCHMARK_RUNS,

            "mean_ms": round(
                statistics.mean(timings),
                6,
            ),

            "median_ms": round(
                statistics.median(timings),
                6,
            ),

            "minimum_ms": round(
                min(timings),
                6,
            ),

            "maximum_ms": round(
                max(timings),
                6,
            ),

            "p95_ms": round(
                float(
                    np.percentile(timings, 95)
                ),
                6,
            ),

            "p99_ms": round(
                float(
                    np.percentile(timings, 99)
                ),
                6,
            ),

            "standard_deviation_ms": round(
                statistics.pstdev(timings),
                6,
            ),
        }

        result["success"] = (
            result["numerically_correct"]
        )

    except Exception as error:

        result["error_type"] = (
            type(error).__name__
        )

        result["error"] = str(error)

    return result


def main():

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "python_executable": sys.executable,

        "openvino_version": ov.__version__,

        "model": MODEL_FILE.name,

        "available_devices": [],

        "results": [],

        "success": False,
    }

    if not MODEL_FILE.is_file():

        report["error"] = (
            f"Model file not found: {MODEL_FILE}"
        )

        save_report(report)

        print(report["error"])

        return 1

    try:

        core = ov.Core()

        report["available_devices"] = list(
            core.available_devices
        )

        print("=" * 60)
        print("OPENVINO DEVICE VERIFICATION")
        print("=" * 60)

        print(
            "Available devices:",
            report["available_devices"],
        )

        start = time.perf_counter_ns()

        model = core.read_model(
            str(MODEL_FILE)
        )

        report["model_loading_ms"] = round(
            elapsed_ms(start),
            6,
        )

        for device in report["available_devices"]:

            print(
                f"\nTesting device: {device}"
            )

            result = verify_device(
                core,
                model,
                device,
            )

            report["results"].append(result)

            status = (
                "PASS"
                if result["success"]
                else "FAIL"
            )

            print(
                f"{device}: {status}"
            )

            if result["success"]:

                print(
                    "Mean inference:",
                    result["benchmark"]["mean_ms"],
                    "ms",
                )

            else:

                print(
                    result.get(
                        "error",
                        "Numerical verification failed",
                    )
                )

            save_report(report)

        successful = [
            result
            for result in report["results"]
            if result["success"]
        ]

        ranking = sorted(
            successful,
            key=lambda result: (
                result["benchmark"]["mean_ms"]
            ),
        )

        report["summary"] = {
            "devices_tested": len(
                report["results"]
            ),

            "devices_passed": len(successful),

            "devices_failed": (
                len(report["results"])
                - len(successful)
            ),

            "ranking": [
                {
                    "device": result["device"],

                    "mean_ms": (
                        result["benchmark"]["mean_ms"]
                    ),

                    "p95_ms": (
                        result["benchmark"]["p95_ms"]
                    ),
                }
                for result in ranking
            ],
        }

        report["success"] = (
            bool(report["results"])
            and all(
                result["success"]
                for result in report["results"]
            )
        )

    except Exception as error:

        report["error_type"] = (
            type(error).__name__
        )

        report["error"] = str(error)

    finally:

        save_report(report)

    print("\nFINAL DEVICE VERIFICATION REPORT")

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
