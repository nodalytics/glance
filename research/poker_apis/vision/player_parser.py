
from dataclasses import dataclass


@dataclass
class PlayerObservation:
    seat: str
    name: str | None = None
    stack: float | None = None
    current_bet: float | None = None
    confidence: float = 0.0


class PlayerParser:
    """
    Maps OCR observations to configured seat regions.

    Seat coordinates must be calibrated using an authorized
    simulator screenshot.
    """

    def __init__(self, seat_regions: dict):
        self.seat_regions = seat_regions

    @staticmethod
    def inside(item, region: dict) -> bool:
        center_x = item.x + item.width / 2
        center_y = item.y + item.height / 2

        return (
            region["x1"] <= center_x <= region["x2"]
            and region["y1"] <= center_y <= region["y2"]
        )

    def extract(self, items):
        players = []

        for seat, regions in self.seat_regions.items():
            player = PlayerObservation(seat=seat)

            for item in items:
                if self.inside(item, regions["name"]):
                    player.name = item.text
                    player.confidence = item.confidence

                if self.inside(item, regions["stack"]):
                    try:
                        player.stack = float(
                            item.text.replace("$", "").replace(",", "")
                        )
                    except ValueError:
                        pass

                if self.inside(item, regions["bet"]):
                    try:
                        player.current_bet = float(
                            item.text.replace("$", "").replace(",", "")
                        )
                    except ValueError:
                        pass

            players.append(player)

        return players
