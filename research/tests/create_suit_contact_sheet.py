
from pathlib import Path

import cv2
import numpy as np


INPUT_DIR = Path("test_output/card_debug")
OUTPUT_FILE = Path("test_output/card_debug/suit_contact_sheet.jpg")

TILE_WIDTH = 520
TILE_HEIGHT = 430


def resize_contain(image, max_width, max_height):
    height, width = image.shape[:2]

    scale = min(
        max_width / width,
        max_height / height
    )

    new_width = int(width * scale)
    new_height = int(height * scale)

    return cv2.resize(
        image,
        (new_width, new_height),
        interpolation=cv2.INTER_CUBIC
    )


def create_tile(image_path):

    image = cv2.imread(str(image_path))

    if image is None:
        return None

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    _, binary = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    tile = np.full(
        (TILE_HEIGHT, TILE_WIDTH, 3),
        255,
        dtype=np.uint8
    )

    cv2.putText(
        tile,
        image_path.stem,
        (12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2
    )

    original = resize_contain(
        image,
        240,
        350
    )

    processed = resize_contain(
        binary,
        240,
        350
    )

    original_y = 55 + (350 - original.shape[0]) // 2
    processed_y = 55 + (350 - processed.shape[0]) // 2

    tile[
        original_y:original_y + original.shape[0],
        10:10 + original.shape[1]
    ] = original

    processed_bgr = cv2.cvtColor(
        processed,
        cv2.COLOR_GRAY2BGR
    )

    tile[
        processed_y:processed_y + processed.shape[0],
        270:270 + processed.shape[1]
    ] = processed_bgr

    cv2.putText(
        tile,
        "Original",
        (75, 415),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 0),
        1
    )

    cv2.putText(
        tile,
        "Threshold",
        (335, 415),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 0),
        1
    )

    return tile


def main():

    files = sorted(
        INPUT_DIR.glob("*_suit.png")
    )

    if len(files) != 7:
        raise ValueError(
            f"Expected 7 suit images, found {len(files)}"
        )

    tiles = []

    for image_path in files:

        tile = create_tile(image_path)

        if tile is not None:
            tiles.append(tile)

    if len(tiles) != 7:
        raise RuntimeError(
            "Could not process all seven suit images."
        )

    columns = 2
    rows = (len(tiles) + columns - 1) // columns

    sheet = np.full(
        (
            rows * TILE_HEIGHT,
            columns * TILE_WIDTH,
            3
        ),
        230,
        dtype=np.uint8
    )

    for index, tile in enumerate(tiles):

        row = index // columns
        column = index % columns

        y = row * TILE_HEIGHT
        x = column * TILE_WIDTH

        sheet[
            y:y + TILE_HEIGHT,
            x:x + TILE_WIDTH
        ] = tile

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    cv2.imwrite(
        str(OUTPUT_FILE),
        sheet
    )

    print("Suit contact sheet created!")
    print(f"Images processed: {len(tiles)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
