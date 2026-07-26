from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2026_pristine_no_checklist_suffix.html"


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

    check("Base Set card 1 insert blank", by_card.get("1", {}).get("insert") == "")
    check(
        "Pristine Autographs (no 'Checklist' suffix) still gets its own Insert",
        by_card.get("PA-AF", {}).get("insert") == "Pristine Autographs",
    )
    check(
        "Pristine Autographs attributes doesn't leak insert name",
        by_card.get("PA-AF", {}).get("attributes") == "Autograph",
    )
    check(
        "Spotless Signatures is its own Insert, not folded into Pristine Autographs",
        by_card.get("SS-BB", {}).get("insert") == "Spotless Signatures",
    )
    check(
        "Italics (single word, no dash-prefix even) still its own Insert",
        by_card.get("I-BB", {}).get("insert") == "Italics",
    )
    check(
        "Monogram under new h2 category is its own Insert",
        by_card.get("M-1", {}).get("insert") == "Monogram",
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
