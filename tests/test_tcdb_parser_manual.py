from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.tcdb_parser import parse_tcdb_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tcdb_1972_topps_sample.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_tcdb_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    by_card = {r["card_number"]: r for r in rows}

    # Team card - descriptive name (no player link), tag TC
    check("card 1 exists", "1" in by_card)
    check("card 1 descriptive name, tag stripped", by_card.get("1", {}).get("player") == "World Champions (Pittsburgh Pirates)")
    check("card 1 attributes TC", by_card.get("1", {}).get("attributes") == "TC")
    check("card 1 team", by_card.get("1", {}).get("team") == "Pittsburgh Pirates")

    # Checklist card - descriptive name, no team, tag CL
    check("card 4 descriptive name, tag stripped", by_card.get("4", {}).get("player") == "1st Series Checklist: 1-132")
    check("card 4 no team", by_card.get("4", {}).get("team") == "")
    check("card 4 attributes CL", by_card.get("4", {}).get("attributes") == "CL")

    # Plain card, no tags
    check("card 5 player", by_card.get("5", {}).get("player") == "John Bateman")
    check("card 5 attributes blank", by_card.get("5", {}).get("attributes") == "")

    # Multi-player card with a non-VAR note - note appended to attributes
    check(
        "card 14 multi-player name, tags stripped",
        by_card.get("14", {}).get("player") == "Phillies 1972 Rookie Stars (Pete Koegel / Mike Anderson / Wayne Twitchell)",
    )
    check(
        "card 14 attributes has RS, RC, and the note",
        by_card.get("14", {}).get("attributes") == "RS, RC, RC for Anderson only",
    )

    # Lettered VAR pair (18a/18b) grouped into one row under "18"
    check("18a/18b grouped under 18", "18" in by_card and "18a" not in by_card and "18b" not in by_card)
    check(
        "card 18 has both VAR parallels, no serial",
        by_card.get("18", {}).get("parallels") == [
            ("Yellow under bottom of C and S", ""),
            ("Green under bottom of C and S", ""),
        ],
    )
    check("card 18 no VAR in attributes", "VAR" not in by_card.get("18", {}).get("attributes", ""))
    check("card 18 attributes blank (no other tags)", by_card.get("18", {}).get("attributes") == "")

    # Lettered VAR pair WITH an extra RC tag (29a/29b) - RC should still show up once
    check("29a/29b grouped under 29", "29" in by_card and "29a" not in by_card and "29b" not in by_card)
    check("card 29 attributes RC (not duplicated)", by_card.get("29", {}).get("attributes") == "RC")
    check(
        "card 29 has both VAR parallels",
        by_card.get("29", {}).get("parallels") == [
            ("Yellow under bottom of C and S", ""),
            ("Green under bottom of C and S", ""),
        ],
    )

    # Plain RC tag, no note, no letter
    check("card 56 attributes RC", by_card.get("56", {}).get("attributes") == "RC")
    check("card 56 no parallels", by_card.get("56", {}).get("parallels") == [])

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
