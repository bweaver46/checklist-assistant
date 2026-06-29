# Checklist Assistant — Project Vision & Technical Design

## Purpose

Checklist Assistant is a desktop application designed to automate the process
of creating trading card checklist CSV files from online sources.

The primary goal is to eliminate repetitive manual work when building
checklists by allowing the user to browse normally, then letting the
application collect, organize, and export the data into a standardized
format.

The first supported source is BuySportsCards, but the application is
intentionally being designed so additional sources can be added later.

## Overall Workflow

1. Open Checklist Assistant
2. Launch Browser
3. BuySportsCards opens
4. User logs in
5. User searches for a player
6. User applies filters (year, brand, etc.)
7. User clicks Extract Checklist
8. Checklist Assistant reads every page
9. Data is cleaned
10. Checklist CSV is generated
11. Ready for import into Check List Builder

The important concept is that Checklist Assistant never tries to perform the
search itself. The user is free to browse however they want. Checklist
Assistant simply extracts whatever is currently displayed.

## Why This Design?

Most web scrapers attempt to automate every click. That creates several
problems: login issues, CAPTCHAs, website updates, and complicated code.

Instead, Checklist Assistant lets the user perform the navigation. Once the
desired results are visible, the application takes over. This dramatically
simplifies the scraper while also making it much more reliable.

## Current Architecture

```
ChecklistAssistant/
    app/         Main application window
    scraper/     Website automation
    exporter/    CSV generation
    settings/    Configuration
    templates/   CSV templates
    docs/        Documentation
    tests/       Future testing
    workers/     Background tasks
```

Each folder has a single responsibility.

## Current Application

### Main Window

Built using PySide6. Current features:
- Launch Browser button
- Extract Checklist button
- Toolbar
- Status bar

The window itself contains almost no scraping logic. Its job is only to
respond to button clicks.

### Browser Manager

Responsible for controlling Playwright. Responsibilities include:
- Launch Chromium
- Keep browser alive
- Keep page alive
- Know current URL

Eventually it will also: read rows, click Next, navigate pages, and extract
card information.

The rest of the application never directly communicates with Playwright.
Everything goes through BrowserManager.

### Launch Browser Button

1. User clicks button
2. BrowserManager launches Chromium
3. BuySportsCards opens
4. Browser remains available

Eventually the browser will remain open for the entire session.

### Extract Checklist Button

Current purpose: verify communication between the application and
BrowserManager. Eventually it will become the primary command that starts
extraction.

## Current Milestones Completed

- [x] Project created
- [x] Python environment configured
- [x] Playwright installed
- [x] Chromium installed
- [x] PySide6 installed
- [x] Desktop application launches
- [x] Browser launches
- [x] Browser remains available
- [x] BrowserManager created
- [x] Extract button connected
- [x] Git repository initialized
- [x] Row counting (Phase 1)
- [x] Read one row / all rows on a page (Phase 1)
- [x] Pagination: detect and click Next, read all pages (Phase 2)
- [x] Raw CardRecord objects (Phase 3)
- [x] Raw CSV export (Phase 4)
- [x] Convert raw records to checklist template rows (Phase 5)
- [x] Merge parallels into one row per card (Phase 6)
- [x] Cleanup rules: remove redundant Base, normalize serials, dedupe (Phase 7, partial)
- [x] Final checklist CSV export (Phase 8)

## Confirmed Against Live Site (2026-06-28)

Selectors and field mapping were confirmed by inspecting the live,
logged-in BuySportsCards inventory table (via Claude in Chrome). Real
table structure:

- Rows: `table tbody tr.MuiTableRow-root.MuiTableRow-hover`
- Columns: checkbox, Name, Card #, Set, Variant (Base/Insert), Variant
  Name (the actual parallel/insert name), Attribute(s) (serial as
  `SN<digits>` and/or autograph flag `AU`), Add button
