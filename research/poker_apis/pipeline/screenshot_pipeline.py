
import time
from pathlib import Path

import cv2

from poker_apis.vision.card_detector import CardDetector
from poker_apis.vision.ocr import PokerOCR
from poker_apis.vision.preprocessing import ImagePreprocessor
from poker_apis.vision.table_parser import parse_table
from poker_apis.vision.table_validation import validate_table_data

from poker_apis.pipeline.offline_pipeline import (
    OfflineProcessingPipeline
)


class ScreenshotPipeline:
    """
    Offline processing pipeline for saved calibration
    screenshots and historical image analysis.

    No live screen capture or poker-client interaction.
    """

    SUPPORTED_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".bmp"
    }

    REFERENCE_WIDTH = 1600
    REFERENCE_HEIGHT = 899

    def __init__(self, project_root=None):

        if project_root is None:
            project_root = (
                Path(__file__).resolve().parents[2]
            )

        self.project_root = Path(project_root)

        self.card_detector = CardDetector(padding=3)

        self.preprocessor = ImagePreprocessor()

        self.offline_pipeline = OfflineProcessingPipeline(
            project_root=self.project_root
        )

        self._table_ocr = None

    # --------------------------------------------------
    # OCR INITIALIZATION
    # --------------------------------------------------

    def get_table_ocr(self):

        if self._table_ocr is None:

            print("Initializing table OCR...")

            self._table_ocr = PokerOCR()

        return self._table_ocr

    # --------------------------------------------------
    # LOAD SCREENSHOT
    # --------------------------------------------------

    def load_screenshot(self, screenshot_path):

        screenshot_path = Path(screenshot_path)

        if not screenshot_path.is_file():

            raise FileNotFoundError(
                f"Screenshot not found: {screenshot_path}"
            )

        if (
            screenshot_path.suffix.lower()
            not in self.SUPPORTED_EXTENSIONS
        ):

            raise ValueError(
                "Unsupported screenshot format."
            )

        image = cv2.imread(
            str(screenshot_path),
            cv2.IMREAD_COLOR
        )

        if image is None or image.size == 0:

            raise ValueError(
                "Unable to decode screenshot."
            )

        height, width = image.shape[:2]

        # Restrict this initial integration to the
        # original calibration dimensions.

        if width != 1600 or height not in (899, 900):

            raise ValueError(
                f"Unsupported calibration dimensions: "
                f"{width}x{height}. "
                "Expected 1600x899 or 1600x900."
            )

        return image

    # --------------------------------------------------
    # SERIALIZE OCR RESULTS
    # --------------------------------------------------

    def serialize_ocr_results(self, results):

        return [
            {
                "text": str(item.text),
                "confidence": float(item.confidence),
                "x": float(item.x),
                "y": float(item.y),
                "width": float(item.width),
                "height": float(item.height)
            }
            for item in results
        ]

    # --------------------------------------------------
    # EXTRACT TABLE INFORMATION
    # --------------------------------------------------

    def extract_table_data(self, image):

        processed = self.preprocessor.process(image)

        ocr = self.get_table_ocr()

        results = ocr.extract(
            processed["enhanced"]
        )

        ocr_items = self.serialize_ocr_results(
            results
        )

        table_data = parse_table(ocr_items)

        table_validation = validate_table_data(
            table_data
        )

        return {
            "table_data": table_data,
            "table_validation": table_validation,
            "ocr_items": ocr_items
        }

    # --------------------------------------------------
    # COMPLETE OFFLINE SCREENSHOT PROCESSING
    # --------------------------------------------------

    def process_file(
        self,
        screenshot_path,
        table_data=None,
        debug_output_dir=None
    ):

        total_start = time.perf_counter()

        # Load original screenshot.

        start = time.perf_counter()

        image = self.load_screenshot(
            screenshot_path
        )

        loading_time = time.perf_counter() - start

        height, width = image.shape[:2]

        # Extract table information automatically,
        # unless explicitly supplied by the caller.

        start = time.perf_counter()

        if table_data is None:

            extraction = self.extract_table_data(
                image
            )

            table_data = extraction["table_data"]

            table_validation = extraction[
                "table_validation"
            ]

            ocr_items = extraction["ocr_items"]

            table_data_origin = "screenshot_ocr"

        else:

            if not isinstance(table_data, dict):

                raise TypeError(
                    "Table data must be a dictionary."
                )

            table_validation = validate_table_data(
                table_data
            )

            ocr_items = []

            table_data_origin = "previously_extracted"

        table_extraction_time = (
            time.perf_counter() - start
        )

        # Crop cards from the original image.

        start = time.perf_counter()

        card_images = self.card_detector.crop_cards(
            image
        )

        cropping_time = time.perf_counter() - start

        # Optionally save debug crops.

        if debug_output_dir is not None:

            self.card_detector.save_cards(
                card_images,
                debug_output_dir
            )

        # Recognize cards and build structured state.

        state = self.offline_pipeline.process(
            table_data=table_data,
            card_images=card_images,
            dataset_type="calibration"
        )

        # Preserve existing table parser diagnostics.

        state["validation"][
            "table_parser_validation"
        ] = table_validation

        parser_valid = (
            table_validation.get("valid") is True
        )

        if not parser_valid:

            state["validation"]["errors"].append({
                "code": "TABLE_PARSER_VALIDATION_FAILED",
                "message": (
                    "Original table parser validation failed."
                )
            })

            state["validation"]["valid"] = False

            state["status"] = "invalid"

        parser_warnings = table_validation.get(
            "warnings", []
        )

        for warning in parser_warnings:

            state["validation"]["warnings"].append({
                "code": "TABLE_PARSER_WARNING",
                "message": str(warning)
            })

        if (
            state["status"] == "valid"
            and state["validation"]["warnings"]
        ):

            state["status"] = "partial"

        state["validation"]["error_count"] = len(
            state["validation"]["errors"]
        )

        state["validation"]["warning_count"] = len(
            state["validation"]["warnings"]
        )

        # Add screenshot metadata.

        state["metadata"]["screenshot"] = {
            "filename": Path(screenshot_path).name,
            "width": width,
            "height": height,
            "layout": "calibration_1600x899"
        }

        state["metadata"]["table_data_origin"] = (
            table_data_origin
        )

        state["metadata"]["ocr_item_count"] = len(
            ocr_items
        )

        total_time = time.perf_counter() - total_start

        state["metadata"]["timings"].update({
            "screenshot_loading_seconds": round(
                loading_time, 6
            ),
            "table_extraction_seconds": round(
                table_extraction_time, 6
            ),
            "card_cropping_seconds": round(
                cropping_time, 6
            ),
            "screenshot_total_seconds": round(
                total_time, 6
            )
        })

        state["metadata"]["processing_time_seconds"] = (
            round(total_time, 6)
        )

        return state
