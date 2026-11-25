
import cv2
import numpy as np


class ImagePreprocessor:
    """Prepares poker-table images for OCR and recognition."""

    @staticmethod
    def resize(
        image: np.ndarray,
        max_width: int = 1600
    ) -> np.ndarray:
        height, width = image.shape[:2]

        if width <= max_width:
            return image.copy()

        scale = max_width / width
        new_size = (
            max_width,
            int(height * scale)
        )

        return cv2.resize(
            image,
            new_size,
            interpolation=cv2.INTER_AREA
        )

    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            5,
            5,
            7,
            21
        )

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )

        enhanced_l = clahe.apply(l_channel)

        enhanced = cv2.merge(
            (enhanced_l, a_channel, b_channel)
        )

        return cv2.cvtColor(
            enhanced,
            cv2.COLOR_LAB2BGR
        )

    @staticmethod
    def grayscale(image: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

    @classmethod
    def process(cls, image: np.ndarray) -> dict:
        """
        Generate multiple image representations.

        Keep the original image for card recognition.
        Use grayscale for text recognition experiments.
        """

        resized = cls.resize(image)
        denoised = cls.denoise(resized)
        enhanced = cls.enhance_contrast(denoised)
        gray = cls.grayscale(enhanced)

        return {
            "original": resized,
            "denoised": denoised,
            "enhanced": enhanced,
            "grayscale": gray
        }
