
import json
import sys

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PERFORMANCE_DIR = (
    ROOT / "test_output" / "performance"
)

OUTPUT_FILE = (
    PERFORMANCE_DIR / "performance_feasibility_report.json"
)

MARKDOWN_FILE = (
    PERFORMANCE_DIR / "performance_feasibility_report.md"
)


REPORT_FILES = {
    "hardware": "hardware_diagnostics.json",
    "profiling": "screenshot_profile.json",
    "baseline": "baseline_benchmark_v1.json",
    "threads": "ocr_thread_benchmark.json",
    "onednn": "ocr_onednn_benchmark.json",
    "models": "ocr_model_benchmark.json",
    "accuracy": "lightweight_ocr_validation.json",
    "errors": "ocr_error_analysis.json",
    "runtimes": "independent_runtime_verification.json",
    "devices": "openvino_device_verification.json",
    "neural": "neural_runtime_benchmark.json",
    "preprocessing": "ocr_preprocessing_benchmark.json",
}


def load_report(filename):

    path = PERFORMANCE_DIR / filename

    if not path.is_file():

        return {
            "available": False,
            "filename": filename,
            "error": "Report not found",
        }

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )

        return {
            "available": True,
            "filename": filename,
            "data": data,
        }

    except Exception as error:

        return {
            "available": False,
            "filename": filename,
            "error": str(error),
        }


def get_data(reports, name):

    return reports.get(
        name, {}
    ).get("data", {})


def analyze_preprocessing(data):

    ranking = data.get("ranking", [])

    baseline = next(
        (
            item for item in ranking
            if item["configuration"] == "original"
        ),
        None,
    )

    eligible = [
        item for item in ranking
        if item.get("accuracy_preserved")
    ]

    best = min(
        eligible,
        key=lambda item: item["mean_total_ms"],
        default=None,
    )

    return {
        "baseline": baseline,
        "best_normalized_accuracy_candidate": best,
        "ranking": ranking,
        "summary": data.get("summary"),
    }


def analyze_neural_runtimes(data):

    workloads = []

    for workload in data.get("workloads", []):

        successful = [
            item
            for item in workload.get("results", [])
            if item.get("success")
        ]

        if not successful:
            continue

        mean_winner = min(
            successful,
            key=lambda item: (
                item["benchmark"]["mean_ms"]
            ),
        )

        p95_winner = min(
            successful,
            key=lambda item: (
                item["benchmark"]["p95_ms"]
            ),
        )

        workloads.append({
            "input_size": workload["input_size"],

            "mean_latency_winner": (
                mean_winner["runtime"]
            ),

            "mean_latency_ms": (
                mean_winner["benchmark"]["mean_ms"]
            ),

            "p95_latency_winner": (
                p95_winner["runtime"]
            ),

            "p95_latency_ms": (
                p95_winner["benchmark"]["p95_ms"]
            ),

            "ranking": workload.get("ranking", []),
        })

    return workloads


def analyze_accuracy(data):

    models = []

    for item in data.get("models", []):

        models.append({
            "model": item.get("model"),
            **item.get("summary", {}),
        })

    return models


def create_markdown(report):

    lines = [
        "# Performance Feasibility Report",
        "",
        f"Generated: {report['timestamp_utc']}",
        "",
        "## Scope",
        "",
        report["scope"],
        "",
        "## Report Availability",
        "",
        "| Report | Available |",
        "|---|---|",
    ]

    for name, item in report["sources"].items():

        status = (
            "YES"
            if item["available"]
            else "NO"
        )

        lines.append(
            f"| {name} | {status} |"
        )

    lines.extend([
        "",
        "## Preprocessing Results",
        "",
        "| Method | Mean ms | Adjusted recall | Strict recall |",
        "|---|---:|---:|---:|",
    ])

    for item in report["preprocessing"]["ranking"]:

        lines.append(
            f"| {item['configuration']} "
            f"| {item['mean_total_ms']:.3f} "
            f"| {item['adjusted_recall_percent']:.3f}% "
            f"| {item['strict_recall_percent']:.3f}% |"
        )

    lines.extend([
        "",
        "## Neural Runtime Results",
        "",
        "| Input size | Mean winner | Mean ms | P95 winner | P95 ms |",
        "|---|---|---:|---|---:|",
    ])

    for item in report["neural_runtimes"]:

        size = item["input_size"]

        lines.append(
            f"| {size} x {size} "
            f"| {item['mean_latency_winner']} "
            f"| {item['mean_latency_ms']:.6f} "
            f"| {item['p95_latency_winner']} "
            f"| {item['p95_latency_ms']:.6f} |"
        )

    lines.extend([
        "",
        "## Adjusted OCR Accuracy",
        "",
        "| Model | Original recall | Adjusted recall |",
        "|---|---:|---:|",
    ])

    for item in report["accuracy_analysis"]:

        lines.append(
            f"| {item['model']} "
            f"| {item.get('original_recall_percent', 'N/A')} "
            f"| {item.get('adjusted_recall_percent', 'N/A')} |"
        )

    lines.extend([
        "",
        "## Research Conclusions",
        "",
    ])

    for conclusion in report["conclusions"]:

        lines.append(f"- {conclusion}")

    lines.extend([
        "",
        "## Limitations",
        "",
    ])

    for limitation in report["limitations"]:

        lines.append(f"- {limitation}")

    lines.extend([
        "",
        "## Production Decision",
        "",
        report["production_decision"],
    ])

    return "\n".join(lines) + "\n"


