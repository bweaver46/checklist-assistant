"""
Tests for app/prompt_dialog.py's build_search_form - specifically the
Pull Team checkbox (Brandon, 2026-08-16: "It needs to have the same
logic as when I pull a set. in create a que you can put a check box
pull team or not. Add a team field if no, but that team is applied to
every card, we are not opening them to look for the team.").

Qt-level (real PySide6, offscreen platform) since build_search_form is
a static method that constructs and execs a real QDialog - there's no
pure-logic seam to test underneath it. QDialog.exec is patched to
auto-accept instead of blocking for real input, matching how a person
clicking OK would resolve it.
"""

from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from app.prompt_dialog import PromptDialog

_app = QApplication.instance() or QApplication([])


def _build(defaults=None):
    with patch.object(QDialog, "exec", return_value=True):
        return PromptDialog.build_search_form(None, defaults=defaults)


def test_fetch_team_defaults_false_and_team_passes_through():
    result = _build({"keyword": "donruss", "team": "Yankees"})
    assert result["fetch_team"] == "false"
    assert result["team"] == "Yankees"


def test_fetch_team_checked_via_defaults_clears_stale_team():
    # A team value left over from a previous edit shouldn't silently
    # apply once Pull Team is turned on - the per-card lookup should
    # be the only source of Team in that case.
    result = _build({"keyword": "donruss", "team": "stale value", "fetch_team": "true"})
    assert result["fetch_team"] == "true"
    assert result["team"] == ""


def test_fetch_team_unset_in_defaults_treated_as_false():
    result = _build({"keyword": "donruss"})
    assert result["fetch_team"] == "false"
