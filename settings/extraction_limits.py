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

# Player-mode team fetching (added 2026-07-22): rather than fetching
# every single row's team (a player's checklist can span tens of
# thousands of rows across a long career) or caching one team for their
# whole career (wrong for anyone who changed teams), sample this many
# rows per distinct year first. If they all agree, that year's whole
# checklist uses the sampled team with no further fetches. If they
# disagree (a mid-season trade), every remaining row in that year gets
# fetched individually instead of guessing which side of the trade it
# falls on. See scraper/browser_manager.py's sample_team_by_year logic.
TEAM_SAMPLE_SIZE_PER_YEAR = 3

