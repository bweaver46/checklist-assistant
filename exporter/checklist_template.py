"""
The standard checklist template. One row per unique physical card design
(same card_number/player/set/etc), after occurrences have been merged in
Phase 6.

`occurrences` is a list of (insert, sub_type, serial) tuples - one per
original website row for this card. Base rows with nothing notable about
them are dropped entirely (see exporter/convert.py); a Base row that does
carry an attribute (e.g. a serial number) is kept with insert="".
"""

from dataclasses import dataclass, field


@dataclass
class ChecklistRow:
    type: str = ""
    sport: str = ""
    year: str = ""
    brand: str = ""
    set: str = ""
    card_number: str = ""
    player: str = ""
    team: str = ""
    occurrences: list = field(default_factory=list)

    def merge_key(self) -> tuple:
        """Two rows are the 'same card' if everything but insert/sub_type/
        serial matches. Those three are per-occurrence, not part of the
        card's identity."""
        return (
            self.type,
            self.sport,
            self.year,
            self.brand,
            self.set,
            self.card_number,
            self.player,
            self.team,
        )
