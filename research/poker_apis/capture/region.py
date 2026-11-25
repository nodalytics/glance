
from dataclasses import dataclass

import numpy as np


@dataclass
class TableRegion:
    """
    Normalized region coordinates.

    All coordinates range from 0.0 to 1.0.
    """

    x: float
    y: float
    width: float
    height: float

    def crop(self, image: np.ndarray) -> np.ndarray:
        image_height, image_width = image.shape[:2]

        if not (
            0 <= self.x < 1
            and 0 <= self.y < 1
            and 0 < self.width <= 1
            and 0 < self.height <= 1
            and self.x + self.width <= 1
            and self.y + self.height <= 1
        ):
            raise ValueError("Invalid normalized table region")

        x1 = round(self.x * image_width)
        y1 = round(self.y * image_height)

        x2 = round((self.x + self.width) * image_width)
        y2 = round((self.y + self.height) * image_height)

        return image[y1:y2, x1:x2].copy()
