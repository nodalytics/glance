
import sys
import json
import time
import tempfile

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from poker_apis.core.config import get_settings

from poker_apis.models.poker_state import (
    PokerStateModel
)

from poker_apis.services.processing_service import (
    OfflineProcessingService,
    ProcessingServiceError
)


# --------------------------------------------------
# TEST PATHS
# --------------------------------------------------

SCREENSHOT_FILE = (
    PROJECT_ROOT
    / "test_images"
    / "ss.jpeg"
)

OUTPUT_DIR = PROJECT_ROOT / "test_output"

STATE_OUTPUT_FILE = (
    OUTPUT_DIR
    / "real_processing_service_state.json"
)

REPORT_OUTPUT_FILE = (
    OUTPUT_DIR
    / "real_processing_service_report.json"
)


# --------------------------------------------------
# EXPECTED CALIBRATION RESULTS
# --------------------------------------------------

EXPECTED_TABLE = {
    "small_blind": 2500,
    "big_blind": 5000,
    "pot": 47500,
    "average_stack": 83333,
    "tournament_position": "12 of 18"
}


EXPECTED_CARDS = {
    "board_1": ("A", "hearts"),
    "board_2": ("8", "spades"),
    "board_3": ("J", "hearts"),
    "board_4": ("J", "diamonds"),
    "board_5": ("2", "hearts"),
    "hero_card_1": ("Q", "clubs"),
    "hero_card_2": ("10", "clubs")
}


# --------------------------------------------------
# MAIN TEST RUNNER
# --------------------------------------------------

