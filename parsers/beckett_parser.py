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
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from exporter.convert import split_trailing_slash_serial

CAPTION_LINE = re.compile(r"^\d+\s+cards?\b", re.IGNORECASE)
RC_SUFFIX = re.compile(r"\s*\(RC\)\s*$|\s+RC\s*$")
CARD_NUM_TOKEN = re.compile(r"^(?:\d+|[A-Z0-9]+-[A-Z0-9\-]+)$")
CHECKLIST_SUFFIX = re.compile(r"\s*Checklist\s*$", re.IGNORECASE)
ONE_OF_ONE_SUFFIX = re.compile(r"^(.*?)\s+1/1\s*$")
TEAM_PAREN_SUFFIX = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")
PARALLEL_LINE_PATTERN = re.compile(r"^[^,]+?(?:\s+/\d+|\s+1/1)\s*$")


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


def parse_beckett_checklist(container_html: str) -> list[dict]:
    """Parse the Full Checklist tab's container HTML into a list of
    raw row dicts, each with keys: insert, card_number, player, team,
    attributes, parallels (list of (parallel, serial) tuples, [] when
    the section has no blanket parallel list)."""
    soup = BeautifulSoup(container_html, "html.parser")

    rows: list[dict] = []
    current_category = ""
    current_insert = ""
    current_subsection = ""
    current_parallels: list[tuple[str, str]] = []
    caption_seen = False
    declared_count: int | None = None
    buffer: list[str] = []

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
                "base_serial": base_serial,
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
                    "base_serial": serial,
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
        elif el.name == "h3":
            flush()
            text = el.get_text(strip=True)
            if CHECKLIST_SUFFIX.search(text):
                current_insert = CHECKLIST_SUFFIX.sub("", text).strip()
                current_subsection = ""
            else:
                # Not a new checklist/Insert - a subsection label (e.g.
                # "Rated Prospects") within whatever Insert is already
                # in effect. Insert stays unchanged; the label goes
                # into attributes instead.
                current_subsection = text
            current_parallels = []
            caption_seen = False
            declared_count = None
        elif el.name == "h4":
            pass
        elif el.name == "ul":
            current_parallels = _parse_parallel_list(el)
        elif el.name == "p":
            if not caption_seen:
                declared_count = _extract_count(el)
                caption_seen = True
            elif not _is_commentary(el):
                lines = _clean_lines(el)
                if _looks_like_parallel_list_paragraph(lines):
                    current_parallels = [_parse_parallel_li(line) for line in lines]
                else:
                    buffer.extend(lines)

        prev_was_ul = is_ul

    flush()
    return rows
