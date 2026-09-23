"""
Manual check of router.route_query(): prints its output for a handful of real questions
chosen to exercise each label and the filter fields. Not part of the app; diagnostic only.
Run with `poetry run python tests/manual/router_check.py`.
"""

from rag_nps.router import route_query

CASES = [
    ("plain retrieval, no filters", "Have there been any bear encounters in Yellowstone?"),
    ("retrieval, named park", "What kinds of falls have happened at Angels Landing in Zion?"),
    ("retrieval, state", "Have there been any mountain lion attacks in California parks?"),
    ("retrieval, date range", "Were there any drownings in Grand Canyon in 2018?"),
    ("aggregate", "How many people have died in Yosemite?"),
    ("off_topic", "What are the entrance fees for Yellowstone?"),
    ("borderline (q44-46 style)", "Is Glacier National Park dangerous?"),
    ("needs_clarification candidate", "tell me about the parks"),
    ("needs_clarification candidate", "incidents"),
    ("retrieval, open-ended date", "Have there been wildlife attacks in Everglades since 2020?"),
    ("off-topic", "bubbles"),
    ("off-topic", "write a basic hello world function in JavaScript")
]

for label, question in CASES:
    result = route_query(question)
    print(f"--- {label} ---")
    print(f"question: {question!r}")
    print(f"label:                {result.label}")
    print(f"reason:               {result.reason}")
    print(f"park_codes:           {result.park_codes}")
    print(f"states:               {result.states}")
    print(f"start_date/end_date:  {result.start_date} / {result.end_date}")
    print(f"clarifying_question:  {result.clarifying_question}")
    print()
