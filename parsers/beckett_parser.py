"""
Beckett Parser

Parses the "Full Checklist" tab content from a Beckett News checklist
article (e.g. beckett.com/news/2025-bowman-baseball-cards/) into raw
card rows.

Structure of the source HTML (confirmed by direct DOM inspection,
2026-07-03, against the live 2025 Bowman Baseball page):

    <h2> = top-level category (Base Set, Prospects, Autographs, Inserts)
    <h3> = individual checklist name, always ends in the literal word
           "Checklist" (e.g. "Anime Checklist") - that suffix is
           stripped when used as the Insert value. Categories with no
           <h3> (e.g. "Base Set") have their cards directly under the
           <h2>; Insert is blank for these.
    <h4 class="wp-block-heading"></h4> (empty) - a continuation marker
           when one checklist's card lines span multiple <p> blocks
           (e.g. cards 1-50 in one <p>, 51-100 in the next). NOT a new
           checklist - ignored entirely.
    The FIRST <p> after any heading is ALWAYS metadata, never card
           data - normally a caption like "34 cards." or
           "35 cards.<br>Retail only.", but even when it isn't (e.g.
           the page's own intro paragraph under the master title) it's
           still skipped, so nothing needs special-casing for that.
    Any OTHER <p> containing an <em> or <a> tag is commentary/notes,
           not card data (e.g. Base Set's "(RC) notes players..."
           explainer) - skipped.
    All remaining <p> tags are card lines, one per <br>-separated
           segment.

Card line formats seen (each segment after splitting on <br>):
    "<CARDNUM> <Name>, <Team>"        - the common case
    "<Name>, <Team>"                   - no card number (e.g. All
                                          America Game Autographs)
    "<Name>"                            - no card number, no team
                                          (e.g. Bowman Buyback
                                          Autographs - retired legends)
    "<CARDNUM> <Name1> / <Name2>, <Team>" - dual autograph, already one
                                          line, no special handling
    Trailing "RC" or "(RC)"             - rookie card flag, stripped
                                          and recorded in attributes.

Special case - single-card checklists with stacked signer lines (e.g.
the "2025 Ultimate Autograph Book Card Checklist", declared as
"1 card." but listing 24 names on 24 lines, only the first of which
has a card number): when a checklist's DECLARED COUNT is exactly 1,
every one of its card lines is combined into ONE output row (names
joined with " / ", teams joined the same way, same positional order).
This is driven by the declared count, not by guessing whether a line
lacks a card number - Buyback Autographs and All America Game
Autographs also have lines with no card number, but their declared
counts are >1, so those correctly stay one row per line.

Known data nuance (not a parser bug - flag to Brandon, don't silently
fix): some Insert checklists (e.g. "Anime Kanji Variations", "Etched
in Glass Variations") re-list card numbers that already appear under a
different Insert earlier on the page - they're marking which existing
cards ALSO have that variation, not introducing new distinct cards.
The parser has no way to distinguish this from a genuinely new card
using only this page's structure, so both show up as separate rows.

Parallels (confirmed 2026-07-04 against the 2025 Donruss Baseball
page - NOT present on the Bowman flagship page, format varies by
product): some sections include a blanket parallel list for every
card in that section, e.g. under "Base Set Checklist":

    <p>200 cards<br>Parallels</p>   <- still just the caption, skipped
    <ul class="wp-block-list">
        <li>Green Laser</li>                    <- no serial
        <li>Orange Laser /299</li>              <- numbered serial
        <li>Artist Proof Black 1/1</li>         <- one-of-one
    </ul>
    <p>1 Luisangel Acuna, New York Mets<br>...</p>   <- card lines

Subsection labels (confirmed 2026-07-04 against the 2025 Donruss
Baseball page): most <h3> headings end in the literal word
"Checklist" and define a new Insert ("Anime Checklist" -> Insert
"Anime"). Some don't - e.g. "Rated Prospects", which continues the
Base Set's own card numbering (100 -> 101) rather than starting a new
checklist. Per Brandon: an <h3> WITHOUT the "Checklist" suffix is a
SUBSECTION LABEL, not a new Insert - it goes into attributes instead,
and Insert is left unchanged (in this case, still blank, since it's
still part of Base Set). It still gets its own caption/parallel-list
scope like any other heading; only where its name is written differs.

Plain-paragraph blanket parallels (confirmed 2026-07-26, Brandon -
Dual Autographed Preeminent Pieces / Dual Preeminent Relics inserts):
some products write their blanket parallel list as bare paragraph
lines instead of the <ul><li> structure above, e.g.:

    <p>4 cards<br>Parallel</p>            <- still just the caption
    <p>Gold /1</p>                          <- the parallel list itself,
                                                just one entry here
    <p>PPDAR-HRJ Cal Ripken Jr./Gunnar Henderson, Baltimore Orioles /5
    <br>...(more card lines)</p>

Same meaning as the <ul> case (this parallel applies to every card in
the section) - just different markup. Detected by
_looks_like_parallel_list_paragraph(): a <p> where EVERY line has no
comma and ends in "/<digits>" or "1/1" is treated as a parallel-list
update rather than card-buffer lines. Note each of these cards ALSO
had its own individual print-run serial appended to its team text
(e.g. "Baltimore Orioles /5") - that's the separate base_serial pattern
documented in _parse_line's docstring, not a parallel at all; a card
can have both a base_serial AND a blanket parallel with its own serial
at the same time, they're independent.

Team suffixes (confirmed 2026-07-26, Brandon): a card line's Team can
carry two different kinds of trailing text that are NOT part of the
team name - see _parse_line's docstring for the full rules:
    "Pittsburgh Pirates (All-Star Game)" - parenthetical card
        attribute, moved to attributes.
    "Texas Rangers /25" - the card's own print-run serial, moved to
        base_serial.

New-Insert detection when the heading doesn't say "Checklist"
(confirmed 2026-07-26, Brandon - 2026 Topps Pristine page): the
"<h3> ends in Checklist" rule assumed every product names its insert
headings that way. Pristine doesn't - headings like "Pristine
Autographs", "Spotless Signatures", "Monogram", "Italics" never say
"Checklist", but each IS a genuinely separate checklist (own card-
number prefix: PA-, SS-, M-, I-...), not a subsection of whatever
came before. Per Brandon: "99% of sets have a different prefix" for
a real new insert; the exception is products like Donruss where an
insert is numbered plainly 1, 2, 3... with no letter prefix - but
those headings DO say "...Checklist", so the original rule already
covers them.

New rule: an <h3> starts a new Insert if EITHER (a) it ends in the
word "Checklist" (original rule, unchanged), OR (b) the card-number
prefix of the first card line under it differs from the prefix
active immediately before this heading. Prefix = the text before the
first "-" in a card number (e.g. "PA-AF" -> "PA", "A-1" -> "A"), or
"" for a plain numeric card number like "101". Classification is
deferred until that first card line is seen (the heading alone
doesn't carry a card number), tracked via `pending_heading` /
`last_prefix` in parse_beckett_checklist(). last_prefix resets to
None at every <h2> category boundary, so the first <h3> under a new
top-level category is always treated as a new Insert even if its
prefix happens to be blank (there's nothing prior in that category to
"continue"). This preserves the confirmed Rated Prospects case (same
"" prefix as Base Set immediately before it -> stays a subsection)
while correctly splitting Pristine's un-suffixed insert headings.

"Base - X" variation re-listing (confirmed 2026-07-26, Brandon -
2026 Topps Chrome page): some products (Chrome's own "Variations"
category) write headings like "Base - Lightboard Variations",
"Base - Image Variations", "Base - Award Winner Variations" that
re-list Base Set's OWN card numbers (1, 2, 7, 9, 12...) - these mean
"this existing Base Set card ALSO comes in this variation," not "here
are new physical cards." This is unambiguous (unlike the general
re-listing nuance noted above) because of the literal "Base -"
prefix, so it's handled directly rather than left as a flagged
limitation: any <h3> matching BASE_VARIATION_PREFIX merges its card
lines onto the matching already-emitted Base Set row (matched by
card_number, insert=="") as an EXTRA parallel tuple
(name, serial) - name is the heading text with the "Base -" prefix
stripped (redundant once merged onto the base row), serial is
whatever trailing "/N" the line's team field carries (e.g. "1 Shohei
Ohtani, Los Angeles Dodgers /25" -> serial "25"), blank if none. No
new row is emitted for these lines at all. Doesn't yet handle a
variation section's OWN parallel sub-rainbow (e.g. Image Variations'
own Green/Purple/Gold Refractor list) - only the base variation
marker itself; flag to Brandon if that layer is ever needed.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from exporter.convert import split_trailing_slash_serial

CAPTION_LINE = re.compile(r"^\d+\s+cards?\b", re.IGNORECASE)
RC_SUFFIX = re.compile(r"\s*\(RC\)\s*$|\s+RC\s*$")
CARD_NUM_TOKEN = re.compile(r"^(?:\d+[A-Za-z]*|[A-Za-z]+\d+|[A-Z0-9]+-[A-Z0-9\-]+)$")
CHECKLIST_SUFFIX = re.compile(r"\s*Checklist\s*$", re.IGNORECASE)
BASE_VARIATION_PREFIX = re.compile(r"^Base\s*[\u2013\u2014-]\s*", re.IGNORECASE)
# Used by extract_flat_checklist_html() - see its docstring.
CHECKLIST_TITLE_PATTERN = re.compile(
    r"Checklist(\s*[\u2013\u2014-]\s*Master Card List)?\s*$", re.IGNORECASE
)
FOOTER_BOUNDARY_PATTERN = re.compile(r"protect your collection with", re.IGNORECASE)
ONE_OF_ONE_SUFFIX = re.compile(r"^(.*?)\s+1/1\s*$")
TEAM_PAREN_SUFFIX = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")
PARALLEL_LINE_PATTERN = re.compile(r"^[^,]+?(?:\s+/\d+|\s+1/1)\s*$")
ALL_CARDS_SERIAL_PATTERN = re.compile(r"^all cards are\s*/(\d+)", re.IGNORECASE)


def _extract_prefix(card_number: str) -> str:
    """'PA-AF' -> 'PA'. 'A-1' -> 'A'. '101' -> '' (plain numeric, no
    letter prefix). Used to detect a genuinely new Insert when its
    heading doesn't say 'Checklist' - see module docstring."""
    if "-" in card_number:
        return card_number.split("-", 1)[0]
    return ""


