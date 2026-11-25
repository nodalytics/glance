
from poker_apis.vision.simulator_card_recognition import (
    SimulatorCardRecognizer
)

from poker_apis.vision.card_occupancy import (
    CardOccupancyDetector
)


class OptimizedSimulatorCardRecognizer(
    SimulatorCardRecognizer
):
    """
    Offline simulator recognizer with explicit
    occupancy detection and empty-slot OCR skipping.
    """

    def __init__(self, *args, **kwargs):

        super().__init__(
            *args,
            **kwargs
        )

        self.occupancy_detector = (
            CardOccupancyDetector()
        )

        self.reset_statistics()

    # --------------------------------------------------
    # STATISTICS
    # --------------------------------------------------

    def reset_statistics(self):

        self.statistics = {
            "total_slots": 0,
            "occupied_slots": 0,
            "empty_slots": 0,
            "unknown_slots": 0,
            "ocr_skipped_slots": 0,
            "recognition_attempts": 0,
            "recognized_cards": 0
        }

    def get_statistics(self):

        result = self.statistics.copy()

        total = result["total_slots"]

        result["ocr_skip_rate"] = (
            result["ocr_skipped_slots"] / total
            if total else 0.0
        )

        return result

    # --------------------------------------------------
    # EMPTY CARD RESPONSE
    # --------------------------------------------------

    def create_empty_response(
        self,
        occupancy
    ):

        return {
            "rank": None,
            "rank_confidence": 0.0,
            "rank_source": None,
            "suit": None,
            "suit_confidence": 0.0,
            "suit_source": None,
            "suit_margin": 0.0,
            "suit_scores": {},
            "suit_color": "unknown",
            "recognized": False,
            "occupied": False,
            "occupancy_state": "empty",
            "occupancy": occupancy,
            "ocr_skipped": True
        }

    # --------------------------------------------------
    # RECOGNIZE CARD
    # --------------------------------------------------

    def recognize_card(
        self,
        card_image,
        card_name=None
    ):

        occupancy = (
            self.occupancy_detector.detect(
                card_image
            )
        )

        self.statistics["total_slots"] += 1

        state = occupancy["state"]

        self.statistics[
            f"{state}_slots"
        ] += 1

        if occupancy["skip_ocr"]:

            self.statistics[
                "ocr_skipped_slots"
            ] += 1

            return self.create_empty_response(
                occupancy
            )

        self.statistics[
            "recognition_attempts"
        ] += 1

        result = super().recognize_card(
            card_image,
            card_name=card_name
        )

        if result["recognized"]:

            self.statistics[
                "recognized_cards"
            ] += 1

        result["occupied"] = (
            True
            if result["recognized"]
            else occupancy["occupied"]
        )

        result["occupancy_state"] = state

        result["occupancy"] = occupancy

        result["ocr_skipped"] = False

        return result