- Pagination: a `<nav>` with numbered page buttons (no real "Next"
  button exists - the arrow icons aren't `<button>` elements). Click
  current-page-number + 1 instead. Confirmed working live.

`settings/selectors.py` and `exporter/convert.py` have been updated and
are no longer placeholders. `tests/test_exporter_pipeline.py` uses
fake data shaped exactly like real confirmed rows (Mike Trout / 2026
Bowman / Anime insert / Rookie and Veteran Autographs Purple).

## Field Mapping Rules (per Brandon, 2026-06-28)

- `year`, `brand`: parsed out of the website's Set string (e.g. "2026
  Bowman" -> year="2026", brand="Bowman"). `set` keeps the full original
  string too.
- `insert`: the website's Variant Name, blank for Base. This is
  per-occurrence (insert_1, insert_2, ...), not a single scalar - the
  same card_number can have several Variant Name values that all need
  to merge into one checklist row.
- `sub_type`: derived from Attributes, also per-occurrence.
  - "AU" becomes "Autograph", UNLESS the word "Autograph" already
    appears in the set or that occurrence's insert text, in which case
    it's dropped as redundant.
  - "PR" (Print Run) is just an alternate label for the same concept as
    SN (Serial Numbered) - not printed on the card, not a distinct
    sub_type category. PR<digits> is treated exactly like SN<digits>:
    the number goes into `serial`, nothing goes into `sub_type`.
- `serial`: the digits from Attributes' "SN<digits>" or "PR<digits>" token.
- `type`, `sport`: not derivable from row data at all - the app now
  prompts for these once per extraction run (see `_prompt_for_context`
  in `app/main_window.py`).
- `team`: not present in row data, supplied via `context`. Optional -
  blank is fine.
- `section`: not present in row data either, supplied via `context`.
  Handles "continuation numbering" - e.g. a Prospects subsection that
  continues a base set's numbering (#101-200) rather than restarting at
  #1. The `set` and `card_number` stay exactly as the website gives
  them - never renumbered. The section name goes into `sub_type`
  instead. Asked for once per extraction run, since each run is already
  scoped to one search.
- A plain Base row (no attributes at all) is dropped entirely, UNLESS a
  Section is active, in which case it's kept with a blank insert so the
  section name doesn't get silently lost.
- Insert/parallel name standardization (Phase 7): hyphens are treated as
  spaces and whitespace is collapsed, so "Black-Wave" and "Black Wave"
  normalize to the same string and correctly dedupe/merge. NOT yet
  implemented: dropping a redundant trailing descriptor like "Refractor"
  ("Blue Mojo" vs "Blue Mojo Refractor") - the rule for *when* that's
  appropriate vs not still needs to come from Brandon.

Final CSV columns: type, sport, year, brand, set, card_number, player,
team, then insert_1/sub_type_1/serial_1, insert_2/sub_type_2/serial_2,
... expanded per row's occurrence count.

## Field Mapping Rules - Round 2 (per Brandon, 2026-06-29)

From reviewing the actual 564-row live extraction:

- `set` now holds brand only, year stripped out (e.g. "Bowman" not
  "2026 Bowman") - year already has its own column, no need to repeat it.
- `card_number`: "#" stripped. If the number has a trailing run of
  digits at the end (e.g. "T91-1", "TBC15", "12P5"), everything before
  that run is a prefix that gets prepended to insert_N - space
  separated, hyphen preserved exactly. Purely numeric numbers (e.g.
  "517") get no prefix. This runs AFTER insert-name normalization
  (hyphen-stripping etc.) so the prefix's own hyphen never gets
  accidentally stripped by that unrelated rule.
- Primary Player (new context field, optional): if the search is
  filtered to one player, typing their name here means any Name field
  containing other text (multi-player inserts, acronyms) keeps just
  that player's name as `player` and moves everything else into
  `sub_type`. If the name isn't found in a given row's Name field,
  nothing changes for that row - no data is ever silently dropped.
- A plain Base row is now droppable only if there's truly nothing to
  record at all: no attributes, no section, no card-number prefix, AND
  no Primary-Player leftover text.

## Field Mapping Rules - Round 3: Scalar Insert/Sub_Type (per Brandon, 2026-06-29)

After reviewing real output against the actual template (`sets-template-2.csv`),
the data model changed in an important way:

- **Insert and Sub_Type are now SCALAR** - one value per card, not
  per-print-version. Only Parallel/Serial repeat
  (parallel_1/serial_1, parallel_2/serial_2, ...).
- **Insert = whatever's common** across all of a card's print versions'
  Variant Name text (computed via longest common word-prefix, not
  hardcoded to any specific insert name). Using the real Anime example
  (#BA-23, four rows: "Anime", "Anime Black Refractors", "Anime Red
  Refractors", "Anime SuperFractors") -> Insert = "Anime".
- **Parallel = the leftover** after stripping that common prefix off
  each row's Variant Name, normalized (plural->singular only - see
  below). For the Anime example: "" (the plain Anime row - the base
  printing, contributes nothing), "Black Refractor", "Red Refractor",
  "SuperFractor".
- A row contributes a parallel_N/serial_N slot only if it has a
  non-blank leftover OR its own serial number. A row with neither
  (like the plain "Anime" row above) contributes nothing - no blank
  slot, indexing starts directly at parallel_1 with the first real
  parallel.
- **The "drop redundant trailing Refractor" rule has been REMOVED.**
  It directly conflicted with the real Anime data: "Black Refractors"
  needs to become "Black Refractor" (kept, singularized), not "Black"
  (dropped). Only plural->singular normalization remains (Refractors->
  Refractor, SuperFractors->SuperFractor, Prizms->Prizm) - nothing
  gets deleted anymore.
- **Brand/Set split changed**: brand is just the FIRST WORD after the
  year; everything else is set. "2026 Panini Prizm" -> brand="Panini",
  set="Prizm". "2026 Bowman" -> brand="Bowman", set="" (blank - that's
  fine, better than repeating the brand).
- card_number's prefix (e.g. "T91-") still prepends to Insert (now the
  scalar Insert, not a per-occurrence value), applied AFTER plural
  normalization so the prefix's own hyphen is never touched by the
  hyphen-to-space rule.

