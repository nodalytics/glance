
import time
from pathlib import Path

import cv2

from poker_apis.vision.card_detector import CardDetector

from poker_apis.pipeline.offline_pipeline import (
    OfflineProcessingPipeline
)


class ScreenshotPipeline:
    """
    Processes saved offline calibration screenshots.

    Accepts previously extracted table information.
    Does not capture live screens or interact with
    poker clients.
    """

    SUPPORTED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp"
    }

    def __init__(self, project_root=None):

        if project_root is None:

            project_root = (
                Path(__file__).resolve().parents[2]
            )

        self.project_root = Path(project_root)

        self.card_detector = CardDetector(
            padding=3
        )

        self.offline_pipeline = (
            OfflineProcessingPipeline(
                project_root=self.project_root
            )
        )

    # --------------------------------------------------
    # LOAD SAVED SCREENSHOT
    # --------------------------------------------------

    def load_screenshot(self, screenshot_path):

        screenshot_path = Path(screenshot_path)

        if not screenshot_path.is_file():

            raise FileNotFoundError(
                f"Screenshot not found: "
                f"{screenshot_path}"
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

        if width < 800 or height < 450:

            raise ValueError(
                "Screenshot resolution is too small."
            )

        reference_ratio = 1600 / 900

        actual_ratio = width / height

        relative_difference = abs(
            actual_ratio - reference_ratio
        ) / reference_ratio

        if relative_difference > 0.02:

            raise ValueError(
                "Screenshot aspect ratio does not "
                "match the calibration layout."
            )

        return image

    # --------------------------------------------------
    # PROCESS SAVED SCREENSHOT
    # --------------------------------------------------

    def process_file(
        self,
        screenshot_path,
        table_data,
        debug_output_dir=None
    ):

        total_start = time.perf_counter()

        # Load screenshot.

        loading_start = time.perf_counter()

        image = self.load_screenshot(
            screenshot_path
        )

        loading_time = (
            time.perf_counter() - loading_start
        )

        height, width = image.shape[:2]

        # Extract card regions.

        cropping_start = time.perf_counter()

        card_images = (
            self.card_detector.crop_cards(image)
        )

        cropping_time = (
            time.perf_counter() - cropping_start
        )

        # Optionally preserve debugging images.

        if debug_output_dir is not None:

            self.card_detector.save_cards(
                card_images,
                debug_output_dir
            )

        # Process using the verified calibration profile.

        state = self.offline_pipeline.process(
            table_data=table_data,
            card_images=card_images,
            dataset_type="calibration"
        )

        # Add screenshot metadata.

        total_time = (
            time.perf_counter() - total_start
        )

        state["metadata"]["screenshot"] = {
            "filename": Path(screenshot_path).name,
            "width": width,
            "height": height,
            "aspect_ratio": round(
                width / height,
                6
            ),
            "layout": "calibration_1600x900"
        }

        state["metadata"]["table_data_origin"] = (
            "previously_extracted"
        )

        state["metadata"]["timings"].update({
            "screenshot_loading_seconds": round(
                loading_time,
                6
            ),
            "card_cropping_seconds": round(
                cropping_time,
                6
            ),
            "screenshot_total_seconds": round(
                total_time,
                6
            )
        })

        state["metadata"][
            "processing_time_seconds"
        ] = round(total_time, 6)

        return state
