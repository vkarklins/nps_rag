"""
Wire the pieces together: given a question, route it, then either retrieve incidents and
generate an answer, decline politely (aggregate/off_topic), or ask for clarification
(needs_clarification). Log every run.

ask() first condenses the question against the conversation so far (see
condense.condense_question), so a follow-up like "what about in Denali?" — or a reply to
a needs_clarification prompt — is rewritten into a standalone question before routing or
retrieval ever see it. Conversation history itself lives outside this module (see
history.py); ask() only reads it to condense, never stores it.
"""

import json
from datetime import datetime
from pathlib import Path

from rag_nps.answer import (
    SYSTEM_PROMPT,
    build_user_message,
    completeness_note,
    describe_filters,
    gap_note,
    generate_answer,
    is_complete,
)
from rag_nps.condense import condense_question
from rag_nps.parks import PARKS, park_codes_for_states
from rag_nps.retrieval import collapse_duplicates, retrieve
from rag_nps.router import Label, route_query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "answers.jsonl"

K = 30  # candidates sent to the answer model; see retrieval eval findings for why

AGGREGATE_MESSAGE = (
    "I can't count or compare incidents across the dataset yet — I can only look up "
    "specific reports. Try asking about specific incidents instead."
)
OFF_TOPIC_MESSAGE = (
    "I'm only equipped to answer questions about safety incidents reported in U.S. "
    "National Parks — I can't help with that here."
)
NO_MATCHING_PARKS_MESSAGE = (
    "I don't have data for that location — none of the parks in this dataset match."
)


def resolve_park_codes(park_codes, states):
    """Union park codes with codes expanded from states, keeping only codes that
    actually exist in parks.PARKS (drops anything hallucinated or unrecognized).
    Used for both the router's include fields and its exclude fields."""
    combined = set(park_codes) | set(park_codes_for_states(states))
    return sorted(code for code in combined if code in PARKS)


def answer_question(
    conn, question, *,
    park_codes=None, exclude_park_codes=None, start_date=None, end_date=None,
    routing=None, raw_question=None, history_length=None,
):
    """Retrieve incidents for `question`, generate an answer, log the run, and return it.

    The returned dict includes everything that's logged (see `_log`) plus `"incidents"`:
    the full collapsed incident data (id, park, date, title, source_url, body, distance),
    already fetched during retrieval, for the caller to build citations/a source list
    from without a second database query.

    `routing` is the router's decision for this question (see `ask`), included in the
    log entry for audit purposes. It plays no part in the retrieval or answer logic —
    the filters actually used come from `park_codes`/`exclude_park_codes`/`start_date`/
    `end_date` above, so this function is still directly callable with explicit filters
    and no router at all.

    `raw_question` and `history_length` are likewise logging-only, added for the
    conversation history feature (see `ask` and condense.condense_question):
    `raw_question` is the user's original, pre-condensing input, and `history_length` is
    how many history entries were available when `question` was condensed from it. Both
    default to None, so a direct caller with no conversation involved (like
    message_check.py) just logs None for both rather than needing placeholders.
    """
    filtered = bool(park_codes or exclude_park_codes or start_date or end_date)

    results = retrieve(
        conn, question, k=K,
        park_codes=park_codes, exclude_park_codes=exclude_park_codes,
        start_date=start_date, end_date=end_date,
    )
    collapsed = collapse_duplicates(results)

    gap = gap_note(start_date, end_date)
    notes = [
        describe_filters(park_codes, start_date, end_date,
                         exclude_park_codes=exclude_park_codes),
        completeness_note(len(results), K, filtered),
        gap,
    ]
    user_message = build_user_message(question, collapsed, notes, gap_warning=gap)
    answer = generate_answer(SYSTEM_PROMPT, user_message)

    log_entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "raw_question": raw_question,
        "history_length": history_length,
        "routing": routing,
        "filters": {
            "park_codes": park_codes,
            "exclude_park_codes": exclude_park_codes,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "k": K,
        "retrieved": [{"incident_id": r["incident_id"], "distance": r["distance"]} for r in results],
        "n_retrieved": len(results),
        "n_after_collapse": len(collapsed),
        "complete": is_complete(len(results), K, filtered),
        "notes": notes,
        "prompt": user_message,
        "answer": answer,
    }
    _log(log_entry)

    return {**log_entry, "incidents": collapsed}


