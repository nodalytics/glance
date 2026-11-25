
from poker_apis.vision.ocr import PokerOCR
from poker_apis.vision.text_parser import PokerTextParser
from poker_apis.vision.card_recognition import CardRecognizer
from poker_apis.vision.game_stage import detect_game_stage
from poker_apis.vision.validation import validate_poker_state


class PokerRecognitionService:
    """Coordinates poker image recognition."""

    def __init__(self):
        self.ocr = PokerOCR()
        self.text_parser = PokerTextParser()
        self.card_recognizer = CardRecognizer()

    def analyze(
        self,
        table_image,
        board_regions: dict,
        hole_regions: dict,
        player_regions: dict | None = None,
    ):

        # 1. Extract text.
        ocr_results = self.ocr.extract(table_image)

        # 2. Parse candidate names and amounts.
        text_results = self.text_parser.parse(ocr_results)

        # 3. Recognize community cards.
        board_results = self.card_recognizer.recognize(
            table_image,
            board_regions,
        )

        # 4. Recognize hole cards in the test environment.
        hole_results = self.card_recognizer.recognize(
            table_image,
            hole_regions,
        )

        board_cards = [item.card for item in board_results]
        hole_cards = [item.card for item in hole_results]

        # 5. Detect game stage.
        stage = detect_game_stage(board_cards)

        # 6. Validate available information.
        validation = validate_poker_state(
            board_cards=board_cards,
            hole_cards=hole_cards,
            pot=None,
            players=[],
        )

        return {
            "game": "Texas Hold'em",
            "stage": stage,
            "community_cards": board_cards,
            "hole_cards": hole_cards,
            "board_confidence": [
                item.confidence for item in board_results
            ],
            "hole_confidence": [
                item.confidence for item in hole_results
            ],
            "text": {
                "names": [
                    item.value
                    for item in text_results["candidate_names"]
                ],
                "amounts": [
                    item.value
                    for item in text_results["candidate_amounts"]
                ],
                "other": [
                    item.value
                    for item in text_results["other_text"]
                ],
            },
            "ocr_results": [
                {
                    "text": item.text,
                    "confidence": item.confidence,
                    "x": item.x,
                    "y": item.y,
                    "width": item.width,
                    "height": item.height,
                }
                for item in ocr_results
            ],
            "validation": {
                "valid": validation.valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
        }
