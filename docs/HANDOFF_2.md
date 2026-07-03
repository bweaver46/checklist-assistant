# HANDOFF_2.md — Checklist Assistant

**Status as of 2026-07-03: v0.13+, active development. Pagination above page 999 is still under investigation — the comma-formatting fix (62b39da) was just pushed and not yet confirmed working by Brandon. Read §OPEN_ISSUE_1 before touching anything pagination-related.**

This document picks up where HANDOFF_1.md left off. Read HANDOFF_1.md first — it covers the founding architecture, all the field-mapping rules, the real examples that drove them, and the working norms. This file covers everything that changed in this session.

---

## 1. What changed this session (summary)

A large number of features and fixes were added. In rough chronological order:

1. **Checklist type selector** — Extract Checklist now asks Set / Player / Team first, then shows only the relevant follow-up questions.
2. **`base` and `base_serial` columns** — two new CSV columns after `team`. `base` always blank from parser (manual fill). `base_serial` auto-populated from SN/PR on the base card row.
3. **Remember last settings** — settings persisted to `settings/last_run.json` (gitignored). On next run: Yes = reuse immediately, No = show prompts pre-filled, Cancel = abort. Page range always re-asked even on Yes.
4. **Column renames** — `sport` column → `sub_type`; old `sub_type` column → `attributes`.
5. **Concatenated player name splitting** — `Dave JollyJim Pendleton` → `Dave Jolly / Jim Pendleton` via `split_concatenated_names()` in `convert.py`.
6. **Team separator formatting** — `Milwaukee Braves, Brooklyn Dodgers` → `Milwaukee Braves / Brooklyn Dodgers` via `normalize_team_separators()`.
7. **Season year formats** — `2021-22 Panini Prizm` → year `2021` (first 4 digits only).
8. **Card number prefix rule removed** — `O-123` was incorrectly prepending `O-` to Insert. `extract_card_number_prefix()` now always returns blank (stub kept for call-site compatibility).
9. **Brand/set exceptions set-value trim** — `" Art Cards"` in the CSV now loads as `"Art Cards"`.
10. **`brand_set_exceptions.csv` untracked** — gitignored, Brandon's local edits never overwritten by pull.
11. **Page range scraping** — Start page / End page prompts. Navigator jumps to start page, stops at end page. Multiple runs accumulate in `settings/accumulator.json` (gitignored); final CSV always rebuilt from all accumulated rows combined.
12. **Accumulator deduplication** — overlapping page ranges safe; exact-match raw rows deduplicated before pipeline.
13. **Team cache persistence** — `settings/team_cache.json` (gitignored). Team lookups persist across runs; in-memory cache wins over disk on conflict so a failed save never wipes a working session cache.
14. **Pause/resume** — Pause button appears during extraction; `QApplication.processEvents()` in the pause callback keeps UI alive (Playwright must stay on the main thread — see §2).
15. **Lettered card variants** (`#1b`, `#1c`) — grouped with base card (`#1`), become parallels using description from Add page. Full details in §3.
16. **Uniform dialog sizing** — custom `PromptDialog` class in `app/prompt_dialog.py`; `setFixedWidth(420)` on a real `QDialog` instead of `QInputDialog`/`QMessageBox` (macOS ignores `setFixedWidth` on those).
17. **Per-page status bar updates** — status bar now shows "Reading page X… (N rows so far)" and "Page X: N rows — M total" during extraction.
18. **Pagination comma fix** — BSC formats numbers ≥ 1000 as `"1,000"`. `str.isdigit()` returns False for these, so `_pagination_status()` capped `highest` at 999, causing `has_next_page()` to return False at page 999 and stop every run there. Fix: `.replace(",", "")` before `isdigit()` and before button text comparisons in `click_next()` and `navigate_to_page()`.

---

## 2. Critical architectural constraint: Playwright must stay on the main thread

