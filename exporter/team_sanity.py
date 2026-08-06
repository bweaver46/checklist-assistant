"""
Phase 7b: team/sport sanity check.

Flags rows where the card's Team text doesn't belong to the sport the
pull was run under - catches scraper cross-contamination (Brandon,
2026-08-06: a 2026 Donruss BASEBALL pull came back with a few NFL
players/teams mixed in - Chris Olave, Kenneth Walker III, etc.).

This is a REVIEW check, never an auto-drop. A flagged row stays in the
export as-is; flagging only surfaces it to Brandon at the end of the
run so he can approve (keep) or reject (remove) it himself. Silently
deleting a row on a guess is a worse failure mode than occasionally
asking about one that turns out fine.

Two known team names are genuinely ambiguous across supported sports
and get dedicated handling instead of the generic team-list check
(Brandon, 2026-08-06):

    "New York Giants" - MLB team through 1957 (moved to SF and became
    the Giants in 1958), and the current NFL team today. A modern-dated
    Baseball product CAN legitimately print a new card of an old-era
    Giant (throwback/legends subsets do this), so year alone isn't
    enough - only flag a post-1957 Baseball "New York Giants" card if
    the player isn't a known notable Giant (settings/
    ny_giants_notable_players.csv, growable). Pre-1958 is always
    treated as legitimate vintage, no flag, no list lookup needed.

    "Boston Braves" - existed in the NFL for exactly one season (1932)
    before renaming to the Redskins, and was the actual MLB Braves'
    home through 1953. That NFL season's roster is small and fixed, so
    it's just hardcoded below (BOSTON_BRAVES_NFL_1932_ROSTER) rather
    than needing a growable file - a Football "Boston Braves" card
    whose player isn't on that one-season roster is almost certainly a
    mislabeled Baseball card, not a real product.

Every other team name is checked against settings/sport_teams.csv (the
sport's own current-team list, same editable-CSV pattern as
brand_set_exceptions.csv). A team that doesn't match its own sport's
list but DOES match a different sport's list is a strong contamination
signal and gets flagged. A team that matches neither (a defunct team,
a college team, international club, etc.) is left alone - the goal is
catching a clear signal, not enforcing a closed team list.

"Mixed" sport pulls (multi-sport products) skip this check entirely -
team/sport mismatches are the whole point of that kind of product.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from exporter.checklist_template import ChecklistRow

SPORT_TEAMS_PATH = Path(__file__).resolve().parent.parent / "settings" / "sport_teams.csv"
NY_GIANTS_NOTABLE_PLAYERS_PATH = (
    Path(__file__).resolve().parent.parent / "settings" / "ny_giants_notable_players.csv"
)

NY_GIANTS_MLB_LAST_SEASON = 1957  # moved to SF, became the Giants, in 1958

# Small and fixed - the Boston Braves' only NFL season. Confirmed
# 2026-08-06 (Brandon) this doesn't need to be a growable file the way
# the NY Giants list does, since the whole team only ever fielded one
# roster.
BOSTON_BRAVES_NFL_1932_ROSTER = {
    "Corrie Artman", "Cliff Battles", "Algy Clark", "Paul Collins",
    "Turk Edwards", "Mickey Erickson", "Nip Felber", "Honolulu Hughes",
    "George Hurley", "George Kenneally", "Joe Kresky", "Jim MacMurdo",
    "Jim Musick", "Curly Oden", "Oran Pape", "Russ Peterson",
    "Ernie Pinckert", "Tony Plansky", "Milt Rehnquist", "Jack Roberts",
    "Reggie Rust", "Kermit Schmidt", "Paul Schuette", "Tony Siano",
    "Jack Spellman", "Dale Waters", "Ed Westfall", "Basil Wilkerson",
    "Lee Woodruff",
}

_sport_teams_cache: dict[str, set[str]] | None = None
_ny_giants_players_cache: set[str] | None = None


def load_sport_teams() -> dict[str, set[str]]:
    """Returns {sport_lower: {team_name, ...}}. Cached after first load.
    Missing file -> empty dict, no crash (same spirit as
    load_brand_set_exceptions - this is an enhancement, not a
    requirement)."""
    global _sport_teams_cache
    if _sport_teams_cache is not None:
        return _sport_teams_cache

    teams: dict[str, set[str]] = {}
    if SPORT_TEAMS_PATH.exists():
        with open(SPORT_TEAMS_PATH, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sport = (row.get("sport") or "").strip()
                team = (row.get("team") or "").strip()
                if sport and team:
                    teams.setdefault(sport.lower(), set()).add(team)

    _sport_teams_cache = teams
    return teams


def load_ny_giants_notable_players() -> set[str]:
    global _ny_giants_players_cache
    if _ny_giants_players_cache is not None:
        return _ny_giants_players_cache

    players: set[str] = set()
    if NY_GIANTS_NOTABLE_PLAYERS_PATH.exists():
        with open(NY_GIANTS_NOTABLE_PLAYERS_PATH, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                player = (row.get("player") or "").strip()
                if player:
                    players.add(player)

    _ny_giants_players_cache = players
    return players


@dataclass
class FlaggedCard:
    row_index: int  # index into the checklist_rows list this came from
    player: str
    team: str
    sport: str
    year: str
    card_number: str
    reason: str


def _split_teams(team_text: str) -> list[str]:
    """Team text may hold more than one team, joined with ' / '
    (normalize_team_separators in convert.py). Check each individually."""
    if not team_text.strip():
        return []
    return [t.strip() for t in team_text.split("/") if t.strip()]


def _split_players(player_text: str) -> list[str]:
    """Player text may hold more than one name for a combo/dual card,
    joined with ' / ' (split_concatenated_names in convert.py)."""
    if not player_text.strip():
        return []
    return [p.strip() for p in player_text.split("/") if p.strip()]


def _any_name_in(names: list[str], known: set[str]) -> bool:
    known_lower = {n.lower() for n in known}
    return any(name.lower() in known_lower for name in names)


def _card_year(year_text: str) -> int | None:
    digits = year_text.strip()[:4]
    return int(digits) if digits.isdigit() else None


def _check_team(
    row_index: int, row: ChecklistRow, sport: str, team: str, sport_teams: dict[str, set[str]]
) -> FlaggedCard | None:
    team_lower = team.lower()
    players = _split_players(row.player)

    if team_lower == "boston braves":
        if sport.lower() == "football" and not _any_name_in(players, BOSTON_BRAVES_NFL_1932_ROSTER):
            return FlaggedCard(
                row_index, row.player, team, sport, row.year, row.card_number,
                "Boston Braves (Football) - not on the 1932 Boston Braves roster, "
                "the only season that team existed in the NFL. Check this isn't a "
                "mislabeled Baseball card.",
            )
        return None

    if team_lower == "new york giants":
        if sport.lower() == "baseball":
            year = _card_year(row.year)
            if year is not None and year > NY_GIANTS_MLB_LAST_SEASON:
                notable = load_ny_giants_notable_players()
                if not _any_name_in(players, notable):
                    return FlaggedCard(
                        row_index, row.player, team, sport, row.year, row.card_number,
                        f"New York Giants (Baseball, {row.year}) - the Giants moved to "
                        "SF after 1957 and this player isn't on the notable-Giants list. "
                        "Check this isn't mislabeled Football data.",
                    )
        return None

    # Generic check: does this team belong to a DIFFERENT sport's list
    # but not this one's? That's the actual contamination signal - a
    # team matching nothing at all (defunct/college/international) is
    # left alone.
    known_for_sport = {t.lower() for t in sport_teams.get(sport.lower(), set())}
    if not known_for_sport or team_lower in known_for_sport:
        return None

    for other_sport, other_teams in sport_teams.items():
        if other_sport == sport.lower():
            continue
        if team_lower in {t.lower() for t in other_teams}:
            return FlaggedCard(
                row_index, row.player, team, sport, row.year, row.card_number,
                f"'{team}' matches {other_sport.title()}'s team list, not {sport}'s - "
                "possible cross-sport data.",
            )
    return None


def find_sport_team_mismatches(rows: list[ChecklistRow]) -> list[FlaggedCard]:
    """Returns flagged rows for manual review. Never modifies rows -
    dropping is the caller's decision after Brandon approves/rejects
    each one (see app/prompt_dialog.py's review dialog)."""
    sport_teams = load_sport_teams()
    flagged: list[FlaggedCard] = []

    for i, row in enumerate(rows):
        sport = (row.sub_type or "").strip()
        if not sport or sport.lower() == "mixed":
            continue
        for team in _split_teams(row.team):
            result = _check_team(i, row, sport, team, sport_teams)
            if result:
                flagged.append(result)

    return flagged
