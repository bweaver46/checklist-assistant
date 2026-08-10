"""
Tests for scraper/search_url.py - building a BSC search URL directly
from filter fields (Brandon, 2026-08-08).
"""

from scraper.search_url import build_search_url, slugify


def test_slugify_matches_confirmed_examples():
    # Confirmed against Brandon's real captured URLs and a live test
    # (2026-08-08: "Panini Diamond Kings" worked as setName[]).
    assert slugify("Topps Chrome") == "topps-chrome"
    assert slugify("Topps Archives") == "topps-archives"
    assert slugify("Panini Diamond Kings") == "panini-diamond-kings"
    assert slugify("Hobby Masters") == "hobby-masters"
    assert slugify("Baseball") == "baseball"


def test_keyword_only_matches_captured_url_shape():
    url = build_search_url({"keyword": "206"})
    assert url == (
        "https://www.buysportscards.com/sellers/inventory"
        "?myInventory=false&p=0&q=206"
    )


def test_confirmed_fields_match_captured_url():
    # Reproduces the second URL Brandon captured (2026-08-06):
    # ...?myInventory=false&p=0&q=2026%20topps%20chrome
    # &setName[]=topps-chrome&sport[]=baseball&year[]=2026
    url = build_search_url({
        "keyword": "2026 topps chrome",
        "set": "Topps Chrome",
        "sport": "Baseball",
        "year": "2026",
    })
    assert "q=2026%20topps%20chrome" in url
    assert "setName[]=topps-chrome" in url
    assert "sport[]=baseball" in url
    assert "year[]=2026" in url


def test_blank_optional_fields_are_omitted():
    url = build_search_url({"keyword": "206", "sport": "", "year": "  "})
    assert "sport[]=" not in url
    assert "year[]=" not in url


def test_year_is_not_slugified():
    url = build_search_url({"keyword": "x", "year": "2020"})
    assert "year[]=2020" in url


def test_diamond_kings_case_verified_live():
    # This exact case was pasted into a browser and confirmed working
    # by Brandon, 2026-08-08.
    url = build_search_url({
        "keyword": "206", "year": "2020", "sport": "Baseball",
        "set": "Panini Diamond Kings",
    })
    assert url.startswith("https://www.buysportscards.com/sellers/inventory?")
    assert "myInventory=false" in url
    assert "p=0" in url
    assert "q=206" in url
    assert "setName[]=panini-diamond-kings" in url
    assert "sport[]=baseball" in url
    assert "year[]=2020" in url
