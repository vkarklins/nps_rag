"""
Check the user message that build_user_message assembles, across a few real test
questions chosen for variety. Diagnostic only, not part of the app; no API calls
are made -- incidents are hand-written stand-ins, not retrieved from the database.

Moved from src/rag_nps/ to tests/manual/ on 2026-09-21 to separate it from
application code; it no longer runs as `python -m rag_nps.message_check`.

Usage (from the project root):
    poetry run python tests/manual/message_check.py

Cases (all from evals/questions.json):
- q14 (Yosemite, 2016): falls entirely inside the September 2015 - March 2017
  coverage gap. Filtered, zero results, so this exercises the "(no reports
  matched)" branch of build_user_message, and the gap note is present -- and
  repeated at the end, since it's the case that motivated repeating it.
- q06 (Angels Landing falls): no filters at all, a normal handful of results.
- q27 (Yosemite bear encounters): park-only filter, few enough results that
  completeness_note can say "all N reports that match the filters".
- q39 (Grand Canyon deaths, 2018): park + date filter, but the result count
  hits k, so completeness_note falls back to "closest matches, not a complete
  list" even though a filter was applied. No gap note (2018 doesn't touch the
  gap), for contrast with q14.
"""

from rag_nps.answer import build_user_message, completeness_note, describe_filters, gap_note


def fake_incident(incident_id, incident_date, park_name, title, body, also_in=None):
    return {
        "incident_id": incident_id,
        "incident_date": incident_date,
        "park_name": park_name,
        "title": title,
        "body": body,
        "also_in": also_in or [],
    }


def build_notes(park_codes, start_date, end_date, n_retrieved, k):
    """Compute the same three notes answer_question will, plus the gap note on its own
    (as build_user_message's new gap_note parameter needs it separately from the list)."""
    filtered = bool(park_codes or start_date or end_date)
    gap = gap_note(start_date, end_date)
    notes = [
        describe_filters(park_codes, start_date, end_date),
        completeness_note(n_retrieved, k, filtered),
        gap,
    ]
    return notes, gap


CASES = []

# q14: Yosemite, 2016 -- inside the coverage gap, zero results.
notes, gap = build_notes(["YOSE"], "2016-01-01", "2016-12-31", n_retrieved=0, k=30)
CASES.append({
    "id": "q14",
    "question": "What incidents happened at Yosemite in 2016?",
    "incidents": [],
    "notes": notes,
    "gap_note": gap,
})

# q06: Angels Landing falls -- no filters, a normal handful of results.
incidents = [
    fake_incident(
        "zion-00309", "1999-07-08", "Zion National Park",
        "Fall From Angels Landing",
        "A visitor fell approximately 300 feet while descending the chain section "
        "of the Angels Landing trail. Park rangers and a helicopter responded; the "
        "visitor was pronounced dead at the scene.",
    ),
    fake_incident(
        "zion-00064", "2007-05-21", "Zion National Park",
        "Fatality on Angels Landing",
        "A hiker lost his footing near the chains on Angels Landing and fell. He "
        "was airlifted to a hospital, where he later died of his injuries.",
    ),
]
notes, gap = build_notes(None, None, None, n_retrieved=len(incidents), k=30)
CASES.append({
    "id": "q06",
    "question": "Has anyone fallen while climbing Angels Landing?",
    "incidents": incidents,
    "notes": notes,
    "gap_note": gap,
})

# q27: Yosemite bear encounters -- park filter only, few results.
incidents = [
    fake_incident(
        "yose-00112", "1998-08-02", "Yosemite National Park",
        "Bear Incident in Tuolumne Meadows",
        "A black bear entered a campsite and obtained food after campers left a "
        "cooler unattended. No injuries were reported.",
    ),
    fake_incident(
        "yose-00340", "2004-06-14", "Yosemite National Park",
        "Bear Bite Reported in Yosemite Valley",
        "A visitor was bitten on the hand after attempting to photograph a bear at "
        "close range near Camp 4. The injury was minor.",
    ),
    fake_incident(
        "yose-00501", "2011-09-03", "Yosemite National Park",
        "Vehicle Break-In by Bear",
        "A bear broke into a parked vehicle after smelling food inside, causing "
        "damage to a door panel.",
    ),
]
notes, gap = build_notes(["YOSE"], None, None, n_retrieved=len(incidents), k=30)
CASES.append({
    "id": "q27",
    "question": "What kinds of bear encounters happen in Yosemite?",
    "incidents": incidents,
    "notes": notes,
    "gap_note": gap,
})

# q39: Grand Canyon deaths, 2018 -- park + date filter, but the count before
# collapse_duplicates hits k, so completeness_note can't claim this is the full
# matching set even though it's filtered. Only a few incidents are included here
# (n_retrieved is passed as 30 regardless) since real pipeline runs can likewise
# have n_retrieved > len(incidents) after collapsing -- this check only needs the
# message's notes to reflect that, not 30 near-identical placeholder reports.
incidents = [
    fake_incident(
        "grca-00512", "2018-03-22", "Grand Canyon National Park",
        "Fatality From Fall",
        "A hiker fell approximately 200 feet from an overlook near the South "
        "Rim. He was pronounced dead at the scene.",
    ),
    fake_incident(
        "grca-00588", "2018-07-09", "Grand Canyon National Park",
        "Heat-Related Fatality on Bright Angel Trail",
        "A hiker was found unresponsive on the Bright Angel Trail during a period "
        "of high temperatures and was pronounced dead at the scene.",
    ),
]
notes, gap = build_notes(["GRCA"], "2018-01-01", "2018-12-31", n_retrieved=30, k=30)
CASES.append({
    "id": "q39",
    "question": "How many people died at Grand Canyon in 2018?",
    "incidents": incidents,
    "notes": notes,
    "gap_note": gap,
})


def main():
    for case in CASES:
        message = build_user_message(
            case["question"], case["incidents"], case["notes"], gap_warning=case["gap_note"]
        )
        print(f"===== {case['id']}: {case['question']} =====")
        print(message)
        print()


if __name__ == "__main__":
    main()