Playwright's sync API uses greenlets internally and requires all calls to be made from the thread where `sync_playwright().start()` was called. When extraction was moved to a `QThread`, it crashed with `"Cannot switch to a different thread / greenlet"`.

**Current design**: `ExtractionWorker` is a plain class (NOT a QThread). `on_extract_checklist()` calls `self._worker.run()` directly on the main thread. `QApplication.processEvents()` is called inside the `_pause_callback` (invoked between every team fetch and every page turn) to keep the UI alive and allow button clicks to register during the blocking scrape.

**Do not move any Playwright calls to a background thread** without switching to Playwright's async API, which would be a large refactor.

---

## 3. Lettered card variants (`#1b`, `#1c`)

BSC lists Short Prints and Variations as separate rows with lettered card numbers alongside the base. They should be one card with the lettered variants as parallels.

**Detection** (`convert.py`):
- `LETTER_VARIANT_PATTERN = re.compile(r'^(\d+)([a-z])$')` — matches `1b`, `1c`, `517b` but NOT `BA-23` or `T91-1`.
- Letter stripped from `card_number` before grouping (so `#1`, `#1b`, `#1c` all group under `card_number = "1"`).
- `is_letter_variant = True` set on the `RawOccurrence`.

**Scraping** (`browser_manager.py`):
- Lettered variant rows ALWAYS visit the Add page to fetch description (even when `fetch_team=False`).
- `fetch_card_details_for_row()` returns `(team, description)`. `read_detail_field(label_selector)` is the shared helper for both.
- `DESCRIPTION_DETAIL_LABEL_SELECTOR = "h6:text-is('Description:')"` in `selectors.py`.
- `CardRecord` has a `description` field.

