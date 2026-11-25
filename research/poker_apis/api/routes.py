
import logging

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Request,
    UploadFile
)

from fastapi.responses import JSONResponse

from starlette.concurrency import run_in_threadpool

from poker_apis.core.config import (
    ApplicationSettings
)

from poker_apis.models.poker_state import (
    PokerStateModel,
    HealthResponseModel,
    ApplicationInfoModel,
    ProfilesResponseModel,
    AvailableProfileModel,
    StatisticsResponseModel,
    ErrorResponseModel
)

from poker_apis.services.processing_service import (
    OfflineProcessingService,
    ProcessingServiceError
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# ROUTERS
# --------------------------------------------------

health_router = APIRouter(
    tags=["Health"]
)

api_router = APIRouter()


# --------------------------------------------------
# DEPENDENCIES
# --------------------------------------------------

def get_application_settings(
    request: Request
) -> ApplicationSettings:

    return request.app.state.settings


def get_processing_service(
    request: Request
) -> OfflineProcessingService:

    return request.app.state.processing_service


SettingsDependency = Annotated[
    ApplicationSettings,
    Depends(get_application_settings)
]

ServiceDependency = Annotated[
    OfflineProcessingService,
    Depends(get_processing_service)
]


# --------------------------------------------------
# ERROR RESPONSE HELPER
# --------------------------------------------------

def create_error_response(
    error: ProcessingServiceError
) -> JSONResponse:

    response = ErrorResponseModel.model_validate(
        error.to_dict()
    )

    headers = {}

    if error.code == "SERVICE_BUSY":

        headers["Retry-After"] = "10"

    return JSONResponse(
        status_code=error.status_code,
        content=response.model_dump(
            mode="json"
        ),
        headers=headers
    )


# --------------------------------------------------
# BOUNDED UPLOAD READING
# --------------------------------------------------

async def read_upload_content(
    upload: UploadFile,
    max_size: int
) -> bytes:

    chunk_size = 64 * 1024

    content = bytearray()

    while True:

        remaining = (
            max_size - len(content)
        )

        chunk = await upload.read(
            min(
                chunk_size,
                remaining + 1
            )
        )

        if not chunk:

            break

        if len(content) + len(chunk) > max_size:

            raise ProcessingServiceError(
                code="FILE_TOO_LARGE",
                message=(
                    "Upload exceeds the configured "
                    "size limit."
                ),
                status_code=413,
                details={
                    "max_upload_size_bytes": max_size
                }
            )

        content.extend(chunk)

    if not content:

        raise ProcessingServiceError(
            code="EMPTY_FILE",
            message="Uploaded file is empty.",
            status_code=400
        )

    return bytes(content)


# --------------------------------------------------
# HEALTH ENDPOINT
# --------------------------------------------------

@health_router.get(
    "/health",
    response_model=HealthResponseModel,
    summary="Check application health"
)
def health_check(
    settings: SettingsDependency,
    service: ServiceDependency
):

    return HealthResponseModel(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        mode=settings.mode,
        pipeline_initialized=(
            service.pipeline_initialized
        ),
        busy=service.is_busy
    )


# --------------------------------------------------
# APPLICATION INFORMATION
# --------------------------------------------------

@api_router.get(
    "/info",
    response_model=ApplicationInfoModel,
    tags=["Information"],
    summary="Get application information"
)
def application_info(
    settings: SettingsDependency
):

    return ApplicationInfoModel.model_validate(
        settings.public_info()
    )


# --------------------------------------------------
# RECOGNITION PROFILES
# --------------------------------------------------

@api_router.get(
    "/profiles",
    response_model=ProfilesResponseModel,
    tags=["Recognition"],
    summary="List offline recognition profiles"
)
def recognition_profiles(
    settings: SettingsDependency
):

    calibration_directory = (
        settings.calibration_templates_dir
    )

    simulator_directory = (
        settings.simulator_templates_dir
    )

    suits = (
        "hearts",
        "diamonds",
        "clubs",
        "spades"
    )

    calibration_available = all(
        (
            calibration_directory
            / f"{suit}.png"
        ).is_file()
        for suit in suits
    )

    simulator_available = all(
        any(
            simulator_directory.glob(
                f"{suit}_*.png"
            )
        )
        for suit in suits
    )

    profiles = [
        AvailableProfileModel(
            name="calibration",
            description=(
                "Recognition profile for the "
                "calibrated saved screenshot layout."
            ),
            recognizer="CardRecognizer",
            input_type="offline_screenshot",
            available=calibration_available,
            api_supported=True,
            occupancy_detection_enabled=False
        ),
        AvailableProfileModel(
            name="simulator",
            description=(
                "Recognition profile for "
                "synthetic simulator card images."
            ),
            recognizer="SimulatorCardRecognizer",
            input_type="offline_card_crops",
            available=simulator_available,
            api_supported=False,
            occupancy_detection_enabled=False
        ),
        AvailableProfileModel(
            name="simulator_optimized",
            description=(
                "Simulator recognition with "
                "empty-slot detection."
            ),
            recognizer=(
                "OptimizedSimulatorCardRecognizer"
            ),
            input_type="offline_card_crops",
            available=simulator_available,
            api_supported=False,
            occupancy_detection_enabled=True
        )
    ]

    return ProfilesResponseModel(
        mode="offline",
        default_profile="calibration",
        profiles=profiles
    )


# --------------------------------------------------
# SERVICE STATISTICS
# --------------------------------------------------

@api_router.get(
    "/statistics",
    response_model=StatisticsResponseModel,
    tags=["Information"],
    summary="Get processing service statistics"
)
def processing_statistics(
    service: ServiceDependency
):

    return StatisticsResponseModel(
        pipeline_initialized=(
            service.pipeline_initialized
        ),
        busy=service.is_busy,
        statistics=service.get_statistics()
    )


# --------------------------------------------------
# SCREENSHOT ANALYSIS
# --------------------------------------------------

@api_router.post(
    "/analyze/screenshot",
    response_model=PokerStateModel,
    tags=["Analysis"],
    summary="Analyze a saved offline screenshot",
    description=(
        "Accepts a previously saved screenshot "
        "matching the calibrated layout. "
        "Returns structured table, player, "
        "card and validation information."
    ),
    responses={
        400: {
            "model": ErrorResponseModel,
            "description": "Invalid upload"
        },
        413: {
            "model": ErrorResponseModel,
            "description": "Upload too large"
        },
        415: {
            "model": ErrorResponseModel,
            "description": "Unsupported image format"
        },
        422: {
            "model": ErrorResponseModel,
            "description": "Invalid image or dimensions"
        },
        500: {
            "model": ErrorResponseModel,
            "description": "Internal processing error"
        },
        503: {
            "model": ErrorResponseModel,
            "description": "Processing service busy"
        }
    }
)
async def analyze_screenshot(
    settings: SettingsDependency,
    service: ServiceDependency,
    file: Annotated[
        UploadFile,
        File(
            description=(
                "Previously saved PNG, JPEG "
                "or BMP screenshot."
            )
        )
    ]
):

    try:

        filename = file.filename or ""

        service.validate_filename(
            filename
        )

        content = await read_upload_content(
            upload=file,
            max_size=(
                settings.max_upload_size_bytes
            )
        )

        result = await run_in_threadpool(
            service.analyze_screenshot,
            filename,
            content
        )

        return result

    except ProcessingServiceError as exc:

        return create_error_response(exc)

    except Exception:

        logger.exception(
            "Unexpected screenshot endpoint failure."
        )

        return create_error_response(
            ProcessingServiceError(
                code="INTERNAL_SERVER_ERROR",
                message=(
                    "An unexpected processing "
                    "error occurred."
                ),
                status_code=500
            )
        )

    finally:

        await file.close()
