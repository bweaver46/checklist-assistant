"""
Regression test for two team-parsing bugs Brandon found 2026-07-26 in
real Beckett checklist data:

  - "Pittsburgh Pirates (All-Star Game)" was landing whole in Team -
    the parenthetical note is a card attribute, not part of the team
    name, and should move to attributes.
  - "Texas Rangers /25" was landing whole in Team too - the trailing
    "/25" is the card's own print-run serial number, not part of the
    team name, and should move to base_serial.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_team_suffixes.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    by_card = {r["card_number"]: r for r in rows}

    check("3 rows parsed", len(rows) == 3)

    r1 = by_card.get("1", {})
    check("card 1 team stripped of parenthetical", r1.get("team") == "Pittsburgh Pirates")
    check("card 1 parenthetical moved to attributes", "All-Star Game" in r1.get("attributes", ""))
    check("card 1 Autograph tag still present", "Autograph" in r1.get("attributes", ""))
    check("card 1 base_serial stays blank", r1.get("base_serial", "") == "")

    r2 = by_card.get("2", {})
    check("card 2 team stripped of trailing serial", r2.get("team") == "Texas Rangers")
    check("card 2 base_serial extracted", r2.get("base_serial") == "25")

    r3 = by_card.get("3", {})
    check("card 3 team unaffected (no suffix)", r3.get("team") == "Boston Red Sox")
    check("card 3 base_serial stays blank", r3.get("base_serial", "") == "")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print(f"\nAll checks passed. {len(rows)} rows parsed.")


if __name__ == "__main__":
    run()