**Parallel building** (`merge.py`):
- `clean_description()`: strips `"VAR: "` prefix (any `"XXX: "` prefix), strips trailing `" Variation"`.
- `attributes_extra()`: returns attribute tokens in the variant but not in the base row, excluding `"VAR"` and serials. E.g. `"SP, VAR"` vs `"-"` → `"SP"`.
- Parallel name = `"SP Dancing Dodgers"` (extra attrs + cleaned description).
- Lettered variants bypass the `is_base` exclusion (BSC marks them as `Variant: Base` but they're really parallels).
- `base_serial` and `base_occ_attrs` only use true non-lettered base rows.

---

## 4. New files

| File | Purpose |
|---|---|
| `app/prompt_dialog.py` | Custom `QDialog`-based prompt class with fixed 420px width. Three static methods: `text()`, `combo()`, `question()`. Replaces all `QInputDialog`/`QMessageBox` usage in `main_window.py`. |
| `app/extraction_worker.py` | Plain class (not QThread) that runs the full extraction pipeline, handles accumulator load/save, team cache load/save, and the pause callback. |
| `settings/accumulator.py` | `load_accumulated()`, `save_accumulated()`, `clear_accumulated()`, `accumulated_count()`. Stored in `settings/accumulator.json` (gitignored). |
| `settings/team_cache.py` | `load_team_cache()`, `save_team_cache()`, `clear_team_cache()`. Stored in `settings/team_cache.json` (gitignored). |

---

## 5. New gitignored files (local user state, never overwritten by pull)

| File | Contents |
|---|---|
| `settings/last_run.json` | Last extraction context (type, sport, team, page range, etc.) |
| `settings/brand_set_exceptions.csv` | Brandon's custom brand/set exception mappings |
| `settings/accumulator.json` | Accumulated raw CardRecord rows across page-range runs |
| `settings/team_cache.json` | Player name → team lookup cache across runs |

---

## 6. CSV column order (current)

```
type, sub_type, year, brand, set, insert, attributes, card_number,
player, team, base, base_serial, parallel_1, serial_1, parallel_2, serial_2, ...
```

**Note on naming**: `sub_type` holds the sport value (what was previously called `sport`). `attributes` holds section/leftover-player-text/autograph flags (what was previously called `sub_type`). This was a deliberate rename by Brandon to match his database schema.

---

## 7. Prompt flow (current)

On "Extract Checklist":
1. **"Use same settings?"** — Yes / No / Cancel (if prior run exists).
   - Yes → skip to page range prompts (everything else reuses).
   - No → show all prompts with last values pre-filled.
   - Cancel → abort.
2. **Checklist type** — Set / Player / Team (dropdown).
3. **Sport** — text field.
4. **Type-specific prompts**:
   - Set: Fetch Team? (Yes/No) → Team (if No) → Section
   - Player: Primary Player → Team
   - Team: Team
5. **Start page** — blank = page 1. Pre-fills last start only if > 1.
6. **End page** — blank = all remaining pages. Pre-fills last end only if last end > new start (stale end ≤ start is always wrong and would stop after one page).

---

## 8. Open issues / known problems

### OPEN_ISSUE_1: Pagination above page 999 still stopping after one page (UNCONFIRMED FIX)

**Root cause identified**: BSC formats page numbers ≥ 1000 with commas (`"1,000"`, `"1,387"`). `str.isdigit()` returns False for these, so `_pagination_status()` never counted them in `highest`. This capped `highest` at 999, causing `has_next_page()` to return False at page 999, and any run starting at page ≥ 1000 to stop immediately after one page.

**Fix pushed** (62b39da): `.replace(",", "")` before `isdigit()` and before all button text comparisons in `_pagination_status()`, `click_next()`, and `navigate_to_page()`.

**Status**: Fix pushed, not yet confirmed working by Brandon. He reported "not working" after the push but the conversation ended before he could report the status bar message. **First thing to do next session: confirm whether this fix resolved the issue**, and if not, get the exact status bar text when it stops.

### OPEN_ISSUE_2: Dialog sizes still inconsistent (reported "no change" after PromptDialog)

Brandon reported dialogs still not uniform after the `PromptDialog` fix. The app was actually running fine (window was behind the terminal — confirmed from screenshot). It's unclear whether the sizing is actually still broken or if he hadn't yet seen the dialogs with the new code. **Confirm next session.**

### OPEN_ISSUE_3: `click_next()` may still fail for buttons hidden in ellipsis

`click_next()` now falls back to URL navigation when the next-page button is hidden in BSC's `"..."`. This was added as a fix but the comma issue (OPEN_ISSUE_1) was the actual cause of the stopping behavior. If OPEN_ISSUE_1 is confirmed fixed, OPEN_ISSUE_3 may never be needed in practice — but the fallback is harmless and should be kept.

### Older open items from HANDOFF_1 still unresolved:

- `"Parallel"` Variant category not specifically tested against Insert/Parallel-merge logic (probably fine, not verified).
- No player-name standardization rules.

---

## 9. Working norms (additions to HANDOFF_1 §10)

- **`branch_set_exceptions.csv` is gitignored** — Brandon edits it locally. Never recreate it in the repo. If it's missing from his machine, the parser falls back to the first-word brand rule.
- **All new settings/state files go in `settings/` and get gitignored** — `accumulator.json`, `team_cache.json`, `last_run.json` are all local user state.
- **`PromptDialog` is the only way to show dialogs** — `QInputDialog` and `QMessageBox` both ignore `setFixedWidth` on macOS. Do not reintroduce them.
- **Playwright on main thread, always** — see §2. Do not move any Playwright call to a background thread.
- **Status bar is the primary diagnostic tool** — when something stops unexpectedly, the status bar text is the first thing to ask Brandon about. The `on_status` callback in `extract_all_pages` now posts per-page progress so you can see exactly which page it stopped on.
- **BSC pagination quirks**:
  - No real Next button — must click the numbered page button.
  - Sliding window hides most page numbers — `click_next()` and `navigate_to_page()` both fall back to URL (`p=N`) when the button isn't visible.
  - Numbers ≥ 1000 formatted with commas — always `.replace(",", "")` before comparing or calling `isdigit()`.
  - `p=` (not `page=`) is the URL pagination parameter.
