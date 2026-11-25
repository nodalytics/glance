
import sys
import io
import json
import time
import logging
import tempfile

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from PIL import Image

from fastapi import FastAPI

from fastapi.testclient import TestClient

from poker_apis.api.routes import (
    health_router,
    api_router
)

from poker_apis.core.config import (
    ApplicationSettings
)

from poker_apis.models.poker_state import (
    PokerStateModel,
    ErrorResponseModel,
    ProfilesResponseModel,
    StatisticsResponseModel
)

from poker_apis.services.processing_service import (
    OfflineProcessingService,
    ProcessingServiceError
)


OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "api_routes_validation_report.json"
)

SAMPLE_STATE_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "real_processing_service_state.json"
)


# --------------------------------------------------
# TEST IMAGE GENERATOR
# --------------------------------------------------

def create_image(
    width=1600,
    height=899,
    image_format="PNG"
):

    buffer = io.BytesIO()

    image = Image.new(
        "RGB",
        (width, height),
        color=(30, 85, 65)
    )

    image.save(
        buffer,
        format=image_format
    )

    return buffer.getvalue()


# --------------------------------------------------
# MOCK PIPELINE
# --------------------------------------------------

class MockScreenshotPipeline:

    def __init__(self, state):

        self.state = state

        self.calls = 0

        self.last_path = None

        self.raise_error = False

    def process_file(self, path):

        self.calls += 1

        self.last_path = Path(path)

        if self.raise_error:

            raise RuntimeError(
                "Simulated processing failure."
            )

        return deepcopy(self.state)


# --------------------------------------------------
# TEMPORARY TEST APPLICATION
# --------------------------------------------------

def create_test_app(settings, service):

    app = FastAPI(
        title="Poker API Route Tests"
    )

    app.state.settings = settings

    app.state.processing_service = service

    app.include_router(
        health_router
    )

    app.include_router(
        api_router,
        prefix=settings.api_prefix
    )

    return app


# --------------------------------------------------
# MAIN TEST RUNNER
# --------------------------------------------------