## Brand/Set Exception Spreadsheet (per Brandon, 2026-06-29)

`settings/brand_set_exceptions.csv` overrides the default "first word
after year is brand, the rest is set" rule for product lines that
don't follow that pattern. Editable directly in Excel/Numbers - just
save back as CSV, no code changes needed.

Columns: `pattern, brand, set`. `pattern` is matched word-by-word
against the start of the Set text (after the year is stripped),
case-insensitive. Longer patterns are checked first.

Current entries:
| pattern | brand | set |
|---|---|---|
| Finest | Topps | Finest |
| Topps Now | Topps | Topps Now |
| Bowman's Best | Bowman | Bowman's Best |
| Stadium Club | Topps | Stadium Club |
| President's Choice | President's Choice | President's Choice |
| Lauran Taylor | Lauran Taylor | Lauran Taylor |
| Upper Deck | Upper Deck | Upper Deck |
| UD | Upper Deck | Upper Deck |

Fixed a real gap (2026-06-29): exception matches now preserve any
words AFTER the matched pattern instead of discarding them - e.g. "UD
Series 1" correctly becomes "Upper Deck Series 1", not just
"Upper Deck" with "Series 1" silently dropped.

Note some of these deliberately repeat the brand inside set (e.g.
"Topps Now" / "Topps Now") - that's intentional per Brandon, an
exception to the general "don't repeat" rule, because that repetition
IS the correct full product name in these specific cases.

To add more: open the CSV, add a row, save. No restart needed beyond
the next time Extract Checklist runs (the file is cached per-run, not
per-app-launch).

## Other Fixes (2026-06-29)

- Final CSV is now sorted by brand (then set, year, card_number as
  stable secondary keys) before export.
- Page extraction safety cap raised from 200 to 2000
  (`settings/extraction_limits.py`, MAX_PAGES) - a large search was
  hitting the old cap and stopping early.

## Per-Card Team Fetching (per Brandon, 2026-06-29)

Team is NOT shown in the search results table at all - confirmed by
inspecting it live. It only appears on the "Sell Your Card" detail page
reached by clicking a row's "Add" control (URL pattern
`/sellers/sell-your-card/add/<id>`). That page only opens BSC's
listing-creation FORM - it does not submit or create anything unless a
submit button is explicitly clicked, which this app never does, so
navigating into it and back is safe. Brandon confirmed clicking Back
restores the exact same results page/scroll position.

Team's label ("Team:") and value sit in two sibling `<div>`s, each
holding a generic `<h6>` with a dynamically-generated class name (e.g.
"jss156988") that will change between site builds - so the label text
itself is used to find it, not the class.

This is now an explicit opt-in choice (`_prompt_fetch_team` in
`app/main_window.py`), NOT a silent default, because the cost is real:
one extra full page visit per row instead of one per ~50 rows. Good for
a full-set pull spanning many teams; not worth it for a single-player
search where Team is constant - use the manual Team prompt instead for
those. If a row's team IS fetched, it overrides the manual Team value
for that row; otherwise the manual value is used as a fallback.

