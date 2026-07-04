from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2025_donruss_baseball.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    by_card = {r["card_number"]: r for r in rows if r["card_number"]}

    expected_parallels = [
        ("Green Laser", ""),
        ("Holo", ""),
        ("Orange Laser", "299"),
        ("Red", "250"),
        ("Artist Proof Black", "1/1"),
        ("Black", "1/1"),
        ("Printing Plates", "1/1"),
    ]

    check("card 1 exists", "1" in by_card)
    if "1" in by_card:
        check("card 1 parallels attached", by_card["1"]["parallels"] == expected_parallels)
        check("card 1 player", by_card["1"]["player"] == "Luisangel Acuna")

    check("card 2 also has same parallels (blanket)", by_card.get("2", {}).get("parallels") == expected_parallels)
    check("card 3 also has same parallels (blanket)", by_card.get("3", {}).get("parallels") == expected_parallels)

    # Autographs section (no <ul> there) should have NO parallels leaking over
    check("SS-1 has no leaked parallels", by_card.get("SS-1", {}).get("parallels") == [])
    check("SS-1 tagged Autograph", by_card.get("SS-1", {}).get("attributes") == "Autograph")

    print()
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    else:
        print(f"All checks passed. {len(rows)} rows parsed.")


if __name__ == "__main__":
    run()
