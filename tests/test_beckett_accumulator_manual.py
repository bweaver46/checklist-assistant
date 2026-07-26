"""
Tests for settings/beckett_accumulator.py - added 2026-07-26 so pulling
related Beckett articles (Base release, Celebration Mega Box, All-Star
Game Mega Box, etc. - anything sharing the same year/brand/set) can
combine into one CSV instead of each pull overwriting the last.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings.beckett_accumulator as ba


def run():
    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    import tempfile
    tmp_path = Path(tempfile.mktemp(suffix=".json"))
    original_path = ba.BECKETT_ACCUMULATOR_PATH
    ba.BECKETT_ACCUMULATOR_PATH = tmp_path

    try:
        rows, name = ba.load_beckett_accumulated()
        check("starts empty", rows == [] and name == "")

        first_pull = [
            {"insert": "", "card_number": "1", "player": "Player A", "team": "Team A",
             "attributes": "", "base_serial": "", "parallels": [("Gold", "1")]},
        ]
        rows, name = ba.load_beckett_accumulated()
        all_rows = rows + first_pull
        output_name = name or "2026 Topps Series 1"
        ba.save_beckett_accumulated(all_rows, output_name)

        second_pull = [
            {"insert": "", "card_number": "2", "player": "Player B", "team": "Team B",
             "attributes": "", "base_serial": "", "parallels": []},
        ]
        rows, name = ba.load_beckett_accumulated()
        check("first pull's row persisted", len(rows) == 1)
        check("output name persisted", name == "2026 Topps Series 1")
        check(
            "parallels round-trip as tuples, not lists",
            bool(rows) and rows[0]["parallels"] == [("Gold", "1")],
        )
        all_rows = rows + second_pull
        ba.save_beckett_accumulated(all_rows, name)

        rows, name = ba.load_beckett_accumulated()
        check("both pulls accumulated", len(rows) == 2)
        check("output name still the same after second pull", name == "2026 Topps Series 1")
        check("row order preserved (first pull first)", rows[0]["card_number"] == "1")
        check("row order preserved (second pull second)", rows[1]["card_number"] == "2")

        check("beckett_accumulated_count matches", ba.beckett_accumulated_count() == 2)

        ba.clear_beckett_accumulated()
        rows, name = ba.load_beckett_accumulated()
        check("clear resets to empty", rows == [] and name == "")
        check("clear resets count to 0", ba.beckett_accumulated_count() == 0)

    finally:
        ba.BECKETT_ACCUMULATOR_PATH = original_path
        tmp_path.unlink(missing_ok=True)

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print("All tests passed.")


if __name__ == "__main__":
    run()