Not yet confirmed: whether clicking "Add" hundreds/thousands of times
rapidly raises any rate-limiting or anti-bot flag on BSC's side. Test
on a moderate-size batch before trying this on a huge multi-thousand-
card full-set pull.

Also noted while inspecting this: BSC's Variant column can show
"Parallel" as a third category (not just "Base"/"Insert") - e.g.
"Parallel (Optic Gold Velocity)". This doesn't currently break
anything (treated the same as "Insert" - any non-Base variant uses its
Variant Name as-is), but worth keeping in mind if more Parallel-
specific quirks turn up.

## Per-Player Team Caching (per Brandon, 2026-06-29)

Brandon's own observation: most rows in any set are parallels of the
SAME player, not unique lookups. Fetching Team via "Add" for every
single row was wasteful when the vast majority of rows share a player
with a row already looked up. Fixed by caching Team per distinct Name
text for the whole extraction run (`BrowserManager._team_cache`,
reset at the start of each `extract_all_pages()` call) - "Add" now
only gets clicked once per distinct player name, not once per row.
Tested with lightweight fakes (no real browser) in
`tests/test_browser_manager.py`.

## Open Questions

1. The "Blue Mojo" vs "Blue Mojo Refractor" rule - when is a trailing
   descriptor word like "Refractor" redundant and droppable vs needed?
2. Phase 7's exact set of standardization rules may grow as more naming
   inconsistencies turn up in real data.
3. The full pipeline has NOT yet been run end-to-end against a live page
   inside the actual desktop app - only validated via direct DOM
   inspection and unit tests against realistically-shaped fake data.

## First Live Test Result (2026-06-28)

Ran for real against a live Mike Trout / 2026 Bowman search via the
Sell Cards comp-browse view: **564 raw rows extracted across multiple
pages, merged down to 68 unique cards, no errors.** Full pipeline
(pagination, field mapping, merging, cleanup, CSV export) confirmed
working end to end.

Fixes made from that first run:
- Type prompt removed entirely - BSC only sells sports cards, so Type
  is now hardcoded to "Sports" rather than asked for each time.
- Section prompt reworded - it wasn't clear what it was for or when to
  use it. Now explicitly says "leave blank for almost every search."
- Status bar and terminal now print the CSVs' full absolute path
  (previously just the filename, which looked like nothing was saved -
  the files were there all along, just not obviously located).

## Next Milestone

Check the actual `checklist_export.csv` and `raw_export.csv` contents
from that 564-row run against the real BuySportsCards listing to spot
any remaining mapping issues at this kind of volume.

## Following Milestones

1. Read first row
2. Read every row
3. Read next page
4. Repeat until finished
5. Collect all cards
6. Export raw CSV
7. Convert to Checklist CSV
8. Merge parallels
9. Clean serial numbering
10. Finished checklist

## Long-Term Vision

Checklist Assistant should eventually support multiple sources, e.g.:
BuySportsCards, Beckett, Cardboard Connection, Trading Card Database, Topps,
Panini, Upper Deck.

Each source will have its own scraper while sharing the same exporter.

## Export System

The exporter should be independent of the scraper.

- Input: list of cards
- Output: Checklist CSV

This allows any scraper to reuse the same exporter.

## Checklist Rules

Checklist Assistant will automatically:
- Merge parallels into a single row
- Normalize serial numbers
- Remove duplicate entries
- Apply Brandon's checklist format
- Avoid redundant naming
- Produce CSV files ready for Check List Builder

## Development Philosophy

The project is intentionally being developed in extremely small steps.
Every task should:
- Take approximately five minutes
- Have one objective
- Be tested immediately
- Be committed to Git after success

This allows rapid progress while minimizing bugs and making troubleshooting
straightforward.

## Design Philosophy

Checklist Assistant is not intended to be a one-off script. It is being
developed as a long-term desktop application that can grow over time.

The emphasis is on: clean architecture, modular components, reusable code,
stable releases, and easy maintenance.

## Current Version

**Version: 0.10.1 (Per-player team cache; HANDOFF_1.md added)**

Current capabilities: everything in v0.10.0, plus:
- Team lookups cached per distinct player Name for the whole
  extraction run - "Add" only clicked once per distinct player, not
  once per row (most rows in a set are parallels of the same player)
- `docs/HANDOFF_1.md` - comprehensive handoff document for picking
  this project back up cold

Next goal (v1.0.0): keep validating against real, larger-volume CSV
output and fix whatever else turns up.
