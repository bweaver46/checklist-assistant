"""
Tests for scraper/site_detect.py's parse_beckett_url() - added
2026-07-26 so Extract Beckett Checklist can pre-fill Product/Sport
from the article URL instead of Brandon typing them every time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.site_detect import parse_beckett_url, detect_source, BSC, BECKETT, TCDB


def run():
    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check(
        "single-word brand",
        parse_beckett_url("https://www.beckett.com/news/2025-bowman-baseball-cards/")
        == ("2025 Bowman", "Baseball"),
    )
    check(
        "multi-word brand/set",
        parse_beckett_url("https://www.beckett.com/news/2025-topps-diamond-icons-baseball-cards/")
        == ("2025 Topps Diamond Icons", "Baseball"),
    )
    check(
        "brand only, no set name",
        parse_beckett_url("https://www.beckett.com/news/1972-topps-baseball-cards/")
        == ("1972 Topps", "Baseball"),
    )
    check(
        "no trailing slash still works",
        parse_beckett_url("https://www.beckett.com/news/2025-bowman-baseball-cards")
        == ("2025 Bowman", "Baseball"),
    )
    check(
        "non-matching slug returns None",
        parse_beckett_url("https://www.beckett.com/news/some-other-article/") is None,
    )
    check(
        "unrelated page returns None",
        parse_beckett_url("https://www.beckett.com/") is None,
    )

    # detect_source still routes correctly (unchanged, just confirming
    # the new import didn't break anything in the same module).
    check("detect_source still finds beckett", detect_source("https://www.beckett.com/news/x/") == BECKETT)
    check("detect_source still finds bsc", detect_source("https://www.buysportscards.com/x") == BSC)
    check("detect_source still finds tcdb", detect_source("https://www.tcdb.com/x") == TCDB)
    check("detect_source still returns None for unknown", detect_source("https://example.com") is None)

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print("All tests passed.")


if __name__ == "__main__":
    run()
