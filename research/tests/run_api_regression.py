
import sys
import os
import json
import time
import argparse
import subprocess

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TESTS_DIR = PROJECT_ROOT / "tests"

OUTPUT_DIR = PROJECT_ROOT / "test_output"

REGRESSION_DIR = OUTPUT_DIR / "api_regression"

LOGS_DIR = REGRESSION_DIR / "logs"

BASE_URL = "http://127.0.0.1:8000"


# --------------------------------------------------
# TEST SUITE REGISTRY
# --------------------------------------------------

TEST_SUITES = [
    {
        "id": "api_models",
        "name": "Pydantic API Models",
        "script": "test_api_models.py",
        "report": "api_models_validation_report.json",
        "expected_tests": 26,
        "timeout": 60,
        "mode": "quick"
    },
    {
        "id": "api_config",
        "name": "Application Configuration",
        "script": "test_api_config.py",
        "report": "api_config_validation_report.json",
        "expected_tests": 39,
        "timeout": 60,
        "mode": "quick"
    },
    {
        "id": "processing_service",
        "name": "Offline Processing Service",
        "script": "test_processing_service.py",
        "report": "processing_service_validation_report.json",
        "expected_tests": 46,
        "timeout": 120,
        "mode": "quick"
    },
    {
        "id": "api_routes",
        "name": "FastAPI Routes",
        "script": "test_api_routes.py",
        "report": "api_routes_validation_report.json",
        "expected_tests": 48,
        "timeout": 120,
        "mode": "quick"
    },
    {
        "id": "api_application",
        "name": "FastAPI Application",
        "script": "test_api_application.py",
        "report": "api_application_validation_report.json",
        "expected_tests": 47,
        "timeout": 120,
        "mode": "quick"
    },
    {
        "id": "real_processing_service",
        "name": "Real OCR Processing Service",
        "script": "test_real_processing_service.py",
        "report": "real_processing_service_report.json",
        "expected_tests": 44,
        "timeout": 900,
        "mode": "full"
    },
    {
        "id": "real_http_api",
        "name": "Real HTTP API Integration",
        "script": "test_real_http_api.py",
        "report": "real_http_api_report.json",
        "expected_tests": 50,
        "timeout": 900,
        "mode": "full"
    }
]


# --------------------------------------------------
# JSON HELPERS
# --------------------------------------------------

def load_json(path):

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )


# --------------------------------------------------
# COMMAND LINE ARGUMENTS
# --------------------------------------------------

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Run the offline API regression suite."
        )
    )

    parser.add_argument(
        "--mode",
        choices=["quick", "full"],
        default="quick",
        help="Select regression testing mode."
    )

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed suite."
    )

    return parser.parse_args()


# --------------------------------------------------
# SERVER AVAILABILITY
# --------------------------------------------------

def check_server():

    import httpx

    try:

        with httpx.Client(
            timeout=10.0,
            trust_env=False
        ) as client:

            response = client.get(
                f"{BASE_URL}/health"
            )

            response.raise_for_status()

            health = response.json()

            if health.get("status") != "ok":

                return False, (
                    "Server health is not ok."
                )

            if health.get("mode") != "offline":

                return False, (
                    "Server is not in offline mode."
                )

            if health.get("busy") is not False:

                return False, (
                    "Processing service is busy."
                )

            return True, health

    except Exception as exc:

        return False, str(exc)


# --------------------------------------------------
# EXECUTE INDIVIDUAL TEST SUITE
# --------------------------------------------------

