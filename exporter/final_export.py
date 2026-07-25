"""
Phase 8: write the final checklist CSV - must match ColLock's import
template exactly for whichever checklist_type produced it. ColLock's
Sets bulk-import and Players bulk-import use TWO DIFFERENT column
layouts (confirmed against Brandon's actual templates), not one shared
schema - see SET_HEADER_MAP vs PLAYER_HEADER_MAP below.

SET_HEADER_MAP (updated 2026-07-22): the "type" column is dropped
entirely - ColLock's Sets template has no equivalent column. The value
is still tracked internally on ChecklistRow (used elsewhere, e.g.
merge.py's grouping key) - it's just not written out for Sets.
Column mapping (internal attribute -> external header):
    sub_type    -> Sport
    year        -> Year
    brand       -> Brand
    set         -> Set name
    insert      -> Insert / subset
    card_number -> Card number
    player      -> Player / card name
    team        -> Team
    attributes  -> Attributes
    base        -> Base
    base_serial -> Serial

PLAYER_HEADER_MAP (added 2026-07-24, confirmed against
collock-bulk-player-template.csv): a completely different layout from
Sets - lowercase headers matching the internal attribute names almost
verbatim, "type" IS included (Sets drops it, Players keeps it), and
"attributes" sits BEFORE card_number (Sets has it after Team).
    type        -> type   (lowercased at write time - the internal
                            value is "Sports", template shows "sports")
    sub_type    -> sport
    year        -> year
    brand       -> brand
    set         -> set
    insert      -> insert
    attributes  -> attributes
    card_number -> card_number
    player      -> player
    team        -> team
    base        -> base
    base_serial -> base_serial

Team column note (2026-07-24, Brandon): Player-mode team fetching (the
year-checkin/retroactive-correction logic in scraper/browser_manager.py)
is no longer wired into the Player prompt flow - Brandon found a better
way to handle team assignment himself and just types it in manually
per run now (see app/main_window.py's _prompt_player_context). The
underlying fetch machinery is left in place, just unused by Player
mode's UI, in case it's wanted again later.

Both maps: then parallel_1, serial_1, parallel_2, serial_2, ...
expanded to however many parallels the widest card in this batch
actually has (at least one pair, even if every card in the batch has
zero parallels). Every parallel_N column is always paired with a
serial_N column, even if serial_N is blank.
"""

from __future__ import annotations

import csv

from exporter.checklist_template import ChecklistRow

# (internal ChecklistRow attribute, external CSV header) in the exact
# order ColLock's Sets template expects. "type" is intentionally
# excluded - see module docstring.
SET_HEADER_MAP = [
    ("sub_type", "Sport"),
    ("year", "Year"),
    ("brand", "Brand"),
    ("set", "Set name"),
    ("insert", "Insert / subset"),
    ("card_number", "Card number"),
    ("player", "Player / card name"),
    ("team", "Team"),
    ("attributes", "Attributes"),
    ("base", "Base"),
    ("base_serial", "Serial"),
]

# (internal ChecklistRow attribute, external CSV header) in the exact
# order ColLock's Players template expects. Note "attributes" comes
# BEFORE card_number here, unlike SET_HEADER_MAP.
PLAYER_HEADER_MAP = [
    ("type", "type"),
    ("sub_type", "sport"),
    ("year", "year"),
    ("brand", "brand"),
    ("set", "set"),
    ("insert", "insert"),
    ("attributes", "attributes"),
    ("card_number", "card_number"),
    ("player", "player"),
    ("team", "team"),
    ("base", "base"),
    ("base_serial", "base_serial"),
]


def sort_rows_by_brand(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    """Sort by brand first, then set/year/card_number for a stable,
    predictable order within each brand."""
    return sorted(rows, key=lambda r: (r.brand, r.set, r.year, r.card_number))


def write_final_csv(rows: list[ChecklistRow], path: str, checklist_type: str = "Set") -> None:
    """checklist_type picks which of ColLock's two import templates to
    write - "Player" uses PLAYER_HEADER_MAP, anything else (Set, Team)
    uses SET_HEADER_MAP. Team checklists reuse the Sets layout since no
    separate Team template has been provided yet - revisit if ColLock
    adds one."""
    header_map = PLAYER_HEADER_MAP if checklist_type == "Player" else SET_HEADER_MAP

    max_parallels = max((len(row.parallels) for row in rows), default=0)
    max_parallels = max(max_parallels, 1)  # template always has at least parallel_1/serial_1

    parallel_columns: list[str] = []
    for i in range(1, max_parallels + 1):
        parallel_columns += [f"parallel_{i}", f"serial_{i}"]

    columns = [header for _, header in header_map] + parallel_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {}
            for attr, header in header_map:
                value = getattr(row, attr)
                if attr == "type":
                    value = value.lower()
                record[header] = value
            for i in range(1, max_parallels + 1):
                if i <= len(row.parallels):
                    parallel, serial = row.parallels[i - 1]
                else:
                    parallel, serial = "", ""
                record[f"parallel_{i}"] = parallel
                record[f"serial_{i}"] = serial
            writer.writerow(record)
