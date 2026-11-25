
import json
import re
from pathlib import Path

from poker_apis.vision.table_validation import validate_table_data


# Reference screenshot dimensions: 1600 x 899.
# Each region is (x1, y1, x2, y2).

SEAT_REGIONS = {
    "top": {
        "name": (720, 160, 880, 205),
        "stack": (750, 200, 850, 245),
        "bounty": (640, 130, 710, 175),
    },
    "upper_left": {
        "name": (320, 215, 450, 265),
        "stack": (330, 255, 440, 305),
        "bounty": (315, 305, 390, 350),
    },
    "upper_right": {
        "name": (1135, 215, 1300, 265),
        "stack": (1160, 255, 1280, 305),
        "bounty": (1230, 305, 1310, 350),
    },
    "middle_left": {
        "name": (265, 460, 370, 515),
        "stack": (270, 505, 370, 555),
        "bounty": (245, 550, 320, 600),
    },
    "middle_right": {
        "name": (1190, 460, 1370, 515),
        "stack": (1225, 505, 1340, 555),
        "bounty": (1290, 550, 1380, 600),
    },
    "bottom_left": {
        "name": (410, 650, 550, 705),
        "stack": (430, 690, 535, 745),
        "bounty": (585, 625, 670, 675),
    },
    "bottom_center": {
        "name": (750, 725, 900, 775),
        "stack": (775, 765, 885, 820),
        "bounty": (660, 690, 740, 740),
    },
}


# --------------------------------------------------
# BASIC HELPERS
# --------------------------------------------------

def center_of(item):
    return (
        item["x"] + item["width"] / 2,
        item["y"] + item["height"] / 2,
    )


def is_inside(item, region):
    cx, cy = center_of(item)

    x1, y1, x2, y2 = region

    return x1 <= cx <= x2 and y1 <= cy <= y2


def find_in_region(
    items,
    region,
    predicate,
    min_confidence=0.80
):
    candidates = [
        item
        for item in items
        if item["confidence"] >= min_confidence
        and is_inside(item, region)
        and predicate(item["text"])
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: item["confidence"]
    )


def parse_integer(text):
    digits = re.sub(r"[^\d]", "", text)

    return int(digits) if digits else None


def parse_amount(text):
    match = re.fullmatch(
        r"\$\s*[\d,]+(?:\.\d{1,2})?",
        text.strip()
    )

    return match.group(0).strip() if match else None


# --------------------------------------------------
# HEADER INFORMATION
# --------------------------------------------------

def parse_header(items):

    header = next(
        (
            item["text"]
            for item in items
            if "Hold'em" in item["text"]
        ),
        ""
    )

    blinds_match = re.search(
        r"([\d,]+)\s*/\s*([\d,]+)",
        header
    )

    return {
        "small_blind": parse_integer(blinds_match.group(1))
        if blinds_match else None,

        "big_blind": parse_integer(blinds_match.group(2))
        if blinds_match else None,
    }


# --------------------------------------------------
# FIND VALUES BESIDE LABELS
# --------------------------------------------------

def find_value_to_right(
    items,
    label_text,
    max_y_difference=12
):
    label = next(
        (
            item
            for item in items
            if item["text"].strip() == label_text
        ),
        None
    )

    if not label:
        return None

    label_right = label["x"] + label["width"]

    label_center_y = (
        label["y"] + label["height"] / 2
    )

    candidates = []

    for item in items:

        if item is label:
            continue

        if item["confidence"] < 0.80:
            continue

        if not re.fullmatch(
            r"\$\s*[\d,]+(?:\.\d{1,2})?",
            item["text"].strip()
        ):
            continue

        item_center_y = (
            item["y"] + item["height"] / 2
        )

        if item["x"] < label_right:
            continue

        if abs(item_center_y - label_center_y) > max_y_difference:
            continue

        candidates.append(item)

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: item["x"] - label_right
    )


