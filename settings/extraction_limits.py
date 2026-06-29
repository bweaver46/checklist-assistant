"""
Safety caps for extraction. These exist only to stop a runaway loop if
pagination detection ever breaks (e.g. the site changes its HTML and
has_next_page() starts returning True forever) - they are not meant to
be hit during normal use. If you're running searches bigger than this,
raise the number.
"""

# At ~50 rows/page, 2000 pages is 100,000 rows - comfortably above any
# real BuySportsCards search while still acting as a genuine safety net.
MAX_PAGES = 2000
