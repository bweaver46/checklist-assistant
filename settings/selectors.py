"""
CSS selectors for the BuySportsCards inventory page.

*** These are placeholder guesses. They have NOT been confirmed against ***
*** the live BuySportsCards DOM.                                        ***

To fix: log in, run a search, right-click a row -> Inspect, and find the
real selectors for the row container, each field within a row, and the
Next/pagination button. Update the values below. Nothing else in the
codebase needs to change.
"""

ROW_SELECTOR = "table tbody tr"

# Selectors are relative to a single row element.
FIELD_SELECTORS = {
    "name": "td:nth-child(1)",
    "card_number": "td:nth-child(2)",
    "set": "td:nth-child(3)",
    "variant": "td:nth-child(4)",
    "variant_name": "td:nth-child(5)",
    "attributes": "td:nth-child(6)",
}

NEXT_BUTTON_SELECTOR = "button[aria-label='Next']"
