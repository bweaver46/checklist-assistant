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


def _parse_line(line: str) -> tuple[str, str, str, bool]:
    """Split one card line into (card_number, name, team, is_rc).
    card_number/team are '' when not present in the line."""
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

    return card_number, name, team, is_rc


def _build_attributes(category: str, is_rc: bool, subsection: str = "") -> str:
    tags = []
    if is_rc:
        tags.append("RC")
    if subsection:
        tags.append(subsection)
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
            for line in buffer:
                num, name, team, is_rc = _parse_line(line)
                if num and not card_number:
                    card_number = num
                names.append(name)
                if team:
                    teams.append(team)
                rc_any = rc_any or is_rc
            rows.append({
                "insert": current_insert,
                "card_number": card_number,
                "player": " / ".join(names),
                "team": " / ".join(teams),
                "attributes": _build_attributes(current_category, rc_any, current_subsection),
                "parallels": list(current_parallels),
            })
        else:
            for line in buffer:
                num, name, team, is_rc = _parse_line(line)
                rows.append({
                    "insert": current_insert,
                    "card_number": num,
                    "player": name,
                    "team": team,
                    "attributes": _build_attributes(current_category, is_rc, current_subsection),
                    "parallels": list(current_parallels),
                })
        buffer = []

    for el in soup.find_all(["h2", "h3", "h4", "p", "ul"]):
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
            continue
        elif el.name == "ul":
            current_parallels = _parse_parallel_list(el)
        elif el.name == "p":
            if not caption_seen:
                declared_count = _extract_count(el)
                caption_seen = True
                continue
            if _is_commentary(el):
                continue
            buffer.extend(_clean_lines(el))

    flush()
    return rows
