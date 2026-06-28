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

## Blocked On

The full pipeline above (Phases 1-8) is wired and unit-tested against
fake data (see tests/test_exporter_pipeline.py - reproduces the Mike
Trout merge example from this doc exactly). It has NOT been run against
the live BuySportsCards site yet, because:

1. `settings/selectors.py` (ROW_SELECTOR, FIELD_SELECTORS,
   NEXT_BUTTON_SELECTOR) are placeholder guesses, not confirmed against
   the real DOM.
2. `exporter/convert.py`'s mapping from raw fields to checklist columns
   (sport, year, brand, type, insert, sub_type, team) is a best guess -
   those values aren't in the row data the original vision doc
   describes, so where they actually come from needs to be confirmed
   against a real search page.
3. Phase 7's "continuation numbering" and "standardize names" rules
   aren't implemented - they depend on conventions only Brandon has.

Next concrete step: log into BuySportsCards, run a search, inspect the
table HTML (or extract once with the placeholder selectors and look at
raw_export.csv), and feed back the real selectors and a sample of real
rows so convert.py and selectors.py can be corrected.

## Next Milestone

Confirm real selectors and field mapping against the live site.

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

**Version: 0.3.0 (Full pipeline, unverified against live site)**

Current capabilities:
- Launches as a desktop application
- Opens a Playwright-controlled Chromium browser
- Maintains a BrowserManager that owns the browser instance
- Reads every row across every page (Phases 1-2)
- Converts raw rows into checklist template rows, merges parallels,
  applies basic cleanup, and exports both a raw debug CSV and a final
  checklist CSV (Phases 3-8)

All of the above is unit-tested against fake data but not yet run
against the real BuySportsCards site - see "Blocked On" above.

Next goal (v0.4.0): confirm real selectors and field mapping against a
live, logged-in BuySportsCards search, then validate the full pipeline
end to end on a real checklist.
