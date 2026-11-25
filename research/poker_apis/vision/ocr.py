
from dataclasses import dataclass
from typing import Any

import numpy as np
from paddleocr import PaddleOCR


@dataclass
class OCRText:
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


class PokerOCR:
    """Extract text and bounding boxes from test screenshots."""

    
    @staticmethod
    def filter_results(
        results: list[OCRText],
        threshold: float = 0.85
    ) -> dict:
        accepted = []
        uncertain = []

        for item in results:
            if item.confidence >= threshold:
                accepted.append(item)
            else:
                uncertain.append(item)

        return {
            "accepted": accepted,
            "uncertain": uncertain,
        }

    def __init__(self):
        self.engine = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )

    def extract(self, image: np.ndarray) -> list[OCRText]:
        results = self.engine.predict(image)
        extracted = []

        for result in results:
            payload = result.json

            if isinstance(payload, dict):
                data = payload.get("res", payload)
            else:
                continue

            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            boxes = data.get("rec_boxes", [])

            for text, score, box in zip(texts, scores, boxes):
                if not str(text).strip():
                    continue

                x1, y1, x2, y2 = map(float, box)

                extracted.append(
                    OCRText(
                        text=str(text).strip(),
                        confidence=float(score),
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    )
                )

        return extracted
