from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2025_donruss_rated_prospects.html"


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

    base_parallels = [("Green Laser", ""), ("Orange Laser", "299")]
    rp_parallels = [("Black", "10"), ("Techno", "5"), ("Platinum", "1/1")]

    check("card 100 insert blank (still Base Set)", by_card.get("100", {}).get("insert") == "")
    check("card 100 no subsection tag", by_card.get("100", {}).get("attributes") == "")
    check("card 100 has Base Set parallels", by_card.get("100", {}).get("parallels") == base_parallels)

    check("card 101 insert STILL blank, not 'Rated Prospects'", by_card.get("101", {}).get("insert") == "")
    check("card 101 tagged with subsection in attributes", by_card.get("101", {}).get("attributes") == "Rated Prospects")
    check("card 101 has ITS OWN parallels, not Base Set's", by_card.get("101", {}).get("parallels") == rp_parallels)
    check("card 103 same subsection tag", by_card.get("103", {}).get("attributes") == "Rated Prospects")

    # Real "...Checklist" h3 still works as a normal Insert, no bleed-over
    check("SS-1 insert is Signature Series, not tagged Rated Prospects", by_card.get("SS-1", {}).get("insert") == "Signature Series")
    check("SS-1 attributes is just Autograph", by_card.get("SS-1", {}).get("attributes") == "Autograph")
    check("SS-1 no parallels leaked from Rated Prospects", by_card.get("SS-1", {}).get("parallels") == [])

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
