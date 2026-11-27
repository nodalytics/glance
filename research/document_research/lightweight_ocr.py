from paddleocr import PaddleOCR


class LightweightOCR:
    """Lightweight OCR for offline document research."""

    def __init__(self):
        self.engine = PaddleOCR(
            text_detection_model_name="PP-OCRv6_tiny_det",
            text_recognition_model_name="PP-OCRv6_tiny_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )

    def extract(self, image):
        return list(self.engine.predict(image))