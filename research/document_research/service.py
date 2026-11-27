
import time
import random
import threading

from collections import Counter


class DocumentServiceBusyError(Exception):
    pass


class DocumentResearchService:

    def __init__(self):

        self._engine = None
        self._lock = threading.Lock()
        self._completed_requests = 0

    @staticmethod
    def elapsed_ms(start):

        return (
            time.perf_counter_ns() - start
        ) / 1_000_000

    def get_status(self):

        return {
            "success": True,
            "scope": "synthetic_document_research",
            "initialized": self._engine is not None,
            "busy": self._lock.locked(),
            "completed_requests": (
                self._completed_requests
            ),
            "model": "PP-OCRv6_tiny",
        }

    @staticmethod
    def create_fixture(variant, seed):

        import cv2
        import numpy as np

        rng = random.Random(seed)

        expected = [
            "Warehouse Inspection",
            f"Reference: WX{rng.randint(100000, 999999)}",
            f"Quantity: {rng.randint(10, 9999)}",
            f"Total: {rng.randint(10000, 999999)}",
            f"Batch Number: {rng.randint(10000, 99999)}",
            f"Location: Building {rng.randint(1, 99)}",
            "Department: Logistics",
            "Status: Approved",
        ]

        background = 255
        foreground = 20
        font_scale = 1.3
        thickness = 2
        spacing = 85

        if variant == "small_text":
            font_scale = 0.65
            thickness = 1

        elif variant == "low_contrast":
            background = 205
            foreground = 145

        elif variant == "dark":
            background = 25
            foreground = 235

        elif variant == "dense":

            font_scale = 0.8
            thickness = 1
            spacing = 42

            expected.extend([
                f"Order Number: {rng.randint(100000, 999999)}",
                f"Units Received: {rng.randint(100, 999)}",
                f"Units Remaining: {rng.randint(1, 99)}",
                "Category: Equipment",
                "Delivery: Scheduled",
                "Condition: Acceptable",
                "Review: Completed",
                "Inspector: David",
            ])

        image = np.full(
            (900, 1600, 3),
            background,
            dtype=np.uint8,
        )

        for index, text in enumerate(expected):

            cv2.putText(
                image,
                text,
                (50, 65 + index * spacing),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (
                    foreground,
                    foreground,
                    foreground,
                ),
                thickness,
                cv2.LINE_AA,
            )

        if variant == "noisy":

            noise_rng = np.random.default_rng(seed)

            noise = noise_rng.normal(
                0,
                12,
                image.shape,
            )

            image = np.clip(
                image.astype(np.float32) + noise,
                0,
                255,
            ).astype(np.uint8)

        return image, expected

    def analyze(
        self,
        variant="standard",
        seed=20261127,
        preprocessing="gaussian",
    ):

        request_start = time.perf_counter_ns()

        if not self._lock.acquire(blocking=False):

            raise DocumentServiceBusyError(
                "Document research engine is busy."
            )

        try:

            from document_research.text_normalizer import (
                DocumentTextNormalizer,
            )

            initialized_this_request = False
            initialization_ms = 0.0

            if self._engine is None:

                start = time.perf_counter_ns()

                from document_research.optimized_ocr import (
                    OptimizedDocumentOCR,
                )

                self._engine = OptimizedDocumentOCR()

                initialization_ms = (
                    self.elapsed_ms(start)
                )

                initialized_this_request = True

            start = time.perf_counter_ns()

            image, expected = self.create_fixture(
                variant,
                seed,
            )

            fixture_generation_ms = (
                self.elapsed_ms(start)
            )

            result = self._engine.recognize(
                image,
                expected,
                preprocessing=preprocessing,
            )

            start = time.perf_counter_ns()

            raw = result["recognized_text"]

            formatted = (
                DocumentTextNormalizer.normalize_lines(
                    raw
                )
            )

            normalization_ms = (
                self.elapsed_ms(start)
            )

            start = time.perf_counter_ns()

            expected_counter = Counter(expected)
            formatted_counter = Counter(formatted)

            matched = sum(
                (
                    expected_counter
                    & formatted_counter
                ).values()
            )

            exact_match = (
                expected_counter == formatted_counter
            )

            ordered_match = formatted == expected

            validation = {
                "expected_count": len(expected),

                "recognized_count": len(formatted),

                "matched_count": matched,

                "recall_percent": round(
                    matched / len(expected) * 100,
                    3,
                ),

                "precision_percent": round(
                    matched
                    / max(len(formatted), 1)
                    * 100,
                    3,
                ),

                "exact_match": exact_match,

                "ordered_match": ordered_match,

                "missing_lines": list(
                    (
                        expected_counter
                        - formatted_counter
                    ).elements()
                ),

                "unexpected_lines": list(
                    (
                        formatted_counter
                        - expected_counter
                    ).elements()
                ),
            }

            formatted_validation_ms = (
                self.elapsed_ms(start)
            )

            self._completed_requests += 1

            return {
                "success": True,

                "scope": "synthetic_document_research",

                "measurement_type": "executed_inference",

                "model": result["model"],

                "variant": variant,

                "seed": seed,

                "preprocessing": preprocessing,

                "request_number": (
                    self._completed_requests
                ),

                "initialized_this_request": (
                    initialized_this_request
                ),

                "cold_inference": result["cold_inference"],

                "raw_text": raw,

                "formatted_text": formatted,

                "expected_text": expected,

                "raw_accuracy": result["accuracy"],

                "formatted_accuracy": validation,

                "validation_status": (
                    "passed"
                    if ordered_match
                    else "review_required"
                ),

                "timings": {
                    **result["timings"],

                    "initialization_this_request_ms": round(
                        initialization_ms, 6
                    ),

                    "fixture_generation_ms": round(
                        fixture_generation_ms, 6
                    ),

                    "normalization_ms": round(
                        normalization_ms, 6
                    ),

                    "formatted_validation_ms": round(
                        formatted_validation_ms, 6
                    ),

                    "service_total_ms": round(
                        self.elapsed_ms(request_start),
                        6,
                    ),
                },

                "application_speedup_verified": False,
            }

        finally:

            self._lock.release()


document_service = DocumentResearchService()
