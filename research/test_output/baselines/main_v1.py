
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from fastapi.exceptions import (
    RequestValidationError
)

from fastapi.responses import JSONResponse

from starlette.exceptions import (
    HTTPException as StarletteHTTPException
)

from poker_apis.api.routes import (
    health_router,
    api_router,
    create_error_response
)

from poker_apis.core.config import (
    ApplicationSettings,
    get_settings
)

from poker_apis.models.poker_state import (
    ErrorResponseModel
)

from poker_apis.services.processing_service import (
    OfflineProcessingService,
    ProcessingServiceError
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# LOGGING CONFIGURATION
# --------------------------------------------------

def configure_logging(
    settings: ApplicationSettings
):

    logging.basicConfig(
        level=getattr(
            logging,
            settings.log_level
        ),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        )
    )


# --------------------------------------------------
# STANDARD ERROR RESPONSE
# --------------------------------------------------

def build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
    headers: dict | None = None
) -> JSONResponse:

    error = ErrorResponseModel.model_validate({
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    })

    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(
            mode="json"
        ),
        headers=headers
    )


# --------------------------------------------------
# APPLICATION FACTORY
# --------------------------------------------------

def create_app(
    settings: ApplicationSettings | None = None,
    processing_service: OfflineProcessingService | None = None
) -> FastAPI:

    settings = settings or get_settings()

    configure_logging(settings)

    if (
        processing_service is not None
        and processing_service.settings != settings
    ):

        raise ValueError(
            "Processing service settings must "
            "match application settings."
        )

    # ----------------------------------------------
    # APPLICATION LIFESPAN
    # ----------------------------------------------

    @asynccontextmanager
    async def lifespan(application: FastAPI):

        logger.info(
            "Starting %s version %s",
            settings.app_name,
            settings.app_version
        )

        logger.info(
            "Operating mode: %s",
            settings.mode
        )

        settings.prepare_runtime_directories()

        service = processing_service

        if service is None:

            service = OfflineProcessingService(
                settings=settings
            )

        application.state.settings = settings

        application.state.processing_service = (
            service
        )

        logger.info(
            "Offline processing service ready."
        )

        logger.info(
            "OCR pipeline initialization is lazy."
        )

        try:

            yield

        finally:

            logger.info(
                "Application shutdown started."
            )

            logger.info(
                "Final service statistics: %s",
                service.get_statistics()
            )

            application.state.processing_service = (
                None
            )

            logger.info(
                "Application shutdown completed."
            )

    # ----------------------------------------------
    # FASTAPI INSTANCE
    # ----------------------------------------------

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            settings.description
            + "\n\n"
            + "Processes previously saved offline "
              "screenshots matching the calibrated "
              "layout."
        ),
        debug=settings.debug,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "Health",
                "description": (
                    "Application availability."
                )
            },
            {
                "name": "Information",
                "description": (
                    "Application information "
                    "and processing statistics."
                )
            },
            {
                "name": "Recognition",
                "description": (
                    "Offline recognition profiles."
                )
            },
            {
                "name": "Analysis",
                "description": (
                    "Saved screenshot analysis."
                )
            }
        ]
    )

    application.state.settings = settings

    # ----------------------------------------------
    # ROOT ENDPOINT
    # ----------------------------------------------

    @application.get(
        "/",
        include_in_schema=False
    )
    def root():

        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "mode": settings.mode,
            "message": (
                "Offline screenshot analysis API"
            ),
            "endpoints": {
                "health": "/health",
                "information": (
                    f"{settings.api_prefix}/info"
                ),
                "profiles": (
                    f"{settings.api_prefix}/profiles"
                ),
                "statistics": (
                    f"{settings.api_prefix}/statistics"
                ),
                "analyze_screenshot": (
                    f"{settings.api_prefix}"
                    "/analyze/screenshot"
                ),
                "documentation": settings.docs_url,
                "redoc": settings.redoc_url,
                "openapi": settings.openapi_url
            }
        }

    # ----------------------------------------------
    # SERVICE EXCEPTION HANDLER
    # ----------------------------------------------

    @application.exception_handler(
        ProcessingServiceError
    )
    async def service_exception_handler(
        request: Request,
        exc: ProcessingServiceError
    ):

        return create_error_response(exc)

    # ----------------------------------------------
    # REQUEST VALIDATION ERROR HANDLER
    # ----------------------------------------------

    @application.exception_handler(
        RequestValidationError
    )
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError
    ):

        validation_errors = []

        for error in exc.errors():

            validation_errors.append({
                "location": [
                    str(item)
                    for item in error.get(
                        "loc", []
                    )
                ],
                "type": error.get(
                    "type",
                    "validation_error"
                ),
                "message": error.get(
                    "msg",
                    "Invalid request."
                )
            })

        return build_error_response(
            status_code=422,
            code="REQUEST_VALIDATION_ERROR",
            message="Request validation failed.",
            details={
                "validation_errors":
                    validation_errors
            }
        )

    # ----------------------------------------------
    # HTTP EXCEPTION HANDLER
    # ----------------------------------------------

    @application.exception_handler(
        StarletteHTTPException
    )
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException
    ):

        error_codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "FILE_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            422: "UNPROCESSABLE_ENTITY",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            503: "SERVICE_UNAVAILABLE"
        }

        messages = {
            400: "Invalid request.",
            401: "Authentication required.",
            403: "Access forbidden.",
            404: "Requested resource not found.",
            405: "HTTP method not allowed.",
            413: "Request is too large.",
            415: "Unsupported media type.",
            422: "Request could not be processed.",
            429: "Too many requests.",
            500: "Internal server error.",
            503: "Service unavailable."
        }

        return build_error_response(
            status_code=exc.status_code,
            code=error_codes.get(
                exc.status_code,
                "HTTP_ERROR"
            ),
            message=messages.get(
                exc.status_code,
                "HTTP request failed."
            ),
            headers=exc.headers
        )

    # ----------------------------------------------
    # UNEXPECTED EXCEPTION HANDLER
    # ----------------------------------------------

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(
        request: Request,
        exc: Exception
    ):

        logger.error(
            "Unhandled application exception.",
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__
            )
        )

        return build_error_response(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message=(
                "An unexpected application "
                "error occurred."
            )
        )

    # ----------------------------------------------
    # REGISTER ROUTERS
    # ----------------------------------------------

    application.include_router(
        health_router
    )

    application.include_router(
        api_router,
        prefix=settings.api_prefix
    )

    return application


# --------------------------------------------------
# DEFAULT ASGI APPLICATION
# --------------------------------------------------

app = create_app()


# --------------------------------------------------
# LOCAL SERVER LAUNCHER
# --------------------------------------------------

def run():

    import uvicorn

    settings = get_settings()

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
        workers=1
    )


if __name__ == "__main__":

    run()
