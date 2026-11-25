
from collections import defaultdict


class CardStateValidator:
    """
    Validates recognized card states from saved
    offline images and local simulator datasets.

    Does not perform OCR or modify recognized cards.
    """

    VALID_RANKS = {
        "A", "K", "Q", "J", "10",
        "9", "8", "7", "6",
        "5", "4", "3", "2"
    }

    VALID_SUITS = {
        "hearts",
        "diamonds",
        "clubs",
        "spades"
    }

    BOARD_SLOTS = [
        "board_1",
        "board_2",
        "board_3",
        "board_4",
        "board_5"
    ]

    HERO_SLOTS = [
        "hero_card_1",
        "hero_card_2"
    ]

    STREET_MAPPING = {
        0: "preflop",
        3: "flop",
        4: "turn",
        5: "river"
    }

    # --------------------------------------------------
    # CREATE VALIDATION ISSUE
    # --------------------------------------------------

    def create_issue(
        self,
        code,
        message,
        slots=None
    ):

        return {
            "code": code,
            "message": message,
            "slots": slots or []
        }

    # --------------------------------------------------
    # GET OCCUPANCY
    # --------------------------------------------------

    def get_occupancy(self, card):

        if "occupied" in card:

            value = card["occupied"]

            if value is True:
                return True

            if value is False:
                return False

            return None

        if card.get("recognized") is True:
            return True

        return None

    # --------------------------------------------------
    # VALIDATE INDIVIDUAL SLOT
    # --------------------------------------------------

    def validate_slot(
        self,
        slot,
        card,
        errors
    ):

        if not isinstance(card, dict):

            errors.append(
                self.create_issue(
                    "INVALID_SLOT",
                    f"{slot} must contain a dictionary.",
                    [slot]
                )
            )

            return None

        occupied = self.get_occupancy(card)

        recognized = (
            card.get("recognized") is True
        )

        rank = card.get("rank")
        suit = card.get("suit")

        if occupied is None:

            errors.append(
                self.create_issue(
                    "UNKNOWN_OCCUPANCY",
                    f"Occupancy is unknown for {slot}.",
                    [slot]
                )
            )

        if occupied is False:

            if (
                recognized
                or rank is not None
                or suit is not None
            ):

                errors.append(
                    self.create_issue(
                        "INCONSISTENT_EMPTY_SLOT",
                        f"{slot} is empty but contains card data.",
                        [slot]
                    )
                )

            return None

        if not recognized:

            if occupied is True:

                errors.append(
                    self.create_issue(
                        "UNRECOGNIZED_CARD",
                        f"Occupied card could not be recognized: {slot}.",
                        [slot]
                    )
                )

            return None

        valid_rank = (
            isinstance(rank, str)
            and rank in self.VALID_RANKS
        )

        valid_suit = (
            isinstance(suit, str)
            and suit in self.VALID_SUITS
        )

        if not valid_rank:

            errors.append(
                self.create_issue(
                    "INVALID_RANK",
                    f"Invalid rank in {slot}: {rank}",
                    [slot]
                )
            )

        if not valid_suit:

            errors.append(
                self.create_issue(
                    "INVALID_SUIT",
                    f"Invalid suit in {slot}: {suit}",
                    [slot]
                )
            )

        if not valid_rank or not valid_suit:
            return None

        return rank, suit

    # --------------------------------------------------
    # VALIDATE COMPLETE CARD STATE
    # --------------------------------------------------

    def validate(self, cards):

        if not isinstance(cards, dict):

            raise TypeError(
                "Cards must be a dictionary."
            )

        errors = []
        warnings = []

        expected_slots = (
            self.BOARD_SLOTS
            + self.HERO_SLOTS
        )

        card_locations = defaultdict(list)

        occupancy = {}

        recognized_cards = 0

        # Validate required slots.

        for slot in expected_slots:

            if slot not in cards:

                errors.append(
                    self.create_issue(
                        "MISSING_SLOT",
                        f"Required slot missing: {slot}",
                        [slot]
                    )
                )

                occupancy[slot] = None

                continue

            card = cards[slot]

            occupancy[slot] = (
                self.get_occupancy(card)
                if isinstance(card, dict)
                else None
            )

            identity = self.validate_slot(
                slot,
                card,
                errors
            )

            if identity is not None:

                card_locations[identity].append(
                    slot
                )

                recognized_cards += 1

        # Detect unexpected slots.

        for slot in cards:

            if slot not in expected_slots:

                errors.append(
                    self.create_issue(
                        "UNEXPECTED_SLOT",
                        f"Unexpected card slot: {slot}",
                        [slot]
                    )
                )

        # Detect duplicate card identities.

        duplicates = []

        for identity, slots in (
            card_locations.items()
        ):

            if len(slots) <= 1:
                continue

            rank, suit = identity

            duplicates.append({
                "rank": rank,
                "suit": suit,
                "slots": slots
            })

            errors.append(
                self.create_issue(
                    "DUPLICATE_CARD",
                    f"Duplicate card detected: {rank} of {suit}",
                    slots
                )
            )

        # Validate community card count.

        board_count = sum(
            occupancy[slot] is True
            for slot in self.BOARD_SLOTS
        )

        unknown_board_slots = [
            slot
            for slot in self.BOARD_SLOTS
            if occupancy[slot] is None
        ]

        street = None

        if not unknown_board_slots:

            street = self.STREET_MAPPING.get(
                board_count
            )

            if street is None:

                errors.append(
                    self.create_issue(
                        "INVALID_BOARD_COUNT",
                        f"Invalid community card count: {board_count}",
                        self.BOARD_SLOTS
                    )
                )

        # Detect gaps between community cards.

        empty_seen = False

        for slot in self.BOARD_SLOTS:

            state = occupancy[slot]

            if state is False:

                empty_seen = True

            elif state is True and empty_seen:

                errors.append(
                    self.create_issue(
                        "BOARD_GAP",
                        f"Occupied board slot after an empty slot: {slot}",
                        [slot]
                    )
                )

        # Validate hero card count.

        hero_count = sum(
            occupancy[slot] is True
            for slot in self.HERO_SLOTS
        )

        if hero_count != 2:

            errors.append(
                self.create_issue(
                    "INVALID_HERO_COUNT",
                    f"Expected 2 hero cards, found {hero_count}.",
                    self.HERO_SLOTS
                )
            )

        occupied_count = sum(
            state is True
            for state in occupancy.values()
        )

        empty_count = sum(
            state is False
            for state in occupancy.values()
        )

        unknown_count = sum(
            state is None
            for state in occupancy.values()
        )

        return {
            "valid": len(errors) == 0,
            "street": street,
            "board_count": board_count,
            "hero_count": hero_count,
            "occupied_count": occupied_count,
            "empty_count": empty_count,
            "unknown_count": unknown_count,
            "recognized_cards": recognized_cards,
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings
        }