def _parse_parallel_li(text: str) -> tuple[str, str]:
    """'Orange Laser /299' -> ('Orange Laser', '299').
    'Artist Proof Black 1/1' -> ('Artist Proof Black', '1/1') - special
    cased since split_trailing_slash_serial would otherwise misread
    '1/1' as name '1' + serial '1'.
    'Green Laser' -> ('Green Laser', '') - no serial."""
    text = text.strip()
    one_of_one = ONE_OF_ONE_SUFFIX.match(text)
    if one_of_one:
        return one_of_one.group(1).strip(), "1/1"
    name, serial = split_trailing_slash_serial(text)
    return name.strip(), serial


def _parse_parallel_list(ul_tag: Tag) -> list[tuple[str, str]]:
    return [
        _parse_parallel_li(li.get_text())
        for li in ul_tag.find_all("li")
        if li.get_text(strip=True)
    ]


def _clean_lines(p_tag: Tag) -> list[str]:
    """Split a <p> tag's text on its <br> tags into stripped,
    non-empty lines."""
    for br in p_tag.find_all("br"):
        br.replace_with("\n")
    text = p_tag.get_text()
    return [line.strip() for line in text.split("\n") if line.strip()]


def _extract_count(p_tag: Tag) -> int | None:
    """Read a leading 'N card(s)' count off a <p> tag's first line,
    or None if it doesn't start that way."""
    lines = _clean_lines(p_tag)
    if not lines:
        return None
    match = CAPTION_LINE.match(lines[0])
    if not match:
        return None
    return int(re.match(r"^\d+", lines[0]).group())


