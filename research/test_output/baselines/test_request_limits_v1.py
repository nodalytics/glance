
import sys
import json
import time
import asyncio
import tempfile

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from poker_apis.main import create_app

from poker_apis.core.config import (
    ApplicationSettings
)

from poker_apis.models.poker_state import (
    ErrorResponseModel
)

from poker_apis.middleware.request_limits import (
    RequestBodyLimitMiddleware,
    MULTIPART_OVERHEAD_BYTES
)


OUTPUT_FILE = (
    PROJECT_ROOT
    / "test_output"
    / "request_limits_validation_report.json"
)


# --------------------------------------------------
# DIRECT ASGI TEST HELPER
# --------------------------------------------------

async def simulate_request(
    chunks,
    headers=None,
    limit=1024,
    disconnect=False
):

    sent_messages = []

    downstream_calls = []

    received_chunks = []

    async def downstream(
        scope,
        receive,
        send
    ):

        downstream_calls.append(True)

        while True:

            message = await receive()

            received_chunks.append(
                message.get("body", b"")
            )

            if not message.get(
                "more_body", False
            ):

                break

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": []
        })

        await send({
            "type": "http.response.body",
            "body": b"OK"
        })

    middleware = RequestBodyLimitMiddleware(
        downstream,
        max_body_size_bytes=limit
    )

    messages = []

    for index, chunk in enumerate(chunks):

        messages.append({
            "type": "http.request",
            "body": chunk,
            "more_body": (
                index < len(chunks) - 1
                or disconnect
            )
        })

    if disconnect:

        messages.append({
            "type": "http.disconnect"
        })

    async def receive():

        if messages:

            return messages.pop(0)

        return {
            "type": "http.disconnect"
        }

    async def send(message):

        sent_messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/test",
        "headers": headers or [],
        "http_version": "1.1"
    }

    await middleware(
        scope,
        receive,
        send
    )

    status = next(
        (
            message["status"]
            for message in sent_messages
            if message["type"]
            == "http.response.start"
        ),
        None
    )

    response_body = b"".join(
        message.get("body", b"")
        for message in sent_messages
        if message["type"]
        == "http.response.body"
    )

    return {
        "status": status,
        "response_body": response_body,
        "downstream_called": bool(
            downstream_calls
        ),
        "received_body": b"".join(
            received_chunks
        )
    }


