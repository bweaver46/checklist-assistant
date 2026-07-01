"""
The standard checklist template - must match the columns Brandon's
Check List Builder expects exactly:

    type, sub_type, year, brand, set, insert, attributes, card_number,
    player, team, base, base_serial, parallel_1, serial_1, parallel_2, serial_2, ...

Insert and attributes are SCALAR - one value per card, describing the
card as a whole. Only parallel/serial repeat, since a single card can
have multiple print versions (different parallels), each with its own
serial number.

Naming note: the column the user sees as "sub_type" holds the sport
value; the column called "attributes" holds what was previously named
sub_type (section, leftover player text, autograph flag).

base is always blank from the parser (manually filled after export
when needed). base_serial is auto-populated from the base card row's
SN/PR attribute, if present.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChecklistRow:
    type: str = ""
    sub_type: str = ""  # holds the sport value
    year: str = ""
    brand: str = ""
    set: str = ""
    insert: str = ""
    attributes: str = ""  # holds section/leftover/autograph text
    card_number: str = ""
    player: str = ""
    team: str = ""
    base: str = ""         # always blank from parser; filled manually after export if needed
    base_serial: str = ""  # auto-populated if the base card row has SN/PR; otherwise blank
    parallels: list = field(default_factory=list)  # list of (parallel_text, serial) tuples
