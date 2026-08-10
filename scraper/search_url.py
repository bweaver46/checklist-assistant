"""
Builds a BuySportsCards inventory-search URL directly from filter
values, instead of Brandon manually navigating and clicking through
BSC's own search/filter UI first (Brandon, 2026-08-08 - confirmed BSC
encodes every filter as a URL query param, from three real URLs he
captured after applying filters by hand on the live site).

CONFIRMED param names (present in Brandon's captured URLs, or verified
by a live test - "Panini Diamond Kings" -> setName[]=panini-diamond-
kings worked 2026-08-08):
    q             - free-text keyword search
    sport[]       - sport slug (e.g. "baseball")
    year[]        - year, plain (not slugified)
    setName[]     - set slug (e.g. "topps-chrome", "panini-diamond-kings")
    variant[]     - "insert" / "base" / "parallel"
    variantName[] - specific insert/parallel name slug (e.g. "hobby-masters")
    p             - page number, 0-indexed (already used elsewhere for
                    pagination - see BrowserManager.navigate_to_page,
                    which reads/writes this same "p=" param)

UNVERIFIED param names below - Brandon asked for these as fields on the
search-builder form, but none of his three captured URLs used them, so
these are a best guess following the same "pluralized array" pattern as
the confirmed params above. Treat any card built using these as needing
a live look before trusting it - a wrong param name won't error, BSC
will most likely just silently ignore it and return results unfiltered
by that field, which only shows up by actually checking the page:
    attribute[]   - card attribute (e.g. autograph, relic, insert-only)
    player[]      - player name
    team[]        - team name
    cardNumber[]  - card number
"""

from __future__ import annotations

import re
from urllib.parse import quote

BASE_URL = "https://www.buysportscards.com/sellers/inventory"

# field key (as used in the search-builder form) -> BSC query param name
FIELD_PARAMS: dict[str, str] = {
    "sport": "sport[]",
    "year": "year[]",
    "set": "setName[]",
    "variant": "variant[]",
    "variant_name": "variantName[]",
    "attribute": "attribute[]",     # unverified - see module docstring
    "player": "player[]",           # unverified - see module docstring
    "team": "team[]",               # unverified - see module docstring
    "card_number": "cardNumber[]",  # unverified - see module docstring
}

UNVERIFIED_FIELDS = {"attribute", "player", "team", "card_number"}


def slugify(value: str) -> str:
    """"Topps Chrome" -> "topps-chrome", "Panini Diamond Kings" ->
    "panini-diamond-kings". Lowercase, non-alphanumeric runs become a
    single hyphen, no leading/trailing hyphen."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def build_search_url(fields: dict[str, str]) -> str:
    """fields must include "keyword" (BSC's free-text search box - the
    only field Brandon wants required); any of the FIELD_PARAMS keys
    are optional and skipped when blank. Year is passed through as-is
    (not slugified - it's already just digits). Returns a full BSC
    inventory-search URL at page 0 (BSC's own URLs are 0-indexed for
    the first page - confirmed from Brandon's captured examples)."""
    keyword = (fields.get("keyword") or "").strip()

    params: list[tuple[str, str]] = [
        ("myInventory", "false"),
        ("p", "0"),
        ("q", keyword),
    ]
    for field_key, param_name in FIELD_PARAMS.items():
        value = (fields.get(field_key) or "").strip()
        if not value:
            continue
        encoded_value = value if field_key == "year" else slugify(value)
        params.append((param_name, encoded_value))

    query = "&".join(f"{name}={quote(value)}" for name, value in params)
    return f"{BASE_URL}?{query}"
