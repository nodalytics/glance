
import sys
from pathlib import Path

import cv2
import numpy as np

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


TEMPLATE_DIR = (
    PROJECT_ROOT
    / "test_assets/card_templates/simulator_suits"
)

TEMPLATE_SIZE = 64
SYMBOL_SIZE = 52


SUIT_SYMBOLS = {
    "hearts": "\u2665",
    "diamonds": "\u2666",
    "clubs": "\u2663",
    "spades": "\u2660"
}


FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "DejaVuSans.ttf"
]


# --------------------------------------------------
# NORMALIZE SYMBOL
# --------------------------------------------------

def normalize_symbol(image):

    _, binary = cv2.threshold(
        image,
        127,
        255,
        cv2.THRESH_BINARY_INV
    )

    points = cv2.findNonZero(binary)

    if points is None:
        return None

    x, y, width, height = cv2.boundingRect(
        points
    )

    symbol = binary[
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
# GENERATE TEMPLATE
# --------------------------------------------------

def generate_template(symbol, font):

    image = Image.new(
        "L",
        (256, 256),
        255
    )

    draw = ImageDraw.Draw(image)

    bbox = draw.textbbox(
        (0, 0),
        symbol,
        font=font
    )

    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]

    x = (256 - width) / 2 - bbox[0]
    y = (256 - height) / 2 - bbox[1]

    draw.text(
        (x, y),
        symbol,
        font=font,
        fill=0
    )

    return normalize_symbol(
        np.array(image)
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 65)
    print("SIMULATOR SUIT TEMPLATE GENERATOR")
    print("=" * 65)

    TEMPLATE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    generated = 0

    for font_path in FONT_CANDIDATES:

        try:

            font = ImageFont.truetype(
                font_path,
                120
            )

        except OSError:

            print(
                f"Font unavailable: {font_path}"
            )

            continue

        font_name = Path(font_path).stem

        print(f"\nFont: {font_name}")

        templates = {}

        for suit, symbol in SUIT_SYMBOLS.items():

            template = generate_template(
                symbol,
                font
            )

            if template is not None:
                templates[suit] = template

        if len(templates) != 4:

            print("Skipped incomplete font")

            continue

        signatures = {
            template.tobytes()
            for template in templates.values()
        }

        if len(signatures) != 4:

            print("Skipped duplicate glyphs")

            continue

        for suit, template in templates.items():

            output_path = (
                TEMPLATE_DIR
                / f"{suit}_{font_name}.png"
            )

            success = cv2.imwrite(
                str(output_path),
                template
            )

            if not success:
                raise IOError(
                    f"Cannot save: {output_path}"
                )

            generated += 1

            print(
                f"Created: {output_path.name}"
            )

    print("\n" + "=" * 65)
    print("TEMPLATE GENERATION COMPLETED")
    print("=" * 65)

    print(f"Templates generated: {generated}")
    print(f"Output directory: {TEMPLATE_DIR}")

    if generated < 4:

        raise RuntimeError(
            "Insufficient suit templates."
        )


if __name__ == "__main__":
    main()