def main():

    PERFORMANCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    reports = {
        name: load_report(filename)
        for name, filename in REPORT_FILES.items()
    }

    preprocessing = analyze_preprocessing(
        get_data(reports, "preprocessing")
    )

    neural = analyze_neural_runtimes(
        get_data(reports, "neural")
    )

    accuracy = analyze_accuracy(
        get_data(reports, "errors")
    )

    available_count = sum(
        item["available"]
        for item in reports.values()
    )

    missing_reports = [
        item["filename"]
        for item in reports.values()
        if not item["available"]
    ]

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "report_version": "1.0.0",

        "scope": (
            "General-purpose offline document OCR "
            "and synthetic inference research."
        ),

        "sources": {
            name: {
                key: value
                for key, value in item.items()
                if key != "data"
            }
            for name, item in reports.items()
        },

        "preprocessing": preprocessing,

        "neural_runtimes": neural,

        "accuracy_analysis": accuracy,

        "conclusions": [
            (
                "Lightweight model selection produced "
                "the largest observed standalone OCR "
                "performance improvement."
            ),
            (
                "Gaussian preprocessing is a provisional "
                "candidate based on normalized accuracy "
                "and measured latency."
            ),
            (
                "ONNX Runtime CPU and OpenVINO CPU/GPU "
                "execution have been demonstrated."
            ),
            (
                "Synthetic runtime results do not "
                "establish actual OCR runtime performance."
            ),
        ],

        "limitations": [
            "Small synthetic document dataset.",
            "Repeated runs are not independent documents.",
            "Normalization can conceal formatting errors.",
            "Actual OCR model conversion remains unresolved.",
            "No controlled C++ versus Python benchmark.",
            "No verified application-level latency improvement.",
            "Fixed benchmark order may affect timing.",
        ],

        "production_decision": (
            "Defer final runtime and language selection "
            "until representative models and production "
            "requirements have been independently validated."
        ),

        "summary": {
            "expected_reports": len(REPORT_FILES),

            "available_reports": available_count,

            "missing_report_count": len(
                missing_reports
            ),

            "missing_reports": missing_reports,

            "preprocessing_configurations": len(
                preprocessing["ranking"]
            ),

            "neural_workloads": len(neural),

            "accuracy_models": len(accuracy),
        },

        "source_reports": {
            name: item["data"]
            for name, item in reports.items()
            if item["available"]
        },
    }

    report["success"] = (
        available_count == len(REPORT_FILES)
        and bool(preprocessing["ranking"])
        and bool(neural)
        and bool(accuracy)
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    MARKDOWN_FILE.write_text(
        create_markdown(report),
        encoding="utf-8",
    )

    print("=" * 60)
    print("PERFORMANCE FEASIBILITY REPORT")
    print("=" * 60)

    print(
        json.dumps(
            {
                "success": report["success"],

                "summary": report["summary"],

                "best_preprocessing": preprocessing[
                    "best_normalized_accuracy_candidate"
                ],

                "neural_runtimes": neural,

                "accuracy_analysis": accuracy,
            },
            indent=4,
            ensure_ascii=False,
        )
    )

    print(f"\nJSON report: {OUTPUT_FILE}")

    print(f"Markdown report: {MARKDOWN_FILE}")

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
