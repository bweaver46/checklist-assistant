from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import extract_flat_checklist_html, parse_beckett_checklist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_rip_night_full_page.html"


def run():
    full_html = FIXTURE.read_text(encoding="utf-8")
    slice_html = extract_flat_checklist_html(full_html)

    print("--- isolated slice ---")
    print(slice_html)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check("isolation found a slice at all", slice_html is not None)
    check("nav menu excluded", "Rookie Cards" not in slice_html)
    check("intro prose / shop links excluded", "was held on February" not in slice_html)
    check("footer boilerplate excluded", "Protect Your Collection" not in slice_html)
    check("related articles excluded", "Related articles" not in slice_html)
    check("comments excluded", "rarity or print run" not in slice_html)
    check("actual checklist content present", "Shohei Ohtani" in slice_html)

    rows = parse_beckett_checklist(slice_html)
    print("--- parsed rows ---")
    for r in rows:
        print(r)

    check("exactly 3 rows parsed (no nav/footer contamination)", len(rows) == 3)
    by_card = {r["card_number"]: r for r in rows}
    check(
        "BB1 parsed cleanly with the parallel list attached",
        by_card.get("BB1", {}).get("player") == "Shohei Ohtani"
        and ("Blue", "") in by_card.get("BB1", {}).get("parallels", []),
    )
    check("RC suffix still recognized", by_card.get("BB19", {}).get("attributes") == "RC")

    # No boundary found at all -> must return None, not guess.
    check(
        "returns None when there's no Checklist-titled heading to anchor on",
        extract_flat_checklist_html("<h2>Random Page</h2><p>hello</p>") is None,
    )
    check(
        "returns None when the footer boundary is missing",
        extract_flat_checklist_html("<h2>2026 Foo Checklist</h2><p>1 A, B</p>") is None,
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
