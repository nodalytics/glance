
import sys
import json
import time

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


import httpx

from poker_apis.models.poker_state import (
    PokerStateModel
)


BASE_URL = "http://127.0.0.1:8000"

SCREENSHOT_FILE = (
    PROJECT_ROOT
    / "test_images"
    / "ss.jpeg"
)

STATE_OUTPUT = (
    PROJECT_ROOT
    / "test_output"
    / "real_http_api_state.json"
)

REPORT_OUTPUT = (
    PROJECT_ROOT
    / "test_output"
    / "real_http_api_report.json"
)


EXPECTED_TABLE = {
    "small_blind": 2500,
    "big_blind": 5000,
    "pot": 47500,
    "average_stack": 83333,
    "tournament_position": "12 of 18",
    "prize_pool_display": "$5",
    "first_place_prize_display": "$1.12"
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


def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )


def main():

    print("=" * 75)
    print("REAL HTTP API INTEGRATION VALIDATION")
    print("=" * 75)

    start = time.perf_counter()

    results = []

    before = None
    after = None
    state = None
    request_time = None

    def record(name, passed, details=None):

        results.append({
            "test": name,
            "passed": bool(passed),
            "details": details
        })

        status = "PASS" if passed else "FAIL"

        print(f"[{status}] {name}")

        if details is not None and not passed:

            print(f"       {details}")

    try:

        if not SCREENSHOT_FILE.is_file():

            raise FileNotFoundError(
                str(SCREENSHOT_FILE)
            )

        timeout = httpx.Timeout(
            600.0,
            connect=10.0
        )

        with httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            trust_env=False
        ) as client:

            # --------------------------------------
            # SERVER CONNECTIVITY
            # --------------------------------------

            print("\nSERVER CONNECTIVITY")

            response = client.get("/health")

            record(
                "Health endpoint returns 200",
                response.status_code == 200
            )

            response.raise_for_status()

            health = response.json()

            record(
                "Application health is ok",
                health["status"] == "ok"
            )

            record(
                "Offline mode confirmed",
                health["mode"] == "offline"
            )

            record(
                "Service available before request",
                health["busy"] is False
            )

            if health["busy"]:

                raise RuntimeError(
                    "Service is currently busy."
                )

            # --------------------------------------
            # APPLICATION INFORMATION
            # --------------------------------------

            print("\nAPPLICATION INFORMATION")

            response = client.get(
                "/api/v1/info"
            )

            response.raise_for_status()

            info = response.json()

            record(
                "Application name correct",
                info["name"] == "poker-apis"
            )

            record(
                "JPEG format supported",
                ".jpeg" in
                info["supported_image_formats"]
            )

            record(
                "Screenshot within upload limit",
                SCREENSHOT_FILE.stat().st_size
                <= info["max_upload_size_bytes"]
            )

            # --------------------------------------
            # INITIAL SERVICE STATISTICS
            # --------------------------------------

            response = client.get(
                "/api/v1/statistics"
            )

            response.raise_for_status()

            before = response.json()

            print("\nINITIAL SERVICE STATISTICS")

            print(
                json.dumps(
                    before,
                    indent=4
                )
            )

            # --------------------------------------
            # REAL MULTIPART HTTP UPLOAD
            # --------------------------------------

            print("\nREAL SCREENSHOT HTTP UPLOAD")

            print(
                f"Screenshot: "
                f"{SCREENSHOT_FILE.name}"
            )

            print(
                f"File size: "
                f"{SCREENSHOT_FILE.stat().st_size:,}"
                " bytes"
            )

            print(
                "Submitting screenshot to API..."
            )

            print(
                "Processing may take several minutes.",
                flush=True
            )

            request_start = time.perf_counter()

            with SCREENSHOT_FILE.open("rb") as file:

                response = client.post(
                    "/api/v1/analyze/screenshot",
                    files={
                        "file": (
                            SCREENSHOT_FILE.name,
                            file,
                            "image/jpeg"
                        )
                    }
                )

            request_time = round(
                time.perf_counter()
                - request_start,
                4
            )

            record(
                "Screenshot analysis returns 200",
                response.status_code == 200,
                response.text[:1000]
                if response.status_code != 200
                else None
            )

            response.raise_for_status()

            record(
                "JSON content type returned",
                "application/json" in
                response.headers.get(
                    "content-type", ""
                )
            )

            state = PokerStateModel.model_validate(
                response.json()
            )

            record(
                "Response matches Pydantic model",
                isinstance(
                    state,
                    PokerStateModel
                )
            )

            # --------------------------------------
            # TABLE FIELD VALIDATION
            # --------------------------------------

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

            # --------------------------------------
            # CARD IDENTITY VALIDATION
            # --------------------------------------

            print("\nCARD IDENTITY VALIDATION")

            all_cards = (
                state.cards.board_slots
                + state.cards.hero_slots
            )

            cards = {
                card.slot: card
                for card in all_cards
            }

            for slot, expected in (
                EXPECTED_CARDS.items()
            ):

                card = cards.get(slot)

                passed = (
                    card is not None
                    and card.rank == expected[0]
                    and card.suit == expected[1]
                    and card.recognized
                    and card.occupied is True
                )

                record(
                    f"Card identity: {slot}",
                    passed,
                    card.model_dump(mode="json")
                    if card else None
                )

            # --------------------------------------
            # STRUCTURED STATE VALIDATION
            # --------------------------------------

            print("\nSTRUCTURED STATE VALIDATION")

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
                "Five community cards",
                state.game.board_count == 5
            )

            record(
                "Two hero cards",
                state.game.hero_card_count == 2
            )

            record(
                "Seven recognized cards",
                state.game.recognized_card_count == 7
            )

            record(
                "Seven unique slots preserved",
                len(all_cards) == 7
                and len(cards) == 7
            )

            record(
                "State validation passed",
                state.validation.valid
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
                len(state.players) > 0
                and any(
                    player.name is not None
                    and player.stack is not None
                    for player in state.players
                )
            )

            # --------------------------------------
            # RESPONSE METADATA
            # --------------------------------------

            print("\nRESPONSE METADATA VALIDATION")

            metadata = state.metadata

            record(
                "Calibration profile selected",
                metadata.recognition_profile
                == "calibration"
            )

            record(
                "Automatic table extraction used",
                metadata.table_data_origin
                == "screenshot_ocr"
            )

            record(
                "OCR items detected",
                (metadata.ocr_item_count or 0) > 0
            )

            record(
                "Original filename preserved",
                metadata.screenshot is not None
                and metadata.screenshot.filename
                == SCREENSHOT_FILE.name
            )

            record(
                "Screenshot dimensions preserved",
                metadata.screenshot is not None
                and metadata.screenshot.width == 1600
                and metadata.screenshot.height == 899
            )

            record(
                "Processing time recorded",
                (metadata.processing_time_seconds
                 or 0) > 0
            )

            # --------------------------------------
            # JSON SERIALIZATION
            # --------------------------------------

            print("\nJSON SERIALIZATION")

            state_data = state.model_dump(
                mode="json"
            )

            serialized = json.dumps(
                state_data,
                allow_nan=False
            )

            restored = (
                PokerStateModel.model_validate_json(
                    serialized
                )
            )

            record(
                "JSON round trip successful",
                restored == state
            )

            save_json(
                STATE_OUTPUT,
                state_data
            )

            record(
                "HTTP response state saved",
                STATE_OUTPUT.is_file()
            )

            # --------------------------------------
            # FINAL SERVICE STATISTICS
            # --------------------------------------

            print("\nFINAL SERVICE STATISTICS")

            response = client.get(
                "/api/v1/statistics"
            )

            response.raise_for_status()

            after = response.json()

            old = before["statistics"]
            new = after["statistics"]

            record(
                "Pipeline initialized",
                after["pipeline_initialized"]
                is True
            )

            record(
                "Processing lock released",
                after["busy"] is False
            )

            record(
                "Exactly one additional request",
                new["total_requests"]
                == old["total_requests"] + 1
            )

            record(
                "Successful request incremented",
                new["successful_requests"]
                == old["successful_requests"] + 1
            )

            record(
                "No additional processing failures",
                new["failed_requests"]
                == old["failed_requests"]
            )

            record(
                "No additional rejected requests",
                new["rejected_requests"]
                == old["rejected_requests"]
            )

            record(
                "No additional busy requests",
                new["busy_requests"]
                == old["busy_requests"]
            )

    except Exception as exc:

        record(
            "HTTP integration completed",
            False,
            str(exc)
        )

    # ----------------------------------------------
    # FINAL REPORT
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
            state.status if state else None
        ),
        "recognized_cards": (
            state.game.recognized_card_count
            if state else None
        ),
        "http_request_time_seconds": request_time,
        "total_time_seconds": round(
            time.perf_counter() - start,
            4
        ),
        "passed": (
            failed_count == 0
            and len(results) == 50
        )
    }

    report = {
        "summary": summary,
        "statistics_before": before,
        "statistics_after": after,
        "failures": [
            item
            for item in results
            if not item["passed"]
        ],
        "results": results
    }

    save_json(
        REPORT_OUTPUT,
        report
    )

    print("\n" + "=" * 75)

    print("REAL HTTP API INTEGRATION SUMMARY")

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
            after,
            indent=4
        )
    )

    if state is not None:

        print(f"\nState saved: {STATE_OUTPUT}")

    print(f"\nReport saved: {REPORT_OUTPUT}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