def main():

    print("=" * 75)

    print("REAL OFFLINE PROCESSING SERVICE INTEGRATION")

    print("=" * 75)

    start = time.perf_counter()

    results = []

    state = None

    statistics = {}

    processing_time = None

    def record(name, passed, details=None):

        results.append({
            "test": name,
            "passed": bool(passed),
            "details": details
        })

        status = "PASS" if passed else "FAIL"

        print(f"[{status}] {name}")

        if details and not passed:

            print(f"       {details}")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # ----------------------------------------------
    # CHECK SCREENSHOT
    # ----------------------------------------------

    if not SCREENSHOT_FILE.is_file():

        print(
            f"Screenshot not found: "
            f"{SCREENSHOT_FILE}"
        )

        return 1

    content = SCREENSHOT_FILE.read_bytes()

    print(
        f"\nScreenshot: {SCREENSHOT_FILE.name}"
    )

    print(
        f"File size: {len(content):,} bytes"
    )

    settings = get_settings()

    # ----------------------------------------------
    # INITIALIZE REAL SERVICE
    # ----------------------------------------------

    service = OfflineProcessingService(
        settings=settings
    )

    existing_temp_files = set(
        settings.temp_upload_dir.iterdir()
    )

    print("\nSERVICE INITIALIZATION")

    record(
        "Pipeline initialization is lazy",
        not service.pipeline_initialized
    )

    record(
        "Service initially available",
        not service.is_busy
    )

    # ----------------------------------------------
    # VALIDATE UPLOAD
    # ----------------------------------------------

    print("\nREAL UPLOAD VALIDATION")

    try:

        upload_info = service.validate_upload(
            SCREENSHOT_FILE.name,
            content
        )

        record(
            "Real screenshot upload accepted",
            upload_info["format"] == "JPEG"
        )

        record(
            "Calibrated dimensions detected",
            (
                upload_info["width"],
                upload_info["height"]
            ) == (1600, 899)
        )

        record(
            "Upload validation remains lazy",
            not service.pipeline_initialized
        )

        print(
            json.dumps(
                upload_info,
                indent=4
            )
        )

        # ------------------------------------------
        # REAL OCR PROCESSING
        # ------------------------------------------

        print("\nREAL SCREENSHOT PROCESSING")

        print(
            "Initializing the real OCR pipeline..."
        )

        print(
            "Processing may take several minutes."
        )

        processing_start = time.perf_counter()

        state = service.analyze_screenshot(
            filename=SCREENSHOT_FILE.name,
            content=content
        )

        processing_time = round(
            time.perf_counter()
            - processing_start,
            4
        )

        record(
            "Real pipeline initialized",
            service.pipeline_initialized
        )

        record(
            "Pydantic state returned",
            isinstance(state, PokerStateModel)
        )

        # ------------------------------------------
        # TABLE FIELD VALIDATION
        # ------------------------------------------

        print("\nTABLE FIELD VALIDATION")

        for field, expected in (
            EXPECTED_TABLE.items()
        ):

            actual = getattr(
                state.table,
                field
            )

            record(
                f"Table field: {field}",
                actual == expected,
                {
                    "expected": expected,
                    "actual": actual
                }
            )

        # ------------------------------------------
        # CARD IDENTITY VALIDATION
        # ------------------------------------------

        print("\nCARD IDENTITY VALIDATION")

        all_cards = (
            state.cards.board_slots
            + state.cards.hero_slots
        )

        cards_by_slot = {
            card.slot: card
            for card in all_cards
        }

        for slot, expected in (
            EXPECTED_CARDS.items()
        ):

            card = cards_by_slot.get(slot)

            if card is None:

                record(
                    f"Card: {slot}",
                    False,
                    "Card slot missing."
                )

                continue

            expected_rank, expected_suit = (
                expected
            )

            passed = (
                card.rank == expected_rank
                and card.suit == expected_suit
                and card.recognized is True
                and card.occupied is True
            )

            record(
                f"Card: {slot}",
                passed,
                {
                    "expected": {
                        "rank": expected_rank,
                        "suit": expected_suit
                    },
                    "actual": {
                        "rank": card.rank,
                        "suit": card.suit
                    }
                }
            )

        # ------------------------------------------
        # STATE VALIDATION
        # ------------------------------------------

        print("\nSTATE VALIDATION")

        record(
            "State status is valid",
            state.status == "valid"
        )

        record(
            "Offline screenshot source",
            state.source == "offline_screenshot"
        )

        record(
            "River street detected",
            state.game.street == "river"
        )

        record(
            "Five community cards detected",
            state.game.board_count == 5
        )

        record(
            "Two hero cards detected",
            state.game.hero_card_count == 2
        )

        record(
            "Seven recognized cards",
            state.game.recognized_card_count == 7
        )

        record(
            "Seven unique card slots preserved",
            len(all_cards) == 7
            and len(cards_by_slot) == 7
        )

        record(
            "Overall state validation passed",
            state.validation.valid is True
        )

        record(
            "No validation errors",
            state.validation.error_count == 0
        )

        record(
            "No duplicate cards",
            state.validation.card_validation
            .duplicate_count == 0
        )

        record(
            "Player information detected",
            any(
                player.name is not None
                and player.stack is not None
                for player in state.players
            )
        )

        # ------------------------------------------
        # METADATA VALIDATION
        # ------------------------------------------

        print("\nSERVICE METADATA VALIDATION")

        record(
            "Calibration profile selected",
            state.metadata.recognition_profile
            == "calibration"
        )

        record(
            "Automatic table extraction used",
            state.metadata.table_data_origin
            == "screenshot_ocr"
        )

        record(
            "OCR items detected",
            (
                state.metadata.ocr_item_count
                or 0
            ) > 0
        )

        record(
            "Original filename preserved",
            state.metadata.screenshot.filename
            == SCREENSHOT_FILE.name
        )

        record(
            "Upload metadata preserved",
            state.metadata.upload["format"]
            == "JPEG"
            and state.metadata.upload[
                "file_size_bytes"
            ] == len(content)
        )

        record(
            "Service processing time recorded",
            state.metadata.service_processing_seconds
            > 0
        )

        # ------------------------------------------
        # JSON SERIALIZATION
        # ------------------------------------------

        print("\nJSON SERIALIZATION")

        serialized = state.model_dump(
            mode="json"
        )

        json_text = json.dumps(
            serialized,
            indent=4,
            allow_nan=False
        )

        restored = PokerStateModel.model_validate(
            json.loads(json_text)
        )

        record(
            "JSON serialization and round trip",
            restored.game.recognized_card_count
            == 7
        )

        STATE_OUTPUT_FILE.write_text(
            json_text,
            encoding="utf-8"
        )

        record(
            "Structured state saved",
            STATE_OUTPUT_FILE.is_file()
        )

    except ProcessingServiceError as exc:

        record(
            "Real service processing completed",
            False,
            exc.to_dict()
        )

    except Exception as exc:

        record(
            "Real integration completed",
            False,
            str(exc)
        )

    # ----------------------------------------------
    # CLEANUP AND STATISTICS
    # ----------------------------------------------

    print("\nCLEANUP AND STATISTICS")

    current_temp_files = set(
        settings.temp_upload_dir.iterdir()
    )

    record(
        "No new temporary files remain",
        not (
            current_temp_files
            - existing_temp_files
        )
    )

    record(
        "Processing lock released",
        not service.is_busy
    )

    statistics = service.get_statistics()

    record(
        "Exactly one request processed",
        statistics["total_requests"] == 1
    )

    record(
        "Successful request recorded",
        statistics["successful_requests"] == 1
    )

    record(
        "No failed requests",
        statistics["failed_requests"] == 0
    )

    record(
        "No rejected or busy requests",
        statistics["rejected_requests"] == 0
        and statistics["busy_requests"] == 0
    )

    # ----------------------------------------------
    # FINAL SUMMARY
    # ----------------------------------------------

    passed_count = sum(
        item["passed"]
        for item in results
    )

    failed_count = (
        len(results) - passed_count
    )

    summary = {
        "total_tests": len(results),
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "state_status": (
            state.status
            if state is not None
            else None
        ),
        "recognized_cards": (
            state.game.recognized_card_count
            if state is not None
            else 0
        ),
        "processing_time_seconds": (
            processing_time
        ),
        "total_time_seconds": round(
            time.perf_counter() - start,
            4
        ),
        "passed": failed_count == 0
    }

    report = {
        "summary": summary,
        "service_statistics": statistics,
        "failures": [
            item
            for item in results
            if not item["passed"]
        ],
        "results": results
    }

    REPORT_OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)

    print("REAL SERVICE INTEGRATION SUMMARY")

    print("=" * 75)

    print(
        json.dumps(
            summary,
            indent=4
        )
    )

    print("\nSERVICE STATISTICS")

    print(
        json.dumps(
            statistics,
            indent=4
        )
    )

    if state is not None:

        print(
            f"\nState saved: "
            f"{STATE_OUTPUT_FILE}"
        )

    print(
        f"\nReport saved: "
        f"{REPORT_OUTPUT_FILE}"
    )

    if summary["passed"]:

        print(
            "\nFINAL RESULT: ALL TESTS PASSED"
        )

        return 0

    print(
        "\nFINAL RESULT: INTEGRATION FAILED"
    )

    return 1


if __name__ == "__main__":

    sys.exit(main())
