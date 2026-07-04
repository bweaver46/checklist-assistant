# HANDOFF_5.md — Checklist Assistant

Short handoff - read HANDOFF_4.md first (multi-source support: Beckett,
TCDB). This file covers one small open item from right after that.

## Open item: brand_set_exceptions.csv additions

Brandon asked to add a batch of vintage/oddball brand names to
`settings/brand_set_exceptions.csv` so they're treated as the FULL
brand (not split first-word-is-brand the way `parse_set()` normally
works - see `exporter/convert.py`). This file is gitignored - it lives
only on Brandon's machine, not in the repo, so nothing has actually
been added yet. He needs to paste these in himself.

**Ready to give him as-is** (format: `pattern,brand,set`, set left
blank, matching the existing convention for names that are already
their own brand with no separate parent company - e.g. how
"Bowman's Best" is presumably already in his file):

```
Mother's Cookies,Mother's Cookies,
Jay Publishing,Jay Publishing,
Manny's Baseball Land,Manny's Baseball Land,
Sports Service,Sports Service,
Zip'z Discs,Zip'z Discs,
Wonder Bread,Wonder Bread,
Wiffle Ball Discs,Wiffle Ball Discs,
Western Playground Association,Western Playground Association,
Wendy's Discs,Wendy's Discs,
Tuff Stuff Classic,Tuff Stuff Classic,
Tuff Stuff,Tuff Stuff,
U.S. Playing Card Co.,U.S. Playing Card Co.,
Whitehead & Hoag,Whitehead & Hoag,
TRUE Value,TRUE Value,
JD McCarthy Postcards,JD McCarthy Postcards,
```

**Blocked on confirmation - asked, not yet answered:**

1. His original list had both "Wilson Meat's" and "Wiffle Wilson
   Meat's" back to back - looks like voice-to-text garbling (possibly
   a stray duplicate, and/or the apostrophe placement is off - "Wilson
   Meats" or "Wilson's Meats" would be the more likely real name).
   Need the real name(s) before adding anything for this one.
2. "Universal Match County" - almost certainly should be "Universal
   Match Corp" (a real vintage card issuer), but not confirmed.

Next session: ask Brandon for the corrected names, then give him the
final 2-3 CSV lines to paste in. Don't guess at these - the whole
point of the exceptions file is precise, deliberate brand-name
overrides, and a wrong entry here would silently mis-tag every card
that matches it.

## Everything else

No other changes since HANDOFF_4.md. See that file for the full
Beckett/TCDB build (parsers, site detection, main_window wiring) and
its one unconfirmed piece (`click_beckett_full_checklist()` - not yet
tested against a live browser).
