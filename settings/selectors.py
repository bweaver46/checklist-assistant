"""
CSS selectors for the BuySportsCards inventory page.

Confirmed 2026-06-28 against the live "/sellers/inventory" market-browse
table (Material-UI based) while logged in. If BuySportsCards changes their
frontend framework or table markup, these will need to be re-confirmed -
that's the whole point of keeping them isolated here instead of scattered
through the codebase.

Table structure (8 <td> per row):
    [0] checkbox (unused)
    [1] Name
    [2] Card #
    [3] Set
    [4] Variant       - "Base" or "Insert"
    [5] Variant Name   - the actual parallel/insert name, e.g.
                          "Anime Red Refractors". "-" when not applicable.
    [6] Attribute(s)   - e.g. "-", "SN150", "AU", "AU, SN150"
    [7] Add button (unused)
"""

ROW_SELECTOR = "table tbody tr.MuiTableRow-root.MuiTableRow-hover"

# Selectors are relative to a single row element. nth-child is 1-indexed
# and includes the leading checkbox column, so "name" is the 2nd <td>.
FIELD_SELECTORS = {
    "name": "td:nth-child(2)",
    "card_number": "td:nth-child(3)",
    "set": "td:nth-child(4)",
    "variant": "td:nth-child(5)",
    "variant_name": "td:nth-child(6)",
    "attributes": "td:nth-child(7)",
}

# Pagination is a <nav><ul><li>...</li></ul></nav> with numbered page
# buttons (1, 2, 3 ... last) plus prev/next arrow icons at each end that
# are NOT real <button> elements (just <p><svg>), so they can't be
# reliably clicked or checked for "disabled" state. Instead, BrowserManager
# finds the current page via [aria-current="true"] and clicks the button
# for current+1, which is confirmed working against the live site.
PAGINATION_NAV_SELECTOR = "nav"

# Confirmed 2026-06-29 against the "Sell Your Card" detail page (reached
# by clicking "Add" on a row). Team's label and value sit in two SIBLING
# <div>s, each holding a generic <h6> with a dynamically-generated class
# (e.g. "jss156988") - that class WILL change between site builds, so
# matching on the literal label text "Team:" instead is the durable way
# to find it. The value is in the next sibling div.
TEAM_DETAIL_LABEL_SELECTOR = "h6:text-is('Team:')"
