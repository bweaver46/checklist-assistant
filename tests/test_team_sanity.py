"""
Tests for exporter/team_sanity.py - the team/sport mismatch review
check (Brandon, 2026-08-06).
"""

from exporter.checklist_template import ChecklistRow
from exporter.team_sanity import find_sport_team_mismatches


def row(**kwargs) -> ChecklistRow:
    defaults = dict(
        type="Sports", sub_type="Baseball", year="2026", brand="Donruss",
        set="", insert="", attributes="", card_number="1", player="",
        team="", base="", base_serial="", parallels=[],
    )
    defaults.update(kwargs)
    return ChecklistRow(**defaults)


# --- generic cross-sport contamination ---

def test_flags_team_belonging_to_a_different_sport():
    rows = [row(sub_type="Baseball", team="Seattle Seahawks", player="Chris Olave")]
    flagged = find_sport_team_mismatches(rows)
    assert len(flagged) == 1
    assert flagged[0].row_index == 0
    assert "Football" in flagged[0].reason


def test_does_not_flag_team_matching_its_own_sport():
    rows = [row(sub_type="Baseball", team="Seattle Mariners", player="Ken Griffey Jr.")]
    assert find_sport_team_mismatches(rows) == []


def test_does_not_flag_unrecognized_team_no_signal():
    # A minor-league/college/defunct team not in either list - no clear
    # signal either way, so it's left alone rather than flagged on a guess.
    rows = [row(sub_type="Baseball", team="Albuquerque Isotopes")]
    assert find_sport_team_mismatches(rows) == []


def test_mixed_sport_skips_the_check_entirely():
    rows = [row(sub_type="Mixed", team="Seattle Seahawks", player="Chris Olave")]
    assert find_sport_team_mismatches(rows) == []


# --- New York Giants (Baseball through 1957, NFL today) ---

def test_ny_giants_baseball_pre_1958_never_flagged():
    rows = [row(sub_type="Baseball", team="New York Giants", year="1954", player="Nobody Famous")]
    assert find_sport_team_mismatches(rows) == []


def test_ny_giants_baseball_modern_notable_player_not_flagged():
    rows = [row(sub_type="Baseball", team="New York Giants", year="2026", player="Christy Mathewson")]
    assert find_sport_team_mismatches(rows) == []


def test_ny_giants_baseball_modern_unknown_player_flagged():
    rows = [row(sub_type="Baseball", team="New York Giants", year="2026", player="Some Rando")]
    flagged = find_sport_team_mismatches(rows)
    assert len(flagged) == 1
    assert "New York Giants" in flagged[0].reason


def test_ny_giants_football_never_flagged():
    rows = [row(sub_type="Football", team="New York Giants", year="2026", player="Anyone")]
    assert find_sport_team_mismatches(rows) == []


# --- Boston Braves (NFL 1932 only, MLB for decades) ---

def test_boston_braves_football_1932_roster_player_not_flagged():
    rows = [row(sub_type="Football", team="Boston Braves", year="1932", player="Cliff Battles")]
    assert find_sport_team_mismatches(rows) == []


def test_boston_braves_football_non_roster_player_flagged():
    rows = [row(sub_type="Football", team="Boston Braves", year="1932", player="Random Guy")]
    flagged = find_sport_team_mismatches(rows)
    assert len(flagged) == 1
    assert "Boston Braves" in flagged[0].reason


def test_boston_braves_baseball_never_flagged():
    rows = [row(sub_type="Baseball", team="Boston Braves", year="1948", player="Anyone")]
    assert find_sport_team_mismatches(rows) == []


# --- multi-team / multi-player cards ---

def test_multi_team_card_checks_each_team_independently():
    rows = [row(sub_type="Baseball", team="Seattle Mariners / Seattle Seahawks", player="Someone")]
    flagged = find_sport_team_mismatches(rows)
    assert len(flagged) == 1
    assert "Football" in flagged[0].reason


def test_multi_player_card_ny_giants_one_notable_one_not_still_passes():
    rows = [row(
        sub_type="Baseball", team="New York Giants", year="2026",
        player="Christy Mathewson / Some Rando",
    )]
    assert find_sport_team_mismatches(rows) == []
