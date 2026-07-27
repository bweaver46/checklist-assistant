"""
Regression test for a real Beckett parsing bug found 2026-07-26
(Brandon, real extraction against 2026 Topps Series 1/2 Baseball):
card numbers that mix letters and digits with NO hyphen (e.g. "41T",
"US175") weren't recognized as card numbers at all, so the whole line
("41T Ken Griffey Jr.") landed in the Player field instead of
splitting card_number="41T", player="Ken Griffey Jr.".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_unhyphenated_card_numbers.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check("9 rows parsed", len(rows) == 9)

    by_card = {r["card_number"]: r for r in rows}

    check("41T card_number extracted", "41T" in by_card)
    check("41T player correct", by_card.get("41T", {}).get("player") == "Ken Griffey Jr.")
    check("41T team correct", by_card.get("41T", {}).get("team") == "Seattle Mariners")

    check("US175 card_number extracted", "US175" in by_card)
    check("US175 player correct", by_card.get("US175", {}).get("player") == "Mike Trout")

    check("700 card_number extracted", "700" in by_card)
    check("700 player correct", by_card.get("700", {}).get("player") == "Shohei Ohtani")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print(f"\nAll checks passed. {len(rows)} rows parsed.")


if __name__ == "__main__":
    run()
