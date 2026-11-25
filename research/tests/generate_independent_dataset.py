
import json
import random
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_DIR = (
    PROJECT_ROOT
    / "test_assets/validation/independent_v1"
)

CARDS_DIR = DATASET_DIR / "cards"

EXPECTED_FILE = DATASET_DIR / "expected.json"

RANDOM_SEED = 7319

RNG = random.Random(RANDOM_SEED)

WIDTH = 108
HEIGHT = 148

FONT_DIR = Path("C:/Windows/Fonts")

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

VARIANTS = [
    "font_variation",
    "combined_distortion"
]


def draw_centered(
    draw,
    position,
    text,
    font,
    color
):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    width = box[2] - box[0]
    height = box[3] - box[1]

    x = position[0] - width / 2 - box[0]
    y = position[1] - height / 2 - box[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill=color
    )


def create_card(rank, suit, variant):

    brightness = RNG.randint(235, 255)

    background = (
        brightness,
        brightness,
        brightness
    )

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        background
    )

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (0, 0, WIDTH - 1, HEIGHT - 1),
        radius=5,
        outline=(180, 180, 180),
        width=1
    )

    rank_font_name = RNG.choice([
        "arialbd.ttf",
        "calibrib.ttf",
        "tahomabd.ttf"
    ])

    rank_size = RNG.randint(28, 34)

    if rank == "10":
        rank_size -= 5

    rank_font = ImageFont.truetype(
        str(FONT_DIR / rank_font_name),
        rank_size
    )

    small_suit_font = ImageFont.truetype(
        str(FONT_DIR / "seguisym.ttf"),
        25
    )

    large_suit_font = ImageFont.truetype(
        str(FONT_DIR / "seguisym.ttf"),
        52
    )

    if suit in ("hearts", "diamonds"):

        color = (
            RNG.randint(170, 210),
            RNG.randint(10, 35),
            RNG.randint(15, 45)
        )

    else:

        shade = RNG.randint(10, 40)

        color = (shade, shade, shade)

    offset_x = RNG.randint(-2, 2)
    offset_y = RNG.randint(-2, 2)

    draw_centered(
        draw,
        (23 + offset_x, 22 + offset_y),
        rank,
        rank_font,
        color
    )

    draw_centered(
        draw,
        (23, 53),
        SUITS[suit],
        small_suit_font,
        color
    )

    draw_centered(
        draw,
        (54, 91),
        SUITS[suit],
        large_suit_font,
        color
    )

    draw_centered(
        draw,
        (85, 126),
        rank,
        rank_font,
        color
    )

    transform = {
        "rank_font": rank_font_name,
        "rank_size": rank_size,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "background_brightness": brightness
    }

    if variant == "combined_distortion":

        blur_radius = round(
            RNG.uniform(0.6, 1.3),
            3
        )

        rotation = round(
            RNG.uniform(-3.5, 3.5),
            3
        )

        image = image.filter(
            ImageFilter.GaussianBlur(
                radius=blur_radius
            )
        )

        image = image.rotate(
            rotation,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=background
        )

        transform.update({
            "blur_radius": blur_radius,
            "rotation_degrees": rotation
        })

    return image, transform


def main():

    if EXPECTED_FILE.exists():

        raise FileExistsError(
            "Independent dataset already exists. "
            "Refusing to overwrite."
        )

    required_fonts = [
        "arialbd.ttf",
        "calibrib.ttf",
        "tahomabd.ttf",
        "seguisym.ttf"
    ]

    for font_name in required_fonts:

        if not (FONT_DIR / font_name).is_file():

            raise FileNotFoundError(
                f"Missing font: {font_name}"
            )

    CARDS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    records = []

    for variant in VARIANTS:

        for rank in RANKS:

            for suit in SUITS:

                image, transform = create_card(
                    rank,
                    suit,
                    variant
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

    # Generate independent empty-slot images.

    for index in range(1, 13):

        color = (
            RNG.randint(20, 45),
            RNG.randint(65, 110),
            RNG.randint(45, 85)
        )

        image = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            color
        )

        filename = f"empty_{index:03}.png"

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
                "background_color": list(color)
            }
        })

    RNG.shuffle(records)

    dataset = {
        "dataset_id": "independent_v1",
        "type": "synthetic_independent",
        "random_seed": RANDOM_SEED,
        "image_width": WIDTH,
        "image_height": HEIGHT,
        "total_images": len(records),
        "occupied_cards": 104,
        "empty_slots": 12,
        "records": records
    }

    EXPECTED_FILE.write_text(
        json.dumps(dataset, indent=4),
        encoding="utf-8"
    )

    print("=" * 65)
    print("INDEPENDENT DATASET GENERATED")
    print("=" * 65)

    print("Font variation cards: 52")
    print("Combined distortion cards: 52")
    print("Empty slots: 12")
    print(f"Total images: {len(records)}")
    print(f"Random seed: {RANDOM_SEED}")
    print(f"Dataset saved: {DATASET_DIR}")


if __name__ == "__main__":
    main()
