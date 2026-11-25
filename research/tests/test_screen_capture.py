
from pathlib import Path

from poker_apis.capture.screenshot import ScreenshotCapture
from poker_apis.capture.region import TableRegion
from poker_apis.vision.preprocessing import ImagePreprocessor


def main():
    # Use a screenshot from an authorized test environment.
    image_path = "test_images/ss.jpeg"

    capture = ScreenshotCapture()

    # Load screenshot.
    image = capture.load_image(image_path)

    print("Original resolution:", image.shape)

    # Define the table region.
    region = TableRegion(
        x=0.10,
        y=0.10,
        width=0.80,
        height=0.80
    )

    table_image = region.crop(image)

    print("Table region:", table_image.shape)

    # Process image.
    processor = ImagePreprocessor()
    results = processor.process(table_image)

    # Save outputs.
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    for name, processed_image in results.items():
        output_path = output_dir / f"{name}.png"

        ScreenshotCapture.save_image(
            processed_image,
            str(output_path)
        )

        print(f"Saved: {output_path}")

    print("Screen capture pipeline completed!")


if __name__ == "__main__":
    main()
