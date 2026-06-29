# HANDOFF_1.md — Checklist Assistant

**Status as of 2026-06-29: v0.10.0, confirmed working against live data.**

This document exists so anyone (human or AI) can read it cold and step
straight into continuing this project without needing to re-derive any
of the decisions below. It is deliberately long. If you're picking this
up, read this whole file before changing anything.

---

## 1. What this project is

Checklist Assistant is a Mac desktop app that automates building trading
card checklist CSVs from BuySportsCards.com (BSC). Brandon browses BSC
normally (logs in, searches, filters) inside a Playwright-controlled
Chromium window the app opens for him. When he's looking at the results
he wants, he clicks **Extract Checklist**, and the app reads every row
across every page, cleans and restructures the data, and writes two CSV
files: a raw debug export and a final checklist matching Brandon's exact
Check List Builder template.

The original design philosophy (from the founding vision doc, still in
`docs/VISION.md`) is: the app never drives the search itself. The human
browses, the app only extracts whatever is currently on screen. This
keeps the scraper simple and avoids fighting BSC's login/search UI.

## 2. Where everything lives

```
checklist-assistant/
    main.py                          entrypoint
    Launch Checklist Assistant.command   double-clickable Finder launcher
    requirements.txt                 PySide6, playwright
    README.md                        quick-start + current status summary

    app/
        main_window.py               PySide6 UI shell, all the extraction prompts

    scraper/
        browser_manager.py           owns the Playwright browser, all DOM interaction
        card_record.py                CardRecord dataclass (raw row data)

    exporter/
        convert.py                    Phase 5: per-row cleaning -> RawOccurrence
        merge.py                      Phase 6: group rows into ChecklistRow (Insert/Sub_Type/Parallels)
        cleanup.py                     Phase 7: dedupe parallels
        checklist_template.py         ChecklistRow dataclass
        raw_export.py                 writes raw_export.csv
        final_export.py               writes checklist_export.csv, sort_rows_by_brand

    settings/
        selectors.py                  ALL CSS/text selectors for BSC's DOM, confirmed live
        brand_set_exceptions.csv      editable spreadsheet, brand/set overrides
        window_layout.py              screen positions for the two windows
        extraction_limits.py          MAX_PAGES safety cap (currently 2000)

    tests/
        test_exporter_pipeline.py     full unit test suite, no Playwright needed
        test_browser_manager.py       BrowserManager logic (team cache), lightweight fakes, no Playwright needed

    docs/
        VISION.md                     original founding vision doc + running changelog
                                       of every field-mapping rule decision, in order,
                                       with the reasoning behind each one
        HANDOFF_1.md                  this file
```

`docs/VISION.md` is the detailed decision log — every rule change, every
real example that drove a decision, every open question, in
chronological order. This handoff is the *summary and orientation*;
VISION.md is the *detailed paper trail*. If something in this handoff
seems underspecified, check VISION.md first — the nuance is probably
there.

## 3. How to actually run it

```bash
cd checklist-assistant
source venv/bin/activate      # must exist already; if not: python3 -m venv venv && pip install -r requirements.txt && playwright install chromium
python main.py
```

Or double-click **`Launch Checklist Assistant.command`** in Finder — it
does the `cd` + `source venv/bin/activate` + `python main.py` for you.

Brandon's Python is 3.9.6 (Mac default-adjacent). This matters: the
codebase uses modern type-hint syntax (`dict | None`, `list[str]`)
which requires Python 3.10+ UNLESS every file starts with
`from __future__ import annotations`. **Every .py file in this repo has
that import as the first line after its docstring.** If you add a new
file, add that import too, or it will crash on his machine with
`TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`
— this already happened once (see commit `5f6346c`).

Run tests with:
```bash
PYTHONPATH=. python3 tests/test_exporter_pipeline.py
PYTHONPATH=. python3 tests/test_browser_manager.py
```
Neither needs Playwright/a real browser — `test_exporter_pipeline.py`
feeds fake `CardRecord` objects straight into the pipeline;
`test_browser_manager.py` uses lightweight fake Page/Locator/Row
objects to test `BrowserManager`'s pure logic (currently just the team
cache) in isolation.

