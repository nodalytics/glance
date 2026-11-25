
import json
import shutil
from pathlib import Path


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_CARDS = (
    PROJECT_ROOT / "test_output/card_crops"
)

SOURCE_EXPECTED = (
    PROJECT_ROOT
    / "test_assets/validation/calibration_expected.json"
)

DATASET_ROOT = (
    PROJECT_ROOT / "test_assets/validation/datasets"
)

CALIBRATION_DIR = (
    DATASET_ROOT / "calibration_sample_001"
)

CALIBRATION_CARDS = (
    CALIBRATION_DIR / "cards"
)

MANIFEST_FILE = (
    DATASET_ROOT / "manifest.json"
)


# --------------------------------------------------
# EXPECTED CARD SLOTS
# --------------------------------------------------

CARD_SLOTS = [
    "board_1",
    "board_2",
    "board_3",
    "board_4",
    "board_5",
    "hero_card_1",
    "hero_card_2"
]


# --------------------------------------------------
# COPY WITHOUT OVERWRITING
# --------------------------------------------------

def safe_copy(source, destination):

    if not source.is_file():
        raise FileNotFoundError(
            f"Missing source file: {source}"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if destination.exists():

        if source.read_bytes() != destination.read_bytes():
            raise RuntimeError(
                f"Existing file differs: {destination}"
            )

        print(f"Already preserved: {destination.name}")
        return

    shutil.copy2(source, destination)

    print(f"Copied: {destination.name}")


# --------------------------------------------------
# PRESERVE CALIBRATION SAMPLE
# --------------------------------------------------

def preserve_calibration():

    CALIBRATION_CARDS.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nPreserving calibration images...")

    for card_name in CARD_SLOTS:

        source = SOURCE_CARDS / f"{card_name}.png"

        destination = (
            CALIBRATION_CARDS / f"{card_name}.png"
        )

        safe_copy(source, destination)

    safe_copy(
        SOURCE_EXPECTED,
        CALIBRATION_DIR / "expected.json"
    )


# --------------------------------------------------
# CREATE DATASET MANIFEST
# --------------------------------------------------

def create_manifest():

    if MANIFEST_FILE.exists():

        with open(
            MANIFEST_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            manifest = json.load(file)

    else:

        manifest = {
            "version": 1,
            "datasets": []
        }

    sample = {
        "id": "calibration_sample_001",
        "type": "calibration",
        "street": "river",
        "cards_directory": (
            "calibration_sample_001/cards"
        ),
        "expected_file": (
            "calibration_sample_001/expected.json"
        ),
        "enabled": True
    }

    existing = next(
        (
            item for item in manifest["datasets"]
            if item["id"] == sample["id"]
        ),
        None
    )

    if existing is None:
        manifest["datasets"].append(sample)

    elif existing != sample:
        raise RuntimeError(
            "Existing calibration manifest entry differs."
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

    print(f"\nManifest saved: {MANIFEST_FILE}")


# --------------------------------------------------
# PREPARE INDEPENDENT DATASET DIRECTORIES
# --------------------------------------------------

def prepare_independent_directories():

    scenarios = [
        "preflop_sample_001",
        "flop_sample_001",
        "turn_sample_001",
        "river_sample_001"
    ]

    for scenario in scenarios:

        directory = (
            DATASET_ROOT / scenario / "cards"
        )

        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        print(f"Prepared: {scenario}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print("=" * 65)
    print("OFFLINE VALIDATION DATASET PREPARATION")
    print("=" * 65)

    preserve_calibration()

    create_manifest()

    print("\nPreparing independent datasets...")

    prepare_independent_directories()

    preserved = list(
        CALIBRATION_CARDS.glob("*.png")
    )

    print("\n" + "=" * 65)
    print("DATASET PREPARATION COMPLETED")
    print("=" * 65)

    print(f"Calibration cards preserved: {len(preserved)}")
    print(f"Independent directories prepared: 4")
    print(f"Dataset root: {DATASET_ROOT}")


if __name__ == "__main__":
    main()
