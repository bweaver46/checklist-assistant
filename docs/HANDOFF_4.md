# HANDOFF_4.md — Checklist Assistant

Read HANDOFF_1.md first if you haven't (full architecture, field-mapping
rules, working norms). HANDOFF_2/3 cover BSC-specific fixes. This file
covers a new, large feature: multi-source support (Beckett, TCDB), on
top of the existing BuySportsCards.com scraper.

## What's new this session

Checklist Assistant now supports THREE sources, auto-detected from
whatever URL is currently in the Playwright browser window when
**Extract Checklist** is clicked - no source picker, Brandon just
navigates the browser himself (per the app's original design
philosophy: the human browses, the app extracts what's on screen).

- **BuySportsCards.com (BSC)** - unchanged, existing flow.
- **Beckett** (`beckett.com`) - a checklist *article*, not a live
  database. No login. Bot-detection blocks plain HTTP fetch, so this
  still goes through Playwright like BSC, but doesn't need any of
  BSC's login/search/Team-fetch machinery.
- **TCDB** (`tcdb.com`) - a live set-checklist database. No login, NO
  bot detection (plain fetch works, confirmed). Paginated via
  `?PageIndex=N`.

## New files

| File | Purpose |
|---|---|
| `parsers/beckett_parser.py` | Parses a Beckett "Full Checklist" tab's HTML into raw rows. See its module docstring - it's long and documents several real, non-obvious page-format quirks (see below). |
| `parsers/tcdb_parser.py` | Parses one page of a TCDB set-checklist table into raw rows. |
| `scraper/site_detect.py` | `detect_source(url)` -> `"bsc"` / `"beckett"` / `"tcdb"` / `None`, based on hostname. |
| `scraper/tcdb_pagination.py` | `tcdb_page_url(base_url, page_num)` - pure URL builder, no Playwright needed, fully unit-tested. |
| `exporter/external_source_mapper.py` | Maps Beckett/TCDB raw row dicts straight onto `ChecklistRow` (Beckett/TCDB rows are already close to final shape, unlike BSC's raw occurrences which need `convert.py`+`merge.py`'s full Insert/Parallel derivation). Reuses `parse_set()` (the exact same year/brand/set splitter + `brand_set_exceptions.csv` BSC uses) against a single "Product" string Brandon types once per extraction (e.g. "2025 Bowman", "1972 Topps") - neither site gives a clean brand/set string separate from the sport the way BSC's own Set column does. |

Tests: `tests/test_beckett_parser_manual.py`, `test_beckett_parallels_manual.py`,
`test_beckett_subsection_manual.py`, `test_beckett_label_after_list_manual.py`,
`test_tcdb_parser_manual.py`, `test_external_source_mapper_manual.py` - all
pure-Python, no Playwright needed, all built against REAL page HTML Brandon
pulled via Chrome DevTools inspection (not guessed). Run with
`python3 tests/test_X_manual.py` (not pytest - same ad-hoc style as
`test_exporter_pipeline.py`/`test_browser_manager.py`, just newer files
that haven't been folded into that runner yet).

## Beckett parser - real quirks encountered (all handled, all confirmed against live HTML)

1. **First `<p>` after any heading is ALWAYS metadata**, never card
   data - true even when it's not a "N cards." caption (e.g. the
   page's own intro paragraph under the master title).
2. **`<h4>` (empty) is a continuation marker**, not a new section -
   happens when one checklist's cards span multiple `<p>` blocks.
3. **Declared card count drives multi-signer merging**: when a
   checklist's declared count is exactly 1 but lists many names on
   many lines (e.g. a 24-signer "Ultimate Autograph Book Card"), ALL
   lines merge into ONE row (names/teams joined with " / "). Buyback
   Autographs and All America Game Autographs ALSO have lines with no
   card number, but their counts are >1, so they correctly stay
   separate rows. Driven by the count, not by guessing per-line.
4. **`<ul>` = a blanket parallel list** for every card in that section
   (confirmed on Donruss, absent on Bowman - format varies by product).
   Handles plain names, `/NNN` serials, and `1/1` one-of-ones (special-
   cased since generic slash-parsing would misread "1/1" as name "1" +
   serial "1").
5. **`<h3>` WITHOUT the word "Checklist" at the end = a subsection
   label**, not a new Insert (e.g. "Rated Prospects" continues Base
   Set's own numbering). Goes into attributes instead; Insert stays
   unchanged. Every other real `<h3>` insert name ends in "Checklist" -
   that's the signal used to tell them apart.
6. **A heading immediately following a `<ul>` with nothing in between
   is a LABEL for that list**, not a new section (e.g. "Clearly Rated
   Prospects" naming a preceding Black/Techno/Platinum parallel list -
   confirmed the label sits AFTER the list in the real HTML, opposite
   of every other heading pattern on the page). Gets prepended onto
   every parallel name already captured; does not touch category/
   insert/subsection state at all.
7. Nicknames like "JJ"/"CJ" are all-uppercase - the card-number
   detector requires a real card number to be pure digits OR contain a
   hyphen, specifically so it doesn't mistake a nickname for a card
   number on lines with no real card number.

**Not yet confirmed against a live browser**:
`BrowserManager.click_beckett_full_checklist()` - built from real HTML
Brandon provided (a `<li class="advgb-tab...">` wrapping an `<a
href="#advgb-tabs-tab4">` around `<strong>Full Checklist</strong>`,
and a `<div aria-labelledby="advgb-tabs-tab4">` panel), but Playwright
isn't available in the dev sandbox this was built in, and beckett.com
blocks the fetch tool outright (bot detection) - so this has never
actually been clicked for real. **First real Beckett extraction is
the real test of this.** If it doesn't find/click the tab, get the
exact error and the live HTML around the tab and fix from there - same
process as every other selector in this app.

**Known data nuance, not fixed** (structural limit of the source, not
a parser bug): checklists like "Anime Kanji Variations" or "Etched in
Glass Variations" re-list card numbers that already appear under a
different Insert - they're marking "this existing card also has this
variation," not introducing new cards. Both show up as separate rows;
the page gives no way to tell these apart from genuinely new cards.

**Expect more one-off fixes as new Beckett product pages get used** -
different products' checklist articles are hand-written, not generated
from one consistent template. This isn't a sign the parser is broken;
it's the nature of scraping prose articles instead of a structured DB.

## TCDB parser - real quirks encountered

1. **Fixed column positions** in each `<tr>` (several blank spacer
   `<td>`s in between) - card number is `td[4]`, player cell is
   `td[8]`, team is `td[11]`. Confirmed against a real row; if TCDB
   ever changes their table markup, re-confirm this first.
2. **Tag glossary is per-set** (`GlossaryS.cfm/sid/{sid}/{slug}`) -
   fetched separately, not hardcoded, since abbreviation meanings could
   vary by set/sport. Per Brandon: short codes (RC, TC, CL, RS, etc.)
   stay as-is in attributes - do NOT expand to the full glossary term.
3. **VAR is the one tag that does NOT go into attributes.** A VAR tag
   means this row is a printing variation - it becomes a PARALLEL
   instead, using the `<figcaption class="figure-caption">` note text
   (with any leading "VAR: " stripped) as the parallel name.
4. **Lettered variants (18a/18b, 29a/29b) group under one base card
   number**, same `LETTER_VARIANT_PATTERN` regex BSC already uses
   (`exporter/convert.py`) - reused directly, not re-derived. Each
   lettered row's VAR note becomes one parallel slot on the merged row.
   Non-VAR tags (e.g. RC) on any lettered variant still show up once on
   the merged row (deduplicated, not repeated per letter).
5. **Non-VAR notes** (e.g. "RC for Anderson only" on a multi-player
   Rookie Stars card) get appended onto attributes verbatim, alongside
   whatever tags are present.
6. **Cells with no player `<a>` link** (Team Cards, Checklist cards,
   multi-player descriptive names) needed a real bug fix: initially the
   whole cell text was being treated as "tags." Fixed by only treating
   a TRAILING comma-separated list of short (2-4 letter) all-caps
   tokens as tags, keeping everything before that as the actual name.
   This is a heuristic (no HTML boundary marks where the name ends and
   tags begin, unlike linked cells where the `<a>` tag itself provides
   that boundary) - it worked on every real example tested, but could
   misfire if a future card's name legitimately ends in something
   that looks like a tag code. Fix with a real example if that happens,
   don't guess preemptively.
7. Pagination is `?PageIndex=N` on the same path; page 1 has NO
   PageIndex param at all (not `PageIndex=1`) - `tcdb_page_url()`
   handles this correctly and is unit-tested for it.

## main_window.py wiring

- `on_extract_checklist()` now calls `detect_source()` first. `None` ->
  tells Brandon to launch/navigate somewhere supported first, does
  nothing else. `BECKETT`/`TCDB` -> routes to the new lightweight
  methods below. `BSC` (or match) -> falls through to the existing,
  untouched flow.
- `_extract_beckett()` and `_extract_tcdb()` are new, self-contained
  methods - they do NOT go through `ExtractionWorker`/`convert.py`/
  `merge.py` at all (unnecessary - Beckett/TCDB rows are already close
  to final shape). They prompt for Product + Sport (shared helper:
  `_prompt_product_and_sport()`) + export name (reusing
  `resolve_unique_output_name()`), then for TCDB also Start/End page,
  then write the final CSV directly via the existing
  `write_final_csv()`/`sort_rows_by_brand()` - no changes needed to
  either of those, they already widen `parallel_N`/`serial_N` columns
  dynamically based on the widest row, which Just Worked for TCDB's
  variable parallel counts with zero export-side changes.
- Beckett/TCDB extractions do **not** touch `settings/accumulator.json`
  at all - that stays BSC-only (page-range chunk merging across
  multiple app runs for the same live paginated table). TCDB's own
  pagination accumulates in-memory within a single extraction call
  only; there's no "resume this TCDB set across app restarts" feature
  (not asked for, didn't build it).
- Both new methods disable/re-enable `extract_button` around their
  work (`try/finally`), matching BSC's existing button-disable
  behavior, so a double-click can't start two overlapping extractions
  during a long TCDB multi-page pull.
- No new source-picker UI was added - "Launch Browser" still opens BSC
  by default, but Brandon can just navigate that same browser window
  himself to a Beckett or TCDB page (same as he already does for BSC's
  own search), then click Extract Checklist - `detect_source()` picks
  up wherever the browser actually is.

## Architecture notes carried forward from HANDOFF_1/2/3

(Unchanged this session - see HANDOFF_1.md: per-row cleaning/merge
pipeline for BSC, Insert/Sub_Type scalar + repeating parallels,
lettered-variant handling, pause/resume, page-range accumulator system,
gitignored settings files. See HANDOFF_3.md: export naming collision
avoidance, accumulator-carryover warning on new export names - both
confirmed working and unrelated to this session's changes.)

## Brandon's communication style

- Direct, terse, often via voice-to-text (expect phonetic garbling -
  read for intent, not literal spelling; e.g. "sebsites" = "websites",
  "si" = "is").
- No em dashes in writing.
- Prefers confirming real HTML/structure via Chrome DevTools inspect
  before building, over guessing - this caught multiple real bugs this
  session (the "JJ"/"CJ" nickname false-positive, the team-card tag/
  name split, the label-after-list ordering) that would have shipped
  broken if built from assumption instead of confirmed markup.
- Comfortable approving multi-step builds in one "keep going" without
  re-confirming every sub-decision, AS LONG AS each concrete fork in
  the design (parallel handling, tag mapping, grouping rules) was
  asked about explicitly first via the elicitation tool - don't skip
  that step even when he's said "keep going" generally.
- IMPORTANT: after drafting a handoff file, actually create it with
  create_file and push it to GitHub before telling Brandon it exists.
  Do not describe a handoff in a chat reply and consider that
  equivalent to it being in the repo.
- GitHub PAT: ask Brandon for a fresh one each session if the old one
  doesn't work - but his existing fine-grained PAT has been valid
  across every session so far; try it before asking for a new one.