def _extract_all_cards_serial(p_tag: Tag) -> str:
    """Read a section-wide serial note off the caption paragraph's
    OTHER lines (e.g. 'Vintage Stock Variations' caption reads
    '100 cards<br>All cards are /99' - the count line is handled by
    _extract_count, this reads the '/99' the caption states for every
    card in the section). Confirmed 2026-07-26 (Brandon, real 2026
    Topps Series 1 data): this note used to be silently discarded
    entirely (only the caption's first line was ever read), so a
    "Base - Vintage Stock Variations" merge onto Base Set rows (see
    BASE_VARIATION_PREFIX handling) landed with no serial at all even
    though the page states one for the whole section. Returns '' if no
    such line is present."""
    for line in _clean_lines(p_tag)[1:]:
        match = ALL_CARDS_SERIAL_PATTERN.match(line)
        if match:
            return match.group(1)
    return ""


def _is_commentary(p_tag: Tag) -> bool:
    return p_tag.find("em") is not None or p_tag.find("a") is not None


def _looks_like_parallel_list_paragraph(lines: list[str]) -> bool:
    """True if every line looks like a blanket-parallel entry (a name
    with no comma, ending in '/<digits>' or '1/1') rather than a real
    card line. Confirmed 2026-07-26 (Brandon) - some products write
    their blanket parallel list as bare paragraph lines (e.g.
    "Gold /1" on its own line right after the caption) instead of the
    <ul><li> structure this parser already handled - same meaning
    (this parallel applies to every card in the section), different
    markup. A real card line always either has a comma (", Team") or,
    in the rare no-team case, is just a plain name that does NOT end
    in a slash-number or "1/1" - so requiring ALL lines in the
    paragraph to match this shape is a safe, narrow signal."""
    return bool(lines) and all(PARALLEL_LINE_PATTERN.match(line) for line in lines)


