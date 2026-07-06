# HANDOFF_6.md — Checklist Assistant

Read HANDOFF_1.md first (core architecture, field-mapping rules,
working norms) if you haven't. This file covers a `parse_set()`/brand-
exceptions session that followed HANDOFF_4 (multi-source: Beckett,
TCDB) and HANDOFF_5 (a small pending item that's now resolved, see
below).

## What happened this session

Brandon spent a long session identifying vintage/oddball card brands
(food-issue premiums, regional issuers, promo sets - Mother's Cookies,
Wonder Bread, Burger King, etc.) that were parsing wrong: `parse_set()`
normally treats the FIRST WORD after the year as brand and everything
else as set, which breaks for multi-word brand names like "Mother's
Cookies" (would otherwise become brand "Mother's", set "Cookies").

### 1. ~160 new brand_set_exceptions.csv entries

All delivered as a single downloadable file:
`brand_set_exceptions_master_list.csv` (given directly to Brandon, not
committed to the repo - that file is gitignored, lives only on his
machine). If you need the full list, ask Brandon for it or regenerate
by re-reading this conversation - it is NOT duplicated in the repo on
purpose, to avoid two sources of truth silently drifting apart.

**The established convention** (confirmed against the real,
already-working entries in `tests/test_exporter_pipeline.py`, e.g.
"Finest"/"Topps"/"Finest" and "Upper Deck"/"Upper Deck"/"Upper Deck"):
that's for names where the exception's OWN brand differs from a
"parent company" pattern, or where the CSV is repeating the full
product name into `set` on purpose. For Brandon's new batch - genuine
standalone brand names with no further subdivision - the correct
convention (confirmed directly by Brandon: "it looks like Mother's
Cookies worked as long as it wasn't followed by anything... if it
starts with the [pattern], that becomes the brand, anything after that
becomes the set") is **blank `set`**, e.g. `Mother's Cookies,Mother's
Cookies,` - NOT `Mother's Cookies,Mother's Cookies,Mother's Cookies`.
I got this wrong once mid-session (copied the wrong convention from a
different kind of exception) and had to correct a full batch - if
building more of these, blank `set` is correct for a "this whole
phrase is simply the brand" entry.

**Alias pairs** (same real-world brand, two different ways it shows up
in the source text) - both patterns map to the SAME brand text:
- `Royal Crown Cola` and `Royal Crown` -> both brand `Royal Crown Cola`
- `Bishop and Company` and `Bishop and Co.` -> both brand `Bishop and
  Company`

**Explicit brand/set splits** (Brandon gave the exact desired output,
not just "whole phrase = brand"):
```
Sports Cards Magazine - 2000 Fleer Greats of the Game Exclusive -> Sports Cards Magazine / 2000 Fleer Greats of the Game Exclusive
Sports Equation Math Learning Cards-Addition & Subtraction -> Sports Equation Math Learning Cards / Addition & Subtraction
New Pinnacle -> Pinnacle / New
National Baseball Card Day -> Topps / National Baseball Card Day
Mono Cigarettes Baseball (T217) -> Mono Cigarettes Baseball / T217
R&N China Topps -> Topps / R&N China
Pacific/Advil Nolan Ryan -> Pacific / Advil
The Diamond King Diamond Immortals -> Panini / The Diamond King Diamond Immortals
```
Note on `R&N China Topps` and `Pacific/Advil Nolan Ryan`: these use
the FULL literal phrase as the pattern (not just the first word/token),
because `match_brand_set_exception()` always appends any leftover
words onto `set` (see `exporter/convert.py`, "nothing gets silently
dropped"). Matching the whole known phrase is what keeps `set` exactly
"Advil" instead of "Advil Nolan Ryan". If either product's real set
text ever has different trailing words, these specific lines will stop
matching and need adjusting - they are exact-phrase matches, not
prefix rules.

Caught (by Brandon, not proactively) and corrected mid-session:
"Louisville Sluger" -> "Louisville Slugger" (missing g), "Baseball
Treasure" -> "Baseball Treasure Chest" (incomplete name - the 2-word
version would have partial-matched and dumped "Chest" into `set`
instead of leaving it blank).

### 2. Hard-coded "Unlicensed" rule (real code change, not CSV)

Per Brandon: wherever the literal text "(unlicensed)" appears anywhere
in a product's Set text, brand ALWAYS becomes "Unlicensed" and the rest
of the text (with "(unlicensed)" removed, year still extracted
normally if present) becomes `set` - regardless of the normal
first-word-is-brand rule or any exceptions entry. Explicitly NOT put in
the CSV since the surrounding wording varies per product; only the
word "unlicensed" itself is the reliable signal.

Implemented in `exporter/convert.py`, `parse_set()`, checked FIRST
before any other logic (year-stripping, exceptions, first-word split).
Example: `"The Press Box Collector's Choices of the 1980's
(unlicensed)"` -> `("", "Unlicensed", "The Press Box Collector's
Choices of the 1980's")`. Tested with and without a leading year, and
for case-insensitivity ("(Unlicensed)" also works). Full existing test
suite (`tests/test_exporter_pipeline.py`) still passes - confirmed by
temporarily recreating a local stand-in `settings/brand_set_exceptions.csv`
(matching the exact entries that file's own tests expect, e.g. Finest/
Topps Now/Bowman's Best/Stadium Club/Upper Deck/UD/President's Choice/
Lauran Taylor) since that file is gitignored and doesn't exist in a
fresh clone.

### 3. Real bug found and fixed: BOM silently broke the WHOLE exceptions file

After Brandon pasted the new batch in, he reported NONE of the
exceptions worked - not even ones that supposedly already worked
(like Baseball Treasure). This smelled like a structural bug, not bad
entries, so it got diagnosed rather than re-guessed at.

**Root cause**: `load_brand_set_exceptions()` opened the CSV with
plain `encoding="utf-8"`. Excel and Numbers (both very plausible given
Brandon edits this file as a spreadsheet) commonly write a UTF-8 BOM
character at the very start of a saved CSV. That BOM attaches itself
to the FIRST column header, silently turning `pattern` into
`\ufeffpattern` - which means `row.get("pattern")` returns `None` for
**every row in the file**, not just the new ones, and the entire
exceptions list silently loads as empty (no crash, no error message -
by design, "missing file -> empty list, no crash," but a BOM-corrupted
file looks identical to a missing one at that point).

**Fix**: changed the file open to `encoding="utf-8-sig"`, which strips
a leading BOM if present and behaves identically to `utf-8` when there
isn't one - confirmed both ways with a real test (BOM-prefixed file
now loads correctly; plain file unaffected). Full test suite still
passes. Pushed to `main`.

**Not yet confirmed**: whether this was actually the cause of
Brandon's specific failure - he hadn't tested the fix yet as of this
handoff. First thing to check next session: did pulling the latest
code and re-running actually fix it? If not, get the EXACT way he
edits/saves that file (which app, which save format) rather than
guessing at a second theory - this bug was diagnosed with a real
reproduction, not assumed, and the next one should be too if this
wasn't it.

## Everything else

No other changes since HANDOFF_5.md (Wilson Meat's / Wiffle Ball
Discs were confirmed as two separate real names; Universal Match
County confirmed correct as typed, not a typo). See HANDOFF_4.md for
the full Beckett/TCDB multi-source build - still has one unconfirmed
piece (`click_beckett_full_checklist()`, never run against a live
browser).
