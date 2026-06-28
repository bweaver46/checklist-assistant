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
- `team`: still unresolved - not in the row data, not yet asked for.
  Left blank.
- A plain Base row (no attributes at all) is dropped entirely. A Base
  row that does carry an attribute (e.g. a serial number) is kept with
  insert left blank.

Final CSV columns: type, sport, year, brand, set, card_number, player,
team, then insert_1/sub_type_1/serial_1, insert_2/sub_type_2/serial_2,
... expanded per row's occurrence count.

## Open Questions

1. Where should `team` come from?
2. Phase 7's "continuation numbering" and "standardize names" rules
   still aren't implemented.
3. The full pipeline has NOT yet been run end-to-end against a live page
   inside the actual desktop app - only validated via direct DOM
   inspection and unit tests against realistically-shaped fake data.

## Next Milestone

Run Extract Checklist for real against a live BuySportsCards search
and check the resulting CSVs.

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

**Version: 0.5.0 (Field mapping rules applied: per-occurrence insert/sub_type/serial, year/brand parsed from set, Type/Sport prompt)**

Current capabilities:
- Launches as a desktop application
- Opens a Playwright-controlled Chromium browser
- Maintains a BrowserManager that owns the browser instance
- Reads every row across every page using selectors confirmed against
  the real, logged-in BuySportsCards table (Phases 1-2)
- Prompts for Sport and Type once per extraction run
- Converts raw rows into checklist rows with per-occurrence
  insert/sub_type/serial, parses year/brand from the set string, drops
  plain Base rows, applies the Autograph-dedup rule, merges occurrences
  by card identity, and exports both a raw debug CSV and a final
  checklist CSV (Phases 3-8)

Not yet done: a real, live, end-to-end run of Extract Checklist inside
the actual desktop app. See "Open Questions" above.

Next goal (v0.6.0): run Extract Checklist for real, validate output
against the live site, and resolve the remaining open questions.