def run_suite(suite, run_logs_dir):

    start = time.perf_counter()

    script_path = (
        TESTS_DIR / suite["script"]
    )

    report_path = (
        OUTPUT_DIR / suite["report"]
    )

    log_path = (
        run_logs_dir / f"{suite['id']}.log"
    )

    result = {
        "id": suite["id"],
        "name": suite["name"],
        "script": suite["script"],
        "expected_tests": suite["expected_tests"],
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "exit_code": None,
        "report_generated": False,
        "passed": False,
        "error": None,
        "duration_seconds": None,
        "log_file": str(
            log_path.relative_to(PROJECT_ROOT)
        ),
        "report_file": str(
            report_path.relative_to(PROJECT_ROOT)
        )
    }

    try:

        if not script_path.is_file():

            raise FileNotFoundError(
                f"Missing test script: {script_path}"
            )

        # Remove previous report so stale results
        # cannot be counted as a successful run.

        if report_path.exists():

            report_path.unlink()

        environment = os.environ.copy()

        environment["PYTHONUNBUFFERED"] = "1"

        environment["PYTHONIOENCODING"] = "utf-8"

        command = [
            sys.executable,
            "-u",
            str(script_path)
        ]

        print(
            f"Running: {suite['script']}",
            flush=True
        )

        print(
            f"Log: {log_path}",
            flush=True
        )

        # Redirect output to disk to avoid keeping
        # large OCR logs in memory.

        with log_path.open(
            "w",
            encoding="utf-8"
        ) as log_file:

            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=suite["timeout"],
                check=False
            )

        result["exit_code"] = (
            completed.returncode
        )

        if not report_path.is_file():

            raise RuntimeError(
                "Test did not generate a fresh report."
            )

        result["report_generated"] = True

        report = load_json(report_path)

        summary = report["summary"]

        for field in [
            "total_tests",
            "passed_tests",
            "failed_tests"
        ]:

            value = summary[field]

            if type(value) is not int or value < 0:

                raise ValueError(
                    f"Invalid report counter: {field}"
                )

            result[field] = value

        expected_count = (
            result["total_tests"]
            == suite["expected_tests"]
        )

        consistent_counts = (
            result["passed_tests"]
            + result["failed_tests"]
            == result["total_tests"]
        )

        result["passed"] = (
            completed.returncode == 0
            and summary.get("passed") is True
            and expected_count
            and consistent_counts
            and result["failed_tests"] == 0
        )

        if not result["passed"]:

            result["error"] = (
                "Suite failed or report counters "
                "did not match expectations."
            )

    except subprocess.TimeoutExpired:

        result["error"] = (
            f"Suite exceeded its "
            f"{suite['timeout']}-second timeout."
        )

    except Exception as exc:

        result["error"] = str(exc)

    finally:

        result["duration_seconds"] = round(
            time.perf_counter() - start,
            4
        )

    return result


# --------------------------------------------------
# MAIN REGRESSION RUNNER
# --------------------------------------------------

