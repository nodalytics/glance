
import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import threading
import time
import traceback

from datetime import datetime, timezone
from pathlib import Path

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
)

DEFAULT_SCREENSHOT = (
    PROJECT_ROOT
    / "test_images"
    / "ss.jpeg"
)

MIB = 1024 ** 2


def elapsed_ms(started_ns):
    return round(
        (time.perf_counter_ns() - started_ns)
        / 1_000_000,
        3,
    )


class ResourceMonitor:

    def __init__(self, interval=0.25):

        self.interval = interval

        self.process = psutil.Process(
            os.getpid()
        )

        self.samples = []

        self.stop_event = threading.Event()

        self.thread = None

        self.started = None

    def collect_sample(self):

        try:

            memory = self.process.memory_info()

            system_memory = (
                psutil.virtual_memory()
            )

            self.samples.append({
                "elapsed_ms": round(
                    (
                        time.perf_counter()
                        - self.started
                    ) * 1000,
                    3,
                ),
                "process_cpu_percent": (
                    self.process.cpu_percent(
                        interval=None
                    )
                ),
                "process_rss_mib": round(
                    memory.rss / MIB,
                    3,
                ),
                "system_cpu_percent": (
                    psutil.cpu_percent(
                        interval=None
                    )
                ),
                "system_available_memory_mib": round(
                    system_memory.available / MIB,
                    3,
                ),
                "system_memory_percent": (
                    system_memory.percent
                ),
                "process_thread_count": (
                    self.process.num_threads()
                ),
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
        ):
            pass

    def monitor(self):

        while not self.stop_event.is_set():

            self.collect_sample()

            self.stop_event.wait(
                self.interval
            )

    def start(self):

        self.started = time.perf_counter()

        self.process.cpu_percent(
            interval=None
        )

        psutil.cpu_percent(
            interval=None
        )

        self.thread = threading.Thread(
            target=self.monitor,
            daemon=True,
        )

        self.thread.start()

    def stop(self):

        self.stop_event.set()

        if self.thread is not None:
            self.thread.join()

        self.collect_sample()

    def summary(self):

        if not self.samples:
            return {}

        # Ignore the initial CPU sample,
        # which may not be representative.

        cpu_samples = (
            self.samples[1:]
            or self.samples
        )

        cpu_values = [
            item["process_cpu_percent"]
            for item in cpu_samples
        ]

        memory_values = [
            item["process_rss_mib"]
            for item in self.samples
        ]

        available_memory = [
            item["system_available_memory_mib"]
            for item in self.samples
        ]

        thread_values = [
            item["process_thread_count"]
            for item in self.samples
        ]

        system_cpu = [
            item["system_cpu_percent"]
            for item in cpu_samples
        ]

        logical_cpus = (
            psutil.cpu_count(logical=True)
            or 1
        )

        average_cpu = (
            sum(cpu_values)
            / len(cpu_values)
        )

        return {
            "sample_count": len(self.samples),

            "sampling_interval_ms": (
                self.interval * 1000
            ),

            "average_process_cpu_percent": round(
                average_cpu,
                3,
            ),

            "normalized_average_cpu_percent": round(
                average_cpu / logical_cpus,
                3,
            ),

            "maximum_process_cpu_percent": (
                max(cpu_values)
            ),

            "average_system_cpu_percent": round(
                sum(system_cpu)
                / len(system_cpu),
                3,
            ),

            "initial_process_memory_mib": (
                memory_values[0]
            ),

            "peak_sampled_process_memory_mib": (
                max(memory_values)
            ),

            "final_process_memory_mib": (
                memory_values[-1]
            ),

            "minimum_available_system_memory_mib": (
                min(available_memory)
            ),

            "maximum_process_threads": (
                max(thread_values)
            ),
        }


def extract_function_statistics(
    profiler,
    limit=40,
):

    stats = pstats.Stats(profiler)

    functions = []

    for (
        filename,
        line_number,
        function_name,
    ), values in stats.stats.items():

        (
            primitive_calls,
            total_calls,
            internal_time,
            cumulative_time,
            callers,
        ) = values

        functions.append({
            "filename": filename,
            "line_number": line_number,
            "function": function_name,

            "primitive_calls": primitive_calls,

            "total_calls": total_calls,

            "internal_time_ms": round(
                internal_time * 1000,
                3,
            ),

            "cumulative_time_ms": round(
                cumulative_time * 1000,
                3,
            ),

            "average_internal_time_ms": round(
                (
                    internal_time
                    / total_calls
                    * 1000
                )
                if total_calls
                else 0,
                6,
            ),
        })

    by_cumulative = sorted(
        functions,
        key=lambda item: (
            item["cumulative_time_ms"]
        ),
        reverse=True,
    )

    by_internal = sorted(
        functions,
        key=lambda item: (
            item["internal_time_ms"]
        ),
        reverse=True,
    )

    project_functions = [
        item
        for item in by_cumulative
        if "poker_apis" in item["filename"]
        .replace("\\", "/")
        .lower()
    ]

    ocr_functions = [
        item
        for item in by_cumulative
        if any(
            keyword in (
                item["filename"]
                + " "
                + item["function"]
            ).lower()
            for keyword in [
                "paddle",
                "ocr",
                "predict",
                "inference",
            ]
        )
    ]

    return {
        "total_function_calls": (
            stats.total_calls
        ),

        "primitive_function_calls": (
            stats.prim_calls
        ),

        "profiled_internal_time_ms": round(
            stats.total_tt * 1000,
            3,
        ),

        "top_cumulative_functions": (
            by_cumulative[:limit]
        ),

        "top_internal_functions": (
            by_internal[:limit]
        ),

        "top_project_functions": (
            project_functions[:limit]
        ),

        "top_ocr_functions": (
            ocr_functions[:limit]
        ),
    }


def save_text_profile(profiler, path):

    stream = io.StringIO()

    stats = pstats.Stats(
        profiler,
        stream=stream,
    )

    stream.write(
        "\nTOP FUNCTIONS BY CUMULATIVE TIME\n"
    )

    stream.write("=" * 80 + "\n")

    stats.sort_stats(
        "cumulative"
    ).print_stats(60)

    stream.write(
        "\nTOP FUNCTIONS BY INTERNAL TIME\n"
    )

    stream.write("=" * 80 + "\n")

    stats.sort_stats(
        "time"
    ).print_stats(60)

    stream.write(
        "\nTOP FUNCTIONS BY CALL COUNT\n"
    )

    stream.write("=" * 80 + "\n")

    stats.sort_stats(
        "calls"
    ).print_stats(60)

    path.write_text(
        stream.getvalue(),
        encoding="utf-8",
    )


def summarize_state(state):

    if hasattr(state, "model_dump"):

        state = state.model_dump(
            mode="json"
        )

    game = state.get("game", {})

    validation = state.get(
        "validation",
        {},
    )

    metadata = state.get(
        "metadata",
        {},
    )

    cards = state.get("cards", {})

    return {
        "status": state.get("status"),

        "street": game.get("street"),

        "recognized_card_count": game.get(
            "recognized_card_count"
        ),

        "occupied_card_count": game.get(
            "occupied_count"
        ),

        "player_count": len(
            state.get("players", [])
        ),

        "validation_valid": validation.get(
            "valid"
        ),

        "validation_error_count": validation.get(
            "error_count"
        ),

        "validation_warning_count": validation.get(
            "warning_count"
        ),

        "recognition_profile": metadata.get(
            "recognition_profile"
        ),

        "community_cards": [
            {
                "rank": card.get("rank"),
                "suit": card.get("suit"),
            }
            for card in cards.get(
                "community",
                [],
            )
        ],

        "hero_cards": [
            {
                "rank": card.get("rank"),
                "suit": card.get("suit"),
            }
            for card in cards.get(
                "hero",
                [],
            )
        ],

        "backend_processing_time_seconds": (
            metadata.get(
                "processing_time_seconds"
            )
        ),

        "backend_timings": (
            metadata.get("timings", {})
        ),
    }


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--image",
        type=Path,
        default=DEFAULT_SCREENSHOT,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=30,
    )

    args = parser.parse_args()

    screenshot = args.image.resolve()

    if not screenshot.is_file():

        raise FileNotFoundError(
            f"Screenshot not found: {screenshot}"
        )

    if args.top < 1:
        parser.error("--top must be positive")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        OUTPUT_DIR
        / "screenshot_profile.json"
    )

    raw_profile_path = (
        OUTPUT_DIR
        / "screenshot_pipeline.prof"
    )

    text_profile_path = (
        OUTPUT_DIR
        / "screenshot_profile.txt"
    )

    state_path = (
        OUTPUT_DIR
        / "profiled_table_state.json"
    )

    samples_path = (
        OUTPUT_DIR
        / "resource_samples.json"
    )

    print("=" * 70)

    print(
        "PHASE 7.2 - SCREENSHOT PIPELINE PROFILING"
    )

    print("=" * 70)

    print(f"Screenshot: {screenshot}")

    print(
        f"File size: "
        f"{screenshot.stat().st_size} bytes"
    )

    report = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "screenshot": screenshot.name,

        "file_size_bytes": (
            screenshot.stat().st_size
        ),

        "python_version": sys.version,

        "success": False,

        "timings_ms": {},
    }

    total_started = time.perf_counter_ns()

    monitor = ResourceMonitor(
        interval=0.25
    )

    profiler = cProfile.Profile()

    profile_started = False

    monitor.start()

    try:

        print(
            "\n[1/4] Importing screenshot pipeline...",
            flush=True,
        )

        started = time.perf_counter_ns()

        from poker_apis.pipeline.screenshot_pipeline import (
            ScreenshotPipeline,
        )

        report["timings_ms"][
            "pipeline_import"
        ] = elapsed_ms(started)

        print(
            "Import completed: "
            f"{report['timings_ms']['pipeline_import']} ms"
        )

        print(
            "\n[2/4] Initializing pipeline...",
            flush=True,
        )

        started = time.perf_counter_ns()

        pipeline = ScreenshotPipeline()

        report["timings_ms"][
            "pipeline_initialization"
        ] = elapsed_ms(started)

        print(
            "Initialization completed: "
            f"{report['timings_ms']['pipeline_initialization']} ms"
        )

        print(
            "\n[3/4] Profiling screenshot processing...",
            flush=True,
        )

        print(
            "Please wait. This may take several minutes.",
            flush=True,
        )

        started = time.perf_counter_ns()

        profiler.enable()

        profile_started = True

        try:

            state = pipeline.process_file(
                screenshot
            )

        finally:

            profiler.disable()

            report["timings_ms"][
                "screenshot_processing"
            ] = elapsed_ms(started)

        print(
            "Processing completed: "
            f"{report['timings_ms']['screenshot_processing']} ms"
        )

        report["state_summary"] = (
            summarize_state(state)
        )

        if hasattr(state, "model_dump"):

            state = state.model_dump(
                mode="json"
            )

        state_path.write_text(
            json.dumps(
                state,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report["success"] = True

    except Exception as error:

        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }

        print(
            f"\nERROR: {error}",
            flush=True,
        )

    finally:

        report["timings_ms"][
            "total_execution"
        ] = elapsed_ms(total_started)

        monitor.stop()

        print(
            "\n[4/4] Generating performance reports...",
            flush=True,
        )

        report["resource_usage"] = (
            monitor.summary()
        )

        if profile_started:

            profiler.dump_stats(
                str(raw_profile_path)
            )

            report["function_statistics"] = (
                extract_function_statistics(
                    profiler,
                    limit=args.top,
                )
            )

            save_text_profile(
                profiler,
                text_profile_path,
            )

        samples_path.write_text(
            json.dumps(
                monitor.samples,
                indent=2,
            ),
            encoding="utf-8",
        )

        report_path.write_text(
            json.dumps(
                report,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    print("\n" + "=" * 70)

    print("PERFORMANCE SUMMARY")

    print("=" * 70)

    summary = {
        "success": report["success"],

        "timings_ms": report["timings_ms"],

        "resource_usage": report[
            "resource_usage"
        ],

        "state_summary": report.get(
            "state_summary"
        ),

        "error": report.get("error"),
    }

    print(
        json.dumps(
            summary,
            indent=4,
        )
    )

    print("\n" + "=" * 70)

    print("REPORT FILES")

    print("=" * 70)

    print(f"JSON report: {report_path}")

    print(f"Raw profile: {raw_profile_path}")

    print(f"Text profile: {text_profile_path}")

    print(f"Resource samples: {samples_path}")

    print(f"Table state: {state_path}")

    if not report["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
