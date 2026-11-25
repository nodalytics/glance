#!/usr/bin/env python3
"""Turn glance table-state JSON into a review record.

Input is either a raw state object or a JSONL line written by batch_extract.py
(`{"ts", "source", "state"}`). The output keeps cards, pot, stacks, bets, and
a seat position derived from the dealer seat.

Positions walk increasing seat index from the dealer, wrapping around:
6-max is BTN, SB, BB, UTG, HJ, CO. Heads-up is BTN, BB. This is a label on
the seat list glance already returned. It is not an action and not a claim
about pixel layout.

Missing numeric fields are omitted. Glance leaves them out when OCR did not
read them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Clockwise-from-button labels keyed by how many seats the state contains.
_FROM_BUTTON = {
    2: ("BTN", "BB"),
    3: ("BTN", "SB", "BB"),
    4: ("BTN", "SB", "BB", "UTG"),
    5: ("BTN", "SB", "BB", "UTG", "CO"),
    6: ("BTN", "SB", "BB", "UTG", "HJ", "CO"),
}


def seat_positions(seat_count: int, dealer_seat: int) -> dict[int, str]:
    labels = _FROM_BUTTON.get(seat_count)
    if labels is None or seat_count <= 0:
        return {}
    if not 1 <= dealer_seat <= seat_count:
        return {}
    positions: dict[int, str] = {}
    for step, label in enumerate(labels):
        seat = ((dealer_seat - 1 + step) % seat_count) + 1
        positions[seat] = label
    return positions


def format_state(state: dict) -> dict:
    seats_in = state.get("seats") or []
    seat_count = len(seats_in)
    dealer = state.get("dealer")
    positions = (
        seat_positions(seat_count, dealer) if isinstance(dealer, int) else {}
    )
    seats = []
    hero = None
    for seat in seats_in:
        index = seat.get("index")
        row = {
            "seat": index,
            "position": positions.get(index),
            "cards": list(seat.get("cards") or []),
            "in_hand": bool(seat.get("in_hand", False)),
        }
        if "stack" in seat:
            row["stack"] = seat["stack"]
        if "bet" in seat:
            row["bet"] = seat["bet"]
        seats.append(row)
        if index == 1:
            hero = {"seat": 1, "cards": list(state.get("my_cards") or row["cards"])}
            if "stack" in seat:
                hero["stack"] = seat["stack"]
            if "bet" in seat:
                hero["bet"] = seat["bet"]

    formatted = {
        "street": state.get("stage"),
        "board": list(state.get("board") or []),
        "dealer_seat": dealer if isinstance(dealer, int) else None,
        "seats": seats,
    }
    if "pot" in state:
        formatted["pot"] = state["pot"]
    if hero is not None:
        formatted["hero"] = hero
    return formatted


def state_from_record(record: dict) -> dict | None:
    if "state" in record and isinstance(record["state"], dict):
        return record["state"]
    if "seats" in record or "stage" in record:
        return record
    return None


def format_jsonl(text: str) -> list[dict]:
    formatted = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        state = state_from_record(record)
        if state is None:
            raise ValueError(f"line {line_number} is not a glance state")
        item = format_state(state)
        if isinstance(record.get("source"), str):
            item["source"] = record["source"]
        if isinstance(record.get("ts"), str):
            item["ts"] = record["ts"]
        formatted.append(item)
    return formatted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path, help="glance state JSONL, or batch_extract output")
    parser.add_argument("--output", type=Path, help="write JSONL here instead of stdout")
    args = parser.parse_args(argv)
    try:
        formatted = format_jsonl(args.jsonl.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    text = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in formatted)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
