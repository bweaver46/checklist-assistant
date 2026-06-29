"""
The standard checklist template - must match the columns Brandon's
Check List Builder expects exactly:

    type, sport, year, brand, set, insert, sub_type, card_number,
    player, team, parallel_1, serial_1, parallel_2, serial_2, ...

Insert and sub_type are SCALAR - one value per card, describing the
card as a whole. Only parallel/serial repeat, since a single card can
have multiple print versions (different parallels), each with its own
serial number.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChecklistRow:
    type: str = ""
    sport: str = ""
    year: str = ""
    brand: str = ""
    set: str = ""
    insert: str = ""
    sub_type: str = ""
    card_number: str = ""
    player: str = ""
    team: str = ""
    parallels: list = field(default_factory=list)  # list of (parallel_text, serial) tuples
