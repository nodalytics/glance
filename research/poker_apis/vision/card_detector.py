
from pathlib import Path
import cv2


# Reference screenshot dimensions: 1600 x 900.
# Coordinates are approximate bounding boxes around each visible card.
# They scale proportionally if the screenshot is resized.
REFERENCE_WIDTH = 1600
REFERENCE_HEIGHT = 900

CARD_REGIONS = {
    "board_1": (545, 380, 646, 523),
    "board_2": (648, 380, 750, 523),
    "board_3": (752, 380, 853, 523),
    "board_4": (855, 380, 956, 523),
    "board_5": (958, 380, 1058, 523),

    "hero_card_1": (752, 632, 840, 741),
    "hero_card_2": (812, 632, 915, 741),
}


class CardDetector:
    def __init__(self, padding=3):
        self.padding = padding

    def crop_cards(self, image):
        if image is None:
            raise ValueError("Input image is empty.")

        height, width = image.shape[:2]

        scale_x = width / REFERENCE_WIDTH
        scale_y = height / REFERENCE_HEIGHT

        crops = {}

        for card_name, (x1, y1, x2, y2) in CARD_REGIONS.items():
            # Scale reference coordinates to the actual image size.
            x1 = round(x1 * scale_x)
            x2 = round(x2 * scale_x)
            y1 = round(y1 * scale_y)
            y2 = round(y2 * scale_y)

            # Add a small margin around each card.
            pad_x = round(self.padding * scale_x)
            pad_y = round(self.padding * scale_y)

            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(width, x2 + pad_x)
            y2 = min(height, y2 + pad_y)

            crop = image[y1:y2, x1:x2]

            if crop.size == 0:
                raise ValueError(f"Empty crop for {card_name}")

            crops[card_name] = crop

        return crops

    def save_cards(self, crops, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for card_name, crop in crops.items():
            output_path = output_dir / f"{card_name}.png"

            success = cv2.imwrite(str(output_path), crop)

            if not success:
                raise IOError(f"Could not save {output_path}")

            print(f"Saved: {output_path}")
