
def detect_game_stage(board_cards: list) -> str:
    """
    Determine Texas Hold'em stage from recognized
    community-card slots.

    Unknown or uncertain cards must not be counted.
    """

    recognized = [
        card for card in board_cards
        if card is not None
    ]

    count = len(recognized)

    stages = {
        0: "preflop",
        3: "flop",
        4: "turn",
        5: "river",
    }

    return stages.get(count, "unknown")
