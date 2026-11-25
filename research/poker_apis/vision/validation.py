
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_poker_state(
    board_cards: list,
    hole_cards: list,
    pot: float | None,
    players: list,
) -> ValidationResult:

    errors = []
    warnings = []

    # Validate board card count.
    if len(board_cards) not in (0, 3, 4, 5):
        errors.append("Invalid community card count")

    # Validate duplicate recognized cards.
    all_cards = [
        card for card in board_cards + hole_cards
        if card is not None
    ]

    if len(all_cards) != len(set(all_cards)):
        errors.append("Duplicate playing card detected")

    # Validate recognized card format.
    valid_ranks = {
        "A", "K", "Q", "J", "10",
        "9", "8", "7", "6", "5", "4", "3", "2"
    }

    valid_suits = {"h", "d", "c", "s"}

    for card in all_cards:
        if (
            not isinstance(card, str)
            or len(card) < 2
            or card[:-1] not in valid_ranks
            or card[-1] not in valid_suits
        ):
            errors.append(f"Invalid card: {card}")

    # Validate pot.
    if pot is not None and pot < 0:
        errors.append("Pot cannot be negative")

    # Validate player amounts.
    for player in players:
        if player.stack is not None and player.stack < 0:
            errors.append(
                f"Negative stack for {player.seat}"
            )

        if player.current_bet is not None and player.current_bet < 0:
            errors.append(
                f"Negative bet for {player.seat}"
            )

    # Missing information is a warning, not a fabricated value.
    if pot is None:
        warnings.append("Pot value not recognized")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
