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

## Next Milestone

Read the number of rows currently displayed. Nothing else.

If we can count rows, then we know Checklist Assistant can "see" the page.

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

**Version: 0.0.2 (Row counting)**

Current capabilities:
- Launches as a desktop application
- Opens a Playwright-controlled Chromium browser
- Maintains a BrowserManager that owns the browser instance
- Counts rows currently displayed on the active page

Next goal (v0.0.3): Read the data in the first row, then progressively
expand to reading every row, multi-page extraction, and CSV generation.