def main():

    args = parse_arguments()

    start = time.perf_counter()

    run_id = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S_%fZ")

    run_logs_dir = LOGS_DIR / run_id

    run_logs_dir.mkdir(
        parents=True,
        exist_ok=False
    )

    selected_suites = [
        suite
        for suite in TEST_SUITES
        if args.mode == "full"
        or suite["mode"] == "quick"
    ]

    expected_tests = sum(
        suite["expected_tests"]
        for suite in selected_suites
    )

    print("=" * 75)
    print("OFFLINE API REGRESSION SUITE")
    print("=" * 75)

    print(f"Run ID: {run_id}")
    print(f"Mode: {args.mode.upper()}")
    print(f"Selected suites: {len(selected_suites)}")
    print(f"Expected tests: {expected_tests}")
    print(f"Fail fast: {args.fail_fast}")

    results = []

    blocker = None

    # ----------------------------------------------
    # FULL MODE SERVER PREFLIGHT
    # ----------------------------------------------

    if args.mode == "full":

        print("\nSERVER PREFLIGHT")

        available, details = check_server()

        if available:

            print("[PASS] Local API server available")

        else:

            blocker = (
                "Full regression requires an "
                "available local API server."
            )

            print(f"[FAIL] {blocker}")
            print(details)

            print(
                "\nStart the server in another "
                "terminal using:"
            )

            print("python -m poker_apis.main")

    # ----------------------------------------------
    # EXECUTE SELECTED SUITES
    # ----------------------------------------------

    if blocker is None:

        for index, suite in enumerate(
            selected_suites,
            start=1
        ):

            print("\n" + "-" * 75)

            print(
                f"[{index}/{len(selected_suites)}] "
                f"{suite['name']}"
            )

            print("-" * 75)

            result = run_suite(
                suite,
                run_logs_dir
            )

            results.append(result)

            status = (
                "PASS"
                if result["passed"]
                else "FAIL"
            )

            print(
                f"[{status}] "
                f"{result['passed_tests']}/"
                f"{result['expected_tests']} checks"
            )

            print(
                f"Duration: "
                f"{result['duration_seconds']:.4f}s"
            )

            if result["error"]:

                print(
                    f"Error: {result['error']}"
                )

            if (
                args.fail_fast
                and not result["passed"]
            ):

                print(
                    "\nStopping after failed suite."
                )

                break

    # ----------------------------------------------
    # CONSOLIDATED SUMMARY
    # ----------------------------------------------

    passed_suites = sum(
        item["passed"]
        for item in results
    )

    failed_suites = (
        len(results) - passed_suites
    )

    executed_tests = sum(
        item["total_tests"]
        for item in results
    )

    passed_tests = sum(
        item["passed_tests"]
        for item in results
    )

    failed_tests = sum(
        item["failed_tests"]
        for item in results
    )

    executed_ids = {
        item["id"]
        for item in results
    }

    skipped_suites = [
        suite["id"]
        for suite in selected_suites
        if suite["id"] not in executed_ids
    ]

    summary = {
        "mode": args.mode,
        "expected_suites": len(selected_suites),
        "executed_suites": len(results),
        "passed_suites": passed_suites,
        "failed_suites": failed_suites,
        "skipped_suites": len(skipped_suites),
        "expected_tests": expected_tests,
        "executed_tests": executed_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "total_time_seconds": round(
            time.perf_counter() - start,
            4
        ),
        "passed": (
            blocker is None
            and not skipped_suites
            and failed_suites == 0
            and failed_tests == 0
            and executed_tests == expected_tests
            and passed_tests == expected_tests
        )
    }

    report = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "summary": summary,
        "blocker": blocker,
        "skipped_suites": skipped_suites,
        "failures": [
            item
            for item in results
            if not item["passed"]
        ],
        "suites": results
    }

    report_path = (
        REGRESSION_DIR
        / f"api_regression_{args.mode}_report.json"
    )

    historical_report = (
        REGRESSION_DIR
        / "history"
        / f"{run_id}_{args.mode}.json"
    )

    save_json(report_path, report)

    save_json(historical_report, report)

    # ----------------------------------------------
    # TERMINAL OUTPUT
    # ----------------------------------------------

    print("\n" + "=" * 75)

    print("API REGRESSION SUMMARY")

    print("=" * 75)

    print(
        json.dumps(
            summary,
            indent=4
        )
    )

    print("\nINDIVIDUAL SUITE RESULTS")

    for item in results:

        status = (
            "PASS"
            if item["passed"]
            else "FAIL"
        )

        print(
            f"[{status}] "
            f"{item['name']}: "
            f"{item['passed_tests']}/"
            f"{item['expected_tests']} "
            f"({item['duration_seconds']:.2f}s)"
        )

    print(f"\nReport saved: {report_path}")

    print(
        f"Historical report: {historical_report}"
    )

    print(f"Logs directory: {run_logs_dir}")

    if summary["passed"]:

        print(
            "\nFINAL RESULT: ALL REGRESSION TESTS PASSED"
        )

        return 0

    print(
        "\nFINAL RESULT: REGRESSION VALIDATION FAILED"
    )

    return 1


if __name__ == "__main__":

    sys.exit(main())