## 4. The actual workflow, end to end

1. User clicks **Launch Browser** → `BrowserManager.launch()` opens a
   real (headed, visible) Chromium window via Playwright, positioned per
   `settings/window_layout.py`, navigated to buysportscards.com.
2. User logs in and browses **manually** — crucially, as a **seller**
   account. Brandon's account is a BSC seller account. Searching as a
   buyer redirects oddly; the reliable path is the **"Sell Cards" /
   market-browse view** at `/sellers/inventory?myInventory=false` — this
   shows the full market listing table (not just what's currently for
   sale), which is what the app actually reads.
3. User clicks **Extract Checklist**. The app prompts for:
   - **Sport** (required to proceed — Cancel here aborts extraction)
   - **Primary Player** (optional — see §6)
   - **Fetch Team per card?** Yes/No (see §7) — if No, then:
   - **Team** (optional, one value for the whole batch)
   - **Section** (optional — see §6, continuation numbering)
4. `BrowserManager.extract_all_pages()` reads every row on every page
   (clicking through BSC's own pagination), optionally fetching Team
   per row if that was turned on.
5. Raw rows get written immediately to `raw_export.csv` (debugging
   tool — if final output looks wrong, compare against this).
6. The full conversion pipeline runs (§5) producing the final
   `checklist_export.csv`, sorted by brand.
7. Status bar shows the full absolute path to both files when done.

Both CSV files land directly in the `checklist-assistant` folder
(wherever it currently is — Brandon has moved it once already; the app
doesn't care, it just uses relative paths from wherever it's launched).

## 5. The data pipeline — this is the part that matters most

This went through several real redesigns. **The current model (as of
commit `277d50c`, "Major rewrite") is the right one and should not be
reverted to anything per-occurrence for Insert/Sub_Type.** Here's why,
and how it actually works.

### 5a. The template Brandon's Check List Builder needs

Exact columns, confirmed against his real template file
(`sets-template-2.csv`, not in this repo but referenced in VISION.md):

```
type,sport,year,brand,set,insert,sub_type,card_number,player,team,parallel_1,serial_1,parallel_2,serial_2,...
```

**`type`, `sport`, `year`, `brand`, `set`, `insert`, `sub_type`,
`card_number`, `player`, `team` are all SCALAR — one value per card.**
Only `parallel_N`/`serial_N` repeat, because a single physical card can
have multiple print versions (different colored parallels), each with
its own serial number.

### 5b. Why Insert/Sub_Type are scalar, not per-occurrence

This was the biggest design mistake I made and then had to unwind. My
first instinct was to make Insert and Sub_Type repeat per occurrence
too (`insert_1/sub_type_1/serial_1`, `insert_2/...`). Brandon corrected
this directly by showing the real template — Insert and Sub_Type
describe **the card**, not any one print version of it.

The real example that nailed down the actual algorithm — one
`card_number` (`#BA-23`), four raw website rows, all "Mike Trout":

| Variant Name (raw) |
|---|
| Anime |
| Anime Black Refractors |
| Anime Red Refractors |
| Anime SuperFractors |

"Anime" is common to all four → **Insert = "Anime"**. What's left over
per row, after stripping that common text, is the **Parallel**:
- `""` (the plain "Anime" row — this is the base printing of the
  insert, it contributes NO parallel slot at all)
- `"Black Refractor"` (normalized from "Black Refractors" — singular,
  but the word itself is KEPT, not dropped)
- `"Red Refractor"`
- `"SuperFractor"`

So the algorithm in `merge.py`:
1. Group all raw rows by card identity:
   `(type, sport, year, brand, set, card_number, player, team)`.
2. Within a group, take every row's Variant Name text and compute the
   **longest common word-prefix** across all of them
   (`longest_common_word_prefix` in `merge.py`). That's Insert.
   - If there's only ONE row in the group, the "common prefix" is
     trivially that row's whole Variant Name — meaning Insert =
     the full name, and that row gets no parallel (its own text was
     entirely "common" with itself).
   - If ALL rows in a group are Base with blank Variant Name, common
     prefix is `""` — no Insert, normal case for plain numbered cards.
3. For each row, strip that common prefix off its own Variant Name to
   get the **remainder**, then run `normalize_plural_terms()` on it
   (singularizes Refractors→Refractor, SuperFractors→SuperFractor,
   Prizms→Prizm; does NOT delete anything).
4. A row gets a `parallel_N`/`serial_N` slot **only if** its remainder
   is non-blank OR it has its own serial number (SN/PR). If neither,
   it contributes nothing — no blank slot, the numbering for the NEXT
   real parallel starts wherever it would have anyway (e.g. if the
   plain "Anime" row is skipped, the next row becomes `parallel_1`,
   not `parallel_2`).
5. `card_number`'s prefix (see §5d) prepends onto the scalar **Insert**,
   not onto any individual parallel — it identifies which subset/era
   the whole card belongs to.
6. Sub_Type is also built once per group: combines the Section context
   value (if any), any Primary-Player leftover text (§6), and
   "Autograph" if any row in the group has `AU` in its Attributes AND
   the word "Autograph" doesn't already appear elsewhere (set, insert,
   section, leftover text) — avoids "Autograph" being redundantly
   stated when the insert is already named e.g. "Rookie and Veteran
   Autographs Purple".

