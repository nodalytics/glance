
import io
import logging
import tempfile
import threading
import time

from pathlib import Path
from typing import Callable, Any

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from poker_apis.core.config import (
    ApplicationSettings,
    get_settings
)

from poker_apis.models.poker_state import (
    PokerStateModel
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# STRUCTURED SERVICE EXCEPTION
# --------------------------------------------------

class ProcessingServiceError(Exception):

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None
    ):

        super().__init__(message)

        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_dict(self) -> dict:

        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }


# --------------------------------------------------
# OFFLINE PROCESSING SERVICE
# --------------------------------------------------

class OfflineProcessingService:

    SUPPORTED_DIMENSIONS = {
        (1600, 899),
        (1600, 900)
    }

    FORMAT_MAPPING = {
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".bmp": "BMP"
    }

    def __init__(
        self,
        settings: ApplicationSettings | None = None,
        pipeline_factory: Callable[[], Any] | None = None
    ):

        self.settings = settings or get_settings()

        self._pipeline_factory = (
            pipeline_factory
            or self._create_default_pipeline
        )

        self._pipeline = None

        self._processing_lock = threading.Lock()

        self._statistics_lock = threading.Lock()

        self._statistics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rejected_requests": 0,
            "busy_requests": 0
        }

        self.settings.prepare_runtime_directories()

    # ----------------------------------------------
    # PIPELINE INITIALIZATION
    # ----------------------------------------------

    def _create_default_pipeline(self):

        from poker_apis.pipeline.screenshot_pipeline import (
            ScreenshotPipeline
        )

        return ScreenshotPipeline(
            project_root=self.settings.project_root
        )

    def _get_pipeline(self):

        if self._pipeline is None:

            logger.info(
                "Initializing offline screenshot pipeline."
            )

            self._pipeline = (
                self._pipeline_factory()
            )

        return self._pipeline

    @property
    def pipeline_initialized(self) -> bool:

        return self._pipeline is not None

    @property
    def is_busy(self) -> bool:

        return self._processing_lock.locked()

    # ----------------------------------------------
    # STATISTICS
    # ----------------------------------------------

    def _increment_statistic(self, key):

        with self._statistics_lock:

            self._statistics[key] += 1

    def get_statistics(self) -> dict:

        with self._statistics_lock:

            return self._statistics.copy()

    # ----------------------------------------------
    # FILENAME VALIDATION
    # ----------------------------------------------

    def validate_filename(
        self,
        filename: str
    ) -> str:

        if (
            not isinstance(filename, str)
            or not filename.strip()
        ):

            raise ProcessingServiceError(
                code="INVALID_FILENAME",
                message="A filename is required.",
                status_code=400
            )

        filename = filename.strip()

        if (
            "/" in filename
            or "\\" in filename
            or ":" in filename
            or any(ord(char) < 32 for char in filename)
            or filename in {".", ".."}
            or len(filename) > 255
        ):

            raise ProcessingServiceError(
                code="INVALID_FILENAME",
                message="Invalid upload filename.",
                status_code=400
            )

        extension = Path(
            filename
        ).suffix.lower()

        if extension not in (
            self.settings.supported_image_formats
        ):

            raise ProcessingServiceError(
                code="UNSUPPORTED_FILE_FORMAT",
                message="Unsupported image extension.",
                status_code=415,
                details={
                    "supported_formats": list(
                        self.settings.supported_image_formats
                    )
                }
            )

        return extension

    # ----------------------------------------------
    # FILE SIZE VALIDATION
    # ----------------------------------------------

    def validate_file_size(
        self,
        content: bytes
    ):

        if not isinstance(content, bytes):

            raise ProcessingServiceError(
                code="INVALID_FILE_CONTENT",
                message="File content must be bytes.",
                status_code=400
            )

        if not content:

            raise ProcessingServiceError(
                code="EMPTY_FILE",
                message="Uploaded file is empty.",
                status_code=400
            )

        file_size = len(content)

        if file_size > (
            self.settings.max_upload_size_bytes
        ):

            raise ProcessingServiceError(
                code="FILE_TOO_LARGE",
                message="Upload exceeds the configured size limit.",
                status_code=413,
                details={
                    "file_size_bytes": file_size,
                    "max_upload_size_bytes": (
                        self.settings.max_upload_size_bytes
                    )
                }
            )

    # ----------------------------------------------
    # IMAGE CONTENT VALIDATION
    # ----------------------------------------------

    def validate_image_content(
        self,
        content: bytes,
        extension: str
    ) -> dict:

        expected_format = (
            self.FORMAT_MAPPING[extension]
        )

        try:

            with Image.open(
                io.BytesIO(content)
            ) as image:

                actual_format = image.format

                width, height = image.size

                if actual_format != expected_format:

                    raise ProcessingServiceError(
                        code="IMAGE_FORMAT_MISMATCH",
                        message=(
                            "Image content does not match "
                            "the file extension."
                        ),
                        status_code=415
                    )

                if (
                    width,
                    height
                ) not in self.SUPPORTED_DIMENSIONS:

                    raise ProcessingServiceError(
                        code="UNSUPPORTED_IMAGE_DIMENSIONS",
                        message=(
                            "Screenshot dimensions do not "
                            "match the calibrated layout."
                        ),
                        status_code=422,
                        details={
                            "width": width,
                            "height": height,
                            "supported_dimensions": [
                                [1600, 899],
                                [1600, 900]
                            ]
                        }
                    )

                if getattr(
                    image, "n_frames", 1
                ) != 1:

                    raise ProcessingServiceError(
                        code="UNSUPPORTED_IMAGE_CONTENT",
                        message="Animated images are not supported.",
                        status_code=415
                    )

                image.verify()

            # Reopen and decode after verification.
            with Image.open(
                io.BytesIO(content)
            ) as image:

                image.load()

            return {
                "format": actual_format,
                "width": width,
                "height": height,
                "file_size_bytes": len(content)
            }

        except ProcessingServiceError:

            raise

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError
        ) as exc:

            raise ProcessingServiceError(
                code="INVALID_IMAGE",
                message="Uploaded image could not be decoded.",
                status_code=422
            ) from exc

    # ----------------------------------------------
    # COMPLETE UPLOAD VALIDATION
    # ----------------------------------------------

    def validate_upload(
        self,
        filename: str,
        content: bytes
    ) -> dict:

        extension = self.validate_filename(
            filename
        )

        self.validate_file_size(content)

        image_info = self.validate_image_content(
            content,
            extension
        )

        return {
            "filename": filename.strip(),
            "extension": extension,
            **image_info
        }

    # ----------------------------------------------
    # TEMPORARY FILE MANAGEMENT
    # ----------------------------------------------

    def _create_temporary_file(
        self,
        content: bytes,
        extension: str
    ) -> Path:

        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=extension,
                prefix="offline_upload_",
                dir=self.settings.temp_upload_dir,
                delete=False
            ) as temp_file:

                temp_path = Path(
                    temp_file.name
                )

                temp_file.write(content)

            return temp_path

        except OSError as exc:

            if temp_path is not None:

                self._cleanup_temporary_file(
                    temp_path
                )

            raise ProcessingServiceError(
                code="TEMP_FILE_ERROR",
                message=(
                    "Could not prepare the uploaded "
                    "image for processing."
                ),
                status_code=500
            ) from exc

    def _cleanup_temporary_file(
        self,
        temp_path: Path | None
    ):

        if temp_path is None:

            return

        try:

            temp_path.unlink(
                missing_ok=True
            )

        except OSError:

            logger.exception(
                "Temporary upload cleanup failed."
            )

            raise ProcessingServiceError(
                code="TEMP_CLEANUP_FAILED",
                message="Temporary file cleanup failed.",
                status_code=500
            )

    # ----------------------------------------------
    # MAIN PROCESSING METHOD
    # ----------------------------------------------

    def analyze_screenshot(
        self,
        filename: str,
        content: bytes
    ) -> PokerStateModel:

        self._increment_statistic(
            "total_requests"
        )

        try:

            upload_info = self.validate_upload(
                filename,
                content
            )

        except ProcessingServiceError:

            self._increment_statistic(
                "rejected_requests"
            )

            raise

        acquired = (
            self._processing_lock.acquire(
                blocking=False
            )
        )

        if not acquired:

            self._increment_statistic(
                "busy_requests"
            )

            raise ProcessingServiceError(
                code="SERVICE_BUSY",
                message=(
                    "Another screenshot is currently "
                    "being processed."
                ),
                status_code=503
            )

        temp_path = None

        start = time.perf_counter()

        try:

            temp_path = (
                self._create_temporary_file(
                    content,
                    upload_info["extension"]
                )
            )

            pipeline = self._get_pipeline()

            state = pipeline.process_file(
                temp_path
            )

            # Preserve the original upload filename.
            metadata = state.setdefault(
                "metadata", {}
            )

            screenshot_metadata = (
                metadata.setdefault(
                    "screenshot", {}
                )
            )

            screenshot_metadata["filename"] = (
                upload_info["filename"]
            )

            metadata["upload"] = upload_info

            metadata["service_processing_seconds"] = (
                round(
                    time.perf_counter() - start,
                    6
                )
            )

            result = PokerStateModel.model_validate(
                state
            )

            # Ensure JSON serialization is supported.
            result.model_dump_json()

            # Cleanup before reporting success.
            self._cleanup_temporary_file(
                temp_path
            )

            temp_path = None

            self._increment_statistic(
                "successful_requests"
            )

            logger.info(
                "Offline screenshot processed. "
                "State status: %s",
                result.status
            )

            return result

        except ProcessingServiceError:

            self._increment_statistic(
                "failed_requests"
            )

            raise

        except ValidationError as exc:

            self._increment_statistic(
                "failed_requests"
            )

            logger.exception(
                "Pipeline response validation failed."
            )

            raise ProcessingServiceError(
                code="INVALID_PIPELINE_RESPONSE",
                message=(
                    "The processing pipeline returned "
                    "an invalid response."
                ),
                status_code=500
            ) from exc

        except Exception as exc:

            self._increment_statistic(
                "failed_requests"
            )

            logger.exception(
                "Offline screenshot processing failed."
            )

            raise ProcessingServiceError(
                code="PROCESSING_FAILED",
                message="Screenshot processing failed.",
                status_code=500
            ) from exc

        finally:

            try:

                if temp_path is not None:

                    self._cleanup_temporary_file(
                        temp_path
                    )

            finally:

                self._processing_lock.release()
