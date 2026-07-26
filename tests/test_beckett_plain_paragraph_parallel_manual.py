"""
Regression test for a real Beckett parsing bug found 2026-07-26
(Brandon, "Dual Autographed Preeminent Pieces" / "Dual Preeminent
Relics" inserts): a blanket parallel written as a bare paragraph line
("Gold /1") right after the caption, instead of the <ul><li> structure
the parser already handled, was falling into the card-line buffer and
becoming a bogus standalone row (player="Gold /1") instead of being
applied to every real card in the section.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_plain_paragraph_parallel.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check("14 real card rows, no bogus Gold/Parallel rows", len(rows) == 14)

    bogus_players = [r["player"] for r in rows if r["player"] in ("Gold /1", "Gold", "Parallel", "Parallels")]
    check("no bogus 'Gold /1' or 'Parallel' row exists", not bogus_players)

    check("every row got the Gold /1 blanket parallel", all(r["parallels"] == [("Gold", "1")] for r in rows))

    by_card = {r["card_number"]: r for r in rows}

    r1 = by_card.get("PPDAR-HRJ", {})
    check("PPDAR-HRJ team stripped of its own serial", r1.get("team") == "Baltimore Orioles")
    check("PPDAR-HRJ base_serial extracted", r1.get("base_serial") == "5")
    check("PPDAR-HRJ still has its Gold parallel", r1.get("parallels") == [("Gold", "1")])

    r2 = by_card.get("DPPR-BG", {})
    check("DPPR-BG team stripped of its own serial", r2.get("team") == "Toronto Blue Jays")
    check("DPPR-BG base_serial extracted", r2.get("base_serial") == "5")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print(f"\nAll checks passed. {len(rows)} rows parsed.")


if __name__ == "__main__":
    run()
