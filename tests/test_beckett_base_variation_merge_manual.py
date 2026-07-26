from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2026_chrome_base_variations.html"


def run():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_beckett_checklist(html)

    for r in rows:
        print(r)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check("no duplicate rows - exactly 5 (Base Set count)", len(rows) == 5)

    by_card = {r["card_number"]: r for r in rows}

    check("card 1 stays a single row with all 3 variations merged",
          by_card.get("1", {}).get("parallels") == [
              ("Lightboard Variations", ""),
              ("Image Variations", ""),
              ("Award Winner Variations", "25"),
          ])
    check("card 2 only got Lightboard (not in the other two sections)",
          by_card.get("2", {}).get("parallels") == [("Lightboard Variations", "")])
    check("card 100 skipped Image Variations but has Award Winner /25",
          by_card.get("100", {}).get("parallels") == [
              ("Lightboard Variations", ""),
              ("Award Winner Variations", "25"),
          ])
    check("variation rows never created their own insert",
          all(r["insert"] == "" for r in rows))

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
