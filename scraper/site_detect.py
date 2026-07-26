"""
Site Detection

Identifies which supported site the browser is currently showing, so
Extract Checklist can route to the right parser automatically instead
of Brandon having to pick a source manually.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

BSC = "bsc"
BECKETT = "beckett"
TCDB = "tcdb"

BECKETT_SLUG_PATTERN = re.compile(r"^(\d{4})-(.+)-([a-z]+)-cards$")


def detect_source(url: str | None) -> str | None:
    """Return 'bsc', 'beckett', 'tcdb', or None if the current URL
    doesn't match a known source."""
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if "buysportscards.com" in host:
        return BSC
    if "beckett.com" in host:
        return BECKETT
    if "tcdb.com" in host:
        return TCDB
    return None


def parse_beckett_url(url: str) -> tuple[str, str] | None:
    """Derive (product, sport) from a Beckett checklist article URL's
    slug, e.g.
    'https://www.beckett.com/news/2025-bowman-baseball-cards/'
    -> ('2025 Bowman', 'Baseball')
    'https://www.beckett.com/news/2025-topps-diamond-icons-baseball-cards/'
    -> ('2025 Topps Diamond Icons', 'Baseball')

    Confirmed 2026-07-26 (Brandon): this info is always present in the
    URL, so it's used as a PRE-FILLED DEFAULT in the product/sport
    prompts rather than skipping them - Brandon can still edit or
    override before continuing, in case a slug doesn't fit this
    pattern (multi-word sport, unusual formatting, etc.). Returns None
    if the URL's last path segment doesn't match the expected
    '<year>-<words>-<sport>-cards' shape.
    """
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    slug = path.rsplit("/", 1)[-1]
    match = BECKETT_SLUG_PATTERN.match(slug)
    if not match:
        return None
    year, middle, sport = match.groups()
    product = f"{year} " + " ".join(word.capitalize() for word in middle.split("-"))
    return product, sport.capitalize()
