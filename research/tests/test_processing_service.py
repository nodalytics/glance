
import sys
import io
import json
import time
import logging
import tempfile
import threading

from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from PIL import Image

from poker_apis.core.config import (
    ApplicationSettings
)

from poker_apis.models.poker_state import (
    PokerStateModel,
    ErrorResponseModel
)

from poker_apis.services.processing_service import (
    OfflineProcessingService,
    ProcessingServiceError
)


OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "processing_service_validation_report.json"
)

SAMPLE_STATE_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "screenshot_table_state.json"
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

        self.file_existed_during_processing = False

        self.raise_error = False

        self.return_invalid_state = False

    def process_file(self, screenshot_path):

        self.calls += 1

        self.last_path = Path(
            screenshot_path
        )

        self.file_existed_during_processing = (
            self.last_path.is_file()
        )

        if self.raise_error:

            raise RuntimeError(
                "Simulated pipeline failure."
            )

        if self.return_invalid_state:

            return {
                "invalid": True
            }

        return deepcopy(
            self.state
        )


# --------------------------------------------------
# MAIN TEST RUNNER
# --------------------------------------------------

def main():

    print("=" * 75)
    print("OFFLINE PROCESSING SERVICE VALIDATION")
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

    def expect_error(
        name,
        callback,
        expected_code,
        expected_status
    ):

        try:

            callback()

        except ProcessingServiceError as exc:

            record(
                name,
                exc.code == expected_code
                and exc.status_code == expected_status,
                f"{exc.code}: {exc.status_code}"
            )

            return exc

        except Exception as exc:

            record(
                name,
                False,
                str(exc)
            )

        else:

            record(
                name,
                False,
                "Expected error was not raised."
            )

        return None

    # Suppress expected simulated error logs.
    logging.disable(logging.CRITICAL)

    try:

        with tempfile.TemporaryDirectory() as temp:

            settings = ApplicationSettings(
                project_root=Path(temp)
            )

            mock_pipeline = MockScreenshotPipeline(
                sample_state
            )

            factory_calls = []

            def pipeline_factory():

                factory_calls.append(True)

                return mock_pipeline

            service = OfflineProcessingService(
                settings=settings,
                pipeline_factory=pipeline_factory
            )

            # --------------------------------------
            # INITIALIZATION
            # --------------------------------------

            print("\nSERVICE INITIALIZATION TESTS")

            record(
                "Runtime directory created",
                settings.temp_upload_dir.is_dir()
            )

            record(
                "Pipeline initialization is lazy",
                not service.pipeline_initialized
                and len(factory_calls) == 0
            )

            record(
                "Service initially available",
                not service.is_busy
            )

            # --------------------------------------
            # FILENAME VALIDATION
            # --------------------------------------

            print("\nFILENAME VALIDATION TESTS")

            record(
                "PNG extension accepted",
                service.validate_filename(
                    "sample.png"
                ) == ".png"
            )

            record(
                "Uppercase extension normalized",
                service.validate_filename(
                    "sample.JPEG"
                ) == ".jpeg"
            )

            filename_cases = [
                (
                    "Missing filename rejected",
                    "",
                    "INVALID_FILENAME",
                    400
                ),
                (
                    "Parent path rejected",
                    "../sample.png",
                    "INVALID_FILENAME",
                    400
                ),
                (
                    "Windows path rejected",
                    r"C:\temp\sample.png",
                    "INVALID_FILENAME",
                    400
                ),
                (
                    "Unsupported extension rejected",
                    "sample.exe",
                    "UNSUPPORTED_FILE_FORMAT",
                    415
                )
            ]

            for (
                name,
                filename,
                code,
                status
            ) in filename_cases:

                expect_error(
                    name,
                    lambda f=filename:
                        service.validate_filename(f),
                    code,
                    status
                )

            # --------------------------------------
            # FILE SIZE VALIDATION
            # --------------------------------------

            print("\nFILE SIZE VALIDATION TESTS")

            expect_error(
                "Empty upload rejected",
                lambda: service.validate_file_size(
                    b""
                ),
                "EMPTY_FILE",
                400
            )

            expect_error(
                "Non-byte content rejected",
                lambda: service.validate_file_size(
                    "not bytes"
                ),
                "INVALID_FILE_CONTENT",
                400
            )

            expect_error(
                "Oversized upload rejected",
                lambda: service.validate_file_size(
                    b"x" * (
                        settings.max_upload_size_bytes
                        + 1
                    )
                ),
                "FILE_TOO_LARGE",
                413
            )

            # --------------------------------------
            # IMAGE VALIDATION
            # --------------------------------------

            print("\nIMAGE VALIDATION TESTS")

            png_info = service.validate_upload(
                "sample.png",
                valid_png
            )

            record(
                "Valid PNG accepted",
                png_info["format"] == "PNG"
                and png_info["width"] == 1600
                and png_info["height"] == 899
            )

            jpeg_info = service.validate_upload(
                "sample.jpeg",
                valid_jpeg
            )

            record(
                "Valid JPEG accepted",
                jpeg_info["format"] == "JPEG"
            )

            alternate_image = create_image(
                height=900
            )

            record(
                "1600x900 dimensions accepted",
                service.validate_upload(
                    "alternate.png",
                    alternate_image
                )["height"] == 900
            )

            expect_error(
                "Corrupted image rejected",
                lambda: service.validate_upload(
                    "corrupted.png",
                    b"invalid image content"
                ),
                "INVALID_IMAGE",
                422
            )

            expect_error(
                "Image extension mismatch rejected",
                lambda: service.validate_upload(
                    "sample.jpg",
                    valid_png
                ),
                "IMAGE_FORMAT_MISMATCH",
                415
            )

            wrong_dimensions = create_image(
                width=800,
                height=600
            )

            expect_error(
                "Unsupported dimensions rejected",
                lambda: service.validate_upload(
                    "small.png",
                    wrong_dimensions
                ),
                "UNSUPPORTED_IMAGE_DIMENSIONS",
                422
            )

            record(
                "Upload validation does not initialize OCR",
                not service.pipeline_initialized
            )

            # --------------------------------------
            # SUCCESSFUL PROCESSING
            # --------------------------------------

            print("\nSUCCESSFUL PROCESSING TESTS")

            state = service.analyze_screenshot(
                "original_screenshot.png",
                valid_png
            )

            record(
                "Pipeline initialized on first request",
                service.pipeline_initialized
                and len(factory_calls) == 1
            )

            record(
                "Pipeline received existing temporary file",
                mock_pipeline.file_existed_during_processing
            )

            record(
                "Validated response returned",
                isinstance(
                    state,
                    PokerStateModel
                )
            )

            record(
                "Original filename preserved",
                state.metadata.screenshot.filename
                == "original_screenshot.png"
            )

            record(
                "Upload metadata included",
                state.metadata.upload["format"]
                == "PNG"
            )

            record(
                "Service timing included",
                state.metadata.service_processing_seconds
                >= 0
            )

            record(
                "Temporary file removed after success",
                not mock_pipeline.last_path.exists()
            )

            record(
                "Processing lock released after success",
                not service.is_busy
            )

            first_path = mock_pipeline.last_path

            service.analyze_screenshot(
                "second_screenshot.png",
                valid_png
            )

            record(
                "Pipeline reused for second request",
                len(factory_calls) == 1
                and mock_pipeline.calls == 2
            )

            record(
                "Unique temporary filenames generated",
                first_path != mock_pipeline.last_path
            )

            # --------------------------------------
            # PROCESSING FAILURE
            # --------------------------------------

            print("\nPROCESSING FAILURE TESTS")

            mock_pipeline.raise_error = True

            expect_error(
                "Pipeline failure converted to service error",
                lambda: service.analyze_screenshot(
                    "failure.png",
                    valid_png
                ),
                "PROCESSING_FAILED",
                500
            )

            record(
                "Temporary file removed after failure",
                not mock_pipeline.last_path.exists()
            )

            record(
                "Processing lock released after failure",
                not service.is_busy
            )

            mock_pipeline.raise_error = False

            mock_pipeline.return_invalid_state = True

            expect_error(
                "Invalid pipeline response rejected",
                lambda: service.analyze_screenshot(
                    "invalid_state.png",
                    valid_png
                ),
                "INVALID_PIPELINE_RESPONSE",
                500
            )

            record(
                "Temporary file removed after schema failure",
                not mock_pipeline.last_path.exists()
            )

            mock_pipeline.return_invalid_state = False

            # --------------------------------------
            # CONCURRENT PROCESSING
            # --------------------------------------

            print("\nCONCURRENCY TESTS")

            started = threading.Event()

            release = threading.Event()

            worker_errors = []

            original_process = (
                mock_pipeline.process_file
            )

            def blocking_process(path):

                started.set()

                if not release.wait(timeout=10):

                    raise TimeoutError(
                        "Test worker timed out."
                    )

                return original_process(path)

            mock_pipeline.process_file = (
                blocking_process
            )

            def worker():

                try:

                    service.analyze_screenshot(
                        "worker.png",
                        valid_png
                    )

                except Exception as exc:

                    worker_errors.append(
                        str(exc)
                    )

            thread = threading.Thread(
                target=worker,
                daemon=True
            )

            thread.start()

            try:

                worker_started = started.wait(
                    timeout=5
                )

                record(
                    "Worker acquired processing lock",
                    worker_started
                    and service.is_busy
                )

                expect_error(
                    "Concurrent processing rejected",
                    lambda: service.analyze_screenshot(
                        "concurrent.png",
                        valid_png
                    ),
                    "SERVICE_BUSY",
                    503
                )

            finally:

                release.set()

                thread.join(timeout=15)

            record(
                "Worker completed successfully",
                not thread.is_alive()
                and not worker_errors
            )

            record(
                "Service available after worker completion",
                not service.is_busy
            )

            mock_pipeline.process_file = (
                original_process
            )

            # --------------------------------------
            # REQUEST REJECTION
            # --------------------------------------

            print("\nREQUEST REJECTION TESTS")

            error = expect_error(
                "Invalid request rejected before processing",
                lambda: service.analyze_screenshot(
                    "invalid.exe",
                    valid_png
                ),
                "UNSUPPORTED_FILE_FORMAT",
                415
            )

            try:

                error_model = (
                    ErrorResponseModel.model_validate(
                        error.to_dict()
                    )
                )

                record(
                    "Structured error matches API model",
                    error_model.success is False
                )

            except Exception as exc:

                record(
                    "Structured error matches API model",
                    False,
                    str(exc)
                )

            # --------------------------------------
            # STATISTICS AND CLEANUP
            # --------------------------------------

            print("\nSTATISTICS AND CLEANUP TESTS")

            statistics = service.get_statistics()

            record(
                "Total request count correct",
                statistics["total_requests"] == 7
            )

            record(
                "Successful request count correct",
                statistics["successful_requests"] == 3
            )

            record(
                "Failed request count correct",
                statistics["failed_requests"] == 2
            )

            record(
                "Rejected request count correct",
                statistics["rejected_requests"] == 1
            )

            record(
                "Busy request count correct",
                statistics["busy_requests"] == 1
            )

            record(
                "No temporary upload files remain",
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

    print("PROCESSING SERVICE VALIDATION SUMMARY")

    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print("\nSERVICE STATISTICS")

    print(json.dumps(statistics, indent=4))

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
