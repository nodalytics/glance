
import json
import logging

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


performance_router = APIRouter(
    prefix="/performance",
    tags=["Performance Research"],
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


REPORT_PATH = (
    PROJECT_ROOT
    / "test_output"
    / "performance"
    / "performance_feasibility_report.json"
)


def error_response(
    status_code,
    code,
    message,
):

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": None,
            },
        },
    )


@performance_router.get("/report")
def get_performance_report():

    if not REPORT_PATH.is_file():

        return error_response(
            404,
            "PERFORMANCE_REPORT_NOT_FOUND",
            "Generate the performance feasibility report first.",
        )

    try:

        report = json.loads(
            REPORT_PATH.read_text(
                encoding="utf-8-sig"
            )
        )

        if not isinstance(report, dict):

            raise ValueError(
                "Invalid report structure."
            )

        if report.get("success") is not True:

            return error_response(
                503,
                "PERFORMANCE_REPORT_INCOMPLETE",
                "The performance research report is incomplete.",
            )

        return {
            "success": True,

            "mode": "offline",

            "measurement_type": (
                "recorded_research_benchmarks"
            ),

            "report_version": report.get(
                "report_version"
            ),

            "timestamp_utc": report.get(
                "timestamp_utc"
            ),

            "scope": report.get(
                "scope"
            ),

            "summary": report.get(
                "summary", {}
            ),

            "preprocessing": report.get(
                "preprocessing", {}
            ),

            "neural_runtimes": report.get(
                "neural_runtimes", []
            ),

            "accuracy_analysis": report.get(
                "accuracy_analysis", []
            ),

            "conclusions": report.get(
                "conclusions", []
            ),

            "limitations": report.get(
                "limitations", []
            ),

            "production_decision": report.get(
                "production_decision"
            ),

            "application_speedup_verified": False,
        }

    except (
        OSError,
        ValueError,
        TypeError,
    ):

        logger.exception(
            "Failed to load performance report."
        )

        return error_response(
            500,
            "PERFORMANCE_REPORT_READ_FAILED",
            "Unable to read the performance research report.",
        )



from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from document_research.service import (
    document_service,
    DocumentServiceBusyError,
)


class DocumentAnalysisRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    variant: Literal[
        "standard",
        "small_text",
        "low_contrast",
        "noisy",
        "dark",
        "dense",
    ] = "standard"

    seed: int = Field(
        default=20261127,
        ge=0,
        le=2147483647,
        strict=True,
    )

    preprocessing: Literal[
        "original",
        "gaussian",
    ] = "gaussian"


@performance_router.get("/document/status")
def get_document_status():

    return document_service.get_status()


@performance_router.post("/document/analyze")
def analyze_document(
    request: DocumentAnalysisRequest,
):

    try:

        return document_service.analyze(
            variant=request.variant,
            seed=request.seed,
            preprocessing=request.preprocessing,
        )

    except DocumentServiceBusyError:

        return error_response(
            503,
            "DOCUMENT_ENGINE_BUSY",
            "Document research engine is busy.",
        )

    except Exception:

        logger.exception(
            "Document research inference failed."
        )

        return error_response(
            500,
            "DOCUMENT_INFERENCE_FAILED",
            "Unable to execute document recognition.",
        )

