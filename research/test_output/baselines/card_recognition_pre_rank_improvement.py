
from pathlib import Path
import re

import cv2
import numpy as np

from poker_apis.vision.ocr import PokerOCR


# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------

RANKS = {
    "A", "K", "Q", "J", "10",
    "9", "8", "7", "6", "5", "4", "3", "2"
}

SUITS = {
    "hearts",
    "diamonds",
    "clubs",
    "spades"
}

SUIT_COLORS = {
    "hearts": "red",
    "diamonds": "red",
    "clubs": "black",
    "spades": "black"
}

TEMPLATE_SIZE = 64
SYMBOL_SIZE = 52


# --------------------------------------------------
# CARD RECOGNIZER
# --------------------------------------------------

class CardRecognizer:
    """
    Offline playing-card image recognizer.

    Rank recognition:
        PaddleOCR with primary and fallback regions.

    Suit recognition:
        OpenCV contour extraction and calibrated
        template matching.
    """

    def __init__(
        self,
        suit_template_dir="test_assets/card_templates/suits",
        confidence_threshold=0.75,
        suit_confidence_threshold=0.75,
        suit_margin_threshold=0.05
    ):

        self.ocr = PokerOCR()

        self.confidence_threshold = confidence_threshold

        self.suit_confidence_threshold = (
            suit_confidence_threshold
        )

        self.suit_margin_threshold = (
            suit_margin_threshold
        )

        self.suit_templates = self._load_suit_templates(
            suit_template_dir
        )

    # --------------------------------------------------
    # TEMPLATE LOADING
    # --------------------------------------------------

    def _load_suit_templates(self, template_dir):

        templates = {}
        template_dir = Path(template_dir)

        if not template_dir.exists():
            return templates

        for suit in sorted(SUITS):

            path = template_dir / f"{suit}.png"

            if not path.exists():
                continue

            image = cv2.imread(
                str(path),
                cv2.IMREAD_GRAYSCALE
            )

            if image is None:
                continue

            image = cv2.resize(
                image,
                (TEMPLATE_SIZE, TEMPLATE_SIZE),
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

            if foreground == 0:
                continue

            if foreground == image.size:
                continue

            templates[suit] = image

        return templates

    # --------------------------------------------------
    # CARD REGION EXTRACTION
    # --------------------------------------------------

    def extract_corner(self, card_image):

        if card_image is None or card_image.size == 0:
            raise ValueError("Card image is empty.")

        height, width = card_image.shape[:2]

        x1 = int(width * 0.02)
        x2 = int(width * 0.65)

        y1 = int(height * 0.02)
        y2 = int(height * 0.65)

        corner = card_image[y1:y2, x1:x2]

        if corner.size == 0:
            raise ValueError(
                "Could not extract card corner."
            )

        return cv2.resize(
            corner,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC
        )

    def extract_rank_region(self, corner):

        height = corner.shape[0]

        return corner[:int(height * 0.65), :]

    def extract_suit_region(self, corner):

        height = corner.shape[0]

        return corner[int(height * 0.40):, :]

    def extract_fallback_rank_region(self, card_image):

        height, width = card_image.shape[:2]

        region = card_image[
            :int(height * 0.65),
            :int(width * 0.65)
        ]

        if region.size == 0:
            return None

        return cv2.resize(
            region,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC
        )

    # --------------------------------------------------
    # NORMALIZED REGION CROPPING
    # --------------------------------------------------

    def crop_region(self, image, region):

        height, width = image.shape[:2]

        x1, y1, x2, y2 = region

        return image[
            int(height * y1):int(height * y2),
            int(width * x1):int(width * x2)
        ]

    # --------------------------------------------------
    # SUIT REGION PROFILES
    # --------------------------------------------------

    def extract_suit_candidates(
        self,
        card_image,
        card_name=None
    ):

        corner = self.extract_corner(card_image)

        suit_region = self.extract_suit_region(
            corner
        )

        candidates = []

        if card_name == "hero_card_1":

            regions = [
                (0.08, 0.61, 0.35, 0.84),
                (0.07, 0.60, 0.37, 0.86)
            ]

            for index, region in enumerate(regions):

                candidates.append((
                    f"hero_1_region_{index}",
                    self.crop_region(card_image, region)
                ))

        elif card_name == "hero_card_2":

            regions = [
                (0.22, 0.57, 0.44, 0.81),
                (0.20, 0.56, 0.46, 0.83)
            ]

            for index, region in enumerate(regions):

                candidates.append((
                    f"hero_2_region_{index}",
                    self.crop_region(card_image, region)
                ))

        else:

            regions = [
                (0.04, 0.08, 0.50, 0.58),
                (0.04, 0.10, 0.49, 0.64),
                (0.03, 0.09, 0.45, 0.66)
            ]

            for index, region in enumerate(regions):

                candidates.append((
                    f"board_region_{index}",
                    self.crop_region(suit_region, region)
                ))

        return [
            (name, image)
            for name, image in candidates
            if image is not None and image.size > 0
        ]

    # --------------------------------------------------
    # RANK RECOGNITION
    # --------------------------------------------------

    def _normalize_rank(self, text):

        text = text.strip().upper()
        text = text.replace(" ", "")

        corrections = {
            "T": "10",
            "1O": "10",
            "IO": "10",
        }

        text = corrections.get(text, text)

        if text in RANKS:
            return text

        matches = re.findall(
            r"10|[AKQJ2-9]",
            text
        )

        if len(matches) == 1:
            return matches[0]

        return None

    def recognize_rank(
        self,
        rank_image,
        fallback_images=None
    ):

        candidates = []

        images_to_scan = [
            ("primary", rank_image)
        ]

        if fallback_images:

            for name, image in fallback_images:

                if image is not None and image.size > 0:

                    images_to_scan.append(
                        (name, image)
                    )

        for region_name, image in images_to_scan:

            if image is None or image.size == 0:
                continue

            results = self.ocr.extract(image)

            for item in results:

                rank = self._normalize_rank(
                    item.text
                )

                if rank is None:
                    continue

                candidates.append({
                    "rank": rank,
                    "confidence": float(item.confidence),
                    "source": region_name
                })

        if not candidates:

            return {
                "rank": None,
                "confidence": 0.0,
                "source": None
            }

        best = max(
            candidates,
            key=lambda item: item["confidence"]
        )

        if best["confidence"] < self.confidence_threshold:

            return {
                "rank": None,
                "confidence": best["confidence"],
                "source": best["source"]
            }

        return best

    # --------------------------------------------------
    # SUIT SYMBOL NORMALIZATION
    # --------------------------------------------------

    def normalize_suit_symbol(self, image):

        if image is None or image.size == 0:
            return None

        if len(image.shape) == 3:

            gray = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY
            )

        else:

            gray = image.copy()

        gray = cv2.resize(
            gray,
            None,
            fx=4,
            fy=4,
            interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.GaussianBlur(
            gray,
            (3, 3),
            0
        )

        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        largest = max(
            contours,
            key=cv2.contourArea
        )

        if cv2.contourArea(largest) < 20:
            return None

        x, y, width, height = cv2.boundingRect(
            largest
        )

        if width == 0 or height == 0:
            return None

        aspect_ratio = width / height

        if not 0.45 <= aspect_ratio <= 1.8:
            return None

        mask = np.zeros_like(binary)

        cv2.drawContours(
            mask,
            [largest],
            -1,
            255,
            thickness=cv2.FILLED
        )

        symbol = mask[
            y:y + height,
            x:x + width
        ]

        scale = SYMBOL_SIZE / max(width, height)

        new_width = max(
            1,
            round(width * scale)
        )

        new_height = max(
            1,
            round(height * scale)
        )

        symbol = cv2.resize(
            symbol,
            (new_width, new_height),
            interpolation=cv2.INTER_NEAREST
        )

        canvas = np.zeros(
            (TEMPLATE_SIZE, TEMPLATE_SIZE),
            dtype=np.uint8
        )

        offset_x = (
            TEMPLATE_SIZE - new_width
        ) // 2

        offset_y = (
            TEMPLATE_SIZE - new_height
        ) // 2

        canvas[
            offset_y:offset_y + new_height,
            offset_x:offset_x + new_width
        ] = symbol

        return 255 - canvas

    # --------------------------------------------------
    # APPROXIMATE SUIT COLOR
    # --------------------------------------------------

    def detect_suit_color(self, suit_image):

        if suit_image is None or suit_image.size == 0:
            return "unknown"

        hsv = cv2.cvtColor(
            suit_image,
            cv2.COLOR_BGR2HSV
        )

        red_mask_1 = cv2.inRange(
            hsv,
            np.array([0, 60, 50]),
            np.array([12, 255, 255])
        )

        red_mask_2 = cv2.inRange(
            hsv,
            np.array([165, 60, 50]),
            np.array([180, 255, 255])
        )

        red_mask = red_mask_1 | red_mask_2

        dark_mask = cv2.inRange(
            hsv,
            np.array([0, 0, 0]),
            np.array([180, 255, 125])
        )

        red_pixels = cv2.countNonZero(red_mask)
        dark_pixels = cv2.countNonZero(dark_mask)

        total = red_pixels + dark_pixels

        if total < 10:
            return "unknown"

        red_ratio = red_pixels / total

        if red_ratio > 0.20:
            return "red"

        if dark_pixels > 0:
            return "black"

        return "unknown"

    # --------------------------------------------------
    # TEMPLATE SIMILARITY
    # --------------------------------------------------

    
    def extract_symbol_contour(self, image):
        """
        Extract the largest foreground contour from
        a normalized black-on-white suit symbol.
        """

        if image is None or image.size == 0:
            return None

        if image.ndim == 3:
            image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY
            )

        _, binary = cv2.threshold(
            image,
            127,
            255,
            cv2.THRESH_BINARY_INV
        )

        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        contour = max(
            contours,
            key=cv2.contourArea
        )

        if cv2.contourArea(contour) < 20:
            return None

        return contour

    def calculate_similarity(self, symbol, template):
        """
        Compare normalized suit symbols using:

        1. Dice pixel similarity.
        2. Hu moment contour similarity.

        Returns a combined similarity score
        between 0.0 and 1.0.
        """

        if symbol is None or template is None:
            return 0.0

        if symbol.shape != template.shape:
            return 0.0

        # ------------------------------------------
        # DICE PIXEL SIMILARITY
        # ------------------------------------------

        symbol_mask = symbol < 128
        template_mask = template < 128

        intersection = np.count_nonzero(
            symbol_mask & template_mask
        )

        total = (
            np.count_nonzero(symbol_mask)
            + np.count_nonzero(template_mask)
        )

        if total == 0:
            return 0.0

        dice_score = float(
            2.0 * intersection / total
        )

        # ------------------------------------------
        # CONTOUR SHAPE SIMILARITY
        # ------------------------------------------

        symbol_contour = self.extract_symbol_contour(
            symbol
        )

        template_contour = self.extract_symbol_contour(
            template
        )

        if (
            symbol_contour is None
            or template_contour is None
        ):
            return 0.0

        shape_distance = cv2.matchShapes(
            symbol_contour,
            template_contour,
            cv2.CONTOURS_MATCH_I1,
            0.0
        )

        if not np.isfinite(shape_distance):
            return 0.0

        shape_score = 1.0 / (
            1.0 + 5.0 * shape_distance
        )

        # ------------------------------------------
        # COMBINED SIMILARITY
        # ------------------------------------------

        dice_weight = 0.40
        shape_weight = 0.60

        combined_score = (
            dice_weight * dice_score
            + shape_weight * shape_score
        )

        return float(
            np.clip(combined_score, 0.0, 1.0)
        )


    # --------------------------------------------------
    # EXACT SUIT RECOGNITION
    # --------------------------------------------------

    def recognize_exact_suit(self, suit_candidates):

        empty_result = {
            "suit": None,
            "confidence": 0.0,
            "source": None,
            "margin": 0.0,
            "scores": {}
        }

        if len(self.suit_templates) != 4:
            return empty_result

        if isinstance(suit_candidates, np.ndarray):

            suit_candidates = [
                ("default", suit_candidates)
            ]

        best_by_suit = {}

        for source, image in suit_candidates:

            normalized = self.normalize_suit_symbol(
                image
            )

            if normalized is None:
                continue

            for suit, template in self.suit_templates.items():

                score = self.calculate_similarity(
                    normalized,
                    template
                )

                previous = best_by_suit.get(suit)

                if previous is None or score > previous["score"]:

                    best_by_suit[suit] = {
                        "score": score,
                        "source": source
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
            best_score >= self.suit_confidence_threshold
            and margin >= self.suit_margin_threshold
        )

        return {
            "suit": best_suit if accepted else None,
            "confidence": best_score,
            "source": best_result["source"],
            "margin": margin,
            "scores": scores
        }

    # --------------------------------------------------
    # DEBUG IMAGE SAVING
    # --------------------------------------------------

    def save_debug_regions(
        self,
        card_image,
        card_name,
        output_dir
    ):

        output_dir = Path(output_dir)

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        corner = self.extract_corner(card_image)

        rank_region = self.extract_rank_region(
            corner
        )

        suit_region = self.extract_suit_region(
            corner
        )

        fallback_region = self.extract_fallback_rank_region(
            card_image
        )

        images = {
            "corner": corner,
            "rank": rank_region,
            "suit": suit_region,
            "fallback_rank": fallback_region
        }

        for name, image in images.items():

            if image is None or image.size == 0:
                continue

            cv2.imwrite(
                str(
                    output_dir
                    / f"{card_name}_{name}.png"
                ),
                image
            )

        candidates = self.extract_suit_candidates(
            card_image,
            card_name
        )

        for source, image in candidates:

            cv2.imwrite(
                str(
                    output_dir
                    / f"{card_name}_{source}_raw.png"
                ),
                image
            )

            normalized = self.normalize_suit_symbol(
                image
            )

            if normalized is not None:

                cv2.imwrite(
                    str(
                        output_dir
                        / f"{card_name}_{source}_normalized.png"
                    ),
                    normalized
                )

    # --------------------------------------------------
    # COMPLETE CARD RECOGNITION
    # --------------------------------------------------

    def recognize_card(
        self,
        card_image,
        card_name=None
    ):

        if card_image is None or card_image.size == 0:
            raise ValueError("Card image is empty.")

        corner = self.extract_corner(
            card_image
        )

        rank_region = self.extract_rank_region(
            corner
        )

        fallback_region = self.extract_fallback_rank_region(
            card_image
        )

        rank_result = self.recognize_rank(
            rank_region,
            fallback_images=[
                (
                    "top_left_fallback",
                    fallback_region
                )
            ]
        )

        suit_candidates = self.extract_suit_candidates(
            card_image,
            card_name
        )

        suit_result = self.recognize_exact_suit(
            suit_candidates
        )

        exact_suit = suit_result["suit"]

        if exact_suit is not None:

            suit_color = SUIT_COLORS[exact_suit]

        elif suit_candidates:

            suit_color = self.detect_suit_color(
                suit_candidates[0][1]
            )

        else:

            suit_color = "unknown"

        return {
            "rank": rank_result["rank"],
            "rank_confidence": rank_result["confidence"],
            "rank_source": rank_result["source"],

            "suit": exact_suit,
            "suit_confidence": suit_result["confidence"],
            "suit_source": suit_result["source"],
            "suit_margin": suit_result["margin"],
            "suit_scores": suit_result["scores"],
            "suit_color": suit_color,

            "recognized": (
                rank_result["rank"] is not None
                and exact_suit is not None
            )
        }

    # --------------------------------------------------
    # MULTIPLE CARD RECOGNITION
    # --------------------------------------------------

    def recognize_cards(self, card_crops):

        results = {}

        for card_name, card_image in card_crops.items():

            results[card_name] = self.recognize_card(
                card_image,
                card_name=card_name
            )

        return results
