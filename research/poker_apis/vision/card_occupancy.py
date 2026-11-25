
import cv2
import numpy as np


class CardOccupancyDetector:
    """
    Lightweight occupancy detector for locally
    generated offline simulator card slots.

    Does not require PaddleOCR.

    Possible states:
        occupied
        empty
        unknown
    """

    def __init__(
        self,
        occupied_white_threshold=0.55,
        empty_green_threshold=0.85,
        empty_white_threshold=0.05,
        empty_edge_threshold=0.03
    ):

        self.occupied_white_threshold = (
            occupied_white_threshold
        )

        self.empty_green_threshold = (
            empty_green_threshold
        )

        self.empty_white_threshold = (
            empty_white_threshold
        )

        self.empty_edge_threshold = (
            empty_edge_threshold
        )

    # --------------------------------------------------
    # VALIDATE IMAGE
    # --------------------------------------------------

    def validate_image(self, image):

        if image is None or image.size == 0:

            raise ValueError(
                "Card slot image is empty."
            )

        if image.ndim != 3 or image.shape[2] != 3:

            raise ValueError(
                "Expected a BGR color image."
            )

        height, width = image.shape[:2]

        if height < 10 or width < 10:

            raise ValueError(
                "Card slot image is too small."
            )

    # --------------------------------------------------
    # EXTRACT INNER REGION
    # --------------------------------------------------

    def extract_inner_region(self, image):

        height, width = image.shape[:2]

        x_margin = int(width * 0.05)
        y_margin = int(height * 0.05)

        return image[
            y_margin:height - y_margin,
            x_margin:width - x_margin
        ]

    # --------------------------------------------------
    # CALCULATE IMAGE FEATURES
    # --------------------------------------------------

    def calculate_features(self, image):

        region = self.extract_inner_region(
            image
        )

        hsv = cv2.cvtColor(
            region,
            cv2.COLOR_BGR2HSV
        )

        gray = cv2.cvtColor(
            region,
            cv2.COLOR_BGR2GRAY
        )

        # Bright, low-saturation card background.

        white_mask = cv2.inRange(
            hsv,
            np.array([0, 0, 180]),
            np.array([180, 65, 255])
        )

        # Green simulator table background.

        green_mask = cv2.inRange(
            hsv,
            np.array([35, 40, 20]),
            np.array([100, 255, 200])
        )

        # Detect visible image structure.

        edges = cv2.Canny(
            gray,
            50,
            150
        )

        total_pixels = gray.size

        white_ratio = (
            cv2.countNonZero(white_mask)
            / total_pixels
        )

        green_ratio = (
            cv2.countNonZero(green_mask)
            / total_pixels
        )

        edge_ratio = (
            cv2.countNonZero(edges)
            / total_pixels
        )

        return {
            "white_ratio": float(white_ratio),
            "green_ratio": float(green_ratio),
            "edge_ratio": float(edge_ratio),
            "mean_brightness": float(
                np.mean(gray)
            ),
            "brightness_std": float(
                np.std(gray)
            )
        }

    # --------------------------------------------------
    # DETECT OCCUPANCY
    # --------------------------------------------------

    def detect(self, image):

        self.validate_image(image)

        features = self.calculate_features(
            image
        )

        white_ratio = features["white_ratio"]
        green_ratio = features["green_ratio"]
        edge_ratio = features["edge_ratio"]

        if (
            white_ratio
            >= self.occupied_white_threshold
        ):

            state = "occupied"

            reason = (
                "Bright card background detected"
            )

        elif (
            green_ratio
            >= self.empty_green_threshold

            and white_ratio
            <= self.empty_white_threshold

            and edge_ratio
            <= self.empty_edge_threshold
        ):

            state = "empty"

            reason = (
                "Uniform green table background"
            )

        else:

            state = "unknown"

            reason = (
                "Insufficient occupancy evidence"
            )

        occupied = {
            "occupied": True,
            "empty": False,
            "unknown": None
        }[state]

        return {
            "state": state,
            "occupied": occupied,
            "skip_ocr": state == "empty",
            "reason": reason,
            "features": features
        }
