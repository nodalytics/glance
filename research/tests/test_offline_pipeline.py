"""Offline batch logger and history formatter. Standard-library unittest only."""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from unittest import mock

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

import batch_extract  # noqa: E402
import format_history  # noqa: E402


def _http_error(status: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        batch_extract.DEFAULT_URL,
        status,
        "error",
        Message(),
        io.BytesIO(body),
    )


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class CanonicalStateTests(unittest.TestCase):
    def test_key_order_does_not_change_the_token(self) -> None:
        left = {"stage": "Flop", "pot": 10, "seats": [{"index": 1}]}
        right = {"seats": [{"index": 1}], "pot": 10, "stage": "Flop"}
        self.assertEqual(batch_extract.canonical_state(left), batch_extract.canonical_state(right))
        self.assertNotEqual(
            batch_extract.canonical_state(left),
            batch_extract.canonical_state({"stage": "Turn", "pot": 10}),
        )


class ImageListTests(unittest.TestCase):
    def test_sorts_images_and_skips_other_files(self) -> None:
        with self._temp_dir() as raw:
            directory = Path(raw)
            for name in ("z.png", "a.jpg", "m.JPEG", "notes.txt", "mapping.json"):
                (directory / name).write_bytes(b"x")
            names = [path.name for path in batch_extract.list_images(directory)]
        self.assertEqual(names, ["a.jpg", "m.JPEG", "z.png"])

    def _temp_dir(self):
        import tempfile

        return tempfile.TemporaryDirectory()


class ExtractFilterTests(unittest.TestCase):
    def test_non_200_is_dropped_and_reordered_state_is_skipped(self) -> None:
        state_a = {"stage": "Flop", "pot": 3}
        state_a_reordered = {"pot": 3, "stage": "Flop"}
        state_b = {"stage": "Turn", "pot": 9}
        scripted = [
            _http_error(422, b'{"error":"table not found"}'),
            _Response(200, json.dumps({"error": "could not decode image"}).encode()),
            _Response(200, json.dumps(state_a).encode()),
            _Response(200, json.dumps(state_a_reordered).encode()),
            _Response(200, json.dumps(state_b).encode()),
        ]

        def fake_urlopen(request: urllib.request.Request, timeout: float = 0):
            del request, timeout
            item = scripted.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with self._temp_dir() as raw:
            directory = Path(raw)
            for name in ("a.png", "b.jpg", "c.jpeg", "d.png", "e.png"):
                (directory / name).write_bytes(b"frame")
            output = directory / "out.jsonl"
            with mock.patch.object(batch_extract.urllib.request, "urlopen", fake_urlopen):
                code = batch_extract.extract(directory, batch_extract.DEFAULT_URL, output, 1.0)
            lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(code, 0)
        self.assertEqual([line["source"] for line in lines], ["c.jpeg", "e.png"])
        self.assertEqual(lines[0]["state"]["stage"], "Flop")
        self.assertEqual(lines[1]["state"]["stage"], "Turn")
        self.assertEqual(scripted, [])

    def _temp_dir(self):
        import tempfile

        return tempfile.TemporaryDirectory()


class SeatPositionTests(unittest.TestCase):
    def test_six_max_from_seat_1(self) -> None:
        self.assertEqual(
            format_history.seat_positions(6, 1),
            {1: "BTN", 2: "SB", 3: "BB", 4: "UTG", 5: "HJ", 6: "CO"},
        )

    def test_six_max_wraps_from_the_last_seat(self) -> None:
        self.assertEqual(
            format_history.seat_positions(6, 6),
            {6: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "HJ", 5: "CO"},
        )

    def test_heads_up_wraps(self) -> None:
        self.assertEqual(format_history.seat_positions(2, 1), {1: "BTN", 2: "BB"})
        self.assertEqual(format_history.seat_positions(2, 2), {2: "BTN", 1: "BB"})


class FormatStateTests(unittest.TestCase):
    def test_unread_numbers_are_omitted(self) -> None:
        formatted = format_history.format_state(
            {
                "stage": "PreFlop",
                "dealer": 1,
                "my_cards": ["Ah", "2c"],
                "seats": [
                    {"index": 1, "cards": ["Ah", "2c"], "in_hand": True},
                    {"index": 2, "in_hand": False},
                ],
            }
        )
        self.assertNotIn("pot", formatted)
        self.assertNotIn("stack", formatted["hero"])
        self.assertNotIn("bet", formatted["hero"])
        self.assertNotIn("stack", formatted["seats"][0])
        self.assertNotIn("bet", formatted["seats"][1])
        self.assertEqual(formatted["hero"]["cards"], ["Ah", "2c"])
        self.assertEqual(formatted["seats"][0]["position"], "BTN")
        self.assertEqual(formatted["seats"][1]["position"], "BB")
        self.assertIsNot(formatted["seats"][0].get("stack"), 0)


if __name__ == "__main__":
    unittest.main()
