
import sys
import json
from pathlib import Path

import cv2

# --------------------------------------------------
# PROJECT IMPORTS
# --------------------------------------------------

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from poker_apis.vision.card_recognition import CardRecognizer


# --------------------------------------------------
# PATHS
# --------------------------------------------------

CARD_DIR = Path("test_output/card_crops")
OUTPUT_DIR = Path("test_output/card_debug")
OUTPUT_JSON = Path("test_output/card_recognition.json")

# Cards that receive additional OCR diagnostics.
DEBUG_CARDS = {
    "board_1",
    "hero_card_1",
    "hero_card_2",
}


# --------------------------------------------------
# DIAGNOSTIC FUNCTION
# --------------------------------------------------

def print_diagnostics(recognizer, card_name, image):

    print(f"\n{'-' * 50}")
    print(f"DIAGNOSTICS: {card_name}")
    print("-" * 50)

    print(f"Original dimensions: {image.shape}")

    corner = recognizer.extract_corner(image)
    rank_region = recognizer.extract_rank_region(corner)
    suit_region = recognizer.extract_suit_region(corner)

    print(f"Corner dimensions: {corner.shape}")
    print(f"Rank dimensions: {rank_region.shape}")
    print(f"Suit dimensions: {suit_region.shape}")

    print("\nRaw OCR results:")

    ocr_results = recognizer.ocr.extract(rank_region)

    if not ocr_results:
        print("No text detected.")
    else:
        for item in ocr_results:
            print(
                f"Text: {item.text} | "
                f"Confidence: {item.confidence:.3f}"
            )


# --------------------------------------------------
# MULTI-REGION OCR SCAN
# --------------------------------------------------

def inspect_card_regions(recognizer, image, card_name):

    print(f"\nMULTI-REGION SCAN: {card_name}")
    print("=" * 50)

    height, width = image.shape[:2]

    regions = {
        "top_left": image[
            0:int(height * 0.65),
            0:int(width * 0.65)
        ],

        "top_right": image[
            0:int(height * 0.65),
            int(width * 0.35):width
        ],

        "bottom_left": image[
            int(height * 0.35):height,
            0:int(width * 0.65)
        ],

        "bottom_right": image[
            int(height * 0.35):height,
            int(width * 0.35):width
        ],

        "full_card": image
    }

    for region_name, region in regions.items():

        enlarged = cv2.resize(
            region,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC
        )

        results = recognizer.ocr.extract(enlarged)

        print(f"\nRegion: {region_name}")

        if not results:
            print("No text detected.")
            continue

        for item in results:
            print(
                f"Text: {item.text} | "
                f"Confidence: {item.confidence:.3f}"
            )


# --------------------------------------------------
# MAIN PROCESS
# --------------------------------------------------

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    card_crops = {}

    print("=" * 50)
    print("POKER CARD RECOGNITION TEST")
    print("=" * 50)

    # ----------------------------------------------
    # LOAD CARD CROPS
    # ----------------------------------------------

    print("\nLoading card crops...")

    for path in sorted(CARD_DIR.glob("*.png")):

        image = cv2.imread(str(path))

        if image is None:
            print(f"Could not load: {path}")
            continue

        card_crops[path.stem] = image

        print(
            f"Loaded: {path.name} | "
            f"Dimensions: {image.shape}"
        )

    if not card_crops:
        raise FileNotFoundError(
            f"No card images found in {CARD_DIR}"
        )

    print(
        f"\nTotal cards loaded: {len(card_crops)}"
    )

    # ----------------------------------------------
    # INITIALIZE RECOGNIZER
    # ----------------------------------------------

    print("\nInitializing card recognizer...")

    recognizer = CardRecognizer()

    # ----------------------------------------------
    # SAVE DEBUG IMAGES FOR ALL CARDS
    # ----------------------------------------------

    print("\nSaving debug images for ALL cards...")

    for card_name, image in sorted(card_crops.items()):

        recognizer.save_debug_regions(
            image,
            card_name,
            OUTPUT_DIR
        )

        print(
            f"Saved debug images: {card_name}"
        )

    # ----------------------------------------------
    # ADDITIONAL OCR DIAGNOSTICS
    # ----------------------------------------------

    print("\nRunning additional diagnostics...")

    for card_name in sorted(DEBUG_CARDS):

        if card_name not in card_crops:
            continue

        print_diagnostics(
            recognizer,
            card_name,
            card_crops[card_name]
        )

    # ----------------------------------------------
    # MULTI-REGION SCAN FOR HERO CARD 1
    # ----------------------------------------------

    if "hero_card_1" in card_crops:

        inspect_card_regions(
            recognizer,
            card_crops["hero_card_1"],
            "hero_card_1"
        )

    # ----------------------------------------------
    # RECOGNIZE ALL CARDS
    # ----------------------------------------------

    print("\nRecognizing all cards...")

    results = recognizer.recognize_cards(
        card_crops
    )

    # ----------------------------------------------
    # PRINT RESULTS
    # ----------------------------------------------

    print("\nCARD RECOGNITION RESULTS")
    print("=" * 50)

    for card_name, result in results.items():

        print(f"\n{card_name}")

        print(f"  Rank: {result['rank']}")

        print(
            f"  Rank confidence: "
            f"{result['rank_confidence']:.3f}"
        )

        print(f"  Suit: {result['suit']}")

        print(f"  Suit color: {result['suit_color']}")

        print(
            f"  Suit confidence: "
            f"{result['suit_confidence']:.3f}"
        )

        print(
            f"  Recognized: "
            f"{result['recognized']}"
        )

    # ----------------------------------------------
    # SAVE JSON RESULTS
    # ----------------------------------------------

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4
        )

    # ----------------------------------------------
    # VERIFY DEBUG IMAGES
    # ----------------------------------------------

    suit_images = sorted(
        OUTPUT_DIR.glob("*_suit.png")
    )

    corner_images = sorted(
        OUTPUT_DIR.glob("*_corner.png")
    )

    rank_images = sorted(
        OUTPUT_DIR.glob("*_rank.png")
    )

    print("\n" + "=" * 50)
    print("PROCESS COMPLETED")
    print("=" * 50)

    print(f"Cards loaded: {len(card_crops)}")
    print(f"Suit images: {len(suit_images)}")
    print(f"Corner images: {len(corner_images)}")
    print(f"Rank images: {len(rank_images)}")

    print("\nGenerated suit images:")

    for path in suit_images:
        print(f"  {path.name}")

    print(f"\nJSON saved: {OUTPUT_JSON}")
    print(f"Debug images saved: {OUTPUT_DIR}")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()
