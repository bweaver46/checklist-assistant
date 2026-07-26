"""
Phase 8: write the final checklist CSV - must match ColLock's import
template exactly for whichever checklist_type produced it.

SET_HEADER_MAP (corrected 2026-07-26, Brandon supplied the actual
current collock-bulk-set-template.csv): this now matches
PLAYER_HEADER_MAP's schema exactly - lowercase headers, "type"
included, "attributes" before card_number, "base_serial" (not
"Serial"). The previous version of this map (capitalized headers, no
"type" column, "Set name"/"Insert / subset"/"Card number"/"Player /
card name"/"Serial") was based on an earlier template that's since
been superseded - ColLock's Sets bulk-import evidently now uses the
same column layout as Players. If a genuinely different Sets template
shows up again later, don't assume - ask for the actual file, same as
this fix.
Column mapping (internal attribute -> external header):
    type        -> type    (lowercased at write time)
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

PLAYER_HEADER_MAP (added 2026-07-24, confirmed against
collock-bulk-player-template.csv): identical layout to SET_HEADER_MAP
above (see history note there for why they used to differ and no
longer do).
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
# order ColLock's Sets template expects (corrected 2026-07-26 - see
# module docstring; this now matches PLAYER_HEADER_MAP exactly).
SET_HEADER_MAP = [
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
