
import re
from dataclasses import dataclass

from poker_apis.vision.ocr import OCRText


@dataclass
class ExtractedValue:
    value: str
    confidence: float
    x: float
    y: float


class PokerTextParser:
    """Extract candidate poker-related text and amounts."""

    AMOUNT_PATTERN = re.compile(
        r"^\$?\s*(\d[\d,]*(?:\.\d{1,2})?)$"
    )

    def parse(self, items: list[OCRText]) -> dict:
        names = []
        amounts = []
        other_text = []

        for item in items:
            text = item.text.strip()

            value = ExtractedValue(
                value=text,
                confidence=item.confidence,
                x=item.x,
                y=item.y,
            )

            if self.AMOUNT_PATTERN.match(text):
                amounts.append(value)

            elif self._looks_like_name(text):
                names.append(value)

            else:
                other_text.append(value)

        return {
            "candidate_names": names,
            "candidate_amounts": amounts,
            "other_text": other_text,
        }

    @staticmethod
    def _looks_like_name(text: str) -> bool:
        if len(text) < 2 or len(text) > 24:
            return False

        if re.fullmatch(r"[\d$,.]+", text):
            return False

        return bool(re.search(r"[A-Za-z]", text))
