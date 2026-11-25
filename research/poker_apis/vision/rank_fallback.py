
import cv2


class RankFallback:
    """
    Dedicated rank recognition fallback for
    saved synthetic playing-card images.
    """

    VALID_RANKS = {
        "A", "K", "Q", "J", "10",
        "9", "8", "7", "6",
        "5", "4", "3", "2"
    }

    def __init__(
        self,
        ocr,
        confidence_threshold=0.75
    ):

        self.ocr = ocr

        self.confidence_threshold = (
            confidence_threshold
        )

    def normalize_rank(self, text):

        text = (
            str(text)
            .strip()
            .upper()
            .replace(" ", "")
        )

        aliases = {
            "T": "10",
            "1O": "10",
            "IO": "10"
        }

        text = aliases.get(text, text)

        if text in self.VALID_RANKS:
            return text

        return None

    def extract_rank_region(self, image):

        if image is None or image.size == 0:

            raise ValueError(
                "Card image is empty."
            )

        height, width = image.shape[:2]

        x1 = int(width * 0.03)
        y1 = int(height * 0.01)

        x2 = int(width * 0.43)
        y2 = int(height * 0.24)

        region = image[y1:y2, x1:x2]

        if region.size == 0:

            raise ValueError(
                "Rank region is empty."
            )

        return region

    def prepare_image(self, image):

        region = self.extract_rank_region(
            image
        )

        enlarged = cv2.resize(
            region,
            None,
            fx=4,
            fy=4,
            interpolation=cv2.INTER_CUBIC
        )

        prepared = cv2.copyMakeBorder(
            enlarged,
            20,
            20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=(255, 255, 255)
        )

        return prepared

    def recognize(self, image):

        prepared = self.prepare_image(
            image
        )

        results = self.ocr.extract(
            prepared
        )

        candidates = []

        for item in results:

            rank = self.normalize_rank(
                item.text
            )

            if rank is None:
                continue

            candidates.append({
                "rank": rank,
                "confidence": float(
                    item.confidence
                )
            })

        if not candidates:

            return {
                "rank": None,
                "confidence": 0.0,
                "source": None,
                "accepted": False
            }

        best = max(
            candidates,
            key=lambda item: item["confidence"]
        )

        accepted = (
            best["confidence"]
            >= self.confidence_threshold
        )

        return {
            "rank": (
                best["rank"]
                if accepted else None
            ),
            "confidence": best["confidence"],
            "source": "dedicated_rank_fallback",
            "accepted": accepted
        }
