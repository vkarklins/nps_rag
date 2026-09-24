"""
Interactive command-line ask-loop: type a question, get an answer with numbered
citations and a source list grouped by URL (several incidents can share one park page).
Non-streaming; streaming is a later step (see progress-and-next-steps.md,
"Citations and streaming"). Each question is routed by `pipeline.ask` before any
retrieval happens; aggregate/off_topic/needs_clarification questions come back with no
incidents, so they print with no citations or source list.

The loop owns conversation history for the process's lifetime (see history.py): each
exchange is appended after it's shown to the user, using the displayed answer text
(after citation conversion), never the raw incident data. history.append_turn() enforces
a fixed-size window; once it starts dropping older exchanges, a note is printed after
every subsequent turn, not just the first, since the model's lack of visibility into
earlier turns is true on every turn past that point.
"""

import re

from rag_nps.db_connect import get_connection
from rag_nps.history import append_turn
from rag_nps.pipeline import ask

# Matches the exact citation format SYSTEM_PROMPT asks for, e.g. [yose-00571].
CITATION_RE = re.compile(r"\[([a-z]+-\d+)\]")

EXIT_WORDS = {"exit", "quit"}

# Shown under answers built from the closest-matching reports rather than every matching
# report. The answer prompt tells the model not to repeat this itself (see answer.py
# SYSTEM_PROMPT, step 4).
PARTIAL_RESULTS_FOOTER = (
    "Note: this answer is based on the reports that best match your question, not "
    "every relevant report in the dataset."
)

# Shown under answers to questions the router marked as asking for advice. The answer
# model may only use the reports (see answer.py SYSTEM_PROMPT), so pointing to official
# guidance has to come from the app.
ADVICE_NOTICE = (
    "Note: I can only share what incident reports say, not general safety advice. For "
    "guidance before your visit, check the park's website (nps.gov) or ask a ranger."
)


def convert_citations(answer_text, incidents_by_id):
    """Replace [incident_id] citations with sequential [N] numbers, assigned in order
    of first appearance. Returns (converted_text, numbers, unknown):
      numbers  dict of incident_id -> assigned number, in citation order
      unknown  set of cited incident_ids that weren't in incidents_by_id (the model
               cited something that wasn't actually in the prompt)
    """
    numbers = {}
    unknown = set()

    def replace(match):
        incident_id = match.group(1)
        if incident_id not in incidents_by_id:
            unknown.add(incident_id)
            return "[?]"
        numbers.setdefault(incident_id, len(numbers) + 1)
        return f"[{numbers[incident_id]}]"

    converted = CITATION_RE.sub(replace, answer_text)
    return converted, numbers, unknown


def build_source_list(numbers, incidents_by_id):
    """Group cited incidents by source URL (a park's whole incident history lives on
    one page, so several citations often share a URL), listing each one's assigned
    number(s) and report date under its URL, so the reader can find the specific entry
    on an otherwise undifferentiated page. Order follows first citation.
    """
    groups = {}  # source_url -> list of (number, date)
    for incident_id, number in numbers.items():
        incident = incidents_by_id[incident_id]
        url = incident["source_url"]
        groups.setdefault(url, []).append((number, incident["incident_date"]))

    lines = ["Sources:"]
    for url, entries in groups.items():
        number_tags = "".join(f"[{n}]" for n, _ in entries)
        dates = ", ".join(str(date) for _, date in entries)
        label = "report" if len(entries) == 1 else "reports"
        lines.append(f"{number_tags} {url} — {label} dated {dates}")
    return "\n".join(lines)


def main():
    conn = get_connection()
    history = []
    try:
        while True:
            try:
                question = input(
                    "\nAsk a question about national park safety (type 'exit' or 'quit' to stop): "
                ).strip()
            except EOFError:
                break
            if question.lower() in EXIT_WORDS:
                break
            if not question:
                continue

            result = ask(conn, question, history=history)
            incidents_by_id = {incident["incident_id"]: incident for incident in result["incidents"]}
            converted, numbers, unknown = convert_citations(result["answer"], incidents_by_id)

            print()
            print(converted)
            # "complete" is only in results that reached the answer step, so declines and
            # clarifying questions never get either notice.
            answered = "complete" in result
            if answered and (result.get("routing") or {}).get("asks_for_advice"):
                print()
                print(ADVICE_NOTICE)
            if result.get("complete") is False:
                print()
                print(PARTIAL_RESULTS_FOOTER)
            if numbers:
                print()
                print(build_source_list(numbers, incidents_by_id))
            if unknown:
                print()
                print(f"Warning: cited incident ID(s) not in the retrieved set: {', '.join(sorted(unknown))}")

            history, trimmed = append_turn(history, question, converted)
            if trimmed:
                print()
                print("Note: this conversation has gone on long enough that earlier turns are no longer in context.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
