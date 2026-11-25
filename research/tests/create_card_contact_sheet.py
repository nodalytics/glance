
from pathlib import Path
import cv2
import numpy as np

CARD_DIR = Path("test_output/card_crops")
OUTPUT_PATH = Path("test_output/card_contact_sheet.jpg")

files = sorted(CARD_DIR.glob("*.png"))

if not files:
    raise FileNotFoundError(f"No card crops found in {CARD_DIR}")

cards = []

for path in files:
    image = cv2.imread(str(path))

    if image is None:
        print(f"Skipping unreadable image: {path}")
        continue

    # Resize each crop to a consistent preview size.
    preview = cv2.resize(image, (180, 240))
    preview = cv2.copyMakeBorder(
        preview, 30, 10, 10, 10,
        cv2.BORDER_CONSTANT,
        value=(35, 35, 35)
    )

    cv2.putText(
        preview,
        path.stem,
        (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1
    )

    cards.append(preview)

columns = 4
rows = (len(cards) + columns - 1) // columns
blank = np.zeros_like(cards[0])

while len(cards) < rows * columns:
    cards.append(blank.copy())

sheet_rows = []

for row in range(rows):
    start = row * columns
    sheet_rows.append(np.hstack(cards[start:start + columns]))

contact_sheet = np.vstack(sheet_rows)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(OUTPUT_PATH), contact_sheet)

print(f"Contact sheet saved: {OUTPUT_PATH}")
