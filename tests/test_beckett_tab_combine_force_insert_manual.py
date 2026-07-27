from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_road_to_opening_day_combined_tabs.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html, force_new_insert_for_all_h3=True)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    by_card = {r["card_number"]: r for r in rows}

    check("Base card 1 has blank Insert", by_card.get("1", {}).get("insert") == "")
    check("Base card 2 has blank Insert", by_card.get("2", {}).get("insert") == "")
    check(
        "plain Autograph card gets Insert='Autographs', not blank",
        by_card.get("A-AJ", {}).get("insert") == "Autographs",
    )
    check(
        "plain Autograph attributes is just 'Autograph'",
        by_card.get("A-AJ", {}).get("attributes") == "Autograph",
    )
    check(
        "Dual Autographs gets its OWN Insert despite sharing the 'A-' prefix",
        by_card.get("A-AH", {}).get("insert") == "Dual Autographs",
    )
    check(
        "Dual Autographs attributes no longer duplicates the subsection name",
        by_card.get("A-AH", {}).get("attributes") == "Autograph",
    )

    # Sanity: without the flag, the OLD prefix-based behavior should
    # still hold (Dual Autographs folds into attributes, matching the
    # normal aggregate-tab pages this flag must NOT affect).
    rows_normal = parse_beckett_checklist(html, force_new_insert_for_all_h3=False)
    by_card_normal = {r["card_number"]: r for r in rows_normal}
    check(
        "flag=False preserves old subsection-folding behavior",
        by_card_normal.get("A-AH", {}).get("insert") == "Autographs"
        and "Dual Autographs" in by_card_normal.get("A-AH", {}).get("attributes", ""),
    )

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
