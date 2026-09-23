"""
route_query() classifies a user's question and extracts search filters, in one LLM call
before any retrieval happens.

It returns a RouterOutput: a label (retrieval / aggregate / off_topic / needs_clarification),
a one-sentence reason for logging, any park codes or states named in the question, an
optional ISO date range, and — only for needs_clarification — a clarifying question to show
the user. park_codes and states are returned separately: the caller is expected to expand
states through parks.park_codes_for_states() and union the result with park_codes before
passing filters to retrieval.retrieve().
"""

from enum import Enum

from pydantic import BaseModel

from rag_nps.openai_client import client
from rag_nps.parks import format_park_table

CHAT_MODEL = "gpt-4o-mini"


class Label(str, Enum):
    RETRIEVAL = "retrieval"
    AGGREGATE = "aggregate"
    OFF_TOPIC = "off_topic"
    NEEDS_CLARIFICATION = "needs_clarification"


class RouterOutput(BaseModel):
    label: Label
    reason: str
    park_codes: list[str]
    states: list[str]
    start_date: str | None
    end_date: str | None
    clarifying_question: str | None


ROUTER_SYSTEM_PROMPT = f"""\
You are a query router for a National Park Service safety-incident search tool. Classify \
each user question and extract search filters. Always return every field defined by the \
schema.

Labels:
- retrieval: A question about specific safety incidents, hazards, or dangers in national \
parks — anything this tool's database of incident reports could help answer. This \
includes broad or opinion-adjacent safety questions (e.g. "best time of year to visit \
Yosemite", "is Glacier National Park dangerous") and yes/no existence questions (e.g. \
"were there any drownings in 2018", "have there been bear attacks here") — the latter \
ask whether matching incidents exist, not for a count, so they are retrieval even \
though they contain words like "any" or "were there". The database also covers \
law-enforcement and resource-violation incidents, not just physical hazards - poaching, \
illegal collection, and wildlife trafficking investigations are all in scope. A question \
about an investigation, operation, or enforcement action tied to one of these is still \
retrieval, even when phrased in administrative language ("operation", "investigation") \
rather than "incident" or "danger" - judge by the topic, not the phrasing. A specific \
topic with no park named (e.g. "overheating incidents", "where have rattlesnakes been \
encountered") is also retrieval, searched with no park filter across the whole dataset - \
naming a park is never required, only an interpretable subject. Err toward retrieval for \
anything safety-adjacent, even if broad: a wasted search costs little, but wrongly \
refusing a legitimate question costs more.
- aggregate: A question asking specifically for a count, comparison, or ranking across \
the dataset — the answer would be a number or a ranking, not a description of specific \
incidents (e.g. "how many deaths were there in Yosemite in 2019", "which park has the \
most bear attacks"). A yes/no or "were there any" question is retrieval, not aggregate, \
even when it also names a park and date range. This tool cannot compute aggregates yet.
- off_topic: Nothing to do with national park safety incidents (hours, permits, general \
park info, or unrelated topics).
- needs_clarification: ONLY when the question gives no usable topic, park, or timeframe at \
all (e.g. a single word, or "tell me about the parks"). A specific topic with no named \
park is NOT missing a usable topic - see the retrieval examples above and below. Do NOT \
use this for a broad-but-answerable question — prefer retrieval whenever there's any \
interpretable subject.

Also extract, when present:
- park_codes: codes explicitly named, chosen ONLY from the table below. Never guess a code \
for a place not listed.
- states: two-letter state/territory codes named or clearly implied, ONLY when the \
question is about parks in a state generally (e.g. "California parks") rather than one or \
more specific named parks. Do not add a state just because a park already listed in \
park_codes happens to sit in it — states triggers an app-side expansion to every park \
touching that state, which would wrongly broaden a question about one specific park. \
Return the state itself — do not resolve it to park codes yourself.
- start_date / end_date: an ISO date range if one is specified (a bare year like "2019" \
becomes 2019-01-01 through 2019-12-31). Leave both null otherwise.

Give a one-sentence reason for your label, for logging only.

If label is needs_clarification, fill clarifying_question with a short, specific question. \
Otherwise leave it null.

Example: "bear encounters in Yellowstone" → park_codes: ["YELL"], states: [] — not \
states: ["WY", "MT", "ID"], which would pull in Grand Teton and Glacier too.

Example: "were there any drownings in Grand Canyon in 2018" → retrieval, not \
aggregate — it asks whether matching incidents exist (and for examples), not for a \
count.

Example: "tell me more about the undercover operation into illegal reptile collecting" \
→ retrieval, not off_topic — a poaching investigation is a real incident category in \
this dataset, even though the question doesn't use words like "safety" or "danger".

Example: "where have rattlesnakes been encountered" → retrieval, not \
needs_clarification, with park_codes: [] and states: [] — an unfiltered search across \
every park. The topic (rattlesnake encounters) is enough on its own; no park needs to \
be named.

Known parks (code — name — state(s)):
{format_park_table()}
"""


def route_query(question):
    """Classify `question` and extract filters, returning a RouterOutput."""
    response = client.responses.parse(
        model=CHAT_MODEL,
        input=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
        text_format=RouterOutput,
    )
    return response.output_parsed
