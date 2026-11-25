
from pathlib import Path

import cv2
import numpy as np


INPUT_DIR = Path("test_output/card_crops")
OUTPUT_FILE = Path("test_output/hero_card_inspection.png")


def main():

    card_names = [
        "hero_card_1",
        "hero_card_2"
    ]

    tiles = []

    for card_name in card_names:

        path = INPUT_DIR / f"{card_name}.png"
        image = cv2.imread(str(path))

        if image is None:
            raise FileNotFoundError(
                f"Could not load {path}"
            )

        height, width = image.shape[:2]

        enlarged = cv2.resize(
            image,
            None,
            fx=4,
            fy=4,
            interpolation=cv2.INTER_CUBIC
        )

        tile = np.full(
            (540, 500, 3),
            255,
            dtype=np.uint8
        )

        cv2.putText(
            tile,
            card_name,
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2
        )

        h, w = enlarged.shape[:2]

        x = (500 - w) // 2
        y = 50

        tile[y:y+h, x:x+w] = enlarged

        tiles.append(tile)

        print(
            f"{card_name}: "
            f"width={width}, height={height}"
        )

    sheet = np.hstack(tiles)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not cv2.imwrite(str(OUTPUT_FILE), sheet):
        raise RuntimeError("Could not save image.")

    print("\nHero card inspection completed.")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
