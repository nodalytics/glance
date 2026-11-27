
import time
import unicodedata
import threading

from collections import Counter

import cv2
import numpy as np

from paddleocr import PaddleOCR


class OptimizedDocumentOCR:

    def __init__(self):

        self._lock = threading.Lock()
        self._request_count = 0

        start = time.perf_counter_ns()

        self.engine = PaddleOCR(
            text_detection_model_name=(
                "PP-OCRv6_tiny_det"
            ),
            text_recognition_model_name=(
                "PP-OCRv6_tiny_rec"
            ),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )

        self.initialization_ms = (
            self.elapsed_ms(start)
        )

    @staticmethod
    def elapsed_ms(start):

        return (
            time.perf_counter_ns() - start
        ) / 1_000_000

    @staticmethod
    def normalize_strict(text):

        return " ".join(
            text.lower().split()
        )

    @staticmethod
    def normalize_adjusted(text):

        text = unicodedata.normalize(
            "NFKC",
            text,
        ).lower()

        return "".join(text.split())

    @staticmethod
    def evaluate(
        expected,
        recognized,
        normalizer,
    ):

        expected_counter = Counter(
            normalizer(text)
            for text in expected
        )

        recognized_counter = Counter(
            normalizer(text)
            for text in recognized
        )

        matched = sum(
            (
                expected_counter
                & recognized_counter
            ).values()
        )

        return {
            "expected_count": len(expected),
            "recognized_count": len(recognized),
            "matched_count": matched,

            "recall_percent": round(
                matched / max(len(expected), 1)
                * 100,
                3,
            ),

            "precision_percent": round(
                matched / max(len(recognized), 1)
                * 100,
                3,
            ),

            "exact_match": (
                expected_counter
                == recognized_counter
            ),

            "missing_lines": list(
                (
                    expected_counter
                    - recognized_counter
                ).elements()
            ),

            "unexpected_lines": list(
                (
                    recognized_counter
                    - expected_counter
                ).elements()
            ),
        }

    def recognize(
        self,
        image: np.ndarray,
        expected_text: list[str],
        preprocessing: str = "gaussian",
    ):

        if not expected_text:
            raise ValueError(
                "Expected document text is required."
            )

        if (
            not isinstance(image, np.ndarray)
            or image.size == 0
            or image.ndim != 3
            or image.shape[2] != 3
            or image.dtype != np.uint8
        ):
            raise ValueError(
                "Expected a nonempty uint8 BGR image."
            )

        if preprocessing not in {
            "original",
            "gaussian",
        }:
            raise ValueError(
                "Unsupported preprocessing method."
            )

        request_start = time.perf_counter_ns()

        with self._lock:

            processing_start = (
                time.perf_counter_ns()
            )

            queue_ms = (
                processing_start - request_start
            ) / 1_000_000

            start = time.perf_counter_ns()

            if preprocessing == "gaussian":

                processed = cv2.GaussianBlur(
                    image,
                    (3, 3),
                    0,
                )

            else:

                processed = image.copy()

            preprocessing_ms = (
                self.elapsed_ms(start)
            )

            start = time.perf_counter_ns()

            results = list(
                self.engine.predict(processed)
            )

            inference_ms = self.elapsed_ms(start)

            start = time.perf_counter_ns()

            recognized = []

            for result in results:

                payload = result.json

                if not isinstance(payload, dict):
                    continue

                data = payload.get(
                    "res",
                    payload,
                )

                for text in data.get(
                    "rec_texts",
                    [],
                ):

                    text = str(text).strip()

                    if text:
                        recognized.append(text)

            extraction_ms = self.elapsed_ms(start)

            start = time.perf_counter_ns()

            strict = self.evaluate(
                expected_text,
                recognized,
                self.normalize_strict,
            )

            adjusted = self.evaluate(
                expected_text,
                recognized,
                self.normalize_adjusted,
            )

            literal_match = (
                Counter(expected_text)
                == Counter(recognized)
            )

            validation_ms = self.elapsed_ms(start)

            self._request_count += 1

            return {
                "success": True,

                "scope": (
                    "offline_document_validation"
                ),

                "model": "PP-OCRv6_tiny",

                "preprocessing": preprocessing,

                "request_number": (
                    self._request_count
                ),

                "cold_inference": (
                    self._request_count == 1
                ),

                "recognized_text": recognized,

                "accuracy": {
                    "literal_line_match": (
                        literal_match
                    ),
                    "strict": strict,
                    "adjusted": adjusted,
                },

                "validation_status": (
                    "exact_line_match"
                    if literal_match
                    else "normalized_match"
                    if adjusted["exact_match"]
                    else "review_required"
                ),

                "timings": {
                    "initialization_ms": round(
                        self.initialization_ms, 6
                    ),

                    "queue_ms": round(
                        queue_ms, 6
                    ),

                    "preprocessing_ms": round(
                        preprocessing_ms, 6
                    ),

                    "inference_ms": round(
                        inference_ms, 6
                    ),

                    "extraction_ms": round(
                        extraction_ms, 6
                    ),

                    "validation_ms": round(
                        validation_ms, 6
                    ),

                    "processing_ms": round(
                        self.elapsed_ms(
                            processing_start
                        ),
                        6,
                    ),

                    "total_request_ms": round(
                        self.elapsed_ms(
                            request_start
                        ),
                        6,
                    ),
                },
            }
