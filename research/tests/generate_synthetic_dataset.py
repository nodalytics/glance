
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_ROOT = (
    PROJECT_ROOT / "test_assets/validation/datasets"
)

MANIFEST_FILE = DATASET_ROOT / "manifest.json"


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

RANDOM_SEED = 42

CARD_WIDTH = 108
CARD_HEIGHT = 148

RANKS = [
    "A", "K", "Q", "J", "10",
    "9", "8", "7", "6", "5",
    "4", "3", "2"
]

SUITS = [
    "hearts",
    "diamonds",
    "clubs",
    "spades"
]

SUIT_SYMBOLS = {
    "hearts": "\u2665",
    "diamonds": "\u2666",
    "clubs": "\u2663",
    "spades": "\u2660"
}

SUIT_COLORS = {
    "hearts": (190, 20, 30),
    "diamonds": (190, 20, 30),
    "clubs": (20, 20, 20),
    "spades": (20, 20, 20)
}

CARD_SLOTS = [
    "board_1",
    "board_2",
    "board_3",
    "board_4",
    "board_5",
    "hero_card_1",
    "hero_card_2"
]

SCENARIOS = {
    "preflop": 0,
    "flop": 3,
    "turn": 4,
    "river": 5
}


# --------------------------------------------------
# FONT LOADING
# --------------------------------------------------

def load_font(size, suit_font=False):

    if suit_font:
        candidates = [
            "C:/Windows/Fonts/seguisym.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "DejaVuSans.ttf"
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "DejaVuSans-Bold.ttf"
        ]

    for candidate in candidates:

        try:
            return ImageFont.truetype(
                candidate,
                size
            )

        except OSError:
            continue

    raise RuntimeError(
        "No suitable playing-card font found."
    )


# --------------------------------------------------
# DRAW CENTERED TEXT
# --------------------------------------------------

def draw_centered_text(
    draw,
    text,
    center_x,
    center_y,
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

    x = center_x - width / 2 - bbox[0]
    y = center_y - height / 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill=color
    )


# --------------------------------------------------
# GENERATE PLAYING CARD
# --------------------------------------------------

def generate_card(rank, suit):

    image = Image.new(
        "RGB",
        (CARD_WIDTH, CARD_HEIGHT),
        (248, 248, 248)
    )

    draw = ImageDraw.Draw(image)

    color = SUIT_COLORS[suit]
    symbol = SUIT_SYMBOLS[suit]

    rank_font = load_font(
        27 if rank == "10" else 32
    )

    small_suit_font = load_font(
        25,
        suit_font=True
    )

    large_suit_font = load_font(
        52,
        suit_font=True
    )

    # Card border

    draw.rounded_rectangle(
        (0, 0, CARD_WIDTH - 1, CARD_HEIGHT - 1),
        radius=5,
        outline=(190, 190, 190),
        width=1
    )

    # Top-left rank

    draw_centered_text(
        draw,
        rank,
        23,
        22,
        rank_font,
        color
    )

    # Top-left suit

    draw_centered_text(
        draw,
        symbol,
        23,
        53,
        small_suit_font,
        color
    )

    # Central suit

    draw_centered_text(
        draw,
        symbol,
        CARD_WIDTH // 2,
        91,
        large_suit_font,
        color
    )

    # Bottom-right rank

    draw_centered_text(
        draw,
        rank,
        CARD_WIDTH - 23,
        CARD_HEIGHT - 22,
        rank_font,
        color
    )

    return image


# --------------------------------------------------
# GENERATE EMPTY SLOT
# --------------------------------------------------

def generate_empty_slot():

    return Image.new(
        "RGB",
        (CARD_WIDTH, CARD_HEIGHT),
        (30, 85, 65)
    )


# --------------------------------------------------
# CREATE STANDARD DECK
# --------------------------------------------------

def create_deck():

    return [
        {
            "rank": rank,
            "suit": suit
        }
        for rank in RANKS
        for suit in SUITS
    ]


