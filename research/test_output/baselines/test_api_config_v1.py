
import sys
import os
import json
import time
import tempfile

from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from pydantic import ValidationError

from poker_apis.core.config import (
    ApplicationSettings,
    load_settings,
    get_settings
)

from poker_apis.models.poker_state import (
    ApplicationInfoModel
)


OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "api_config_validation_report.json"
)


def main():

    print("=" * 75)
    print("APPLICATION CONFIGURATION VALIDATION")
    print("=" * 75)

    start = time.perf_counter()

    results = []

    def record(name, passed, details=None):

        results.append({
            "test": name,
            "passed": bool(passed),
            "details": details
        })

        status = "PASS" if passed else "FAIL"

        print(f"[{status}] {name}")

        if details and not passed:

            print(f"       {details}")

    def expect_rejection(name, data):

        try:

            ApplicationSettings.model_validate(
                data
            )

        except ValidationError:

            record(name, True)

        except Exception as exc:

            record(name, False, str(exc))

        else:

            record(
                name,
                False,
                "Invalid configuration accepted."
            )

    # ----------------------------------------------
    # DEFAULT CONFIGURATION
    # ----------------------------------------------

    print("\nDEFAULT CONFIGURATION TESTS")

    settings = ApplicationSettings()

    record(
        "Default application name",
        settings.app_name == "poker-apis"
    )

    record(
        "Offline mode enforced",
        settings.mode == "offline"
    )

    record(
        "Default local server host",
        settings.host == "127.0.0.1"
    )

    record(
        "Default server port",
        settings.port == 8000
    )

    record(
        "Default API prefix",
        settings.api_prefix == "/api/v1"
    )

    record(
        "Default upload limit",
        settings.max_upload_size_bytes
        == 10485760
    )

    record(
        "Default supported formats",
        set(settings.supported_image_formats)
        == {".png", ".jpg", ".jpeg", ".bmp"}
    )

    record(
        "Debug disabled by default",
        settings.debug is False
    )

    record(
        "Swagger enabled by default",
        settings.docs_url == "/docs"
    )

    record(
        "Single processing operation configured",
        settings.max_concurrent_processing == 1
    )

    record(
        "Temporary cleanup required",
        settings.cleanup_temp_files is True
    )

    # ----------------------------------------------
    # INVALID CONFIGURATION TESTS
    # ----------------------------------------------

    print("\nINVALID CONFIGURATION TESTS")

    invalid_cases = [
        (
            "Invalid server port rejected",
            {"port": 70000}
        ),
        (
            "Zero server port rejected",
            {"port": 0}
        ),
        (
            "External host rejected",
            {"host": "0.0.0.0"}
        ),
        (
            "Unsupported operating mode rejected",
            {"mode": "live"}
        ),
        (
            "Negative upload limit rejected",
            {"max_upload_size_bytes": -1}
        ),
        (
            "Excessive upload limit rejected",
            {
                "max_upload_size_bytes":
                    100 * 1024 * 1024
            }
        ),
        (
            "Invalid API prefix rejected",
            {"api_prefix": "api/v1"}
        ),
        (
            "Trailing slash rejected",
            {"api_prefix": "/api/v1/"}
        ),
        (
            "Invalid logging level rejected",
            {"log_level": "UNKNOWN"}
        ),
        (
            "Unsupported image format rejected",
            {
                "supported_image_formats":
                    [".exe"]
            }
        ),
        (
            "Empty image format list rejected",
            {"supported_image_formats": []}
        ),
        (
            "Concurrent processing override rejected",
            {"max_concurrent_processing": 2}
        ),
        (
            "Cleanup disabling rejected",
            {"cleanup_temp_files": False}
        )
    ]

    for name, data in invalid_cases:

        expect_rejection(name, data)

    # ----------------------------------------------
    # ENVIRONMENT CONFIGURATION
    # ----------------------------------------------

    print("\nENVIRONMENT CONFIGURATION TESTS")

    with tempfile.TemporaryDirectory() as temp:

        temp_root = Path(temp)

        env_file = temp_root / ".env"

        env_file.write_text(
            "POKER_PORT=9000\n"
            "POKER_DEBUG=true\n"
            "POKER_LOG_LEVEL=debug\n"
            "POKER_DOCS_ENABLED=false\n"
            "POKER_MAX_UPLOAD_SIZE_BYTES=5242880\n",
            encoding="utf-8"
        )

        loaded = load_settings(
            env_file=env_file,
            include_os_environment=False
        )

        record(
            "Environment port loaded",
            loaded.port == 9000
        )

        record(
            "Environment boolean loaded",
            loaded.debug is True
        )

        record(
            "Logging level normalized",
            loaded.log_level == "DEBUG"
        )

        record(
            "Environment upload limit loaded",
            loaded.max_upload_size_bytes
            == 5242880
        )

        record(
            "Documentation disabled correctly",
            loaded.docs_url is None
            and loaded.redoc_url is None
            and loaded.openapi_url is None
        )

        with patch.dict(
            os.environ,
            {"POKER_PORT": "9100"},
            clear=True
        ):

            overridden = load_settings(
                env_file=env_file
            )

            record(
                "OS environment takes priority",
                overridden.port == 9100
            )

        missing = load_settings(
            env_file=temp_root / "missing.env",
            include_os_environment=False
        )

        record(
            "Missing environment file uses defaults",
            missing.port == 8000
        )

        # ------------------------------------------
        # DIRECTORY MANAGEMENT
        # ------------------------------------------

        print("\nDIRECTORY MANAGEMENT TESTS")

        runtime_settings = ApplicationSettings(
            project_root=temp_root
        )

        runtime_settings.prepare_runtime_directories()

        record(
            "Temporary upload directory created",
            runtime_settings.temp_upload_dir.is_dir()
        )

        record(
            "Output directory created",
            runtime_settings.output_dir.is_dir()
        )

        record(
            "Calibration template path resolved",
            runtime_settings.calibration_templates_dir
            == (
                temp_root
                / "test_assets"
                / "card_templates"
                / "suits"
            )
        )

        record(
            "Simulator template path resolved",
            runtime_settings.simulator_templates_dir
            == (
                temp_root
                / "test_assets"
                / "card_templates"
                / "simulator_suits"
            )
        )

    # ----------------------------------------------
    # IMMUTABILITY AND CACHING
    # ----------------------------------------------

    print("\nIMMUTABILITY AND CACHING TESTS")

    try:

        settings.port = 9000

    except ValidationError:

        record(
            "Configuration is immutable",
            True
        )

    else:

        record(
            "Configuration is immutable",
            False
        )

    get_settings.cache_clear()

    first = get_settings()

    second = get_settings()

    record(
        "Configuration object cached",
        first is second
    )

    get_settings.cache_clear()

    # ----------------------------------------------
    # PUBLIC APPLICATION INFORMATION
    # ----------------------------------------------

    print("\nPUBLIC INFORMATION TESTS")

    public_info = settings.public_info()

    try:

        model = ApplicationInfoModel.model_validate(
            public_info
        )

        record(
            "Public information matches API model",
            model.name == settings.app_name
            and model.mode == "offline"
        )

    except ValidationError as exc:

        record(
            "Public information matches API model",
            False,
            str(exc)
        )

    private_fields = {
        "project_root",
        "temp_upload_dir",
        "output_dir",
        "test_assets_dir"
    }

    record(
        "Internal paths excluded from public info",
        not private_fields.intersection(
            public_info
        )
    )

    # ----------------------------------------------
    # FINAL SUMMARY
    # ----------------------------------------------

    passed_count = sum(
        item["passed"]
        for item in results
    )

    failed_count = (
        len(results) - passed_count
    )

    summary = {
        "total_tests": len(results),
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "total_time_seconds": round(
            time.perf_counter() - start,
            4
        ),
        "passed": failed_count == 0
    }

    report = {
        "summary": summary,
        "configuration": public_info,
        "failures": [
            item
            for item in results
            if not item["passed"]
        ],
        "results": results
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)
    print("CONFIGURATION VALIDATION SUMMARY")
    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
