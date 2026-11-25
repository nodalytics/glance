
import sys
from pathlib import Path
import cv2

# Allow imports from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poker_apis.vision.card_detector import CardDetector


IMAGE_PATH = "test_images/ss.jpeg"
OUTPUT_DIR = "test_output/card_crops"


def main():
    image = cv2.imread(IMAGE_PATH)

    if image is None:
        raise FileNotFoundError(
            f"Could not load {IMAGE_PATH}. "
            "Check that the screenshot exists at this path."
        )

    height, width = image.shape[:2]

    print(f"Loaded screenshot: {width} x {height}")

    detector = CardDetector(padding=3)

    crops = detector.crop_cards(image)
    detector.save_cards(crops, OUTPUT_DIR)

    print(f"\nSuccessfully cropped {len(crops)} card regions.")

    for name, crop in crops.items():
        print(f"{name}: {crop.shape[1]} x {crop.shape[0]}")


if __name__ == "__main__":
    main()
