"""
Phase 7: cleanup rules.

Insert/Parallel/Sub_Type terminology normalization happens earlier, in
exporter/merge.py (where Insert is computed). What's left here is a
defensive dedupe in case the exact same (parallel, serial) pair shows
up twice for one card, plus a cross-row serial backfill (see
backfill_known_serials below).
"""

from __future__ import annotations

from collections import defaultdict

from exporter.checklist_template import ChecklistRow


def dedupe_parallels(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    for row in rows:
        seen = set()
        deduped = []
        for pair in row.parallels:
            if pair not in seen:
                seen.add(pair)
                deduped.append(pair)
        row.parallels = deduped
    return rows


def backfill_known_serials(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    """A parallel's print run (e.g. 'Chrome Black Refractor' /77) is
    fixed for the whole release, not something that varies card to
    card - but BSC doesn't display it in the variant-name text for
    every card type. Confirmed (Brandon, 2026-08-02, 2026 Topps
    Heritage): standard numbered player cards show 'Chrome Black
    Refractor /77' directly, so its serial parses out fine, but the
    equivalent row for League Leaders / other subset combo cards just
    shows 'Chrome Black Refractor' with no serial at all - same
    parallel, same print run, just not printed on BSC's listing for
    that card type. Confirmed across the whole file that every
    parallel name with a blank serial ANYWHERE also has exactly one
    consistent non-blank value elsewhere - never two conflicting
    non-blank values for the same name - so it's safe to backfill from
    whichever rows do show it.

    If a parallel name ever DOES show two different non-blank serial
    values in the same export (a genuinely varying serial, not just a
    missing one), it's deliberately left alone - not backfilled - since
    there'd be no single correct value to apply.
    """
    serial_by_parallel: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for parallel_name, serial in row.parallels:
            if serial.strip():
                serial_by_parallel[parallel_name].add(serial.strip())

    known_serial = {
        name: next(iter(serials))
        for name, serials in serial_by_parallel.items()
        if len(serials) == 1
    }
    if not known_serial:
        return rows

    for row in rows:
        row.parallels = [
            (name, known_serial[name]) if not serial.strip() and name in known_serial else (name, serial)
            for name, serial in row.parallels
        ]
    return rows


def apply_cleanup(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    rows = dedupe_parallels(rows)
    rows = backfill_known_serials(rows)
    return rows