def main():

    print("=" * 75)
    print("HTTP REQUEST BODY LIMIT VALIDATION")
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

        if not passed and details is not None:

            print(f"       {details}")

    def check_error(
        name,
        result,
        expected_status,
        expected_code
    ):

        try:

            error = ErrorResponseModel.model_validate_json(
                result["response_body"]
            )

            record(
                name,
                result["status"] == expected_status
                and error.error.code == expected_code
                and not result["downstream_called"]
            )

        except Exception as exc:

            record(name, False, str(exc))

    # ----------------------------------------------
    # CONFIGURATION TESTS
    # ----------------------------------------------

    print("\nCONFIGURATION TESTS")

    for invalid_limit in [0, -1, True, 1.5]:

        try:

            RequestBodyLimitMiddleware(
                FastAPI(),
                invalid_limit
            )

        except ValueError:

            record(
                f"Invalid limit rejected: "
                f"{invalid_limit!r}",
                True
            )

        else:

            record(
                f"Invalid limit rejected: "
                f"{invalid_limit!r}",
                False
            )

    # ----------------------------------------------
    # NORMAL REQUEST TESTS
    # ----------------------------------------------

    print("\nNORMAL REQUEST TESTS")

    result = asyncio.run(
        simulate_request([b""])
    )

    record(
        "Empty request accepted",
        result["status"] == 200
        and result["downstream_called"]
    )

    result = asyncio.run(
        simulate_request(
            [b"hello"],
            headers=[
                (b"content-length", b"5")
            ]
        )
    )

    record(
        "Valid Content-Length accepted",
        result["status"] == 200
    )

    record(
        "Original body preserved",
        result["received_body"] == b"hello"
    )

    result = asyncio.run(
        simulate_request(
            [b"x" * 1024],
            headers=[
                (b"content-length", b"1024")
            ]
        )
    )

    record(
        "Exact request size limit accepted",
        result["status"] == 200
        and len(result["received_body"]) == 1024
    )

    # ----------------------------------------------
    # OVERSIZED REQUEST TESTS
    # ----------------------------------------------

    print("\nOVERSIZED REQUEST TESTS")

    result = asyncio.run(
        simulate_request(
            [b"x" * 1025],
            headers=[
                (b"content-length", b"1025")
            ]
        )
    )

    check_error(
        "Oversized Content-Length rejected",
        result,
        413,
        "REQUEST_BODY_TOO_LARGE"
    )

    result = asyncio.run(
        simulate_request(
            [b"x" * 1025]
        )
    )

    check_error(
        "Oversized body without header rejected",
        result,
        413,
        "REQUEST_BODY_TOO_LARGE"
    )

    result = asyncio.run(
        simulate_request(
            [
                b"x" * 600,
                b"y" * 500
            ]
        )
    )

    check_error(
        "Oversized multi-chunk body rejected",
        result,
        413,
        "REQUEST_BODY_TOO_LARGE"
    )

    result = asyncio.run(
        simulate_request(
            [b"x" * 1025],
            headers=[
                (b"content-length", b"10")
            ]
        )
    )

    check_error(
        "False small Content-Length cannot bypass limit",
        result,
        413,
        "REQUEST_BODY_TOO_LARGE"
    )

    # ----------------------------------------------
    # INVALID HEADER TESTS
    # ----------------------------------------------

    print("\nINVALID HEADER TESTS")

    for value in [
        b"-1",
        b"abc",
        b"",
        b"1.5",
        b"+10"
    ]:

        result = asyncio.run(
            simulate_request(
                [b""],
                headers=[
                    (b"content-length", value)
                ]
            )
        )

        check_error(
            f"Invalid Content-Length rejected: "
            f"{value!r}",
            result,
            400,
            "INVALID_CONTENT_LENGTH"
        )

    result = asyncio.run(
        simulate_request(
            [b"hello"],
            headers=[
                (b"content-length", b"5"),
                (b"content-length", b"5")
            ]
        )
    )

    check_error(
        "Duplicate Content-Length rejected",
        result,
        400,
        "INVALID_CONTENT_LENGTH"
    )

    result = asyncio.run(
        simulate_request(
            [b"hello"],
            headers=[
                (b"content-length", b"4")
            ]
        )
    )

    check_error(
        "Content-Length mismatch rejected",
        result,
        400,
        "CONTENT_LENGTH_MISMATCH"
    )

    # ----------------------------------------------
    # CHUNK AND DISCONNECT TESTS
    # ----------------------------------------------

    print("\nCHUNK AND DISCONNECT TESTS")

    result = asyncio.run(
        simulate_request(
            [
                b"hello",
                b" ",
                b"world"
            ]
        )
    )

    record(
        "Valid multi-chunk request accepted",
        result["status"] == 200
    )

    record(
        "Chunk ordering preserved",
        result["received_body"] == b"hello world"
    )

    result = asyncio.run(
        simulate_request(
            [b"partial"],
            disconnect=True
        )
    )

    record(
        "Disconnected request not forwarded",
        not result["downstream_called"]
    )

    record(
        "No response attempted after disconnect",
        result["status"] is None
    )

    # ----------------------------------------------
    # FASTAPI BODY REPLAY TESTS
    # ----------------------------------------------

    print("\nFASTAPI BODY REPLAY TESTS")

    echo_app = FastAPI()

    echo_app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_size_bytes=1024
    )

    @echo_app.post("/echo")
    async def echo(request: Request):

        body = await request.body()

        return {
            "size": len(body),
            "text": body.decode("utf-8")
        }

    with TestClient(echo_app) as client:

        response = client.post(
            "/echo",
            content=b"test payload"
        )

        record(
            "FastAPI receives validated request",
            response.status_code == 200
        )

        record(
            "FastAPI receives unchanged body",
            response.json() == {
                "size": 12,
                "text": "test payload"
            }
        )

        response = client.post(
            "/echo",
            content=b"x" * 1025
        )

        record(
            "FastAPI oversized request returns 413",
            response.status_code == 413
        )

    # ----------------------------------------------
    # REAL APPLICATION INTEGRATION
    # ----------------------------------------------

    print("\nREAL APPLICATION INTEGRATION")

    with tempfile.TemporaryDirectory() as temp:

        settings = ApplicationSettings(
            project_root=Path(temp),
            max_upload_size_bytes=1024
        )

        app = create_app(
            settings=settings
        )

        body_limit = (
            settings.max_upload_size_bytes
            + MULTIPART_OVERHEAD_BYTES
        )

        with TestClient(app) as client:

            service = app.state.processing_service

            response = client.get("/health")

            record(
                "Health endpoint remains available",
                response.status_code == 200
            )

            response = client.get("/docs")

            record(
                "Swagger documentation remains available",
                response.status_code == 200
            )

            response = client.get("/openapi.json")

            record(
                "OpenAPI schema remains available",
                response.status_code == 200
            )

            before = service.get_statistics().copy()

            response = client.post(
                "/api/v1/analyze/screenshot",
                files={
                    "file": (
                        "oversized.png",
                        b"x" * (body_limit + 1),
                        "image/png"
                    )
                }
            )

            record(
                "Oversized multipart request rejected",
                response.status_code == 413
            )

            error = ErrorResponseModel.model_validate(
                response.json()
            )

            record(
                "Request limit error uses API schema",
                error.error.code
                == "REQUEST_BODY_TOO_LARGE"
            )

            record(
                "Configured request limit reported",
                error.error.details is not None
                and error.error.details.get(
                    "max_body_size_bytes"
                ) == body_limit
            )

            record(
                "Oversized request never reaches service",
                service.get_statistics() == before
            )

            record(
                "Oversized request does not initialize OCR",
                not service.pipeline_initialized
            )

            record(
                "Oversized request creates no service upload files",
                not any(
                    settings.temp_upload_dir.iterdir()
                )
            )

            response = client.post(
                "/api/v1/analyze/screenshot",
                files={
                    "file": (
                        "oversized_file.png",
                        b"x" * 2048,
                        "image/png"
                    )
                }
            )

            record(
                "Existing file size protection remains active",
                response.status_code == 413
                and response.json()["error"]["code"]
                == "FILE_TOO_LARGE"
            )

            response = client.post(
                "/api/v1/analyze/screenshot"
            )

            record(
                "Missing upload validation preserved",
                response.status_code == 422
            )

            response = client.get("/health")

            record(
                "Application remains healthy after rejection",
                response.status_code == 200
                and response.json()["busy"] is False
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

    print("HTTP REQUEST LIMIT VALIDATION SUMMARY")

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