def _parse_line(line: str) -> tuple[str, str, str, bool, str, str]:
    """Split one card line into
    (card_number, name, team, is_rc, team_note, base_serial).
    card_number/team are '' when not present in the line.

    team_note is a parenthetical note trailing the team name (e.g.
    "Pittsburgh Pirates (All-Star Game)" -> team "Pittsburgh Pirates",
    team_note "All-Star Game") - it's a card attribute, not part of the
    team, and gets folded into attributes by the caller.

    base_serial is a print-run number trailing the team with no
    parallel name attached (e.g. "Texas Rangers /25" -> team
    "Texas Rangers", base_serial "25") - this is the card's OWN serial
    number, not a named parallel, so it belongs in base_serial rather
    than the parallels list. Confirmed against Brandon's report
    2026-07-26 - a card line's team can carry either of these
    trailing suffixes.
    """
    is_rc = False
    match = RC_SUFFIX.search(line)
    if match:
        is_rc = True
        line = line[: match.start()].strip()

    card_number = ""
    rest = line
    parts = line.split(" ", 1)
    if len(parts) == 2 and CARD_NUM_TOKEN.match(parts[0]):
        card_number, rest = parts[0], parts[1].strip()

    if "," in rest:
        name, team = rest.rsplit(",", 1)
        name, team = name.strip(), team.strip()
    else:
        name, team = rest.strip(), ""

    team_note = ""
    paren_match = TEAM_PAREN_SUFFIX.match(team)
    if paren_match:
        team, team_note = paren_match.group(1).strip(), paren_match.group(2).strip()

    base_serial = ""
    stripped_team, serial = split_trailing_slash_serial(team)
    if serial:
        team, base_serial = stripped_team.strip(), serial

    return card_number, name, team, is_rc, team_note, base_serial


def _build_attributes(category: str, is_rc: bool, subsection: str = "", team_note: str = "") -> str:
    tags = []
    if is_rc:
        tags.append("RC")
    if subsection:
        tags.append(subsection)
    if team_note:
        tags.append(team_note)
    if category == "Autographs":
        tags.append("Autograph")
    return ", ".join(tags)