# --------------------------------------------------
# TABLE INFORMATION
# --------------------------------------------------

def parse_table_info(items):

    pot = None
    average_stack = None
    position = None

    for item in items:

        text = item["text"].strip()

        # Pot
        if "Total:" in text:
            pot = parse_integer(text)

        # Average stack
        elif (
            re.fullmatch(r"[\d,]+", text)
            and is_inside(item, (1200, 40, 1300, 85))
        ):
            average_stack = parse_integer(text)

        # Tournament position
        elif re.fullmatch(r"\d+\s+of\s+\d+", text):
            position = text

    # Dynamically extract prize information
    prize_item = find_value_to_right(
        items,
        "Prize Pool"
    )

    first_place_item = find_value_to_right(
        items,
        "1st Place"
    )

    return {
        "pot": pot,

        "prize_pool_display": (
            prize_item["text"] if prize_item else None
        ),

        "first_place_prize_display": (
            first_place_item["text"]
            if first_place_item else None
        ),

        "average_stack": average_stack,

        "tournament_position": position,
    }


# --------------------------------------------------
# PLAYER INFORMATION
# --------------------------------------------------

def parse_players(items):

    players = []

    name_pattern = re.compile(
        r"^[A-Za-z0-9_]{2,24}$"
    )

    stack_pattern = re.compile(
        r"^[\d,]+$"
    )

    bounty_pattern = re.compile(
        r"^\$\s*\d+(?:\.\d{1,2})?$"
    )

    for seat_name, regions in SEAT_REGIONS.items():

        # Player name
        name_item = find_in_region(
            items,
            regions["name"],
            lambda text: bool(
                name_pattern.fullmatch(text)
            )
        )

        # Player stack
        stack_item = find_in_region(
            items,
            regions["stack"],
            lambda text: bool(
                stack_pattern.fullmatch(text)
            )
        )

        # Player bounty
        bounty_item = find_in_region(
            items,
            regions["bounty"],
            lambda text: bool(
                bounty_pattern.fullmatch(text)
            )
        )

        player = {
            "seat": seat_name,

            "name": (
                name_item["text"]
                if name_item else None
            ),

            "name_confidence": (
                name_item["confidence"]
                if name_item else None
            ),

            "stack": (
                parse_integer(stack_item["text"])
                if stack_item else None
            ),

            "stack_confidence": (
                stack_item["confidence"]
                if stack_item else None
            ),

            "bounty_display": (
                bounty_item["text"]
                if bounty_item else None
            ),

            "bounty_confidence": (
                bounty_item["confidence"]
                if bounty_item else None
            ),
        }

        players.append(player)

    return players


# --------------------------------------------------
# COMPLETE TABLE PARSER
# --------------------------------------------------

def parse_table(ocr_items):

    table = {
        **parse_header(ocr_items),

        **parse_table_info(ocr_items),

        "players": parse_players(ocr_items),
    }

    return table


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    input_path = Path(
        "test_output/ocr_results.json"
    )

    output_path = Path(
        "test_output/table_data.json"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Could not find OCR file: {input_path}"
        )

    # Read OCR results
    with input_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        ocr_items = json.load(file)

    # Extract structured table information
    table_data = parse_table(ocr_items)

    # Validate extracted information
    validation = validate_table_data(table_data)

    table_data["validation"] = validation

    # Create output directory
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Save JSON
    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            table_data,
            file,
            indent=4
        )

    print("\nTABLE DATA")
    print("=" * 50)

    print(
        json.dumps(
            table_data,
            indent=4
        )
    )

    print("\n" + "=" * 50)

    print("VALIDATION:", validation["valid"])

    print(
        "PLAYERS DETECTED:",
        validation["players_detected"]
    )

    print(
        "WARNINGS:",
        len(validation["warnings"])
    )

    print(
        "\nStructured table data saved to:",
        output_path
    )


if __name__ == "__main__":
    main()
