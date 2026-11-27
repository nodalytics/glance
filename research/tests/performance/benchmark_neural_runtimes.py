
import gc
import json
import statistics
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import openvino as ov

from onnx import (
    TensorProto,
    helper,
    numpy_helper,
)


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "test_output" / "performance"

OUTPUT_FILE = (
    OUTPUT_DIR / "neural_runtime_benchmark.json"
)

INPUT_SIZES = [64, 128, 256]

WARMUP_RUNS = 10
BENCHMARK_RUNS = 30

SEED = 42


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
        json.dumps(report, indent=4),
        encoding="utf-8",
    )


def create_model(size):

    rng = np.random.default_rng(SEED)

    weights_1 = rng.normal(
        0,
        0.05,
        size=(16, 3, 3, 3),
    ).astype(np.float32)

    weights_2 = rng.normal(
        0,
        0.05,
        size=(32, 16, 3, 3),
    ).astype(np.float32)

    bias_1 = np.zeros(
        16,
        dtype=np.float32,
    )

    bias_2 = np.zeros(
        32,
        dtype=np.float32,
    )

    initializers = [
        numpy_helper.from_array(
            weights_1, "weights_1"
        ),

        numpy_helper.from_array(
            weights_2, "weights_2"
        ),

        numpy_helper.from_array(
            bias_1, "bias_1"
        ),

        numpy_helper.from_array(
            bias_2, "bias_2"
        ),
    ]

    nodes = [

        helper.make_node(
            "Conv",
            ["input", "weights_1", "bias_1"],
            ["conv_1"],
            pads=[1, 1, 1, 1],
        ),

        helper.make_node(
            "Relu",
            ["conv_1"],
            ["relu_1"],
        ),

        helper.make_node(
            "Conv",
            ["relu_1", "weights_2", "bias_2"],
            ["conv_2"],
            pads=[1, 1, 1, 1],
        ),

        helper.make_node(
            "Relu",
            ["conv_2"],
            ["relu_2"],
        ),

        helper.make_node(
            "GlobalAveragePool",
            ["relu_2"],
            ["output"],
        ),
    ]

    graph = helper.make_graph(
        nodes,
        f"synthetic_cnn_{size}",

        [
            helper.make_tensor_value_info(
                "input",
                TensorProto.FLOAT,
                [1, 3, size, size],
            )
        ],

        [
            helper.make_tensor_value_info(
                "output",
                TensorProto.FLOAT,
                [1, 32, 1, 1],
            )
        ],

        initializer=initializers,
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

    path = (
        OUTPUT_DIR
        / f"synthetic_cnn_{size}.onnx"
    )

    onnx.save(model, str(path))

    return path


def create_input(size):

    rng = np.random.default_rng(SEED)

    return rng.random(
        (1, 3, size, size),
        dtype=np.float32,
    )


def benchmark(function):

    start = time.perf_counter_ns()

    output = np.array(
        function(),
        copy=True,
    )

    first_inference_ms = elapsed_ms(start)

    for _ in range(WARMUP_RUNS):

        function()

    timings = []

    for _ in range(BENCHMARK_RUNS):

        start = time.perf_counter_ns()

        function()

        timings.append(
            elapsed_ms(start)
        )

    metrics = {
        "first_inference_ms": round(
            first_inference_ms, 6
        ),

        "warmup_runs": WARMUP_RUNS,

        "benchmark_runs": BENCHMARK_RUNS,

        "mean_ms": round(
            statistics.mean(timings), 6
        ),

        "median_ms": round(
            statistics.median(timings), 6
        ),

        "minimum_ms": round(
            min(timings), 6
        ),

        "maximum_ms": round(
            max(timings), 6
        ),

        "p95_ms": round(
            float(np.percentile(timings, 95)),
            6,
        ),

        "p99_ms": round(
            float(np.percentile(timings, 99)),
            6,
        ),

        "standard_deviation_ms": round(
            statistics.pstdev(timings),
            6,
        ),
    }

    return output, metrics


def run_onnxruntime(model_path, data):

    start = time.perf_counter_ns()

    session = ort.InferenceSession(
        str(model_path),

        providers=[
            "CPUExecutionProvider"
        ],
    )

    initialization_ms = elapsed_ms(start)

    def inference():

        return session.run(
            ["output"],
            {"input": data},
        )[0]

    output, metrics = benchmark(inference)

    result = {
        "runtime": "onnxruntime_cpu",

        "execution_devices": (
            session.get_providers()
        ),

        "initialization_ms": round(
            initialization_ms, 6
        ),

        "benchmark": metrics,

        "success": True,
    }

    return output, result


def run_openvino(model_path, data, device):

    core = ov.Core()

    start = time.perf_counter_ns()

    model = core.read_model(
        str(model_path)
    )

    loading_ms = elapsed_ms(start)

    start = time.perf_counter_ns()

    compiled = core.compile_model(
        model,
        device,
        {
            "INFERENCE_PRECISION_HINT": "f32"
        },
    )

    compilation_ms = elapsed_ms(start)

    output_port = compiled.output(0)

    def inference():

        return compiled(
            [data]
        )[output_port]

    output, metrics = benchmark(inference)

    result = {
        "runtime": (
            f"openvino_{device.lower()}"
        ),

        "execution_devices": list(
            compiled.get_property(
                "EXECUTION_DEVICES"
            )
        ),

        "model_loading_ms": round(
            loading_ms, 6
        ),

        "compilation_ms": round(
            compilation_ms, 6
        ),

        "benchmark": metrics,

        "success": True,
    }

    return output, result


def compare_outputs(reference, actual):

    if reference.shape != actual.shape:

        return {
            "numerically_correct": False,

            "error": "Output shape mismatch",
        }

    difference = np.abs(
        reference - actual
    )

    return {
        "numerically_correct": bool(
            np.allclose(
                reference,
                actual,
                rtol=1e-3,
                atol=1e-5,
            )
        ),

        "maximum_absolute_error": float(
            np.max(difference)
        ),

        "mean_absolute_error": float(
            np.mean(difference)
        ),

        "output_shape": list(actual.shape),
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

        "python_executable": sys.executable,

        "versions": {
            "onnx": onnx.__version__,
            "onnxruntime": ort.__version__,
            "openvino": ov.__version__,
            "numpy": np.__version__,
        },

        "input_sizes": INPUT_SIZES,

        "workloads": [],

        "success": False,
    }

    print("=" * 60)
    print("SYNTHETIC NEURAL RUNTIME BENCHMARK")
    print("=" * 60)

    for size in INPUT_SIZES:

        print(f"\nINPUT SIZE: {size} x {size}")

        model_path = create_model(size)

        data = create_input(size)

        workload = {
            "input_size": size,

            "model": model_path.name,

            "model_size_bytes": (
                model_path.stat().st_size
            ),

            "results": [],
        }

        reference = None

        configurations = [
            "onnxruntime_cpu",
            "openvino_cpu",
            "openvino_gpu",
        ]

        for configuration in configurations:

            print(
                f"Testing {configuration}..."
            )

            try:

                if configuration == "onnxruntime_cpu":

                    output, result = run_onnxruntime(
                        model_path,
                        data,
                    )

                    reference = output.copy()

                    result["validation"] = {
                        "reference_runtime": True,

                        "finite_output": bool(
                            np.isfinite(output).all()
                        ),
                    }

                    result["success"] = (
                        result["validation"]
                        ["finite_output"]
                    )

                    if not result["success"]:

                        reference = None

                else:

                    device = (
                        "CPU"
                        if configuration == "openvino_cpu"
                        else "GPU"
                    )

                    output, result = run_openvino(
                        model_path,
                        data,
                        device,
                    )

                    if reference is not None:

                        result["validation"] = (
                            compare_outputs(
                                reference,
                                output,
                            )
                        )

                        result["success"] = (
                            result["validation"]
                            ["numerically_correct"]
                        )

                    else:

                        result["validation"] = {
                            "error": (
                                "Reference unavailable"
                            )
                        }

                        result["success"] = False

            except Exception as error:

                result = {
                    "runtime": configuration,

                    "success": False,

                    "error_type": (
                        type(error).__name__
                    ),

                    "error": str(error),
                }

            workload["results"].append(result)

            if result["success"]:

                print(
                    "PASS:",
                    result["benchmark"]["mean_ms"],
                    "ms",
                )

            else:

                print(
                    "FAIL:",
                    result.get(
                        "error",
                        "Validation failed",
                    ),
                )

            gc.collect()

        successful = [
            result
            for result in workload["results"]
            if result["success"]
        ]

        ranking = sorted(
            successful,

            key=lambda result: (
                result["benchmark"]["mean_ms"]
            ),
        )

        workload["ranking"] = [
            {
                "runtime": result["runtime"],

                "mean_ms": (
                    result["benchmark"]["mean_ms"]
                ),

                "p95_ms": (
                    result["benchmark"]["p95_ms"]
                ),
            }
            for result in ranking
        ]

        report["workloads"].append(workload)

        save_report(report)

    results = [
        result
        for workload in report["workloads"]
        for result in workload["results"]
    ]

    report["summary"] = {
        "total_tests": len(results),

        "passed_tests": sum(
            result["success"]
            for result in results
        ),

        "failed_tests": sum(
            not result["success"]
            for result in results
        ),
    }

    report["success"] = all(
        result["success"]
        for result in results
    )

    save_report(report)

    print("\nFINAL BENCHMARK REPORT")

    print(
        json.dumps(
            report,
            indent=4,
        )
    )

    print(
        f"\nReport saved: {OUTPUT_FILE}"
    )

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
