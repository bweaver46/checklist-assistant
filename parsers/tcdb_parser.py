"""
TCDB Parser

Parses a set checklist page from tcdb.com (e.g.
tcdb.com/Checklist.cfm/sid/72/1972-Topps) into raw card rows.

Structure of the source HTML (confirmed by direct DOM inspection,
2026-07-04, against the live 1972 Topps checklist page):

    Each card is one <tr> in the checklist table. Column positions are
    fixed (confirmed against a real row, index by position rather than
    by content since several columns are blank spacers):
        td[0], td[1]  - front/back thumbnail images (unused)
        td[4]         - card number, inside an <a> tag
        td[8]         - player name + tags + optional note:
                          <a>Player Name</a> TAG, TAG<br>
                          <figcaption class="figure-caption">note</figcaption>
                        Non-player cards (Team Cards, Checklist cards)
                        have no <a> here - just plain text + tags.
        td[11]        - team, inside an <a> tag (blank for non-team-
                        specific cards like Checklist cards)

    Pagination: ?PageIndex=N query parameter on the same URL.

    Glossary: each set has its own glossary page (GlossaryS.cfm) that
    defines what every tag abbreviation means (RC = Rookie Card, TC =
    Team Card, VAR = Variation, etc.) - fetched separately, not parsed
    from the checklist page itself.

Tag handling (per Brandon, 2026-07-04):
    - Short codes are kept as-is in attributes (e.g. "RC", "TC"), not
      expanded to the full glossary term.
    - VAR is the one exception: it does NOT go into attributes at all.
      A VAR tag means this card is a printing variation - it becomes a
      PARALLEL instead, using the note text as the parallel name (the
      leading "VAR: " prefix is stripped if present, e.g. note
      "VAR: Yellow under bottom of C and S" -> parallel name
      "Yellow under bottom of C and S").
    - Any other note text (e.g. "RC for Anderson only") gets appended
      onto attributes verbatim, alongside whatever tags are present.

Lettered variants (18a/18b, 29a/29b, 45a/45b, ...): grouped under one
base card_number, same LETTER_VARIANT_PATTERN convention already used
for BSC (see exporter/convert.py). Each lettered row's VAR note becomes
one parallel slot on the merged row - this is a simpler version of
BSC's Insert/Parallel grouping (no common-prefix text stripping needed,
since TCDB already gives a clean, specific note per letter).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from exporter.convert import LETTER_VARIANT_PATTERN

VAR_NOTE_PREFIX = re.compile(r"^VAR:\s*", re.IGNORECASE)
TRAILING_TAG_LIST = re.compile(r"\s+([A-Z]{2,4}(?:,\s*[A-Z]{2,4})*)\s*$")


def _parse_player_cell(td: Tag) -> tuple[str, list[str], str]:
    """Returns (player, tags, note). player is the linked player name
    when present, or the plain descriptive text for non-player cards
    (Team Cards, Checklist cards, multi-player description cards) with
    any trailing tag list stripped off."""
    link = td.find("a")
    figcaption = td.find("figcaption")
    note = figcaption.get_text(strip=True) if figcaption else ""

    if link:
        player = link.get_text(strip=True)
        cell = BeautifulSoup(str(td), "html.parser")
        if cell.find("a"):
            cell.find("a").decompose()
        if cell.find("figcaption"):
            cell.find("figcaption").decompose()
        if cell.find("br"):
            cell.find("br").decompose()
        tag_text = cell.get_text(strip=True)
        tags = [t.strip() for t in tag_text.split(",") if t.strip()]
        return player, tags, note

    # No player link - a Team Card, Checklist card, or a descriptive
    # multi-player card name. Tags (if any) are a trailing comma-
    # separated list of short all-caps codes at the very end of the
    # plain text; everything before that is the descriptive name.
    cell = BeautifulSoup(str(td), "html.parser")
    if cell.find("figcaption"):
        cell.find("figcaption").decompose()
    if cell.find("br"):
        cell.find("br").decompose()
    full_text = cell.get_text(strip=True)
    match = TRAILING_TAG_LIST.search(full_text)
    if match:
        tags = [t.strip() for t in match.group(1).split(",") if t.strip()]
        player = full_text[: match.start()].strip()
    else:
        tags = []
        player = full_text

    return player, tags, note


def _parse_row(tr: Tag) -> dict | None:
    tds = tr.find_all("td", recursive=False)
    if len(tds) < 12:
        return None

    card_number_link = tds[4].find("a")
    card_number = card_number_link.get_text(strip=True) if card_number_link else ""
    if not card_number:
        return None

    player, tags, note = _parse_player_cell(tds[8])

    team_link = tds[11].find("a")
    team = team_link.get_text(strip=True) if team_link else ""

    parallel_name = ""
    attributes_tags = []
    for tag in tags:
        if tag.upper() == "VAR":
            parallel_name = VAR_NOTE_PREFIX.sub("", note).strip() if note else ""
        else:
            attributes_tags.append(tag)

    # A non-VAR note (e.g. "RC for Anderson only") gets appended onto
    # attributes verbatim, alongside any tags.
    if note and not parallel_name:
        attributes_tags.append(note)

    return {
        "card_number": card_number,
        "player": player,
        "team": team,
        "attributes": ", ".join(attributes_tags),
        "parallel_name": parallel_name,  # "" unless this row is a VAR row
    }


def _group_lettered_variants(rows: list[dict]) -> list[dict]:
    """Merge rows like 18a/18b (same base number) into one row, each
    lettered row's parallel_name becoming one parallel_N slot on the
    merged row. Rows with no letter suffix pass through unchanged."""
    grouped: list[dict] = []
    index_by_base: dict[str, int] = {}

    for row in rows:
        match = LETTER_VARIANT_PATTERN.match(row["card_number"])
        if not match:
            out = dict(row)
            out["parallels"] = []
            out.pop("parallel_name", None)
            grouped.append(out)
            continue

        base_number = match.group(1)
        if base_number not in index_by_base:
            merged = dict(row)
            merged["card_number"] = base_number
            merged["parallels"] = []
            merged.pop("parallel_name", None)
            index_by_base[base_number] = len(grouped)
            grouped.append(merged)

        target = grouped[index_by_base[base_number]]
        if row["parallel_name"]:
            target["parallels"].append((row["parallel_name"], ""))
        # Attributes (e.g. RC) should still show up on the merged row
        # even if only one lettered variant carried the tag.
        if row["attributes"]:
            existing = [a.strip() for a in target["attributes"].split(",") if a.strip()]
            for attr in row["attributes"].split(","):
                attr = attr.strip()
                if attr and attr not in existing:
                    existing.append(attr)
            target["attributes"] = ", ".join(existing)

    return grouped


def parse_tcdb_checklist(page_html: str) -> list[dict]:
    """Parse one page of a TCDB set checklist into a list of raw row
    dicts: card_number, player, team, attributes, parallels (list of
    (parallel, serial) tuples)."""
    soup = BeautifulSoup(page_html, "html.parser")

    raw_rows = []
    for tr in soup.find_all("tr"):
        row = _parse_row(tr)
        if row is not None:
            raw_rows.append(row)

    return _group_lettered_variants(raw_rows)
