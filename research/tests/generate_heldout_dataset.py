
import json
import random
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/heldout_v1"
)

CARDS_DIR = OUTPUT_DIR / "cards"

EXPECTED_FILE = OUTPUT_DIR / "expected.json"


WIDTH = 108
HEIGHT = 148

RANDOM_SEED = 2026

RANKS = [
    "A", "K", "Q", "J", "10",
    "9", "8", "7", "6",
    "5", "4", "3", "2"
]

SUITS = {
    "hearts": "\u2665",
    "diamonds": "\u2666",
    "clubs": "\u2663",
    "spades": "\u2660"
}

RED_SUITS = {
    "hearts",
    "diamonds"
}

VARIANTS = [
    "standard",
    "blurred",
    "rotated"
]

BACKGROUND = (248, 248, 248)

RANK_FONT_PATH = (
    "C:/Windows/Fonts/arialbd.ttf"
)

SUIT_FONT_PATH = (
    "C:/Windows/Fonts/seguisym.ttf"
)


# --------------------------------------------------
# CENTERED TEXT
# --------------------------------------------------

def draw_centered_text(
    draw,
    center,
    text,
    font,
    color
):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]

    x = center[0] - width / 2 - bbox[0]
    y = center[1] - height / 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill=color
    )


# --------------------------------------------------
# GENERATE CARD
# --------------------------------------------------

def create_card(rank, suit):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BACKGROUND
    )

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (0, 0, WIDTH - 1, HEIGHT - 1),
        radius=5,
        fill=BACKGROUND,
        outline=(190, 190, 190),
        width=1
    )

    color = (
        (190, 20, 30)
        if suit in RED_SUITS
        else (20, 20, 20)
    )

    rank_font = ImageFont.truetype(
        RANK_FONT_PATH,
        27 if rank == "10" else 32
    )

    small_suit_font = ImageFont.truetype(
        SUIT_FONT_PATH,
        25
    )

    large_suit_font = ImageFont.truetype(
        SUIT_FONT_PATH,
        52
    )

    draw_centered_text(
        draw,
        (23, 22),
        rank,
        rank_font,
        color
    )

    draw_centered_text(
        draw,
        (23, 53),
        SUITS[suit],
        small_suit_font,
        color
    )

    draw_centered_text(
        draw,
        (54, 91),
        SUITS[suit],
        large_suit_font,
        color
    )

    draw_centered_text(
        draw,
        (85, 126),
        rank,
        rank_font,
        color
    )

    return image


# --------------------------------------------------
# APPLY IMAGE VARIANT
# --------------------------------------------------

def apply_variant(image, variant, rng):

    if variant == "standard":

        return image.copy(), {}

    if variant == "blurred":

        radius = round(
            rng.uniform(0.5, 1.1),
            3
        )

        result = image.filter(
            ImageFilter.GaussianBlur(
                radius=radius
            )
        )

        return result, {
            "blur_radius": radius
        }

    if variant == "rotated":

        angle = round(
            rng.choice([-1, 1])
            * rng.uniform(1.0, 3.0),
            3
        )

        result = image.rotate(
            angle,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=BACKGROUND
        )

        return result, {
            "rotation_degrees": angle
        }

    raise ValueError(
        f"Unsupported variant: {variant}"
    )


# --------------------------------------------------
# GENERATE EMPTY SLOTS
# --------------------------------------------------

def generate_empty_slots(records, rng):

    for index in range(12):

        color = (
            rng.randint(20, 40),
            rng.randint(65, 100),
            rng.randint(45, 80)
        )

        image = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            color
        )

        filename = (
            f"empty_{index + 1:03d}.png"
        )

        image.save(
            CARDS_DIR / filename
        )

        records.append({
            "file": filename,
            "variant": "empty",
            "occupied": False,
            "rank": None,
            "suit": None,
            "transform": {
                "background_rgb": list(color)
            }
        })


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 70)
    print("HELD-OUT OFFLINE DATASET GENERATOR")
    print("=" * 70)

    if EXPECTED_FILE.exists():

        raise FileExistsError(
            "Held-out dataset already exists. "
            "Preserve it for reproducible testing."
        )

    CARDS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    rng = random.Random(
        RANDOM_SEED
    )

    records = []

    for variant in VARIANTS:

        print(
            f"\nGenerating variant: {variant}"
        )

        count = 0

        for suit in SUITS:

            for rank in RANKS:

                image = create_card(
                    rank,
                    suit
                )

                image, transform = apply_variant(
                    image,
                    variant,
                    rng
                )

                filename = (
                    f"{variant}_{rank}_{suit}.png"
                )

                image.save(
                    CARDS_DIR / filename
                )

                records.append({
                    "file": filename,
                    "variant": variant,
                    "occupied": True,
                    "rank": rank,
                    "suit": suit,
                    "transform": transform
                })

                count += 1

        print(
            f"Generated {count} cards"
        )

    generate_empty_slots(
        records,
        rng
    )

    rng.shuffle(records)

    expected = {
        "dataset_id": "heldout_v1",
        "type": "synthetic_heldout",
        "recognition_profile": "simulator",
        "random_seed": RANDOM_SEED,
        "image_width": WIDTH,
        "image_height": HEIGHT,
        "total_images": len(records),
        "occupied_cards": 156,
        "empty_slots": 12,
        "records": records
    }

    EXPECTED_FILE.write_text(
        json.dumps(
            expected,
            indent=4
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print("DATASET GENERATION COMPLETED")
    print("=" * 70)

    print("Unique cards: 52")
    print("Standard images: 52")
    print("Blurred images: 52")
    print("Rotated images: 52")
    print("Empty slots: 12")
    print(f"Total images: {len(records)}")

    print(
        f"\nCards directory: {CARDS_DIR}"
    )

    print(
        f"Expected file: {EXPECTED_FILE}"
    )


if __name__ == "__main__":
    main()