def extract_flat_checklist_html(full_page_html: str) -> str | None:
    """For Beckett articles with NO tabs structure at all - a single
    flat article body (e.g. 2026 Topps Hobby Rip Night Baseball,
    confirmed 2026-07-26 Brandon) rather than Pristine/Chrome's tabbed
    layout or Road To Opening Day's per-category-tabs-no-aggregate
    layout. Feeding the WHOLE page to parse_beckett_checklist() would
    misparse every h2/h3/p on the page (nav menu, footer, comments,
    related articles) as if it were checklist content - the exact
    "garbage rows" problem the hard error this replaces was written
    to avoid.

    Isolates just the real checklist content using two boundaries
    confirmed identical across every Beckett checklist article seen
    so far (tabbed or not):
      - START: the heading (h1/h2/h3) that IS the checklist section
        title - ends in "Checklist", optionally followed by
        "- Master Card List" (Pristine/Chrome's phrasing). This is
        NOT the same as the page's overall <h1> article title, which
        usually says "... Checklist and Details" or similar and
        doesn't match this pattern (correctly excluded, since starting
        there would also capture the intro prose/shop links above the
        actual checklist).
      - END: the "Protect Your Collection With:" boilerplate that
        Beckett appends after every checklist, verbatim, before
        related-articles/comments/footer content.

    Returns the HTML between those two boundaries (exclusive of the
    title heading, exclusive of the boilerplate), or None if either
    boundary isn't found - callers should treat None as "couldn't
    safely isolate the checklist," not silently fall back to the whole
    page. NOT YET CONFIRMED against a live no-tabs page - report back
    what the exported CSV looks like the first time this runs for
    real."""
    soup = BeautifulSoup(full_page_html, "html.parser")
    elements = soup.find_all(["h1", "h2", "h3", "h4", "p", "ul"])

    start_idx = None
    for i, el in enumerate(elements):
        if el.name in ("h1", "h2", "h3") and CHECKLIST_TITLE_PATTERN.search(el.get_text()):
            start_idx = i + 1
            break
    if start_idx is None:
        return None

    end_idx = None
    for i in range(start_idx, len(elements)):
        if FOOTER_BOUNDARY_PATTERN.search(elements[i].get_text()):
            end_idx = i
            break
    if end_idx is None:
        return None

    return "".join(str(el) for el in elements[start_idx:end_idx])


