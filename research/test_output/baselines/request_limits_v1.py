
import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send


logger = logging.getLogger(__name__)


MULTIPART_OVERHEAD_BYTES = 64 * 1024


class RequestBodyLimitMiddleware:
    """
    Limit HTTP request bodies before multipart parsing.

    Checks both the declared Content-Length and the
    actual bytes received from the ASGI server.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body_size_bytes: int
    ):

        if (
            type(max_body_size_bytes) is not int
            or max_body_size_bytes <= 0
        ):
            raise ValueError(
                "Maximum request body size must "
                "be a positive integer."
            )

        self.app = app

        self.max_body_size_bytes = (
            max_body_size_bytes
        )

    async def send_error(
        self,
        scope,
        receive,
        send,
        status_code,
        code,
        message,
        details=None
    ):

        response = JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": details
                }
            }
        )

        await response(
            scope,
            receive,
            send
        )

    async def reject_oversized_request(
        self,
        scope,
        receive,
        send,
        received_bytes
    ):

        logger.warning(
            "Rejected oversized HTTP request body."
        )

        await self.send_error(
            scope,
            receive,
            send,
            status_code=413,
            code="REQUEST_BODY_TOO_LARGE",
            message=(
                "HTTP request body exceeds "
                "the configured size limit."
            ),
            details={
                "received_bytes": received_bytes,
                "max_body_size_bytes":
                    self.max_body_size_bytes
            }
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):

        # Ignore non-HTTP ASGI connections.

        if scope["type"] != "http":

            await self.app(
                scope,
                receive,
                send
            )

            return

        # ------------------------------------------
        # VALIDATE CONTENT-LENGTH
        # ------------------------------------------

        content_lengths = [
            value
            for name, value in scope.get(
                "headers", []
            )
            if name.lower() == b"content-length"
        ]

        declared_length = None

        if content_lengths:

            try:

                if len(content_lengths) != 1:

                    raise ValueError(
                        "Multiple Content-Length headers."
                    )

                raw_length = (
                    content_lengths[0]
                )

                if (
                    not raw_length
                    or not raw_length.isdigit()
                ):

                    raise ValueError(
                        "Invalid Content-Length."
                    )

                declared_length = int(
                    raw_length
                )

            except ValueError:

                await self.send_error(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    code="INVALID_CONTENT_LENGTH",
                    message=(
                        "Invalid Content-Length header."
                    )
                )

                return

            if (
                declared_length
                > self.max_body_size_bytes
            ):

                await self.reject_oversized_request(
                    scope,
                    receive,
                    send,
                    declared_length
                )

                return

        # ------------------------------------------
        # READ AND COUNT ACTUAL REQUEST BYTES
        # ------------------------------------------

        body = bytearray()

        received_bytes = 0

        while True:

            message = await receive()

            if message["type"] == "http.disconnect":

                return

            if message["type"] != "http.request":

                continue

            chunk = message.get(
                "body", b""
            )

            received_bytes += len(chunk)

            if (
                received_bytes
                > self.max_body_size_bytes
            ):

                await self.reject_oversized_request(
                    scope,
                    receive,
                    send,
                    received_bytes
                )

                return

            body.extend(chunk)

            if not message.get(
                "more_body", False
            ):

                break

        # ------------------------------------------
        # CHECK DECLARED AND ACTUAL LENGTH
        # ------------------------------------------

        if (
            declared_length is not None
            and declared_length != received_bytes
        ):

            await self.send_error(
                scope,
                receive,
                send,
                status_code=400,
                code="CONTENT_LENGTH_MISMATCH",
                message=(
                    "Declared request length does "
                    "not match the received body."
                ),
                details={
                    "declared_bytes": declared_length,
                    "received_bytes": received_bytes
                }
            )

            return

        # ------------------------------------------
        # REPLAY VALIDATED REQUEST BODY
        # ------------------------------------------

        validated_body = bytes(body)

        del body

        body_delivered = False

        async def replay_receive():

            nonlocal body_delivered
            nonlocal validated_body

            if not body_delivered:

                body_delivered = True

                payload = validated_body

                validated_body = b""

                return {
                    "type": "http.request",
                    "body": payload,
                    "more_body": False
                }

            return await receive()

        await self.app(
            scope,
            replay_receive,
            send
        )