### 5c. An earlier rule that got REMOVED — don't reintroduce it

Early on, there was a rule: "drop a redundant trailing 'Refractor'
word entirely" (so "Blue Mojo Refractor" → "Blue Mojo"). **This rule
was removed** (commit `277d50c`) because it directly conflicted with
the real Anime example above — Brandon explicitly wants "Black
Refractor" KEPT (just singularized), not dropped to "Black". The only
remaining transformation is plural→singular normalization
(`normalize_plural_terms` in `convert.py`). If you ever see logic that
deletes a "Refractor"/"Prizm" word entirely instead of just
singularizing it, that's a regression — remove it.

### 5d. card_number cleaning and prefix extraction

- Strip a leading `#` always (`clean_card_number`).
- If the card number has a trailing run of digits at the very end,
  everything before that run is a "prefix" that gets prepended onto
  the card's scalar Insert (space-separated, hyphen preserved exactly).
  - `"T91-1"` → prefix `"T91-"`, the number itself stays `"T91-1"`.
  - `"TBC15"` → prefix `"TBC"`.
  - `"12P5"` → prefix `"12P"` (NOT all leading digits stripped — only
    the trailing digit run matters: regex is `^(.*?)(\d+)$`).
  - `"517"` → prefix `""` (purely numeric, no prefix).
- **Important ordering bug that was caught and fixed**: the
  plural-normalization step (hyphen→space) runs on the Variant-Name-
  derived part BEFORE the card_number prefix gets prepended. If you
  ever refactor this, make sure the prefix's own hyphen (e.g. `"T91-"`)
  never passes through `normalize_plural_terms`/hyphen-stripping logic,
  or it'll get mangled into `"T91 "` with the hyphen gone. There's a
  dedicated test for this:
  `test_card_number_prefix_with_hyphen_survives_normalization`.

### 5e. Brand/Set split

- `year` = leading 4 digits of the website's Set string.
- `brand` = the FIRST WORD remaining after the year. `set` = everything
  else (can be blank — e.g. `"2026 Bowman"` → brand `"Bowman"`, set
  `""`. Blank is fine, intentional — better than repeating the brand).
- **Exceptions** (`settings/brand_set_exceptions.csv`, see §5f) override
  this when the simple first-word rule is wrong for a specific product
  line.

### 5f. The brand/set exception spreadsheet

