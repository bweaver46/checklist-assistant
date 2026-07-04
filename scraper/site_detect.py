"""
Site Detection

Identifies which supported site the browser is currently showing, so
Extract Checklist can route to the right parser automatically instead
of Brandon having to pick a source manually.
"""

from __future__ import annotations

from urllib.parse import urlparse

BSC = "bsc"
BECKETT = "beckett"
TCDB = "tcdb"


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
