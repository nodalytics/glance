
import os

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ApplicationSettings(BaseModel):

    """
    Central configuration for the offline
    poker screenshot analysis service.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    # ----------------------------------------------
    # APPLICATION SETTINGS
    # ----------------------------------------------

    app_name: str = "poker-apis"

    app_version: str = "1.0.0"

    schema_version: str = "1.0.0"

    description: str = (
        "Offline poker screenshot analysis API"
    )

    mode: Literal["offline"] = "offline"

    debug: bool = False

    # ----------------------------------------------
    # SERVER SETTINGS
    # ----------------------------------------------

    host: Literal[
        "127.0.0.1",
        "localhost",
        "::1"
    ] = "127.0.0.1"

    port: int = Field(
        default=8000,
        ge=1,
        le=65535
    )

    api_prefix: str = "/api/v1"

    docs_enabled: bool = True

    # ----------------------------------------------
    # UPLOAD SETTINGS
    # ----------------------------------------------

    max_upload_size_bytes: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        le=50 * 1024 * 1024
    )

    supported_image_formats: tuple[str, ...] = (
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp"
    )

    max_concurrent_processing: Literal[1] = 1

    cleanup_temp_files: Literal[True] = True

    # ----------------------------------------------
    # LOGGING SETTINGS
    # ----------------------------------------------

    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL"
    ] = "INFO"

    # ----------------------------------------------
    # PROJECT PATHS
    # ----------------------------------------------

    project_root: Path = PROJECT_ROOT

    @property
    def test_assets_dir(self) -> Path:

        return self.project_root / "test_assets"

    @property
    def test_images_dir(self) -> Path:

        return self.project_root / "test_images"

    @property
    def output_dir(self) -> Path:

        return self.project_root / "test_output"

    @property
    def temp_upload_dir(self) -> Path:

        return (
            self.project_root
            / "runtime"
            / "uploads"
        )

    @property
    def calibration_templates_dir(self) -> Path:

        return (
            self.test_assets_dir
            / "card_templates"
            / "suits"
        )

    @property
    def simulator_templates_dir(self) -> Path:

        return (
            self.test_assets_dir
            / "card_templates"
            / "simulator_suits"
        )

    @property
    def docs_url(self) -> str | None:

        return "/docs" if self.docs_enabled else None

    @property
    def redoc_url(self) -> str | None:

        return "/redoc" if self.docs_enabled else None

    @property
    def openapi_url(self) -> str | None:

        return (
            "/openapi.json"
            if self.docs_enabled
            else None
        )

    # ----------------------------------------------
    # VALIDATORS
    # ----------------------------------------------

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value):

        if not value.startswith("/"):

            raise ValueError(
                "API prefix must start with '/'."
            )

        if value == "/" or value.endswith("/"):

            raise ValueError(
                "API prefix cannot end with '/'."
            )

        if any(
            not part
            or not part.replace("-", "").replace(
                "_", ""
            ).isalnum()
            for part in value[1:].split("/")
        ):

            raise ValueError(
                "API prefix contains invalid segments."
            )

        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value):

        if isinstance(value, str):

            return value.strip().upper()

        return value

    @field_validator(
        "supported_image_formats"
    )
    @classmethod
    def validate_image_formats(cls, values):

        allowed = {
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp"
        }

        normalized = tuple(
            dict.fromkeys(
                value.strip().lower()
                for value in values
            )
        )

        if not normalized:

            raise ValueError(
                "At least one image format is required."
            )

        if not set(normalized).issubset(allowed):

            raise ValueError(
                "Unsupported image format configured."
            )

        return normalized

    # ----------------------------------------------
    # DIRECTORY MANAGEMENT
    # ----------------------------------------------

    def prepare_runtime_directories(self):

        self.temp_upload_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # ----------------------------------------------
    # PUBLIC APPLICATION INFORMATION
    # ----------------------------------------------

    def public_info(self) -> dict:

        return {
            "name": self.app_name,
            "version": self.app_version,
            "description": self.description,
            "mode": self.mode,
            "schema_version": self.schema_version,
            "supported_image_formats": list(
                self.supported_image_formats
            ),
            "max_upload_size_bytes": (
                self.max_upload_size_bytes
            )
        }


# --------------------------------------------------
# ENVIRONMENT VARIABLE MAPPING
# --------------------------------------------------

ENVIRONMENT_FIELDS = {
    "POKER_APP_NAME": "app_name",
    "POKER_APP_VERSION": "app_version",
    "POKER_DEBUG": "debug",
    "POKER_HOST": "host",
    "POKER_PORT": "port",
    "POKER_API_PREFIX": "api_prefix",
    "POKER_DOCS_ENABLED": "docs_enabled",
    "POKER_MAX_UPLOAD_SIZE_BYTES": (
        "max_upload_size_bytes"
    ),
    "POKER_LOG_LEVEL": "log_level"
}


def load_settings(
    env_file: str | Path | None = None,
    include_os_environment: bool = True
) -> ApplicationSettings:

    if env_file is None:

        env_file = PROJECT_ROOT / ".env"

    env_file = Path(env_file)

    file_values = {}

    if env_file.is_file():

        file_values = dotenv_values(
            env_file,
            encoding="utf-8-sig"
        )

    settings_data = {}

    for env_name, field_name in (
        ENVIRONMENT_FIELDS.items()
    ):

        value = file_values.get(env_name)

        if (
            include_os_environment
            and env_name in os.environ
        ):

            value = os.environ[env_name]

        if value is not None:

            settings_data[field_name] = value

    return ApplicationSettings.model_validate(
        settings_data
    )


@lru_cache(maxsize=1)
def get_settings() -> ApplicationSettings:

    return load_settings()