`settings/brand_set_exceptions.csv` — a real, user-editable CSV.
Columns: `pattern, brand, set`. Brandon can open this in Excel/Numbers,
add a row, save as CSV, and it just works — no code changes, no asking
me. Loaded once per run via `load_brand_set_exceptions()` in
`convert.py` (module-level cache, so within one extraction it only
reads the file once; a fresh app launch re-reads it).

Matching: word-wise, case-insensitive, longest pattern checked first
(so `"Topps Now"` is tried before any shorter pattern that might also
partially match). **Critical detail**: if the real Set text has MORE
words after the matched pattern, those extra words get appended to the
exception's set value rather than discarded — e.g. pattern `"UD"`
matched against `"UD Series 1"` → set becomes `"Upper Deck Series 1"`,
not just `"Upper Deck"`. This was a real bug, caught and fixed (commit
`98d22ec`) — if you ever touch `match_brand_set_exception`, preserve
this behavior; there's a test for it
(`test_brand_set_exception_preserves_trailing_words`).

Current confirmed entries:
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

Some of these deliberately repeat the brand inside set (e.g. "Topps
Now" / "Topps Now") — that's intentional, an exception to the general
"don't repeat" rule, because that repetition IS the correct full
product name for these specific lines.

## 6. Context fields — things only a human can know

Four pieces of information aren't derivable from the page data at all,
so the app asks for them once per extraction run (`_prompt_for_context`
in `main_window.py`):

- **Sport** — required. BSC only sells sports cards, but doesn't say
  *which* sport on the page anywhere we've found.
- **Type** — NOT asked for. Hardcoded to `"Sports"`
  (`DEFAULT_TYPE` constant) because BSC only sells sports cards. If
  Checklist Assistant ever supports a non-sports source, this needs to
  become a real per-source value again.
- **Primary Player** (optional) — for when a search is filtered to one
  player but BSC's Name field has other text jammed in alongside it
  (multi-player inserts, acronyms). Real example: Name field literally
  reads `"Stars Align (Mike TroutZach Neto) CPC"` — note there's no
  real separator between "Mike Trout" and "Zach Neto" in BSC's own
  text. Typing `"Mike Trout"` as Primary Player makes
  `split_primary_player()` find that substring (simple case-insensitive
  substring search — works even with no separator, since "Mike Trout"
  is still a contiguous substring), set Player to exactly that, and
  fold everything else (with that substring removed) into Sub_Type:
  `player="Mike Trout"`, `sub_type="Stars Align (Zach Neto) CPC"`. If
  the Primary Player text isn't found in a given row's Name, that row's
  Name is left completely unchanged — no silent data loss.
- **Team** — optional, one value applied to the whole batch UNLESS
  per-card fetching is used (§7), in which case a fetched value
  overrides this for that specific card.
- **Section** (optional) — for "continuation numbering": e.g. a
  Prospects or Series 2 subsection that continues a base set's
  numbering (#101-200) rather than restarting at #1. `set` and
  `card_number` are NEVER renumbered — the section name just gets
  folded into Sub_Type instead. Leave blank for almost every search;
  the prompt text says so explicitly because Brandon was confused by it
  early on.

## 7. Per-card Team fetching — the newest, riskiest feature

Team is **not shown anywhere in BSC's results table.** Confirmed by
direct DOM inspection. It only appears on the "Sell Your Card" detail
page reached by clicking a row's **"Add"** button
(URL pattern `/sellers/sell-your-card/add/<card-id>`).

Important things confirmed about this page, directly from Brandon:
- Clicking "Add" only **opens BSC's listing-creation form** — it does
  NOT submit or create a listing. Nothing happens to his account just
  from opening it. (The app never clicks any submit button on this
  page, so this remains safe regardless.)
- Clicking the browser's Back button from there returns to the **exact
  same results page state** (same page number, same scroll position) —
  confirmed by Brandon manually testing it before any code was written.
- Team's label (`"Team:"`) and value sit in two **sibling `<div>`s**,
  each containing a generic `<h6>` with a dynamically-generated CSS
  class (e.g. `jss156988`) that WILL change between BSC site builds —
  so the selector matches on the literal text `"Team:"` instead of any
  class name: `TEAM_DETAIL_LABEL_SELECTOR = "h6:text-is('Team:')"` in
  `settings/selectors.py`. The value is read via
  `label.locator("xpath=../following-sibling::div[1]//h6")`.

Because this multiplies extraction time enormously (one full extra
page visit per ROW instead of per ~50-row page), it is **an explicit
opt-in Yes/No prompt** (`_prompt_fetch_team`), defaulting to No. This
was a deliberate choice — never make this a silent default.

**Per-player caching (added 2026-06-29, same day):** Brandon's own
observation — most rows in any set are parallels of the same handful of
players, not unique lookups. `BrowserManager` now keeps
`self._team_cache: dict[str, str]` mapping the raw Name text to its
fetched Team, reset at the start of every `extract_all_pages()` call.
A row's Name is checked against this cache BEFORE clicking "Add" — if
already known (even a previous failed/empty lookup, deliberately, so
one slow row doesn't get retried for every one of its parallels), it's
reused with zero extra page visits. This means the real cost scales
with the number of DISTINCT players in a search, not the number of
rows — for a typical full-set pull (many parallels per player), this
is a large speedup over the naive per-row version. Tested in isolation
with lightweight fakes (no real browser needed) in
`tests/test_browser_manager.py`.

**Not yet confirmed**: whether doing this hundreds/thousands of times
rapidly trips any rate-limiting or anti-bot detection on BSC's systems.
Brandon got it working once; it has not been stress-tested at very high
volume. If he reports anything looking like a block, slowdown, or
CAPTCHA challenge after enabling this on a huge pull, that's the first
thing to investigate.

When fetched, a row's team takes priority over the manual Team prompt
value for that specific card; otherwise the manual value is the
fallback. See `team=(record.team.strip() if ... else context.get("team", ""))`
in `convert.py`.

## 8. The selectors — all confirmed against the live, logged-in site

Everything in `settings/selectors.py` was confirmed by direct DOM
inspection via the Claude in Chrome browser extension (riding on
Brandon's own logged-in session — NOT the same Chromium instance the
actual Playwright app launches, which has its own blank session and
needs Brandon to log in himself every time).

- **Rows**: `table tbody tr.MuiTableRow-root.MuiTableRow-hover` — BSC's
  market-browse table is Material-UI based.
- **Columns** (8 `<td>` per row, 1-indexed with nth-child, position 1 is
  a checkbox):
  1. checkbox (unused)
  2. Name
  3. Card #
  4. Set
  5. Variant — confirmed values seen so far: `"Base"`, `"Insert"`,
     `"Parallel"` (e.g. `"Parallel (Optic Gold Velocity)"` — this third
     category turned up later, during the Team-fetching investigation;
     it's currently treated the same as "Insert" in `convert.py`
     since the is_base check only special-cases the literal string
     `"Base"` — this hasn't caused a known bug yet but is worth
     double-checking if odd output ever turns up for Parallel-variant
     rows).
  6. Variant Name — the actual parallel/insert descriptive text, `"-"`
     when not applicable.
  7. Attribute(s) — `"-"`, `"SN<digits>"`, `"PR<digits>"`, `"AU"`, or
     comma-combos like `"AU, SN150"`. PR (Print Run) is treated
     identically to SN (Serial Numbered) — both just mean "this many
     were made", neither is printed on the card itself, both extract
     into `serial` via the same regex `(?:SN|PR)(\d+)`.
  8. "Add" button (unused for normal extraction; used for Team
     fetching, §7)
- **Pagination**: a `<nav>` containing numbered page buttons. **There
  is no real "Next" button** — the prev/next arrow icons at each end
  are `<p><svg>`, not actual `<button>` elements, so they can't be
  reliably clicked or checked for a disabled state. Instead,
  `_pagination_status()` finds the current page via
  `[aria-current="true"]` and `click_next()` clicks the button whose
  text is `current_page + 1`. Confirmed working by directly clicking
  page "2" live and verifying the table reloaded with new content.

If BSC ever changes their frontend (different framework, restructured
table), this is the file to re-confirm against the live site first —
everything downstream assumes these selectors are correct.

## 9. Things that are still open / unresolved

Carried over from `docs/VISION.md`, current as of this handoff:

1. The `"Parallel"` Variant category (§8) hasn't been specifically
   tested against the Insert/Parallel-merge logic — it's *probably*
   fine since it's treated like "Insert", but hasn't been deliberately
   verified with a real multi-row Parallel-variant card group.
2. Per-card Team fetching hasn't been stress-tested at high volume
   (rate-limiting risk, §7).
3. No "continuation numbering" rules exist yet beyond the Section
   context field — if Brandon finds a case Section doesn't cover,
   that's the next thing to ask him about.
4. No player-name standardization rules exist (Brandon explicitly said
   player names should NOT be reformatted unless the source itself is
   inconsistent — "Mike Trout" stays "Mike Trout").

## 10. Working norms for this project — please follow these

- **Brandon talks in voice-to-text, often terse and sometimes
  garbled.** Real examples have been mis-transcribed before (e.g. "12P5
  -> 12P" rule, player names run together with no separator). When a
  rule is ambiguous or could be read multiple ways, ASK with a concrete
  example rather than guessing — guessing wrong here means silently
  corrupting real checklist data, which is worse than asking.
- **Every rule in this codebase exists because of a specific real
  example Brandon gave**, not because it seemed like a sensible general
  rule. Resist the urge to "clean up" or generalize a rule beyond what
  was actually specified — the Anime/Refractor-drop reversal (§5c) is
  exactly the kind of mistake that happens when a rule gets
  over-generalized from one example.
- **Always write or update a test before considering a rule
  "done."** `tests/test_exporter_pipeline.py` and
  `tests/test_browser_manager.py` require no Playwright and run in
  under a second combined — there's no excuse to skip them. Several
  real bugs (the Refractor/hyphen-order conflict, the exception
  trailing-words drop, the plain-Base-row-with-Section data loss) were
  caught specifically because a new test was written against a
  concrete example before shipping.
- **Compile-check and run the full test suite before every commit**:
  ```bash
  python3 -m py_compile $(find . -name "*.py" -not -path "./venv/*")
  PYTHONPATH=. python3 tests/test_exporter_pipeline.py
  PYTHONPATH=. python3 tests/test_browser_manager.py
  ```
- **Every commit gets pushed immediately** — Brandon works across
  multiple sessions/devices and pulls frequently mid-conversation.
  Don't batch up changes locally.
- **Remember `from __future__ import annotations`** in any new file
  (see §3) — his Python is 3.9.6.
- **The GitHub PAT Brandon provided is embedded directly in push/pull
  URLs in this conversation's history, not stored anywhere in the repo
  itself** — confirmed clean via `git log -p | grep github_pat` after
  every single commit so far. Keep doing that check. If a new token is
  ever provided, treat it the same way: use it in the URL, never write
  it to a tracked file, verify history stays clean.
- **Brandon has moved this folder around (Desktop, back, etc.)** — all
  paths in the code are relative (to the script's own location via
  `Path(__file__)`, or to the current working directory for CSV
  output), so this should keep working regardless of where the folder
  lives. If something breaks specifically after a move, check for an
  accidentally-hardcoded absolute path first.
- **Brandon is non-technical with git/terminal basics** — he's hit
  "wrong directory" git errors multiple times (nested folders, a stale
  unrelated git repo in a parent folder). When giving him terminal
  commands, be explicit about which directory he should be in, and
  expect to need to debug "command not found" / "no such file" type
  issues from first principles (e.g. `python` vs `python3`, needing to
  `source venv/bin/activate` first).
