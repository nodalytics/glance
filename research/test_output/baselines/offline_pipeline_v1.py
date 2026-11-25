
import time
from pathlib import Path

import cv2

from poker_apis.vision.recognition_profiles import (
    RecognitionProfileManager
)

from poker_apis.state.table_state_builder import (
    TableStateBuilder
)


class OfflineProcessingPipeline:
    """
    Centralized processing pipeline for saved
    offline card images and extracted table data.

    Does not capture live screens or interact
    with poker clients.
    """

    REQUIRED_SLOTS = [
        "board_1",
        "board_2",
        "board_3",
        "board_4",
        "board_5",
        "hero_card_1",
        "hero_card_2"
    ]

    SUPPORTED_DATASET_TYPES = {
        "calibration",
        "synthetic",
        "synthetic_heldout",
        "synthetic_optimized"
    }

    def __init__(self, project_root=None):

        if project_root is None:

            project_root = (
                Path(__file__).resolve().parents[2]
            )

        self.project_root = Path(project_root)

        self.profile_manager = (
            RecognitionProfileManager(
                project_root=self.project_root,
                optimize_simulator=True
            )
        )

        self.state_builder = TableStateBuilder()

    # --------------------------------------------------
    # VALIDATE INPUT IMAGES
    # --------------------------------------------------

    def validate_card_images(self, card_images):

        if not isinstance(card_images, dict):

            raise TypeError(
                "Card images must be a dictionary."
            )

        required = set(self.REQUIRED_SLOTS)

        supplied = set(card_images)

        missing = required - supplied

        unexpected = supplied - required

        if missing:

            raise ValueError(
                f"Missing card slots: {sorted(missing)}"
            )

        if unexpected:

            raise ValueError(
                f"Unexpected card slots: "
                f"{sorted(unexpected)}"
            )

        for slot in self.REQUIRED_SLOTS:

            image = card_images[slot]

            if image is None or image.size == 0:

                raise ValueError(
                    f"Empty image for slot: {slot}"
                )

            if (
                image.ndim != 3
                or image.shape[2] != 3
            ):

                raise ValueError(
                    f"Invalid BGR image: {slot}"
                )

    # --------------------------------------------------
    # LOAD SAVED CARD IMAGES
    # --------------------------------------------------

    def load_card_images(self, cards_directory):

        cards_directory = Path(cards_directory)

        if not cards_directory.is_dir():

            raise FileNotFoundError(
                f"Cards directory not found: "
                f"{cards_directory}"
            )

        card_images = {}

        for slot in self.REQUIRED_SLOTS:

            image_path = (
                cards_directory / f"{slot}.png"
            )

            if not image_path.is_file():

                raise FileNotFoundError(
                    f"Missing card image: {image_path}"
                )

            image = cv2.imread(
                str(image_path),
                cv2.IMREAD_COLOR
            )

            if image is None:

                raise IOError(
                    f"Cannot read image: {image_path}"
                )

            card_images[slot] = image

        return card_images

    # --------------------------------------------------
    # PROCESS CARD IMAGES
    # --------------------------------------------------

    def process(
        self,
        table_data,
        card_images,
        dataset_type="synthetic"
    ):

        total_start = time.perf_counter()

        if not isinstance(table_data, dict):

            raise TypeError(
                "Table data must be a dictionary."
            )

        if (
            dataset_type
            not in self.SUPPORTED_DATASET_TYPES
        ):

            raise ValueError(
                f"Unsupported dataset type: "
                f"{dataset_type}"
            )

        self.validate_card_images(card_images)

        # Initialize or retrieve recognition profile.

        initialization_start = time.perf_counter()

        recognizer = (
            self.profile_manager.get_recognizer(
                dataset_type
            )
        )

        profile_info = (
            self.profile_manager.get_profile_info(
                dataset_type
            )
        )

        initialization_time = (
            time.perf_counter()
            - initialization_start
        )

        if hasattr(recognizer, "reset_statistics"):

            recognizer.reset_statistics()

        # Recognize all seven card slots.

        recognition_start = time.perf_counter()

        recognized_cards = {}

        slot_timings = {}

        for slot in self.REQUIRED_SLOTS:

            slot_start = time.perf_counter()

            recognized_cards[slot] = (
                recognizer.recognize_card(
                    card_images[slot],
                    card_name=slot
                )
            )

            slot_timings[slot] = round(
                time.perf_counter() - slot_start,
                6
            )

        recognition_time = (
            time.perf_counter()
            - recognition_start
        )

        # Select offline input source.

        source = (
            "offline_screenshot"
            if dataset_type == "calibration"
            else "offline_simulator"
        )

        # Build and validate structured table state.

        state_start = time.perf_counter()

        state = self.state_builder.build(
            table_data=table_data,
            recognized_cards=recognized_cards,
            source=source,
            recognition_profile=profile_info["profile"]
        )

        state_building_time = (
            time.perf_counter()
            - state_start
        )

        # Collect recognition statistics.

        if hasattr(recognizer, "get_statistics"):

            statistics = recognizer.get_statistics()

        else:

            statistics = {
                "total_slots": len(recognized_cards),

                "ocr_skipped_slots": 0,

                "recognition_attempts": len(
                    recognized_cards
                ),

                "recognized_cards": sum(
                    card.get("recognized") is True
                    for card in recognized_cards.values()
                )
            }

        total_time = (
            time.perf_counter() - total_start
        )

        state["metadata"].update({

            "dataset_type": dataset_type,

            "profile_info": profile_info,

            "processing_time_seconds": round(
                total_time,
                6
            ),

            "timings": {
                "initialization_seconds": round(
                    initialization_time,
                    6
                ),

                "recognition_seconds": round(
                    recognition_time,
                    6
                ),

                "state_building_seconds": round(
                    state_building_time,
                    6
                ),

                "total_seconds": round(
                    total_time,
                    6
                ),

                "card_slots": slot_timings
            },

            "recognition_statistics": statistics
        })

        return state

    # --------------------------------------------------
    # PROCESS SAVED CARD DIRECTORY
    # --------------------------------------------------

    def process_directory(
        self,
        table_data,
        cards_directory,
        dataset_type="synthetic"
    ):

        start_time = time.perf_counter()

        loading_start = time.perf_counter()

        card_images = self.load_card_images(
            cards_directory
        )

        loading_time = (
            time.perf_counter() - loading_start
        )

        state = self.process(
            table_data=table_data,
            card_images=card_images,
            dataset_type=dataset_type
        )

        total_time = (
            time.perf_counter() - start_time
        )

        state["metadata"]["timings"][
            "image_loading_seconds"
        ] = round(loading_time, 6)

        state["metadata"]["timings"][
            "directory_total_seconds"
        ] = round(total_time, 6)

        state["metadata"][
            "processing_time_seconds"
        ] = round(total_time, 6)

        return state
