
from pathlib import Path

import cv2
import numpy as np

from poker_apis.vision.card_recognition import (
    CardRecognizer,
    SUITS,
    SUIT_COLORS
)


class SimulatorCardRecognizer(CardRecognizer):
    """
    Card recognizer for locally generated offline
    simulator images.

    Reuses the original rank recognition engine
    and supports multiple templates per suit.
    """

    def __init__(
        self,
        suit_template_dir=(
            "test_assets/card_templates/simulator_suits"
        ),
        confidence_threshold=0.75,
        suit_confidence_threshold=0.75,
        suit_margin_threshold=0.05
    ):

        super().__init__(
            suit_template_dir=suit_template_dir,
            confidence_threshold=confidence_threshold,
            suit_confidence_threshold=(
                suit_confidence_threshold
            ),
            suit_margin_threshold=suit_margin_threshold
        )

        missing_suits = SUITS.difference(
            self.suit_templates.keys()
        )

        if missing_suits:

            raise RuntimeError(
                f"Missing simulator templates: "
                f"{sorted(missing_suits)}"
            )

    # --------------------------------------------------
    # LOAD MULTIPLE TEMPLATES PER SUIT
    # --------------------------------------------------

    def _load_suit_templates(self, template_dir):

        template_dir = Path(template_dir)

        templates = {}

        if not template_dir.is_dir():
            return templates

        for suit in sorted(SUITS):

            suit_templates = []

            for path in sorted(
                template_dir.glob(f"{suit}_*.png")
            ):

                image = cv2.imread(
                    str(path),
                    cv2.IMREAD_GRAYSCALE
                )

                if image is None:
                    continue

                image = cv2.resize(
                    image,
                    (64, 64),
                    interpolation=cv2.INTER_NEAREST
                )

                _, image = cv2.threshold(
                    image,
                    127,
                    255,
                    cv2.THRESH_BINARY
                )

                foreground = cv2.countNonZero(
                    255 - image
                )

                if (
                    foreground == 0
                    or foreground == image.size
                ):
                    continue

                suit_templates.append({
                    "name": path.stem,
                    "image": image
                })

            if suit_templates:
                templates[suit] = suit_templates

        return templates

    # --------------------------------------------------
    # TEMPLATE COUNT
    # --------------------------------------------------

    @property
    def template_count(self):

        return sum(
            len(items)
            for items in self.suit_templates.values()
        )

    # --------------------------------------------------
    # EXTRACT SIMULATOR SUIT CANDIDATES
    # --------------------------------------------------

    def extract_suit_candidates(
        self,
        card_image,
        card_name=None
    ):

        if (
            card_image is None
            or card_image.size == 0
        ):
            return []

        regions = [
            (
                "simulator_small_suit",
                (0.04, 0.24, 0.40, 0.46)
            ),
            (
                "simulator_small_suit_wide",
                (0.02, 0.23, 0.43, 0.48)
            ),
            (
                "simulator_center_suit",
                (0.23, 0.43, 0.77, 0.79)
            )
        ]

        candidates = []

        for source, region in regions:

            image = self.crop_region(
                card_image,
                region
            )

            if (
                image is not None
                and image.size > 0
            ):

                candidates.append(
                    (source, image)
                )

        return candidates

    # --------------------------------------------------
    # DETECT SUIT COLOR FROM SYMBOL PIXELS
    # --------------------------------------------------

    def detect_suit_color(self, suit_image):

        if (
            suit_image is None
            or suit_image.size == 0
        ):
            return "unknown"

        if suit_image.ndim != 3:
            return "unknown"

        hsv = cv2.cvtColor(
            suit_image,
            cv2.COLOR_BGR2HSV
        )

        red_mask_1 = cv2.inRange(
            hsv,
            np.array([0, 80, 60]),
            np.array([12, 255, 255])
        )

        red_mask_2 = cv2.inRange(
            hsv,
            np.array([165, 80, 60]),
            np.array([180, 255, 255])
        )

        red_mask = (
            red_mask_1 | red_mask_2
        )

        black_mask = cv2.inRange(
            hsv,
            np.array([0, 0, 0]),
            np.array([180, 70, 120])
        )

        red_pixels = cv2.countNonZero(
            red_mask
        )

        black_pixels = cv2.countNonZero(
            black_mask
        )

        total = red_pixels + black_pixels

        if total < 10:
            return "unknown"

        red_ratio = red_pixels / total

        if red_ratio >= 0.80:
            return "red"

        if red_ratio <= 0.20:
            return "black"

        return "unknown"

    # --------------------------------------------------
    # MULTI-TEMPLATE SUIT RECOGNITION
    # --------------------------------------------------

    def recognize_exact_suit(
        self,
        suit_candidates
    ):

        empty_result = {
            "suit": None,
            "confidence": 0.0,
            "source": None,
            "margin": 0.0,
            "scores": {}
        }

        if isinstance(
            suit_candidates,
            np.ndarray
        ):

            suit_candidates = [
                ("default", suit_candidates)
            ]

        if not suit_candidates:
            return empty_result

        best_by_suit = {}

        for source, image in suit_candidates:

            normalized = (
                self.normalize_suit_symbol(image)
            )

            if normalized is None:
                continue

            detected_color = (
                self.detect_suit_color(image)
            )

            for suit, templates in (
                self.suit_templates.items()
            ):

                # Only compare color-compatible suits.

                if (
                    detected_color != "unknown"
                    and SUIT_COLORS[suit]
                    != detected_color
                ):
                    continue

                for template in templates:

                    score = (
                        self.calculate_similarity(
                            normalized,
                            template["image"]
                        )
                    )

                    previous = best_by_suit.get(
                        suit
                    )

                    if (
                        previous is None
                        or score > previous["score"]
                    ):

                        best_by_suit[suit] = {
                            "score": float(score),
                            "source": (
                                f"{source}:"
                                f"{template['name']}"
                            )
                        }

        if not best_by_suit:
            return empty_result

        ranked = sorted(
            best_by_suit.items(),
            key=lambda item: item[1]["score"],
            reverse=True
        )

        best_suit, best_result = ranked[0]

        best_score = best_result["score"]

        second_score = (
            ranked[1][1]["score"]
            if len(ranked) > 1
            else 0.0
        )

        margin = best_score - second_score

        scores = {
            suit: result["score"]
            for suit, result in ranked
        }

        accepted = (
            best_score
            >= self.suit_confidence_threshold
            and margin
            >= self.suit_margin_threshold
        )

        return {
            "suit": (
                best_suit if accepted else None
            ),
            "confidence": best_score,
            "source": best_result["source"],
            "margin": margin,
            "scores": scores
        }
