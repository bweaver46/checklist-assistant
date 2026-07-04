from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2025_donruss_clearly_labeled.html"


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

    labeled_parallels = [
        ("Clearly Rated Prospects Black", "10"),
        ("Clearly Rated Prospects Techno", "5"),
        ("Clearly Rated Prospects Platinum", "1"),
    ]

    # Card 100 (Base Set) unaffected by the label that comes much later
    check("card 100 keeps Base Set's own parallels", by_card.get("100", {}).get("parallels") == [("Green Laser", "")])

    # Cards 101-103 sit right after the label heading, in the middle of
    # the "Rated Prospects" h3's own scope - insert stays blank,
    # subsection tag still applies, parallels now carry the label
    check("card 101 insert still blank", by_card.get("101", {}).get("insert") == "")
    check("card 101 still tagged Rated Prospects subsection", by_card.get("101", {}).get("attributes") == "Rated Prospects")
    check("card 101 parallels are labeled correctly", by_card.get("101", {}).get("parallels") == labeled_parallels)
    check("card 103 parallels are labeled correctly", by_card.get("103", {}).get("parallels") == labeled_parallels)

    # category/section state must be completely undisturbed by the label heading
    check("SS-1 still parses normally afterward", by_card.get("SS-1", {}).get("insert") == "Signature Series")
    check("SS-1 attributes just Autograph, no bleed from label", by_card.get("SS-1", {}).get("attributes") == "Autograph")

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
