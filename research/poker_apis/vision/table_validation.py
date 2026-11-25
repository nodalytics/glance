
def validate_table_data(
    table_data,
    confidence_threshold=0.85
):

    errors = []
    warnings = []

    # --------------------------------
    # Validate blinds
    # --------------------------------

    small_blind = table_data.get("small_blind")
    big_blind = table_data.get("big_blind")

    if small_blind is None or big_blind is None:

        errors.append(
            "Missing blind information."
        )

    elif small_blind <= 0 or big_blind <= 0:

        errors.append(
            "Blind values must be positive."
        )

    elif small_blind >= big_blind:

        warnings.append(
            "Small blind is not lower than big blind."
        )

    # --------------------------------
    # Validate pot
    # --------------------------------

    pot = table_data.get("pot")

    if pot is None:

        warnings.append(
            "Pot was not detected."
        )

    elif pot < 0:

        errors.append(
            "Pot cannot be negative."
        )

    # --------------------------------
    # Validate tournament information
    # --------------------------------

    if table_data.get("prize_pool_display") is None:

        warnings.append(
            "Prize pool was not detected."
        )

    if table_data.get("average_stack") is None:

        warnings.append(
            "Average stack was not detected."
        )

    # --------------------------------
    # Validate players
    # --------------------------------

    players = table_data.get("players", [])

    names = []

    if not players:

        errors.append(
            "No players were detected."
        )

    for player in players:

        seat = player.get("seat", "unknown")

        name = player.get("name")

        stack = player.get("stack")

        if not name:

            warnings.append(
                f"Missing player name at seat {seat}."
            )

        else:

            names.append(name)

        if stack is None:

            warnings.append(
                f"Missing stack at seat {seat}."
            )

        elif stack < 0:

            errors.append(
                f"Negative stack at seat {seat}."
            )

        # Check OCR confidence
        confidence_fields = (
            "name_confidence",
            "stack_confidence",
            "bounty_confidence",
        )

        for field in confidence_fields:

            confidence = player.get(field)

            if (
                confidence is not None
                and confidence < confidence_threshold
            ):

                warnings.append(
                    f"Low {field} at seat {seat}: "
                    f"{confidence:.3f}"
                )

        # Check bounty
        if player.get("bounty_display") is None:

            warnings.append(
                f"Missing bounty at seat {seat}."
            )

    # --------------------------------
    # Duplicate player names
    # --------------------------------

    if len(names) != len(set(names)):

        warnings.append(
            "Duplicate player names detected."
        )

    # --------------------------------
    # Final result
    # --------------------------------

    return {
        "valid": len(errors) == 0,

        "errors": errors,

        "warnings": warnings,

        "players_detected": len(players),

        "players_with_names": sum(
            bool(player.get("name"))
            for player in players
        ),

        "players_with_stacks": sum(
            player.get("stack") is not None
            for player in players
        ),

        "players_with_bounties": sum(
            player.get("bounty_display") is not None
            for player in players
        ),
    }
