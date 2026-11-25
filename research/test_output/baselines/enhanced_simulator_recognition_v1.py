
from poker_apis.vision.simulator_card_recognition import (
    SimulatorCardRecognizer
)

from poker_apis.vision.rank_fallback import (
    RankFallback
)


class EnhancedSimulatorCardRecognizer(
    SimulatorCardRecognizer
):
    """
    Experimental offline simulator recognizer
    with dedicated rank fallback.
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.rank_fallback = RankFallback(
            ocr=self.ocr,
            confidence_threshold=(
                self.confidence_threshold
            )
        )

        self.reset_fallback_statistics()

    def reset_fallback_statistics(self):

        self.fallback_statistics = {
            "total_cards": 0,
            "fallback_attempts": 0,
            "fallback_recovered": 0,
            "fallback_rejected": 0
        }

    def get_fallback_statistics(self):

        return self.fallback_statistics.copy()

    def recognize_card(
        self,
        card_image,
        card_name=None
    ):

        self.fallback_statistics[
            "total_cards"
        ] += 1

        result = super().recognize_card(
            card_image,
            card_name=card_name
        )

        result["rank_fallback_used"] = False

        result["rank_fallback_recovered"] = False

        # Preserve existing successful ranks.

        if result.get("rank") is not None:

            return result

        # Avoid fallback when suit recognition
        # has also failed.

        if result.get("suit") is None:

            return result

        self.fallback_statistics[
            "fallback_attempts"
        ] += 1

        result["rank_fallback_used"] = True

        fallback = self.rank_fallback.recognize(
            card_image
        )

        result["rank_fallback_result"] = fallback

        if not fallback["accepted"]:

            self.fallback_statistics[
                "fallback_rejected"
            ] += 1

            return result

        result["rank"] = fallback["rank"]

        result["rank_confidence"] = (
            fallback["confidence"]
        )

        result["rank_source"] = (
            fallback["source"]
        )

        result["recognized"] = (
            result["rank"] is not None
            and result["suit"] is not None
        )

        result["rank_fallback_recovered"] = True

        self.fallback_statistics[
            "fallback_recovered"
        ] += 1

        return result