def ask(conn, question, history=None):
    """Route `question`, then either answer it, decline politely, or ask for
    clarification. Always returns a dict with at least "answer" and "incidents"
    (empty unless retrieval ran), so callers don't need to branch on label themselves.

    `history` is the conversation so far, as built by history.append_turn() — a list of
    {"role", "content"} exchanges. It's used only to condense `question` into a
    standalone one (see condense.condense_question) before routing or retrieval ever
    see it; `ask` doesn't store or update history itself, that's the caller's job.
    Defaults to an empty conversation, which skips condensing entirely.
    """
    history = history or []
    history_length = len(history)
    condensed_question = condense_question(question, history)

    router_output = route_query(condensed_question)
    routing = {
        "label": router_output.label,
        "reason": router_output.reason,
        "park_codes": router_output.park_codes,
        "states": router_output.states,
        "exclude_park_codes": router_output.exclude_park_codes,
        "exclude_states": router_output.exclude_states,
        "start_date": router_output.start_date,
        "end_date": router_output.end_date,
    }

    if router_output.label == Label.RETRIEVAL:
        requested_location = bool(router_output.park_codes or router_output.states)
        park_codes = resolve_park_codes(router_output.park_codes, router_output.states)
        exclude_park_codes = resolve_park_codes(
            router_output.exclude_park_codes, router_output.exclude_states
        )
        searchable = [code for code in park_codes if code not in exclude_park_codes]

        if requested_location and not searchable:
            # The router named a park or state to search, but nothing is left to
            # search: either none of it resolved to a park in this dataset (e.g. a
            # state with no national park here), or every park it resolved to was
            # also excluded (e.g. "Death Valley but no California parks": Death Valley
            # touches California, so it is excluded too). retrieve() treats an empty
            # park_codes list as "no filter", so without this check we'd silently
            # search the whole dataset instead.
            # requested_location looks only at the include fields on purpose: an
            # exclusion on its own ("everywhere except Yellowstone") is a normal search.
            return _log_decision(
                condensed_question, routing, NO_MATCHING_PARKS_MESSAGE,
                raw_question=question, history_length=history_length,
            )

        return answer_question(
            conn, condensed_question,
            park_codes=park_codes or None,
            exclude_park_codes=exclude_park_codes or None,
            start_date=router_output.start_date,
            end_date=router_output.end_date,
            routing=routing,
            raw_question=question,
            history_length=history_length,
        )

    match router_output.label:
        case Label.AGGREGATE:
            answer = AGGREGATE_MESSAGE
        case Label.OFF_TOPIC:
            answer = OFF_TOPIC_MESSAGE
        case Label.NEEDS_CLARIFICATION:
            answer = router_output.clarifying_question
        case _:
            raise ValueError(f"Unhandled router label: {router_output.label!r}")

    return _log_decision(
        condensed_question, routing, answer,
        raw_question=question, history_length=history_length,
    )


def _log_decision(question, routing, answer, *, raw_question=None, history_length=None):
    """Log a run that never reached retrieval (aggregate/off_topic/needs_clarification,
    or a retrieval request whose location didn't resolve to any known park), and return
    it in the same shape `answer_question` returns, with no incidents.

    `raw_question` and `history_length` are logging-only, same as in `answer_question`.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "raw_question": raw_question,
        "history_length": history_length,
        "routing": routing,
        "answer": answer,
    }
    _log(log_entry)
    return {**log_entry, "incidents": []}


def _log(result):
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(result) + "\n")
