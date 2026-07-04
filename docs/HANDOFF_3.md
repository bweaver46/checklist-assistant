# HANDOFF_3.md — Read this entire file before touching anything.

Read HANDOFF_1.md too if you haven't — it has the full architecture,
field-mapping rules, and working norms. This file only covers what
changed since HANDOFF_2.

## Context
Brandon is VP of Purchasing at Jack's Family Restaurants and the sole
developer of Checklist Assistant, a PySide6/Playwright desktop app that
scrapes BuySportsCards.com to generate trading card checklist CSVs.
Repo: bweaver46/checklist-assistant (GitHub), branch main.
Current commit: fe217d2.

## What's done and confirmed (do not break)

### 1. Pagination past page 999 — CONFIRMED FIXED
HANDOFF_2's OPEN_ISSUE_1 was pagination breaking at 4-digit page numbers
(BSC formats large page numbers with commas, e.g. "1,387", which broke
`str.isdigit()` checks). Commit 62b39da (previous session) stripped
commas before all digit/comparison checks in `_pagination_status()`,
`click_next()`, and `navigate_to_page()`.

This session, added temporary `[DIAG]` status-bar logging (commit
6e164f3) around `navigate_to_page()` and the extraction stop conditions
in `browser_manager.py` to pin down a report of "4-digit pages still
broken" (turned out to be: any run *starting* at a 4-digit page only
processed one page, regardless of end_page — pointed at
`navigate_to_page()`/`has_next_page()` after a direct URL jump, not
`click_next()`).

Brandon re-ran the extraction after pulling the fix and confirmed
**"its working now."** The `[DIAG]` log lines are still in
`browser_manager.py` (in `extract_all_pages()`, gated behind
`if on_status:`) — harmless to leave, but safe to strip out next time
you're in that function if the status bar clutter bothers Brandon.
Nothing else consumes them.

### 2. Export naming — new export name prompt, never overwrites
Brandon's report: building a set, forgetting to save/rename the output
CSV, then starting the next extraction silently overwrote the previous
set's work — because `raw_export.csv` and `checklist_export.csv` were
hardcoded filenames in `extraction_worker.py`.

Fixed in commit fe217d2:
- New module `settings/output_naming.py`:
  - `sanitize_output_name(name)` — strips illegal filename chars
    (replaces with a space, not deletion, so "Chrome/Prizm" becomes
    "Chrome Prizm" not "ChromePrizm"), collapses whitespace, falls back
    to `"checklist"` if blank. Never returns empty.
  - `resolve_unique_output_name(name, directory)` — sanitizes, then
    appends " (2)", " (3)", etc. if either `<name>_raw_export.csv` or
    `<name>_checklist_export.csv` already exists in `directory`. This
    is the collision-avoidance step — it's what guarantees a forgotten
    unsaved export can never be silently clobbered.
  - `raw_export_path(name, directory)` / `final_export_path(name, directory)`
    — build the actual absolute paths from a resolved name.
- `app/main_window.py` (`_prompt_for_context`): asks for an export name
  as the FIRST prompt when starting a fresh context chain (a genuinely
  new set), resolves it via `resolve_unique_output_name()` immediately,
  and stores it as `context["output_name"]`. This is what gets
  persisted to `settings/last_run.json` along with everything else.
  - Answering "Yes" to the reuse-settings prompt (continuing the SAME
    set across page-range chunks) skips this prompt entirely and keeps
    the already-resolved name, so chunked continuations correctly keep
    rebuilding the same file pair instead of getting a new name each
    chunk. The reuse-prompt summary now also shows "Export name: X" so
    it's visible which file you're about to keep writing to.
- `app/extraction_worker.py`: builds `raw_path`/`final_path` from
  `context.get("output_name")` via the new helpers instead of the old
  hardcoded `raw_export.csv`/`checklist_export.csv`. Removed the now-
  unused `import os` at the top of the file.
- `tests/test_output_naming.py`: full coverage of the sanitizer and the
  collision-avoidance counter logic. Passes, along with the existing
  `tests/test_browser_manager.py`.

## Open items — start here

### 1. Accumulator carryover when starting a new set (flagged, not fixed)
`settings/accumulator.json` persists raw rows across runs so page-range
chunks of the SAME set combine correctly into one file. That's
intentional and unrelated to the naming fix above.

But: if Brandon starts a genuinely NEW set (gets a new export name via
the prompt above) without first clicking **Clear Accumulated Data**,
the old set's leftover rows in the accumulator would still get pulled
into the new set's freshly-named file — i.e., the file-overwrite bug is
fixed, but a "wrong data merged into new file" bug could still exist as
a different failure mode. This was flagged to Brandon at the end of
last session; no response yet on whether he wants a safeguard (e.g.,
warn if `accumulated_count() > 0` when a NEW export name is entered).
Ask him before building anything here — don't guess at the desired
behavior.

### 2. `[DIAG]` pagination logging — leave or remove
See item 1 above under "What's done." The diagnostic status-bar lines
added in 6e164f3 are still live and gated behind `if on_status`. They
did their job confirming the pagination fix. Ask Brandon if he wants
them stripped for a cleaner status bar, or left in case 4-digit paging
regresses again.

## Architecture notes carried forward from HANDOFF_1/2
(Unchanged this session — see HANDOFF_1.md for the full list: per-row
cleaning/merge pipeline, Insert/Sub_Type scalar + repeating parallels,
lettered-variant handling for `#1b`/`#1c` style cards, pause/resume,
page-range accumulator system, gitignored settings files including
`settings/brand_set_exceptions.csv` which will NOT exist in a fresh
clone — that's expected, not a regression.)

## Brandon's communication style
- Direct, terse, often via voice-to-text (expect phonetic garbling —
  read for intent, not literal spelling).
- No em dashes in writing.
- Ask concrete diagnostic questions before patching blind; prefers
  instrumentation (status-bar logging) over guesses when a bug isn't
  reproducible from the description alone — this worked well for the
  pagination issue this session.
- GitHub PAT: ask Brandon for a fresh one each session if the old one
  doesn't work — but note his existing fine-grained PAT was scoped to
  BOTH checklist-assistant and collock this session, so it may still be
  valid; try it before asking for a new one.
- IMPORTANT: after drafting a handoff file, actually create it with
  create_file and push it to GitHub before telling Brandon it exists.
  Do not describe a handoff in a chat reply and consider that
  equivalent to it being in the repo.