def main():

    print("=" * 75)
    print("FASTAPI ROUTE VALIDATION")
    print("=" * 75)

    start = time.perf_counter()

    results = []

    sample_state = json.loads(
        SAMPLE_STATE_FILE.read_text(
            encoding="utf-8-sig"
        )
    )

    valid_png = create_image()

    valid_jpeg = create_image(
        image_format="JPEG"
    )

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

    def check_error(
        name,
        response,
        expected_status,
        expected_code
    ):

        try:

            data = ErrorResponseModel.model_validate(
                response.json()
            )

            passed = (
                response.status_code
                == expected_status
                and data.success is False
                and data.error.code
                == expected_code
            )

            record(
                name,
                passed,
                {
                    "status": response.status_code,
                    "code": data.error.code
                }
            )

        except Exception as exc:

            record(
                name,
                False,
                str(exc)
            )

    logging.disable(logging.CRITICAL)

    try:

        with tempfile.TemporaryDirectory() as temp:

            settings = ApplicationSettings(
                project_root=Path(temp),
                max_upload_size_bytes=1024 * 1024
            )

            # Create placeholder template files.
            # These test asset discovery only.

            calibration_dir = (
                settings.calibration_templates_dir
            )

            simulator_dir = (
                settings.simulator_templates_dir
            )

            calibration_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            simulator_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            for suit in (
                "hearts",
                "diamonds",
                "clubs",
                "spades"
            ):

                (
                    calibration_dir
                    / f"{suit}.png"
                ).touch()

                (
                    simulator_dir
                    / f"{suit}_test.png"
                ).touch()

            pipeline = MockScreenshotPipeline(
                sample_state
            )

            service = OfflineProcessingService(
                settings=settings,
                pipeline_factory=lambda: pipeline
            )

            app = create_test_app(
                settings,
                service
            )

            prefix = settings.api_prefix

            endpoint = (
                f"{prefix}/analyze/screenshot"
            )

            with TestClient(app) as client:

                # ----------------------------------
                # HEALTH ENDPOINT
                # ----------------------------------

                print("\nHEALTH ENDPOINT TESTS")

                response = client.get("/health")

                record(
                    "Health endpoint returns 200",
                    response.status_code == 200
                )

                data = response.json()

                record(
                    "Health status is ok",
                    data["status"] == "ok"
                )

                record(
                    "Offline mode reported",
                    data["mode"] == "offline"
                )

                record(
                    "Pipeline initially uninitialized",
                    data["pipeline_initialized"]
                    is False
                )

                # ----------------------------------
                # INFORMATION ENDPOINT
                # ----------------------------------

                print("\nINFORMATION ENDPOINT TESTS")

                response = client.get(
                    f"{prefix}/info"
                )

                record(
                    "Information endpoint returns 200",
                    response.status_code == 200
                )

                data = response.json()

                record(
                    "Application name correct",
                    data["name"] == "poker-apis"
                )

                record(
                    "Configured upload limit reported",
                    data["max_upload_size_bytes"]
                    == 1024 * 1024
                )

                record(
                    "Supported image formats reported",
                    set(
                        data["supported_image_formats"]
                    ) == {
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".bmp"
                    }
                )

                record(
                    "Internal paths not exposed",
                    "project_root" not in data
                    and "temp_upload_dir" not in data
                )

                # ----------------------------------
                # PROFILE ENDPOINT
                # ----------------------------------

                print("\nPROFILE ENDPOINT TESTS")

                response = client.get(
                    f"{prefix}/profiles"
                )

                record(
                    "Profiles endpoint returns 200",
                    response.status_code == 200
                )

                profiles = (
                    ProfilesResponseModel.model_validate(
                        response.json()
                    )
                )

                record(
                    "Three profiles returned",
                    len(profiles.profiles) == 3
                )

                record(
                    "Calibration is default profile",
                    profiles.default_profile
                    == "calibration"
                )

                record(
                    "Template assets detected",
                    all(
                        item.available
                        for item in profiles.profiles
                    )
                )

                record(
                    "Only screenshot profile exposed for analysis",
                    [
                        item.name
                        for item in profiles.profiles
                        if item.api_supported
                    ] == ["calibration"]
                )

                record(
                    "Information endpoints do not initialize OCR",
                    not service.pipeline_initialized
                )

                # ----------------------------------
                # INITIAL STATISTICS
                # ----------------------------------

                print("\nSTATISTICS ENDPOINT TESTS")

                response = client.get(
                    f"{prefix}/statistics"
                )

                record(
                    "Statistics endpoint returns 200",
                    response.status_code == 200
                )

                stats = (
                    StatisticsResponseModel.model_validate(
                        response.json()
                    )
                )

                record(
                    "Initial request count is zero",
                    stats.statistics.total_requests == 0
                )

                record(
                    "Service initially not busy",
                    stats.busy is False
                )

                # ----------------------------------
                # SUCCESSFUL ANALYSIS
                # ----------------------------------

                print("\nSCREENSHOT ANALYSIS TESTS")

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "sample.png",
                            valid_png,
                            "image/png"
                        )
                    }
                )

                record(
                    "PNG analysis returns 200",
                    response.status_code == 200
                )

                state = PokerStateModel.model_validate(
                    response.json()
                )

                record(
                    "Response matches poker state model",
                    isinstance(
                        state,
                        PokerStateModel
                    )
                )

                record(
                    "Valid state returned",
                    state.status == "valid"
                )

                record(
                    "Seven recognized cards returned",
                    state.game.recognized_card_count
                    == 7
                )

                record(
                    "Original filename preserved",
                    state.metadata.screenshot.filename
                    == "sample.png"
                )

                record(
                    "Pipeline initialized",
                    service.pipeline_initialized
                )

                record(
                    "Temporary file cleaned up",
                    not pipeline.last_path.exists()
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "sample.jpeg",
                            valid_jpeg,
                            "image/jpeg"
                        )
                    }
                )

                record(
                    "JPEG analysis returns 200",
                    response.status_code == 200
                )

                record(
                    "Pipeline reused",
                    pipeline.calls == 2
                )

                # ----------------------------------
                # INVALID UPLOADS
                # ----------------------------------

                print("\nINVALID UPLOAD TESTS")

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "empty.png",
                            b"",
                            "image/png"
                        )
                    }
                )

                check_error(
                    "Empty upload returns 400",
                    response,
                    400,
                    "EMPTY_FILE"
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "invalid.exe",
                            valid_png,
                            "application/octet-stream"
                        )
                    }
                )

                check_error(
                    "Unsupported extension returns 415",
                    response,
                    415,
                    "UNSUPPORTED_FILE_FORMAT"
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "../sample.png",
                            valid_png,
                            "image/png"
                        )
                    }
                )

                check_error(
                    "Unsafe filename returns 400",
                    response,
                    400,
                    "INVALID_FILENAME"
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "large.png",
                            b"x" * (
                                settings.max_upload_size_bytes
                                + 1
                            ),
                            "image/png"
                        )
                    }
                )

                check_error(
                    "Oversized upload returns 413",
                    response,
                    413,
                    "FILE_TOO_LARGE"
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "corrupted.png",
                            b"not an image",
                            "image/png"
                        )
                    }
                )

                check_error(
                    "Corrupted image returns 422",
                    response,
                    422,
                    "INVALID_IMAGE"
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "mismatch.jpeg",
                            valid_png,
                            "image/jpeg"
                        )
                    }
                )

                check_error(
                    "Image mismatch returns 415",
                    response,
                    415,
                    "IMAGE_FORMAT_MISMATCH"
                )

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "small.png",
                            create_image(
                                width=800,
                                height=600
                            ),
                            "image/png"
                        )
                    }
                )

                check_error(
                    "Unsupported dimensions return 422",
                    response,
                    422,
                    "UNSUPPORTED_IMAGE_DIMENSIONS"
                )

                response = client.post(
                    endpoint
                )

                record(
                    "Missing upload returns 422",
                    response.status_code == 422
                )

                # ----------------------------------
                # INTERNAL FAILURE
                # ----------------------------------

                print("\nERROR HANDLING TESTS")

                pipeline.raise_error = True

                response = client.post(
                    endpoint,
                    files={
                        "file": (
                            "failure.png",
                            valid_png,
                            "image/png"
                        )
                    }
                )

                check_error(
                    "Pipeline failure returns 500",
                    response,
                    500,
                    "PROCESSING_FAILED"
                )

                record(
                    "Temporary file removed after failure",
                    not pipeline.last_path.exists()
                )

                pipeline.raise_error = False

                # Simulate the busy service response.
                # Actual concurrency was tested earlier.

                with patch.object(
                    service,
                    "analyze_screenshot",
                    side_effect=ProcessingServiceError(
                        code="SERVICE_BUSY",
                        message="Service is busy.",
                        status_code=503
                    )
                ):

                    response = client.post(
                        endpoint,
                        files={
                            "file": (
                                "busy.png",
                                valid_png,
                                "image/png"
                            )
                        }
                    )

                check_error(
                    "Busy service returns 503",
                    response,
                    503,
                    "SERVICE_BUSY"
                )

                record(
                    "Retry-After header included",
                    response.headers.get(
                        "Retry-After"
                    ) == "10"
                )

                # ----------------------------------
                # OPENAPI DOCUMENTATION
                # ----------------------------------

                print("\nOPENAPI DOCUMENTATION TESTS")

                response = client.get(
                    "/openapi.json"
                )

                record(
                    "OpenAPI schema returns 200",
                    response.status_code == 200
                )

                schema = response.json()

                expected_paths = {
                    "/health",
                    f"{prefix}/info",
                    f"{prefix}/profiles",
                    f"{prefix}/statistics",
                    endpoint
                }

                record(
                    "All five API endpoints documented",
                    expected_paths.issubset(
                        schema["paths"]
                    )
                )

                record(
                    "Multipart upload documented",
                    "multipart/form-data" in (
                        schema["paths"][endpoint]
                        ["post"]["requestBody"]
                        ["content"]
                    )
                )

                record(
                    "Poker state response schema documented",
                    "PokerStateModel" in (
                        schema["components"]["schemas"]
                    )
                )

                # ----------------------------------
                # FINAL SERVICE STATE
                # ----------------------------------

                print("\nFINAL SERVICE STATE TESTS")

                response = client.get(
                    f"{prefix}/statistics"
                )

                statistics = response.json()

                counters = statistics["statistics"]

                record(
                    "Two successful requests recorded",
                    counters["successful_requests"] == 2
                )

                record(
                    "One processing failure recorded",
                    counters["failed_requests"] == 1
                )

                record(
                    "Three service-level rejections recorded",
                    counters["rejected_requests"] == 3
                )

                record(
                    "Service available after tests",
                    statistics["busy"] is False
                )

                record(
                    "No temporary files remain",
                    not any(
                        settings.temp_upload_dir.iterdir()
                    )
                )

    finally:

        logging.disable(logging.NOTSET)

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
        "service_statistics": statistics,
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

    print("FASTAPI ROUTE VALIDATION SUMMARY")

    print("=" * 75)

    print(
        json.dumps(
            summary,
            indent=4
        )
    )

    print("\nSERVICE STATISTICS")

    print(
        json.dumps(
            statistics,
            indent=4
        )
    )

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
