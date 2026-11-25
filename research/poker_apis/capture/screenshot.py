
from pathlib import Path

import cv2
import numpy as np


class ScreenshotCapture:
    """Loads screenshots and captures authorized test displays."""

    @staticmethod
    def load_image(image_path: str) -> np.ndarray:
        """Load an image and return it in OpenCV BGR format."""

        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image = cv2.imread(str(path))

        if image is None:
            raise ValueError(f"Unable to read image: {image_path}")

        return image

    @staticmethod
    def capture_monitor(monitor_number: int = 1) -> np.ndarray:
        """
        Capture a monitor in an authorized test environment.
        Monitor 0 represents the virtual combined desktop.
        """

        try:
            import mss
        except ImportError as exc:
            raise RuntimeError(
                "Install mss using: pip install mss"
            ) from exc

        with mss.mss() as screen:
            monitors = screen.monitors

            if not 0 <= monitor_number < len(monitors):
                raise ValueError("Invalid monitor number")

            screenshot = screen.grab(monitors[monitor_number])

            # MSS returns RGB pixels; OpenCV uses BGR.
            image = np.array(screenshot)[:, :, :3]
            return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    @staticmethod
    def save_image(image: np.ndarray, output_path: str) -> None:
        """Save an image to disk."""

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not cv2.imwrite(str(path), image):
            raise IOError(f"Could not save image: {output_path}")
