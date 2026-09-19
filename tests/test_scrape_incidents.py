"""Parser tests, run against a small sample built from real npshistory.com park pages.

The sample (tests/fixtures/park_page_sample.htm) contains 18 incidents chosen to cover the
oddities found when surveying all 62 park pages: headers without a leading <br>, date typos,
date suffixes, multi-line headers, body text glued into the header, <ul>, <blockquote>,
<table>, links and &#151; entities.
"""

from pathlib import Path

import pytest

from rag_nps import scrape_incidents as scr

FIXTURE = Path(__file__).parent / "fixtures" / "park_page_sample.htm"
PAGE = {"page": "cave", "url": "https://example.test/cave.htm", "park_code": "CAVE",
        "park_name": "Carlsbad Caverns National Park"}


@pytest.fixture(scope="module")
def incidents():
    return scr.parse_page(FIXTURE.read_text(encoding="utf-8"), PAGE)


def test_every_header_is_found(incidents):
    # 18 headers in the sample: 1 first-incident, 3 mid-page headers WITHOUT a leading <br>, 14 with one
    assert len(incidents) == 18
    assert [r["seq"] for r in incidents] == list(range(1, 19))


def test_first_incident_has_no_leading_br(incidents):
    first = incidents[0]
    assert first["date"] == "1986-06-23"
    assert first["title"] == "Carlsbad Cavern - Flash Flood"
    assert "Rains started early Monday" in first["body"]
    assert "& concessioner" in first["body"]  # entities decoded


def test_incident_number_and_title(incidents):
    rec = incidents[1]
    assert rec["incident_number"] == "90-307"
    assert rec["date"] == "1990-09-14"
    assert rec["title"].endswith("Successful Rescue")


def test_mid_page_header_without_leading_br_starts_new_incident(incidents):
    rec = incidents[3]
    assert rec["date"] == "2022-07-13"
    assert rec["header_lines"][1:] == ["Acadia National Park", "Follow-up on Previously Reported Incident"]
    assert "August 2019" in rec["body"]


@pytest.mark.parametrize("idx, date_raw, iso", [
    (2, "Thursday, March 9, 19B9", None),            # garbled year: keep raw, no ISO date
    (5, "Monday, October 28 , 1991", "1991-10-28"),   # stray space
    (7, "Monday, May 18. 1998", "1998-05-18"),        # period instead of comma
    (8, "April 15, 2026", "2026-04-15"),              # <b>-wrapped, no weekday
])
def test_date_quirks(incidents, idx, date_raw, iso):
    assert incidents[idx]["date_raw"] == date_raw
    assert incidents[idx]["date"] == iso


def test_date_suffixes_are_kept_as_header_lines(incidents):
    assert incidents[4]["header_lines"][1] == "(Delayed)"
    assert incidents[6]["header_lines"][1] == "MEMORIAL DAY"


def test_multi_line_headers(incidents):
    assert incidents[12]["header_lines"][1] == "Friday, April 04, 2003"  # second date line
    assert incidents[10]["header_lines"][1] == "Yellowstone National Park (ID,MT,WY)"  # newline, not <br>


def test_body_text_inside_header_paragraph_moves_to_body(incidents):
    rec = incidents[11]
    assert rec["header_lines"][-1] == "Follow-up on Trial of Suspect in Double Homicide"
    assert rec["body"].startswith("Last week, the United States attorney")


def test_lists_blockquotes_tables_links_and_entities(incidents):
    assert "- Credit Card Fraud — A suspect" in incidents[13]["body"]
    assert "Eagle Point Fire: 123 acres" in incidents[14]["body"]
    assert "Employee assistance and CISD | 61 (+1)" in incidents[15]["body"]
    assert "|\n|" not in incidents[15]["body"]
    assert "http://www.inciweb.org//incident/732/" in incidents[17]["body"]
    assert "\x97" not in incidents[17]["body"]  # &#151; became an em dash, not a control char


def test_record_fields(incidents):
    rec = incidents[1]
    assert list(rec) == ["incident_id", "park_code", "park_name", "source_url", "seq", "date_raw", "date",
                         "incident_number", "header_lines", "title", "body", "text", "char_count"]
    assert rec["incident_id"] == "cave-00002"
    assert rec["park_code"] == "CAVE"
    assert rec["park_name"] == "Carlsbad Caverns National Park"
    assert rec["char_count"] == len(rec["text"])


@pytest.mark.parametrize("title, expected", [
    ("NPS Incident Reports - Carlsbad Caverns National Park", "Carlsbad Caverns National Park"),
    ("NPS Incident Reports - Sequoia and Kings Canyon National Parks", "Sequoia and Kings Canyon National Parks"),
    ("NPS Incident Reports - North Cascades National Park / Lake Chelan National Recreation Area / "
     "Ross Lake National Recreation Area", "North Cascades National Park"),
    ("NPS Incident Reports - Great Sand Dunes National Park &amp; Preserve", "Great Sand Dunes National Park & Preserve"),
    ("", ""),
])
def test_park_name_from_title(title, expected):
    assert scr.park_name_from_title(title) == expected


def test_text_field_is_header_plus_body(incidents):
    rec = incidents[1]
    assert rec["text"].startswith("Friday, September 14, 1990\n90-307")
    assert rec["text"].endswith(rec["body"])


SELECT_HTML = """
<form><select name="gourl">
<option value="#">Select Park</option>
<option value="https://npshistory.com/morningreport/incidents/acad.htm"> Acadia NP (ACAD)</option>
<option value="https://npshistory.com/morningreport/incidents/dena.htm">Denali NP &amp; Pres (DENA)</option>
<option value="https://npshistory.com/morningreport/incidents/bela.htm">Bering Land Bridge NPres (BELA)</option>
<option value="https://npshistory.com/morningreport/incidents/lewi.htm">Lewis &amp; Clark NHP (LEWI)</option>
<option value="https://npshistory.com/morningreport/incidents/redw.htm">Redwood N &amp; SP (REDW)</option>
<option value="https://npshistory.com/morningreport/incidents/npsa.htm">National Park of American Samoa (NPSA)</option>
<option value="https://npshistory.com/morningreport/incidents/seki.htm">Kings Canyon NP (SEKI)</option>
<option value="https://npshistory.com/morningreport/incidents/seki.htm">Sequoia NP (SEKI)</option>
<option value="https://npshistory.com/morningreport/incidents/amis.htm">Amistad NRA (AMIS)</option>
<option value="https://npshistory.com/morningreport/incidents/regional.htm">Regional/Systemwide</option>
</select></form>
"""


def test_park_selection_keeps_only_national_parks():
    parks = scr.select_parks(SELECT_HTML)
    assert [p["code"] for p in parks] == ["ACAD", "DENA", "REDW", "NPSA", "SEKI", "SEKI"]
    pages = scr.group_by_page(parks)
    assert len(pages) == 5  # Sequoia + Kings Canyon share seki.htm
    assert pages["seki"]["park_code"] == "SEKI"  # one code per page, even for the shared page
    assert pages["seki"]["dropdown_labels"] == ["Kings Canyon NP (SEKI)", "Sequoia NP (SEKI)"]
    assert pages["acad"]["dropdown_labels"] == ["Acadia NP (ACAD)"]
