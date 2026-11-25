
import sys
import json
import time

from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))


from pydantic import ValidationError

from poker_apis.models.poker_state import (
    CardModel,
    PlayerModel,
    PokerStateModel,
    HealthResponseModel,
    ApplicationInfoModel,
    ErrorResponseModel
)


OUTPUT_DIR = PROJECT_ROOT / "test_output"

OUTPUT_FILE = (
    OUTPUT_DIR / "api_models_validation_report.json"
)

SCREENSHOT_STATE_FILE = (
    OUTPUT_DIR / "screenshot_table_state.json"
)

SAMPLE_STATE_FILE = (
    OUTPUT_DIR / "sample_table_state.json"
)

OFFLINE_PIPELINE_DIR = (
    OUTPUT_DIR / "offline_pipeline"
)


def load_json(path):

    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def main():

    print("=" * 75)

    print("PYDANTIC API MODEL VALIDATION")

    print("=" * 75)

    start = time.perf_counter()

    results = []

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

    def expect_rejection(name, model, data):

        try:

            model.model_validate(data)

        except ValidationError:

            record(name, True)

        except Exception as exc:

            record(
                name,
                False,
                str(exc)
            )

        else:

            record(
                name,
                False,
                "Invalid input was accepted."
            )

    def validate_state_file(path):

        try:

            data = load_json(path)

            model = PokerStateModel.model_validate(
                data
            )

            serialized = model.model_dump(
                mode="json"
            )

            json.dumps(
                serialized,
                allow_nan=False
            )

            PokerStateModel.model_validate(
                serialized
            )

            record(
                f"State compatibility: {path.name}",
                True
            )

            return data

        except Exception as exc:

            record(
                f"State compatibility: {path.name}",
                False,
                str(exc)
            )

            return None

    # ----------------------------------------------
    # EXISTING STATE COMPATIBILITY
    # ----------------------------------------------

    print("\nEXISTING STATE COMPATIBILITY")

    screenshot_data = validate_state_file(
        SCREENSHOT_STATE_FILE
    )

    validate_state_file(
        SAMPLE_STATE_FILE
    )

    pipeline_files = sorted(
        OFFLINE_PIPELINE_DIR.glob("*.json")
    )

    record(
        "Five offline pipeline states available",
        len(pipeline_files) == 5,
        f"Found {len(pipeline_files)} files."
    )

    for path in pipeline_files:

        validate_state_file(path)

    # ----------------------------------------------
    # VALID CARD
    # ----------------------------------------------

    print("\nCARD MODEL TESTS")

    valid_card = {
        "slot": "hero_card_1",
        "rank": "Q",
        "suit": "clubs",
        "rank_confidence": 0.999,
        "suit_confidence": 0.98,
        "suit_margin": 0.10,
        "recognized": True,
        "occupied": True,
        "occupancy_state": "occupied",
        "ocr_skipped": False
    }

    try:

        card = CardModel.model_validate(
            valid_card
        )

        record(
            "Valid card accepted",
            card.rank == "Q"
            and card.suit == "clubs"
        )

    except Exception as exc:

        record(
            "Valid card accepted",
            False,
            str(exc)
        )

    # ----------------------------------------------
    # INVALID CARD INPUTS
    # ----------------------------------------------

    invalid_card = deepcopy(valid_card)

    invalid_card["rank"] = "Z"

    expect_rejection(
        "Invalid rank rejected",
        CardModel,
        invalid_card
    )

    invalid_card = deepcopy(valid_card)

    invalid_card["suit"] = "purple"

    expect_rejection(
        "Invalid suit rejected",
        CardModel,
        invalid_card
    )

    invalid_card = deepcopy(valid_card)

    invalid_card["rank_confidence"] = 1.5

    expect_rejection(
        "Confidence above 1 rejected",
        CardModel,
        invalid_card
    )

    invalid_card = deepcopy(valid_card)

    invalid_card["suit_confidence"] = -0.5

    expect_rejection(
        "Negative confidence rejected",
        CardModel,
        invalid_card
    )

    invalid_card = deepcopy(valid_card)

    invalid_card["rank_confidence"] = float("nan")

    expect_rejection(
        "NaN confidence rejected",
        CardModel,
        invalid_card
    )

    # ----------------------------------------------
    # EMPTY CARD SLOT
    # ----------------------------------------------

    try:

        empty_card = CardModel.model_validate({
            "slot": "board_1",
            "rank": None,
            "suit": None,
            "recognized": False,
            "occupied": False,
            "occupancy_state": "empty",
            "ocr_skipped": True
        })

        record(
            "Empty card slot accepted",
            empty_card.occupied is False
            and empty_card.rank is None
        )

    except Exception as exc:

        record(
            "Empty card slot accepted",
            False,
            str(exc)
        )

    # ----------------------------------------------
    # PLAYER MODEL TESTS
    # ----------------------------------------------

    print("\nPLAYER MODEL TESTS")

    try:

        player = PlayerModel.model_validate({
            "seat": "top",
            "name": "SimulatorPlayer",
            "stack": 50000,
            "stack_confidence": 0.99
        })

        record(
            "Valid player accepted",
            player.stack == 50000
        )

    except Exception as exc:

        record(
            "Valid player accepted",
            False,
            str(exc)
        )

    expect_rejection(
        "Negative player stack rejected",
        PlayerModel,
        {
            "seat": "top",
            "stack": -50000
        }
    )

    expect_rejection(
        "Fractional player stack rejected",
        PlayerModel,
        {
            "seat": "top",
            "stack": 50000.5
        }
    )

    # ----------------------------------------------
    # COMPLETE STATE TESTS
    # ----------------------------------------------

    print("\nCOMPLETE STATE TESTS")

    if screenshot_data is not None:

        invalid_state = deepcopy(
            screenshot_data
        )

        invalid_state["status"] = "unsupported"

        expect_rejection(
            "Invalid state status rejected",
            PokerStateModel,
            invalid_state
        )

        invalid_state = deepcopy(
            screenshot_data
        )

        invalid_state["table"]["pot"] = -100

        expect_rejection(
            "Negative pot rejected",
            PokerStateModel,
            invalid_state
        )

        invalid_state = deepcopy(
            screenshot_data
        )

        invalid_state.pop("cards", None)

        expect_rejection(
            "Missing required cards rejected",
            PokerStateModel,
            invalid_state
        )

        invalid_state = deepcopy(
            screenshot_data
        )

        invalid_state["source"] = "live_capture"

        expect_rejection(
            "Unsupported source rejected",
            PokerStateModel,
            invalid_state
        )

        try:

            model = PokerStateModel.model_validate(
                screenshot_data
            )

            schema = model.model_json_schema()

            record(
                "JSON schema generated",
                "properties" in schema
                and "$defs" in schema
            )

        except Exception as exc:

            record(
                "JSON schema generated",
                False,
                str(exc)
            )

    else:

        record(
            "Complete state tests available",
            False,
            "Screenshot state could not be loaded."
        )

    # ----------------------------------------------
    # API RESPONSE MODELS
    # ----------------------------------------------

    print("\nAPI RESPONSE MODEL TESTS")

    try:

        health = HealthResponseModel()

        record(
            "Health response model",
            health.status == "ok"
            and health.mode == "offline"
        )

    except Exception as exc:

        record(
            "Health response model",
            False,
            str(exc)
        )

    try:

        info = ApplicationInfoModel(
            name="poker-apis",
            version="1.0.0",
            description="Offline screenshot analysis",
            supported_image_formats=[
                ".png",
                ".jpg",
                ".jpeg",
                ".bmp"
            ],
            max_upload_size_bytes=10485760
        )

        record(
            "Application information model",
            info.mode == "offline"
        )

    except Exception as exc:

        record(
            "Application information model",
            False,
            str(exc)
        )

    try:

        error = ErrorResponseModel.model_validate({
            "success": False,
            "error": {
                "code": "INVALID_IMAGE",
                "message": "Image could not be loaded."
            }
        })

        record(
            "Structured error response model",
            error.success is False
            and error.error.code == "INVALID_IMAGE"
        )

    except Exception as exc:

        record(
            "Structured error response model",
            False,
            str(exc)
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
        "total_time_seconds": round(
            time.perf_counter() - start,
            4
        ),
        "passed": failed_count == 0
    }

    report = {
        "summary": summary,
        "failures": [
            item for item in results
            if not item["passed"]
        ],
        "results": results
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=4,
            allow_nan=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 75)

    print("API MODEL VALIDATION SUMMARY")

    print("=" * 75)

    print(json.dumps(summary, indent=4))

    print(f"\nReport saved: {OUTPUT_FILE}")

    if summary["passed"]:

        print("\nFINAL RESULT: ALL TESTS PASSED")

        return 0

    print("\nFINAL RESULT: VALIDATION FAILED")

    return 1


if __name__ == "__main__":

    sys.exit(main())
