
from poker_apis.vision.enhanced_simulator_recognition import (
    EnhancedSimulatorCardRecognizer
)


class VerifiedSimulatorCardRecognizer(
    EnhancedSimulatorCardRecognizer
):
    """
    Experimental rank verification for saved
    synthetic playing-card images.
    """

    def __init__(
        self,
        *args,
        verification_trigger=0.90,
        verification_threshold=0.95,
        **kwargs
    ):

        super().__init__(*args, **kwargs)

        if not (
            0.0 <= verification_trigger
            <= verification_threshold <= 1.0
        ):
            raise ValueError(
                "Invalid verification thresholds."
            )

        self.verification_trigger = (
            verification_trigger
        )

        self.verification_threshold = (
            verification_threshold
        )

        self.reset_verification_statistics()

    def reset_verification_statistics(self):

        self.verification_statistics = {
            "total_cards": 0,
            "verification_attempts": 0,
            "confirmed_ranks": 0,
            "changed_ranks": 0,
            "rejected_ranks": 0
        }

    def get_verification_statistics(self):

        return self.verification_statistics.copy()

    def recognize_card(
        self,
        card_image,
        card_name=None
    ):

        self.verification_statistics[
            "total_cards"
        ] += 1

        result = super().recognize_card(
            card_image,
            card_name=card_name
        )

        result["rank_verification_used"] = False

        result["rank_verification_status"] = (
            "not_required"
        )

        if not result.get("recognized"):

            result["rank_verification_status"] = (
                "unrecognized"
            )

            return result

        original_rank = result["rank"]

        original_confidence = float(
            result["rank_confidence"]
        )

        if (
            original_confidence
            >= self.verification_trigger
        ):

            return result

        self.verification_statistics[
            "verification_attempts"
        ] += 1

        result["rank_verification_used"] = True

        result["original_rank"] = original_rank

        result["original_rank_confidence"] = (
            original_confidence
        )

        # Avoid repeating the same dedicated
        # OCR operation if fallback already ran.

        if result.get("rank_fallback_recovered"):

            verification = result[
                "rank_fallback_result"
            ]

        else:

            verification = (
                self.rank_fallback.recognize(
                    card_image
                )
            )

        result["rank_verification_result"] = (
            verification
        )

        verified_rank = verification.get(
            "rank"
        )

        verified_confidence = float(
            verification.get("confidence", 0.0)
        )

        accepted = (
            verification.get("accepted", False)
            and verified_rank is not None
            and verified_confidence
            >= self.verification_threshold
        )

        if not accepted:

            result["rank"] = None

            result["rank_confidence"] = (
                verified_confidence
            )

            result["rank_source"] = (
                "verification_rejected"
            )

            result["recognized"] = False

            result["rank_verification_status"] = (
                "rejected"
            )

            self.verification_statistics[
                "rejected_ranks"
            ] += 1

            return result

        result["rank"] = verified_rank

        result["rank_confidence"] = (
            verified_confidence
        )

        result["rank_source"] = (
            "dedicated_rank_verification"
        )

        result["recognized"] = (
            result["rank"] is not None
            and result["suit"] is not None
        )

        if verified_rank == original_rank:

            result["rank_verification_status"] = (
                "confirmed"
            )

            self.verification_statistics[
                "confirmed_ranks"
            ] += 1

        else:

            result["rank_verification_status"] = (
                "changed"
            )

            self.verification_statistics[
                "changed_ranks"
            ] += 1

        return result
