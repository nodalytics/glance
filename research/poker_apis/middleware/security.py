
import ipaddress
import logging

from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Scope, Receive, Send


logger = logging.getLogger(__name__)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=()"
    )
}


class LocalSecurityMiddleware:
    """
    Security middleware for the local offline API.

    Validates:
        - Client network address
        - HTTP Host header
        - Browser Origin header

    Adds security headers to HTTP responses.
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts=None,
        allow_test_client: bool = False
    ):

        self.app = app

        self.allowed_hosts = frozenset(
            allowed_hosts or (
                "localhost",
                "127.0.0.1",
                "::1"
            )
        )

        self.allow_test_client = allow_test_client

    # ----------------------------------------------
    # CLIENT ADDRESS VALIDATION
    # ----------------------------------------------

    def is_local_client(self, client):

        if not client:

            return False

        address = client[0]

        if (
            self.allow_test_client
            and address == "testclient"
        ):

            return True

        try:

            parsed = ipaddress.ip_address(
                address
            )

            if isinstance(
                parsed,
                ipaddress.IPv6Address
            ):

                if parsed.ipv4_mapped:

                    parsed = parsed.ipv4_mapped

            return parsed.is_loopback

        except ValueError:

            return False

    # ----------------------------------------------
    # HEADER EXTRACTION
    # ----------------------------------------------

    @staticmethod
    def get_header_values(scope, name):

        target = name.lower().encode("ascii")

        return [
            value.decode("latin-1")
            for key, value in scope.get(
                "headers", []
            )
            if key.lower() == target
        ]

    # ----------------------------------------------
    # HOST VALIDATION
    # ----------------------------------------------

    def parse_host(self, value):

        if not value:

            return None

        if any(
            character.isspace()
            or ord(character) < 32
            for character in value
        ):

            return None

        if any(
            character in value
            for character in "/\\@?#,"
        ):

            return None

        try:

            parsed = urlsplit(
                f"http://{value}"
            )

            hostname = parsed.hostname

            port = parsed.port

            if not hostname:

                return None

            if value.endswith(":"):

                return None

            if port is not None and port == 0:

                return None

            return hostname.lower(), port

        except ValueError:

            return None

    def is_allowed_host(self, hostname):

        if hostname in self.allowed_hosts:

            return True

        return (
            self.allow_test_client
            and hostname == "testserver"
        )

    # ----------------------------------------------
    # BROWSER ORIGIN VALIDATION
    # ----------------------------------------------

    def is_allowed_origin(
        self,
        origin,
        host,
        scheme
    ):

        if not origin or origin == "null":

            return False

        if any(
            character.isspace()
            or ord(character) < 32
            for character in origin
        ):

            return False

        try:

            parsed = urlsplit(origin)

            if parsed.scheme not in (
                "http",
                "https"
            ):

                return False

            if (
                parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):

                return False

            if not parsed.hostname:

                return False

            if not self.is_allowed_host(
                parsed.hostname.lower()
            ):

                return False

            request_host, request_port = host

            default_port = (
                443 if scheme == "https"
                else 80
            )

            origin_port = (
                parsed.port
                if parsed.port is not None
                else (
                    443
                    if parsed.scheme == "https"
                    else 80
                )
            )

            return (
                parsed.scheme == scheme
                and parsed.hostname.lower()
                == request_host
                and origin_port
                == (
                    request_port
                    if request_port is not None
                    else default_port
                )
            )

        except ValueError:

            return False

    # ----------------------------------------------
    # STRUCTURED SECURITY ERROR
    # ----------------------------------------------

    async def send_error(
        self,
        scope,
        receive,
        send,
        status_code,
        code,
        message
    ):

        response = JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": None
                }
            }
        )

        await response(
            scope,
            receive,
            send
        )

    # ----------------------------------------------
    # ASGI MIDDLEWARE ENTRY POINT
    # ----------------------------------------------

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):

        if scope["type"] != "http":

            await self.app(
                scope,
                receive,
                send
            )

            return

        # Add headers to downstream responses
        # and middleware-generated errors.

        async def secure_send(message):

            if (
                message["type"]
                == "http.response.start"
            ):

                headers = MutableHeaders(
                    scope=message
                )

                for name, value in (
                    SECURITY_HEADERS.items()
                ):

                    headers[name] = value

            await send(message)

        # ------------------------------------------
        # CLIENT NETWORK ADDRESS
        # ------------------------------------------

        if not self.is_local_client(
            scope.get("client")
        ):

            logger.warning(
                "Rejected non-local HTTP client."
            )

            await self.send_error(
                scope,
                receive,
                secure_send,
                403,
                "NON_LOCAL_CLIENT",
                "Only local clients are permitted."
            )

            return

        # ------------------------------------------
        # HTTP HOST HEADER
        # ------------------------------------------

        host_values = self.get_header_values(
            scope,
            "host"
        )

        host = (
            self.parse_host(host_values[0])
            if len(host_values) == 1
            else None
        )

        if (
            host is None
            or not self.is_allowed_host(host[0])
        ):

            logger.warning(
                "Rejected untrusted HTTP Host header."
            )

            await self.send_error(
                scope,
                receive,
                secure_send,
                400,
                "INVALID_HOST",
                "HTTP Host is not permitted."
            )

            return

        # ------------------------------------------
        # BROWSER ORIGIN
        # ------------------------------------------

        origins = self.get_header_values(
            scope,
            "origin"
        )

        if origins:

            allowed = (
                len(origins) == 1
                and self.is_allowed_origin(
                    origins[0],
                    host,
                    scope.get("scheme", "http")
                )
            )

            if not allowed:

                logger.warning(
                    "Rejected untrusted browser origin."
                )

                await self.send_error(
                    scope,
                    receive,
                    secure_send,
                    403,
                    "ORIGIN_NOT_ALLOWED",
                    "Browser origin is not permitted."
                )

                return

        # ------------------------------------------
        # FORWARD VALIDATED REQUEST
        # ------------------------------------------

        await self.app(
            scope,
            receive,
            secure_send
        )
