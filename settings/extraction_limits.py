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

# Player-mode team fetching (added 2026-07-22, redesigned 2026-07-24 per
# Brandon): rather than fetching every single row's team (a player's
# checklist can span tens of thousands of rows across a long career) or
# caching one team for their whole career (wrong for anyone who changed
# teams), fetch the FIRST card of each distinct year and assume that
# team for the rest of the year. Recheck every TEAM_RECHECK_INTERVAL
# cards - if the recheck still matches, keep assuming and extend the
# interval; if it doesn't, a trade happened, so every remaining card in
# that year gets fetched individually instead of guessing. This catches
# trades that happen anywhere in the year, not just ones visible in the
# first few cards. See scraper/browser_manager.py's sample_team_by_year
# logic.
TEAM_RECHECK_INTERVAL = 50

