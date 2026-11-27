
import importlib
import json
import platform
import statistics
import sys
import time

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    ROOT / "test_output" / "performance"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "inference_runtime_verification.json"
)

MODEL_FILE = (
    OUTPUT_DIR
    / "runtime_smoke_test.onnx"
)

WARMUP_RUNS = 5
BENCHMARK_RUNS = 30


def elapsed_ms(start):

    return round(
        (time.perf_counter_ns() - start)
        / 1_000_000,
        6,
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


def verify_import(module_name, package_name):

    start = time.perf_counter_ns()

    try:

        importlib.import_module(module_name)

        return {
            "success": True,
            "version": version(package_name),
            "import_ms": elapsed_ms(start),
        }

    except Exception as error:

        return {
            "success": False,
            "error_type": type(error).__name__,
            "error": str(error),
        }


def create_test_model():

    import onnx

    from onnx import (
        TensorProto,
        helper,
    )

    input_tensor = helper.make_tensor_value_info(
        "input",
        TensorProto.FLOAT,
        [1, 4],
    )

    output_tensor = helper.make_tensor_value_info(
        "output",
        TensorProto.FLOAT,
        [1, 4],
    )

    multiplier = helper.make_tensor(
        "multiplier",
        TensorProto.FLOAT,
        [1],
        [2.0],
    )

    bias = helper.make_tensor(
        "bias",
        TensorProto.FLOAT,
        [1],
        [3.0],
    )

    nodes = [
        helper.make_node(
            "Mul",
            ["input", "multiplier"],
            ["multiplied"],
        ),

        helper.make_node(
            "Add",
            ["multiplied", "bias"],
            ["output"],
        ),
    ]

    graph = helper.make_graph(
        nodes,
        "runtime_smoke_test",
        [input_tensor],
        [output_tensor],
        initializer=[
            multiplier,
            bias,
        ],
    )

    model = helper.make_model(
        graph,
        producer_name="runtime_research",
        opset_imports=[
            helper.make_opsetid("", 13)
        ],
    )

    model.ir_version = 8

    onnx.checker.check_model(model)

    onnx.save(
        model,
        str(MODEL_FILE),
    )

    return {
        "success": True,
        "filename": MODEL_FILE.name,
        "opset": 13,
        "ir_version": 8,
        "file_size_bytes": MODEL_FILE.stat().st_size,
    }


def benchmark_callable(function):

    for _ in range(WARMUP_RUNS):
        function()

    timings = []

    for _ in range(BENCHMARK_RUNS):

        start = time.perf_counter_ns()

        function()

        timings.append(
            elapsed_ms(start)
        )

    return {
        "warmup_runs": WARMUP_RUNS,
        "benchmark_runs": BENCHMARK_RUNS,

        "mean_ms": round(
            statistics.mean(timings), 6
        ),

        "median_ms": round(
            statistics.median(timings), 6
        ),

        "minimum_ms": min(timings),
        "maximum_ms": max(timings),
    }


def verify_onnxruntime():

    import numpy as np
    import onnxruntime as ort

    result = {
        "success": False,
    }

    try:

        result["available_providers"] = (
            ort.get_available_providers()
        )

        start = time.perf_counter_ns()

        session = ort.InferenceSession(
            str(MODEL_FILE),
            providers=[
                "CPUExecutionProvider"
            ],
        )

        result["initialization_ms"] = (
            elapsed_ms(start)
        )

        result["active_providers"] = (
            session.get_providers()
        )

        data = np.array(
            [[1.0, 2.0, 3.0, 4.0]],
            dtype=np.float32,
        )

        expected = data * 2 + 3

        def inference():

            return session.run(
                ["output"],
                {"input": data},
            )[0]

        actual = inference()

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
                rtol=1e-6,
                atol=1e-6,
            )
        )

        result["benchmark"] = (
            benchmark_callable(inference)
        )

        result["success"] = (
            result["numerically_correct"]
        )

    except Exception as error:

        result["error_type"] = (
            type(error).__name__
        )

        result["error"] = str(error)

    return result


def verify_openvino():

    import numpy as np
    import openvino as ov

    result = {
        "success": False,
    }

    try:

        core = ov.Core()

        result["available_devices"] = list(
            core.available_devices
        )

        result["device_information"] = {}

        for device in core.available_devices:

            try:

                result["device_information"][
                    device
                ] = core.get_property(
                    device,
                    "FULL_DEVICE_NAME",
                )

            except Exception as error:

                result["device_information"][
                    device
                ] = str(error)

        start = time.perf_counter_ns()

        model = core.read_model(
            str(MODEL_FILE)
        )

        result["model_loading_ms"] = (
            elapsed_ms(start)
        )

        start = time.perf_counter_ns()

        compiled_model = core.compile_model(
            model,
            "CPU",
        )

        result["compilation_ms"] = (
            elapsed_ms(start)
        )

        output_port = compiled_model.output(0)

        data = np.array(
            [[1.0, 2.0, 3.0, 4.0]],
            dtype=np.float32,
        )

        expected = data * 2 + 3

        def inference():

            outputs = compiled_model(
                [data]
            )

            return outputs[output_port]

        actual = inference()

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
                rtol=1e-6,
                atol=1e-6,
            )
        )

        result["benchmark"] = (
            benchmark_callable(inference)
        )

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
        "success": False,
    }

    packages = {
        "numpy": "numpy",
        "onnx": "onnx",
        "onnxruntime": "onnxruntime",
        "openvino": "openvino",
        "paddle2onnx": "paddle2onnx",
        "onnxoptimizer": "onnxoptimizer",
        "polygraphy": "polygraphy",
        "google.protobuf": "protobuf",
    }

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

    if not all(
        item["success"]
        for item in report["imports"].values()
    ):

        print(
            "One or more package imports failed."
        )

        print(
            f"Report saved: {OUTPUT_FILE}"
        )

        return 1

    try:

        report["model"] = create_test_model()

        print("ONNX model validation: PASS")

        report["runtimes"]["onnxruntime"] = (
            verify_onnxruntime()
        )

        save_report(report)

        report["runtimes"]["openvino"] = (
            verify_openvino()
        )

        report["success"] = all(
            item["success"]
            for item in report["runtimes"].values()
        )

    except Exception as error:

        report["error_type"] = (
            type(error).__name__
        )

        report["error"] = str(error)

    finally:

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
