"""
Regression test for a real Beckett parsing bug found 2026-07-26
(Brandon, real 2026 Topps Series 1 data): "Base - Vintage Stock
Variations" / "Base - Clear Variation" style headings correctly merge
onto the matching Base Set row as extra parallel tuples (confirmed
intentional design - Brandon: "yes it should treat variations as a
parallel"), but the caption's "All cards are /99" / "All cards are
/10" note - which states the serial for the WHOLE section - was being
silently discarded, so the merged parallel always landed with a blank
serial even when the page clearly states one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_base_variation_all_cards_serial.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check("only the 2 real Base Set rows exist (no extra rows from variations)", len(rows) == 2)

    row10 = next((r for r in rows if r["card_number"] == "10"), None)
    check("card 10 found", row10 is not None)

    parallels = dict(row10["parallels"]) if row10 else {}
    check("Vintage Stock Variations merged with serial 99", parallels.get("Vintage Stock Variations") == "99")
    check("Clear Variation merged with serial 10", parallels.get("Clear Variation") == "10")
    check(
        "Golden Mirror Variation merged with blank serial (none stated on the page)",
        parallels.get("Golden Mirror Variation") == "",
    )

    row11 = next((r for r in rows if r["card_number"] == "11"), None)
    check("card 11 (not in any variation list) has no merged parallels", row11 is not None and row11["parallels"] == [])

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print(f"\nAll checks passed. {len(rows)} rows parsed.")


if __name__ == "__main__":
    run()
