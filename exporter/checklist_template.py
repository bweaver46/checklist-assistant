"""
The standard checklist template. One row per unique card, after parallels
have been merged in Phase 6.

`parallels` is a list of (parallel_name, serial) tuples. It starts with at
most one entry per row coming out of Phase 5 (one row per website row,
before merging) and grows as Phase 6 merges same-card rows together.
"""

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
    parallels: list = field(default_factory=list)

    def merge_key(self) -> tuple:
        """Two rows are the 'same card' if everything but the parallel matches."""
        return (
            self.type,
            self.sport,
            self.year,
            self.brand,
            self.set,
            self.insert,
            self.sub_type,
            self.card_number,
            self.player,
            self.team,
        )