def parse_beckett_checklist(
    container_html: str, force_new_insert_for_all_h3: bool = False,
) -> list[dict]:
    """Parse the Full Checklist tab's container HTML into a list of
    raw row dicts, each with keys: insert, card_number, player, team,
    attributes, parallels (list of (parallel, serial) tuples, [] when
    the section has no blanket parallel list).

    force_new_insert_for_all_h3: set True when container_html came
    from BrowserManager's tab-combining fallback (no aggregate "Full
    Checklist" tab existed - see click_beckett_full_checklist and
    BrowserManager.used_tab_combine_fallback), confirmed 2026-07-26
    (Brandon, Road To Opening Day). On a page like that, headings such
    as "Dual Autographs" share the same card-number prefix as the
    tab's baseline cards (both "A-"), so the normal prefix-based rule
    folds them into a subsection/attribute instead of their own
    Insert - wrong for this kind of page, where Brandon wants them
    treated as full Inserts. This flag skips the prefix comparison
    entirely and treats every <h3> as a new Insert. Only meant for
    that fallback's output - leave False for normal aggregate-tab
    HTML, where the prefix-based rule is still what's confirmed
    correct (e.g. Rated Prospects staying a subsection of Base Set)."""
    soup = BeautifulSoup(container_html, "html.parser")

    rows: list[dict] = []
    current_category = ""
    current_insert = ""
    current_subsection = ""
    current_parallels: list[tuple[str, str]] = []
    caption_seen = False
    declared_count: int | None = None
    declared_all_cards_serial: str = ""
    buffer: list[str] = []
    # Deferred Insert-vs-subsection classification (see module
    # docstring, "New-Insert detection..."). pending_heading holds an
    # <h3>'s text once seen but not yet classified; last_prefix is the
    # card-number prefix of whatever section most recently had actual
    # card lines, used as the comparison baseline.
    pending_heading: str | None = None
    pending_is_checklist_suffix = False
    last_prefix: str | None = None
    # Set when the current <h3> is a "Base - X" variation re-listing
    # (see module docstring) - card lines under it merge onto the
    # matching Base Set row instead of becoming new rows.
    base_variation_name: str | None = None

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        if declared_count == 1:
            names: list[str] = []
            teams: list[str] = []
            card_number = ""
            rc_any = False
            team_notes: list[str] = []
            base_serial = ""
            for line in buffer:
                num, name, team, is_rc, team_note, serial = _parse_line(line)
                if num and not card_number:
                    card_number = num
                names.append(name)
                if team:
                    teams.append(team)
                if team_note:
                    team_notes.append(team_note)
                if serial and not base_serial:
                    base_serial = serial
                rc_any = rc_any or is_rc
            rows.append({
                "insert": current_insert,
                "card_number": card_number,
                "player": " / ".join(names),
                "team": " / ".join(teams),
                "attributes": _build_attributes(
                    current_category, rc_any, current_subsection, ", ".join(team_notes)
                ),
                "base_serial": base_serial or declared_all_cards_serial,
                "parallels": list(current_parallels),
            })
        else:
            for line in buffer:
                num, name, team, is_rc, team_note, serial = _parse_line(line)
                rows.append({
                    "insert": current_insert,
                    "card_number": num,
                    "player": name,
                    "team": team,
                    "attributes": _build_attributes(current_category, is_rc, current_subsection, team_note),
                    "base_serial": serial or declared_all_cards_serial,
                    "parallels": list(current_parallels),
                })
        buffer = []

    prev_was_ul = False
    for el in soup.find_all(["h2", "h3", "h4", "p", "ul"]):
        is_ul = el.name == "ul"

        if el.name in ("h2", "h3") and prev_was_ul:
            # A heading immediately following a <ul> with nothing in
            # between is a LABEL naming that list (e.g. "Clearly Rated
            # Prospects" naming a preceding Black/Techno/Platinum
            # list), not the start of new content. Prepend it onto
            # every parallel already captured; leave everything else
            # (category/insert/subsection/caption state) untouched -
            # this is NOT a section boundary.
            label = el.get_text(strip=True)
            current_parallels = [
                (f"{label} {name}".strip(), serial) for name, serial in current_parallels
            ]
            prev_was_ul = is_ul
            continue

        if el.name == "h2":
            flush()
            current_category = el.get_text(strip=True)
            current_insert = ""
            current_subsection = ""
            current_parallels = []
            caption_seen = False
            declared_count = None
            declared_all_cards_serial = ""
            pending_heading = None
            last_prefix = None
            base_variation_name = None
        elif el.name == "h3":
            flush()
            text = el.get_text(strip=True)
            base_variation_match = BASE_VARIATION_PREFIX.match(text)
            if base_variation_match:
                # "Base - X" - re-lists Base Set's own numbers, merge
                # onto those rows instead of treating as a new Insert
                # or deferring classification (see module docstring).
                base_variation_name = BASE_VARIATION_PREFIX.sub("", text).strip()
                pending_heading = None
                current_subsection = ""
            else:
                base_variation_name = None
                # Classification is deferred to the first card line
                # seen under this heading (need its card-number
                # prefix) - see module docstring. Stash the heading
                # text and whether it already satisfies the old "ends
                # in Checklist" rule.
                pending_heading = text
                pending_is_checklist_suffix = bool(CHECKLIST_SUFFIX.search(text))
                current_subsection = ""
            current_parallels = []
            caption_seen = False
            declared_count = None
            declared_all_cards_serial = ""
        elif el.name == "h4":
            pass
        elif el.name == "ul":
            current_parallels = _parse_parallel_list(el)
        elif el.name == "p":
            if not caption_seen:
                declared_count = _extract_count(el)
                declared_all_cards_serial = _extract_all_cards_serial(el)
                caption_seen = True
            elif not _is_commentary(el):
                lines = _clean_lines(el)
                if _looks_like_parallel_list_paragraph(lines):
                    current_parallels = [_parse_parallel_li(line) for line in lines]
                elif lines and base_variation_name is not None:
                    for line in lines:
                        num, _name, _team, _is_rc, _team_note, serial = _parse_line(line)
                        if not num:
                            continue
                        for row in rows:
                            if row["card_number"] == num and row["insert"] == "":
                                row["parallels"].append((base_variation_name, serial or declared_all_cards_serial))
                                break
                elif lines:
                    if pending_heading is not None:
                        num, *_rest = _parse_line(lines[0])
                        prefix = _extract_prefix(num)
                        if (
                            pending_is_checklist_suffix
                            or prefix != last_prefix
                            or force_new_insert_for_all_h3
                        ):
                            current_insert = CHECKLIST_SUFFIX.sub("", pending_heading).strip()
                            current_subsection = ""
                        else:
                            current_subsection = pending_heading
                        last_prefix = prefix
                        pending_heading = None
                    elif not buffer:
                        num, *_rest = _parse_line(lines[0])
                        last_prefix = _extract_prefix(num)
                    buffer.extend(lines)

        prev_was_ul = is_ul

    flush()
    return rows
