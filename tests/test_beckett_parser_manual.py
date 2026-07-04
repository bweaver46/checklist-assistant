from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2025_bowman_baseball.html"


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

    # Base Set - plain numbered cards, no insert, RC flag present
    check("card 1 insert blank", by_card.get("1", {}).get("insert") == "")
    check("card 1 player", by_card.get("1", {}).get("player") == "Mike Trout")
    check("card 1 team", by_card.get("1", {}).get("team") == "Los Angeles Angels")
    check("card 4 RC tagged", by_card.get("4", {}).get("attributes") == "RC")
    check("card 6 RC tagged", by_card.get("6", {}).get("attributes") == "RC")
    check("card 50 RC tagged (parens style)", by_card.get("50", {}).get("attributes") == "RC")
    check("card 7 no RC", by_card.get("7", {}).get("attributes") == "")
    check("card 51 (continuation across h4)", "51" in by_card)
    check("card 52 (continuation across h4)", "52" in by_card)

    # Prospects
    check("BP-1 insert name", by_card.get("BP-1", {}).get("insert") == "Bowman Prospects")

    # Autographs - Autograph tag auto-added
    check("BDA-JB tagged Autograph", by_card.get("BDA-JB", {}).get("attributes") == "Autograph")
    check("BDA-JB combined player", by_card.get("BDA-JB", {}).get("player") == "Bobby Witt Jr. / Jac Caglianone")
    check("BDA-JB team", by_card.get("BDA-JB", {}).get("team") == "Kansas City Royals")

    # UAC-1 merge: declared count 1 -> all 24 signers combined into ONE row
    uac_rows = [r for r in rows if r["card_number"] == "UAC-1"]
    check("UAC-1 exactly one row", len(uac_rows) == 1)
    if uac_rows:
        names = uac_rows[0]["player"].split(" / ")
        check("UAC-1 has 24 names", len(names) == 24)
        check("UAC-1 first name correct", names[0] == "Konnor Griffin")
        check("UAC-1 last name correct", names[-1] == "Walker Jenkins")
        check("UAC-1 tagged Autograph", uac_rows[0]["attributes"] == "Autograph")

    # All America Game Autographs - declared count 5, NOT merged, no card numbers
    no_number_auto_rows = [r for r in rows if r["insert"] == "All America Game Autographs" and not r["card_number"]]
    check("All America Game has 5 separate rows", len(no_number_auto_rows) == 5)
    check(
        "All America Game row has team",
        any(r["player"] == "Carter Johnson" and r["team"] == "Miami Marlins" for r in no_number_auto_rows),
    )

    # Buyback Autographs - no card number, no team, NOT merged (count 11 != 1)
    buyback_rows = [r for r in rows if r["insert"] == "Bowman Buyback Autographs"]
    check("Buyback has 11 separate rows", len(buyback_rows) == 11)
    check("Buyback row has blank team", all(r["team"] == "" for r in buyback_rows))
    check(
        "Buyback row has correct name, tagged Autograph",
        any(r["player"] == "Andre Dawson" and r["attributes"] == "Autograph" for r in buyback_rows),
    )

    # Rookies and Veterans - "35 cards.<br>Retail only." caption must not leak into data
    check("No stray 'Retail only' row", not any("Retail only" in r["player"] for r in rows))
    check("PRV-AP present", "PRV-AP" in by_card)

    # Inserts category - no Autograph auto-tag
    check("Anime card has no Autograph tag", by_card.get("BA-1", {}).get("attributes") == "")
    check("Anime insert name", by_card.get("BA-1", {}).get("insert") == "Anime")

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