# --------------------------------------------------
# GENERATE SCENARIO
# --------------------------------------------------

def generate_scenario(street, board_count, rng):

    sample_id = f"{street}_sample_001"

    sample_dir = DATASET_ROOT / sample_id

    cards_dir = sample_dir / "cards"

    cards_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    deck = create_deck()

    selected_cards = rng.sample(
        deck,
        board_count + 2
    )

    expected_cards = {}

    occupied_slots = [
        f"board_{index + 1}"
        for index in range(board_count)
    ]

    occupied_slots.extend([
        "hero_card_1",
        "hero_card_2"
    ])

    assigned_cards = dict(
        zip(
            occupied_slots,
            selected_cards
        )
    )

    print(f"\nGenerating: {sample_id}")

    for slot in CARD_SLOTS:

        card = assigned_cards.get(slot)

        if card is not None:

            image = generate_card(
                card["rank"],
                card["suit"]
            )

            expected_cards[slot] = {
                "occupied": True,
                "rank": card["rank"],
                "suit": card["suit"]
            }

            print(
                f"  {slot:15} | "
                f"{card['rank']:3} "
                f"{card['suit']}"
            )

        else:

            image = generate_empty_slot()

            expected_cards[slot] = {
                "occupied": False,
                "rank": None,
                "suit": None
            }

            print(
                f"  {slot:15} | EMPTY"
            )

        image.save(
            cards_dir / f"{slot}.png"
        )

    expected_data = {
        "sample_name": sample_id,
        "type": "synthetic",
        "street": street,
        "board_count": board_count,
        "cards": expected_cards
    }

    expected_file = (
        sample_dir / "expected.json"
    )

    with open(
        expected_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            expected_data,
            file,
            indent=4
        )

    return {
        "id": sample_id,
        "type": "synthetic",
        "street": street,
        "cards_directory": (
            f"{sample_id}/cards"
        ),
        "expected_file": (
            f"{sample_id}/expected.json"
        ),
        "enabled": True
    }


# --------------------------------------------------
# UPDATE MANIFEST
# --------------------------------------------------

def update_manifest(new_entries):

    if not MANIFEST_FILE.exists():

        raise FileNotFoundError(
            "Dataset manifest not found. "
            "Run prepare_validation_dataset.py first."
        )

    with open(
        MANIFEST_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        manifest = json.load(file)

    existing_entries = {
        entry["id"]: entry
        for entry in manifest["datasets"]
    }

    for entry in new_entries:

        existing_entries[entry["id"]] = entry

    manifest["datasets"] = list(
        existing_entries.values()
    )

    with open(
        MANIFEST_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            manifest,
            file,
            indent=4
        )

    print(f"\nManifest updated: {MANIFEST_FILE}")

    return len(manifest["datasets"])


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 65)
    print("SYNTHETIC OFFLINE CARD DATASET GENERATOR")
    print("=" * 65)

    if not MANIFEST_FILE.is_file():
        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_FILE}"
        )

    rng = random.Random(RANDOM_SEED)

    entries = []

    total_images = 0
    occupied_images = 0
    empty_images = 0

    for street, board_count in SCENARIOS.items():

        entry = generate_scenario(
            street,
            board_count,
            rng
        )

        entries.append(entry)

        total_images += 7
        occupied_images += board_count + 2
        empty_images += 5 - board_count

    dataset_count = update_manifest(entries)

    print("\n" + "=" * 65)
    print("DATASET GENERATION COMPLETED")
    print("=" * 65)

    print(f"Random seed: {RANDOM_SEED}")
    print(f"Synthetic datasets: {len(entries)}")
    print(f"Total generated images: {total_images}")
    print(f"Occupied card images: {occupied_images}")
    print(f"Empty slot images: {empty_images}")
    print(f"Total registered datasets: {dataset_count}")
    print(f"Dataset root: {DATASET_ROOT}")


if __name__ == "__main__":
    main()
