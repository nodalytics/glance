
import sys
import json
import time
import tempfile

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from fastapi.testclient import TestClient

from poker_apis.main import create_app

from poker_apis.core.config import (
    ApplicationSettings
)

from poker_apis.models.poker_state import (
    ErrorResponseModel
)

from poker_apis.services.processing_service import (
    OfflineProcessingService,
    ProcessingServiceError
)


OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "api_application_validation_report.json"
)


def main():

    print("=" * 75)
    print("FASTAPI APPLICATION VALIDATION")
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

    def check_error(
        name,
        response,
        expected_status,
        expected_code
    ):

        try:

            error = ErrorResponseModel.model_validate(
                response.json()
            )

            record(
                name,
                response.status_code
                == expected_status
                and error.error.code
                == expected_code,
                {
                    "status": response.status_code,
                    "code": error.error.code
                }
            )

        except Exception as exc:

            record(
                name,
                False,
                str(exc)
            )

    with tempfile.TemporaryDirectory() as temp:

        settings = ApplicationSettings(
            project_root=Path(temp)
        )

        # ------------------------------------------
        # APPLICATION FACTORY
        # ------------------------------------------

        print("\nAPPLICATION FACTORY TESTS")

        app = create_app(settings=settings)

        record(
            "Application factory creates instance",
            app is not None
        )

        record(
            "Application title correct",
            app.title == settings.app_name
        )

        record(
            "Application version correct",
            app.version == settings.app_version
        )

        record(
            "Debug disabled",
            app.debug is False
        )

        second_app = create_app(
            settings=settings
        )

        record(
            "Factory creates independent instances",
            app is not second_app
        )

        # ------------------------------------------
        # TEST-ONLY EXCEPTION ENDPOINTS
        # ------------------------------------------

        @app.get(
            "/test/service-error",
            include_in_schema=False
        )
        def simulated_service_error():

            raise ProcessingServiceError(
                code="SERVICE_BUSY",
                message="Simulated busy service.",
                status_code=503
            )

        @app.get(
            "/test/unexpected-error",
            include_in_schema=False
        )
        def simulated_unexpected_error():

            raise RuntimeError(
                "Simulated internal private error."
            )

        # ------------------------------------------
        # APPLICATION LIFECYCLE
        # ------------------------------------------

        with TestClient(
            app,
            raise_server_exceptions=False
        ) as client:

            print("\nAPPLICATION LIFECYCLE TESTS")

            service = app.state.processing_service

            record(
                "Processing service initialized",
                isinstance(
                    service,
                    OfflineProcessingService
                )
            )

            record(
                "Runtime upload directory created",
                settings.temp_upload_dir.is_dir()
            )

            record(
                "Output directory created",
                settings.output_dir.is_dir()
            )

            record(
                "OCR remains uninitialized at startup",
                not service.pipeline_initialized
            )

            # --------------------------------------
            # ROOT ENDPOINT
            # --------------------------------------

            print("\nROOT ENDPOINT TESTS")

            response = client.get("/")

            record(
                "Root endpoint returns 200",
                response.status_code == 200
            )

            data = response.json()

            record(
                "Root application name correct",
                data["name"] == settings.app_name
            )

            record(
                "Root reports offline mode",
                data["mode"] == "offline"
            )

            record(
                "Root includes documentation URL",
                data["endpoints"]["documentation"]
                == "/docs"
            )

            record(
                "Root includes analysis endpoint",
                data["endpoints"][
                    "analyze_screenshot"
                ] == (
                    "/api/v1/analyze/screenshot"
                )
            )

            # --------------------------------------
            # ROUTER REGISTRATION
            # --------------------------------------

            print("\nROUTER REGISTRATION TESTS")

            for path in [
                "/health",
                "/api/v1/info",
                "/api/v1/profiles",
                "/api/v1/statistics"
            ]:

                response = client.get(path)

                record(
                    f"Registered route: {path}",
                    response.status_code == 200
                )

            # --------------------------------------
            # DOCUMENTATION
            # --------------------------------------

            print("\nDOCUMENTATION TESTS")

            response = client.get("/docs")

            record(
                "Swagger UI returns 200",
                response.status_code == 200
            )

            record(
                "Swagger HTML returned",
                "text/html" in response.headers.get(
                    "content-type", ""
                )
            )

            response = client.get("/redoc")

            record(
                "ReDoc returns 200",
                response.status_code == 200
            )

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
                "/api/v1/info",
                "/api/v1/profiles",
                "/api/v1/statistics",
                "/api/v1/analyze/screenshot"
            }

            record(
                "Five production endpoints documented",
                expected_paths.issubset(
                    schema["paths"]
                )
            )

            record(
                "Root excluded from OpenAPI schema",
                "/" not in schema["paths"]
            )

            # --------------------------------------
            # ERROR HANDLING
            # --------------------------------------

            print("\nERROR HANDLING TESTS")

            response = client.get(
                "/unknown-endpoint"
            )

            check_error(
                "Unknown endpoint returns structured 404",
                response,
                404,
                "NOT_FOUND"
            )

            response = client.post("/health")

            check_error(
                "Unsupported method returns structured 405",
                response,
                405,
                "METHOD_NOT_ALLOWED"
            )

            record(
                "Allow header preserved",
                "GET" in response.headers.get(
                    "Allow", ""
                )
            )

            response = client.post(
                "/api/v1/analyze/screenshot"
            )

            check_error(
                "Missing upload returns structured 422",
                response,
                422,
                "REQUEST_VALIDATION_ERROR"
            )

            error_details = response.json()[
                "error"
            ]["details"]

            record(
                "Validation error details included",
                bool(
                    error_details.get(
                        "validation_errors"
                    )
                )
            )

            response = client.get(
                "/test/service-error"
            )

            check_error(
                "Global service exception handler works",
                response,
                503,
                "SERVICE_BUSY"
            )

            record(
                "Service retry header preserved",
                response.headers.get(
                    "Retry-After"
                ) == "10"
            )

            response = client.get(
                "/test/unexpected-error"
            )

            check_error(
                "Unexpected exception returns structured 500",
                response,
                500,
                "INTERNAL_SERVER_ERROR"
            )

            record(
                "Internal exception details not exposed",
                "Simulated internal private error"
                not in response.text
            )

            # --------------------------------------
            # FINAL SERVICE STATE
            # --------------------------------------

            print("\nFINAL SERVICE STATE TESTS")

            record(
                "OCR remains uninitialized",
                not service.pipeline_initialized
            )

            record(
                "No analysis requests processed",
                service.get_statistics()[
                    "total_requests"
                ] == 0
            )

            record(
                "Service remains available",
                not service.is_busy
            )

        record(
            "Service reference released on shutdown",
            app.state.processing_service is None
        )

        # ------------------------------------------
        # DISABLED DOCUMENTATION
        # ------------------------------------------

        print("\nDISABLED DOCUMENTATION TESTS")

        disabled_settings = ApplicationSettings(
            project_root=Path(temp),
            docs_enabled=False
        )

        disabled_app = create_app(
            settings=disabled_settings
        )

        with TestClient(disabled_app) as client:

            for path in [
                "/docs",
                "/redoc",
                "/openapi.json"
            ]:

                response = client.get(path)

                record(
                    f"Disabled endpoint: {path}",
                    response.status_code == 404
                )

            record(
                "Health available without documentation",
                client.get(
                    "/health"
                ).status_code == 200
            )

        # ------------------------------------------
        # CUSTOM API PREFIX
        # ------------------------------------------

        print("\nCUSTOM API PREFIX TESTS")

        custom_settings = ApplicationSettings(
            project_root=Path(temp),
            api_prefix="/custom/v2"
        )

        custom_app = create_app(
            settings=custom_settings
        )

        with TestClient(custom_app) as client:

            record(
                "Custom API prefix works",
                client.get(
                    "/custom/v2/info"
                ).status_code == 200
            )

            record(
                "Default prefix no longer registered",
                client.get(
                    "/api/v1/info"
                ).status_code == 404
            )

            record(
                "Root reflects custom API prefix",
                client.get("/").json()[
                    "endpoints"
                ]["information"]
                == "/custom/v2/info"
            )

        # ------------------------------------------
        # DEPENDENCY INJECTION
        # ------------------------------------------

        print("\nDEPENDENCY INJECTION TESTS")

        injected_service = (
            OfflineProcessingService(
                settings=settings
            )
        )

        injected_app = create_app(
            settings=settings,
            processing_service=injected_service
        )

        with TestClient(injected_app):

            record(
                "Injected service reused",
                injected_app.state.processing_service
                is injected_service
            )

            record(
                "Injected service remains lazy",
                not injected_service.pipeline_initialized
            )

        try:

            create_app(
                settings=custom_settings,
                processing_service=injected_service
            )

        except ValueError:

            record(
                "Mismatched service settings rejected",
                True
            )

        else:

            record(
                "Mismatched service settings rejected",
                False
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

    print("FASTAPI APPLICATION VALIDATION SUMMARY")

    print("=" * 75)

    print(
        json.dumps(
            summary,
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
