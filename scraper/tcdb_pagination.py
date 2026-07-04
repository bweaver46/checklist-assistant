"""
TCDB Pagination

Builds the URL for a given page of a TCDB set checklist. Confirmed
against the live site (2026-07-04): pages use a ?PageIndex=N query
parameter on the same path; page 1 has no PageIndex param at all.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode


def tcdb_page_url(base_url: str, page_num: int) -> str:
    """'https://www.tcdb.com/Checklist.cfm/sid/72/1972-Topps', 2
    -> 'https://www.tcdb.com/Checklist.cfm/sid/72/1972-Topps?PageIndex=2'.
    page_num=1 always strips any existing PageIndex param instead of
    setting it to 1, matching how the live site links to its own first
    page."""
    parts = urlsplit(base_url)
    query = parse_qs(parts.query)
    query.pop("PageIndex", None)
    if page_num > 1:
        query["PageIndex"] = [str(page_num)]
    new_query = urlencode(query, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
