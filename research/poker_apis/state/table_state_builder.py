
from copy import deepcopy
from datetime import datetime, timezone

from poker_apis.validation.card_state_validator import (
    CardStateValidator
)


class TableStateBuilder:
    """
    Builds structured table-state JSON from saved
    offline screenshots and local simulator data.

    Does not perform OCR or interact with a poker client.
    """

    SCHEMA_VERSION = "1.0.0"

    SUPPORTED_SOURCES = {
        "offline_simulator",
        "offline_screenshot"
    }

    TABLE_FIELDS = [
        "small_blind",
        "big_blind",
        "pot",
        "prize_pool_display",
        "first_place_prize_display",
        "average_stack",
        "tournament_position"
    ]

    def __init__(self):

        self.card_validator = CardStateValidator()

    # --------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------

    def create_timestamp(self):

        return datetime.now(
            timezone.utc
        ).isoformat()

    # --------------------------------------------------
    # BUILD TABLE INFORMATION
    # --------------------------------------------------

    def build_table(self, table_data):

        return {
            field: deepcopy(
                table_data.get(field)
            )
            for field in self.TABLE_FIELDS
        }

    # --------------------------------------------------
    # BUILD PLAYER INFORMATION
    # --------------------------------------------------

    def build_players(self, table_data):

        players = table_data.get("players", [])

        if not isinstance(players, list):

            raise TypeError(
                "Players must be a list."
            )

        return deepcopy(players)

    # --------------------------------------------------
    # BUILD INDIVIDUAL CARD
    # --------------------------------------------------

    def build_card(self, slot, card):

        if not isinstance(card, dict):

            return {
                "slot": slot,
                "rank": None,
                "suit": None,
                "recognized": False,
                "occupied": None,
                "occupancy_state": "unknown"
            }

        occupied = (
            self.card_validator.get_occupancy(card)
        )

        occupancy_state = {
            True: "occupied",
            False: "empty",
            None: "unknown"
        }[occupied]

        return {
            "slot": slot,

            "rank": card.get("rank"),

            "suit": card.get("suit"),

            "rank_confidence": card.get(
                "rank_confidence"
            ),

            "suit_confidence": card.get(
                "suit_confidence"
            ),

            "suit_margin": card.get(
                "suit_margin"
            ),

            "recognized": (
                card.get("recognized") is True
            ),

            "occupied": occupied,

            "occupancy_state": occupancy_state,

            "ocr_skipped": card.get(
                "ocr_skipped"
            )
        }

    # --------------------------------------------------
    # BUILD CARD COLLECTION
    # --------------------------------------------------

    def build_cards(self, recognized_cards):

        board_slots = []

        hero_slots = []

        for slot in self.card_validator.BOARD_SLOTS:

            board_slots.append(
                self.build_card(
                    slot,
                    recognized_cards.get(slot)
                )
            )

        for slot in self.card_validator.HERO_SLOTS:

            hero_slots.append(
                self.build_card(
                    slot,
                    recognized_cards.get(slot)
                )
            )

        community = [
            card
            for card in board_slots
            if card["occupied"] is True
        ]

        hero = [
            card
            for card in hero_slots
            if card["occupied"] is True
        ]

        return {
            "community": community,
            "hero": hero,
            "board_slots": board_slots,
            "hero_slots": hero_slots
        }

    # --------------------------------------------------
    # VALIDATE TABLE INFORMATION
    # --------------------------------------------------

    def validate_table(self, table):

        errors = []

        warnings = []

        numeric_fields = [
            "small_blind",
            "big_blind",
            "pot",
            "average_stack"
        ]

        for field in numeric_fields:

            value = table.get(field)

            if value is None:

                warnings.append({
                    "code": "MISSING_TABLE_FIELD",
                    "field": field,
                    "message": (
                        f"Table field unavailable: {field}"
                    )
                })

                continue

            if (
                type(value) is not int
                or value < 0
            ):

                errors.append({
                    "code": "INVALID_TABLE_VALUE",
                    "field": field,
                    "message": (
                        f"{field} must be a "
                        "non-negative integer."
                    )
                })

        small_blind = table.get("small_blind")
        big_blind = table.get("big_blind")

        for field in ["small_blind", "big_blind"]:

            value = table.get(field)

            if type(value) is int and value == 0:

                errors.append({
                    "code": "INVALID_BLIND",
                    "field": field,
                    "message": (
                        f"{field} must be positive."
                    )
                })

        if (
            type(small_blind) is int
            and type(big_blind) is int
            and small_blind > big_blind
        ):

            errors.append({
                "code": "INVALID_BLIND_ORDER",
                "message": (
                    "Small blind cannot exceed big blind."
                )
            })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    # --------------------------------------------------
    # BUILD COMPLETE TABLE STATE
    # --------------------------------------------------

    def build(
        self,
        table_data,
        recognized_cards,
        source="offline_simulator",
        recognition_profile=None,
        processing_time_seconds=None
    ):

        if not isinstance(table_data, dict):

            raise TypeError(
                "Table data must be a dictionary."
            )

        if not isinstance(recognized_cards, dict):

            raise TypeError(
                "Recognized cards must be a dictionary."
            )

        if source not in self.SUPPORTED_SOURCES:

            raise ValueError(
                f"Unsupported source: {source}"
            )

        table = self.build_table(
            table_data
        )

        players = self.build_players(
            table_data
        )

        cards = self.build_cards(
            recognized_cards
        )

        card_validation = (
            self.card_validator.validate(
                recognized_cards
            )
        )

        table_validation = (
            self.validate_table(table)
        )

        errors = (
            card_validation["errors"]
            + table_validation["errors"]
        )

        warnings = (
            card_validation["warnings"]
            + table_validation["warnings"]
        )

        valid = (
            card_validation["valid"]
            and table_validation["valid"]
        )

        if not valid:

            status = "invalid"

        elif warnings:

            status = "partial"

        else:

            status = "valid"

        return {
            "schema_version": self.SCHEMA_VERSION,

            "timestamp_utc": self.create_timestamp(),

            "source": source,

            "status": status,

            "table": table,

            "game": {
                "variant": "texas_holdem",

                "street": card_validation["street"],

                "board_count": (
                    card_validation["board_count"]
                ),

                "hero_card_count": (
                    card_validation["hero_count"]
                ),

                "occupied_count": (
                    card_validation["occupied_count"]
                ),

                "recognized_card_count": (
                    card_validation["recognized_cards"]
                )
            },

            "cards": cards,

            "players": players,

            "validation": {
                "valid": valid,

                "error_count": len(errors),

                "warning_count": len(warnings),

                "errors": errors,

                "warnings": warnings,

                "card_validation": card_validation,

                "table_validation": table_validation
            },

            "metadata": {
                "recognition_profile": (
                    recognition_profile
                ),

                "processing_time_seconds": (
                    processing_time_seconds
                ),

                "player_count": len(players)
            }
        }
