
from pathlib import Path

import cv2
import numpy as np


# --------------------------------------------------
# PATHS
# --------------------------------------------------

CARD_DIR = Path("test_output/card_crops")
DEBUG_DIR = Path("test_output/card_debug")

TEMPLATE_DIR = Path(
    "test_assets/card_templates/suits"
)

PREVIEW_FILE = Path(
    "test_output/suit_template_preview.png"
)

TEMPLATE_SIZE = 64
SYMBOL_SIZE = 52


# --------------------------------------------------
# CALIBRATION REGIONS
# --------------------------------------------------
# Coordinates are normalized:
# x1, y1, x2, y2
#
# These are specific to our saved calibration sample.
# --------------------------------------------------

TEMPLATE_SOURCES = {
    "hearts": {
        "path": DEBUG_DIR / "board_1_suit.png",
        "region": (0.04, 0.08, 0.50, 0.58)
    },

    "spades": {
        "path": DEBUG_DIR / "board_2_suit.png",
        "region": (0.04, 0.10, 0.49, 0.64)
    },

    "diamonds": {
        "path": DEBUG_DIR / "board_4_suit.png",
        "region": (0.03, 0.09, 0.45, 0.66)
    },

    "clubs": {
        "path": CARD_DIR / "hero_card_1.png",
        "region": (0.08, 0.61, 0.35, 0.84)
    }
}


# --------------------------------------------------
# CROP REGION
# --------------------------------------------------

def crop_region(image, region):

    height, width = image.shape[:2]

    x1, y1, x2, y2 = region

    crop = image[
        int(height * y1):int(height * y2),
        int(width * x1):int(width * x2)
    ]

    if crop.size == 0:
        raise ValueError("Empty calibration crop.")

    return crop


# --------------------------------------------------
# NORMALIZE SYMBOL
# --------------------------------------------------

def normalize_symbol(image):

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.resize(
        gray,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC
    )

    gray = cv2.GaussianBlur(
        gray,
        (3, 3),
        0
    )

    _, binary = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        raise ValueError("No suit contour detected.")

    largest = max(
        contours,
        key=cv2.contourArea
    )

    x, y, width, height = cv2.boundingRect(
        largest
    )

    mask = np.zeros_like(binary)

    cv2.drawContours(
        mask,
        [largest],
        -1,
        255,
        thickness=cv2.FILLED
    )

    symbol = mask[
        y:y + height,
        x:x + width
    ]

    scale = SYMBOL_SIZE / max(width, height)

    new_width = max(
        1,
        round(width * scale)
    )

    new_height = max(
        1,
        round(height * scale)
    )

    symbol = cv2.resize(
        symbol,
        (new_width, new_height),
        interpolation=cv2.INTER_NEAREST
    )

    canvas = np.zeros(
        (TEMPLATE_SIZE, TEMPLATE_SIZE),
        dtype=np.uint8
    )

    offset_x = (
        TEMPLATE_SIZE - new_width
    ) // 2

    offset_y = (
        TEMPLATE_SIZE - new_height
    ) // 2

    canvas[
        offset_y:offset_y + new_height,
        offset_x:offset_x + new_width
    ] = symbol

    return 255 - canvas


# --------------------------------------------------
# CREATE PREVIEW
# --------------------------------------------------

def create_preview(templates):

    tiles = []

    for suit, template in templates.items():

        tile = np.full(
            (250, 220, 3),
            255,
            dtype=np.uint8
        )

        enlarged = cv2.resize(
            template,
            (192, 192),
            interpolation=cv2.INTER_NEAREST
        )

        enlarged = cv2.cvtColor(
            enlarged,
            cv2.COLOR_GRAY2BGR
        )

        tile[45:237, 14:206] = enlarged

        cv2.putText(
            tile,
            suit.upper(),
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2
        )

        tiles.append(tile)

    preview = np.hstack(tiles)

    if not cv2.imwrite(
        str(PREVIEW_FILE),
        preview
    ):
        raise RuntimeError(
            "Could not save template preview."
        )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    TEMPLATE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    PREVIEW_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    templates = {}

    print("=" * 50)
    print("SUIT TEMPLATE CALIBRATION")
    print("=" * 50)

    for suit, config in TEMPLATE_SOURCES.items():

        path = config["path"]

        image = cv2.imread(str(path))

        if image is None:
            raise FileNotFoundError(
                f"Could not load: {path}"
            )

        cropped = crop_region(
            image,
            config["region"]
        )

        template = normalize_symbol(
            cropped
        )

        output_path = TEMPLATE_DIR / f"{suit}.png"

        if not cv2.imwrite(
            str(output_path),
            template
        ):
            raise RuntimeError(
                f"Could not save {output_path}"
            )

        templates[suit] = template

        foreground = cv2.countNonZero(
            255 - template
        )

        print(f"\nSuit: {suit}")
        print(f"  Source: {path.name}")
        print(f"  Dimensions: {template.shape}")
        print(f"  Foreground pixels: {foreground}")
        print(f"  Saved: {output_path}")

    create_preview(templates)

    print("\n" + "=" * 50)
    print("CALIBRATION COMPLETED")
    print("=" * 50)

    print(f"Templates generated: {len(templates)}")
    print(f"Template directory: {TEMPLATE_DIR}")
    print(f"Preview saved: {PREVIEW_FILE}")


if __name__ == "__main__":
    main()
