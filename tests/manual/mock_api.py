"""
Run the web API with the database and OpenAI replaced by fakes, to work on the front end
(or demo it) without a DB connection or API calls.

    poetry run uvicorn tests.manual.mock_api:app --port 8000

- condense_question: returns the question unchanged
- route_query: finds park names in the question by simple text match; "how many" ->
  aggregate; "weather" -> off_topic
- retrieve: keyword-scores reports from data/incidents.jsonl (no embeddings)
- the answer: a canned paragraph that cites the top reports, streamed word by word

Answers are NOT real model output. Nothing is written to logs/answers.jsonl.
"""

import json
import re
import time
from pathlib import Path
from types import SimpleNamespace

from rag_nps import api
from rag_nps.parks import PARKS
from rag_nps.router import Label, RouterOutput

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INCIDENTS = [
    json.loads(line)
    for line in open(PROJECT_ROOT / "data" / "incidents.jsonl", encoding="utf-8")
]
STOPWORDS = set("a an the in at of on to and or for what is are was were have has been "
                "any how do i my me about there tell can you national park parks".split())


def fake_condense(question, history):
    return question


def fake_route(question):
    q = question.lower()
    codes = []
    for code, park in PARKS.items():
        short = park["name"].lower().replace(" national park", "").split(" and ")[0]
        short = short.replace(" national", "").strip()
        if short and short in q:
            codes.append(code)
    label = Label.RETRIEVAL
    if "how many" in q:
        label = Label.AGGREGATE
    elif "weather" in q:
        label = Label.OFF_TOPIC
    return RouterOutput(
        label=label, reason="mock", asks_for_advice=("should i" in q or "how do i" in q),
        park_codes=codes, states=[], exclude_park_codes=[], exclude_states=[],
        start_date=None, end_date=None, clarifying_question=None,
    )


def fake_retrieve(conn, question, k=10, *, park_codes=None, exclude_park_codes=None,
                  start_date=None, end_date=None):
    words = [w for w in re.findall(r"[a-z]+", question.lower()) if w not in STOPWORDS]
    scored = []
    for inc in INCIDENTS:
        if park_codes and inc["park_code"] not in park_codes:
            continue
        text = ((inc["title"] or "") + " " + inc["body"]).lower()
        score = sum(text.count(w) for w in words)
        if score:
            scored.append((score, inc))
    scored.sort(key=lambda pair: -pair[0])
    time.sleep(0.6)
    return [
        {
            "incident_id": inc["incident_id"], "park_code": inc["park_code"],
            "park_name": inc["park_name"], "incident_date": inc["date"],
            "title": inc["title"], "source_url": inc["source_url"], "body": inc["body"],
            "distance": 0.3,
        }
        for _, inc in scored[:k]
    ]


def first_sentence(text):
    text = re.sub(r"^Location:.*\n+", "", text.strip())
    return re.split(r"(?<=[.!?])\s", text.replace("\n", " "), maxsplit=1)[0]


def fake_stream_answer(user_message):
    ids = re.findall(r'<incident id="([a-z]+-\d+)">', user_message)[:4]
    by_id = {inc["incident_id"]: inc for inc in INCIDENTS}
    if not ids:
        text = "I couldn't find any reports of that in the parks searched."
    else:
        pieces = []
        for n, incident_id in enumerate(ids):
            inc = by_id[incident_id]
            lead = "One report" if n == 0 else "Another report"
            pieces.append(f"{lead}, from {inc['date'][:4]} in {inc['park_name']}, describes this: "
                          f"{first_sentence(inc['body'])} [{incident_id}]")
        text = ("(Mock answer, not model output.) " + " ".join(pieces[:2])
                + "\n\n" + " ".join(pieces[2:]))
    for token in re.findall(r"\S+\s*", text):
        time.sleep(0.03)
        yield token


api.condense_question = fake_condense
api.route_query = fake_route
api.retrieve = fake_retrieve
api.get_connection = lambda: SimpleNamespace(close=lambda: None)
api.stream_answer = fake_stream_answer
api._log = lambda entry: None

app = api.app
