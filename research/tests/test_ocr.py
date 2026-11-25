
import json
from pathlib import Path

from poker_apis.capture.screenshot import ScreenshotCapture
from poker_apis.vision.ocr import PokerOCR
from poker_apis.vision.preprocessing import ImagePreprocessor


def main():
    image_path = "test_images/ss.jpeg"

    capture = ScreenshotCapture()
    image = capture.load_image(image_path)

    processor = ImagePreprocessor()
    processed = processor.process(image)

    ocr = PokerOCR()

    # Start with enhanced image.
    results = ocr.extract(processed["enhanced"])

    print("\nOCR RESULTS\n")

    for item in results:
        print(
            f"Text: {item.text} | "
            f"Confidence: {item.confidence:.3f} | "
            f"Position: ({item.x}, {item.y})"
        )

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "ocr_results.json"
    filtered_results = ocr.filter_results(results)
    print("\nHIGH CONFIDENCE DETECTIONS:")
    for item in filtered_results["accepted"]:
        print(item.text, item.confidence)

    print("\nUNCERTAIN DETECTIONS:")
    for item in filtered_results["uncertain"]:
        print(item.text, item.confidence)

    data = [
        {
            "text": item.text,
            "confidence": item.confidence,
            "x": item.x,
            "y": item.y,
            "width": item.width,
            "height": item.height,
        }
        for item in results
    ]

    output_file.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )

    print(f"\nOCR results saved to: {output_file}")


if __name__ == "__main__":
    main()
