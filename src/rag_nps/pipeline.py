"""
Wire the pieces together: given a question and optional filters, retrieve incidents,
assemble the prompt, generate an answer, and log the run.
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
)
from rag_nps.retrieval import collapse_duplicates, retrieve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "answers.jsonl"

K = 30  # candidates sent to the answer model; see retrieval eval findings for why


def answer_question(conn, question, *, park_codes=None, start_date=None, end_date=None):
    """Retrieve incidents for `question`, generate an answer, log the run, and return it.

    The returned dict includes everything that's logged (see `_log`) plus `"incidents"`:
    the full collapsed incident data (id, park, date, title, source_url, body, distance),
    already fetched during retrieval, for the caller to build citations/a source list
    from without a second database query.
    """
    filtered = bool(park_codes or start_date or end_date)

    results = retrieve(
        conn, question, k=K,
        park_codes=park_codes, start_date=start_date, end_date=end_date,
    )
    collapsed = collapse_duplicates(results)

    gap = gap_note(start_date, end_date)
    notes = [
        describe_filters(park_codes, start_date, end_date),
        completeness_note(len(results), K, filtered),
        gap,
    ]
    user_message = build_user_message(question, collapsed, notes, gap_warning=gap)
    answer = generate_answer(SYSTEM_PROMPT, user_message)

    log_entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "filters": {
            "park_codes": park_codes,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "k": K,
        "retrieved": [{"incident_id": r["incident_id"], "distance": r["distance"]} for r in results],
        "n_retrieved": len(results),
        "n_after_collapse": len(collapsed),
        "notes": notes,
        "prompt": user_message,
        "answer": answer,
    }
    _log(log_entry)

    return {**log_entry, "incidents": collapsed}


def _log(result):
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(result) + "\n")
