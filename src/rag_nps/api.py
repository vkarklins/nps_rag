"""
HTTP API for the React front end: a thin FastAPI wrapper around the same steps as
pipeline.ask(), except that the answer is streamed to the browser as it's generated.

Run (from the project root):
    poetry run uvicorn rag_nps.api:app --reload --port 8000

POST /api/ask  {"question": "...", "history": [{"role": ..., "content": ...}, ...]}
returns a Server-Sent Events stream. Each event is "event: <name>\\ndata: <json>\\n\\n":

    status    {"stage": "condensing" | "routing" | "searching" | "writing"}
    meta      {"question", "raw_question", "label", "asks_for_advice", "parks": [{code, name}]}
              parks = the parks the question was resolved to (empty for an all-parks search)
    sources   {"incidents": [{incident_id, park_code, park_name, incident_date, title,
                              source_url, body}]}   (every report sent to the model)
    delta     {"text": "..."}   a chunk of answer text; citations are still [incident_id]
    done      {"answered", "complete", "asks_for_advice"}
    error     {"message": "..."}

Citation numbering ([yose-00571] -> [1]) is done by the browser as text arrives, because
it has to hold back a half-received "[yose-00" until its closing bracket anyway.

Why a separate function instead of calling pipeline.ask(): ask() returns only once the
whole answer exists. stream_ask() below repeats ask()'s decisions step for step (same
helpers, same messages, same log entry shape) but asks OpenAI for a streamed response.
The CLI is unchanged. If ask()'s routing logic changes, mirror it here.

History is kept by the browser (like the CLI keeps it in main()) and sent with each
question; only the last history.MAX_HISTORY entries are used.

If frontend/dist exists (after `npm run build`), it's served at "/", so one process
serves both the API and the built front end (useful for deployment).
"""

import json
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag_nps.answer import (
    CHAT_MODEL,
    REASONING_EFFORT,
    SYSTEM_PROMPT,
    build_user_message,
    completeness_note,
    describe_filters,
    gap_note,
    is_complete,
)
from rag_nps.condense import condense_question
from rag_nps.db_connect import get_connection
from rag_nps.history import MAX_HISTORY
from rag_nps.openai_client import client, model_options
from rag_nps.parks import PARKS
from rag_nps.pipeline import (
    AGGREGATE_MESSAGE,
    K,
    MIN_PER_PARK,
    NO_MATCHING_PARKS_MESSAGE,
    OFF_TOPIC_MESSAGE,
    _log,
    resolve_park_codes,
)
from rag_nps.retrieval import collapse_duplicates, retrieve
from rag_nps.router import Label, route_query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(title="NPS Safety RAG")

# The Vite dev server (port 5173) proxies /api to us, so CORS is only a fallback for
# opening the front end some other way during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[Turn] = []


def sse(event, data):
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def park_list(codes):
    return [{"code": code, "name": PARKS[code]["name"]} for code in codes or []]


def stream_answer(user_message):
    """Yield answer text chunks from a streamed Responses API call (same model and
    options as answer.generate_answer)."""
    stream = client.responses.create(
        model=CHAT_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        stream=True,
        **model_options(CHAT_MODEL, REASONING_EFFORT),
    )
    for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta
        elif event.type in ("response.failed", "error"):
            raise RuntimeError(f"OpenAI stream failed: {event}")


def stream_ask(question, history):
    """Generator of SSE strings for one question. Mirrors pipeline.ask()."""
    history = history[-MAX_HISTORY:]
    history_length = len(history)

    yield sse("status", {"stage": "condensing" if history else "routing"})
    condensed = condense_question(question, history)

    if history:
        yield sse("status", {"stage": "routing"})
    router_output = route_query(condensed)
    routing = {
        "label": router_output.label,
        "reason": router_output.reason,
        "asks_for_advice": router_output.asks_for_advice,
        "park_codes": router_output.park_codes,
        "states": router_output.states,
        "exclude_park_codes": router_output.exclude_park_codes,
        "exclude_states": router_output.exclude_states,
        "start_date": router_output.start_date,
        "end_date": router_output.end_date,
    }

    park_codes = resolve_park_codes(router_output.park_codes, router_output.states)
    exclude_park_codes = resolve_park_codes(
        router_output.exclude_park_codes, router_output.exclude_states
    )
    searchable = [code for code in park_codes if code not in exclude_park_codes]

    yield sse("meta", {
        "question": condensed,
        "raw_question": question,
        "label": router_output.label.value,
        "asks_for_advice": router_output.asks_for_advice,
        "parks": park_list(searchable),
    })

    # Everything that doesn't reach the answer step: same messages as pipeline.ask().
    decline = None
    if router_output.label == Label.RETRIEVAL:
        requested_location = bool(router_output.park_codes or router_output.states)
        if requested_location and not searchable:
            decline = NO_MATCHING_PARKS_MESSAGE
    else:
        match router_output.label:
            case Label.AGGREGATE:
                decline = AGGREGATE_MESSAGE
            case Label.OFF_TOPIC:
                decline = OFF_TOPIC_MESSAGE
            case Label.NEEDS_CLARIFICATION:
                decline = router_output.clarifying_question
            case _:
                raise ValueError(f"Unhandled router label: {router_output.label!r}")

    if decline is not None:
        yield sse("delta", {"text": decline})
        yield sse("done", {"answered": False, "complete": None, "asks_for_advice": False})
        _log({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "question": condensed,
            "raw_question": question,
            "history_length": history_length,
            "routing": routing,
            "answer": decline,
            "source": "web",
        })
        return

    # Retrieval, same as pipeline.answer_question().
    yield sse("status", {"stage": "searching"})
    park_codes = park_codes or None
    exclude_park_codes = exclude_park_codes or None
    start_date, end_date = router_output.start_date, router_output.end_date
    filtered = bool(park_codes or exclude_park_codes or start_date or end_date)
    # Same rule as pipeline.ask(): only when the question itself named 2+ parks.
    min_per_park = MIN_PER_PARK if len(router_output.park_codes) > 1 else 0

    conn = get_connection()
    try:
        results = retrieve(
            conn, condensed, k=K,
            park_codes=park_codes, exclude_park_codes=exclude_park_codes,
            start_date=start_date, end_date=end_date,
            min_per_park=min_per_park,
        )
    finally:
        conn.close()
    collapsed = collapse_duplicates(results)

    yield sse("sources", {"incidents": [
        {key: incident[key] for key in
         ("incident_id", "park_code", "park_name", "incident_date", "title", "source_url", "body")}
        for incident in collapsed
    ]})

    gap = gap_note(start_date, end_date)
    notes = [
        describe_filters(park_codes, start_date, end_date, exclude_park_codes=exclude_park_codes),
        completeness_note(len(results), K, filtered),
        gap,
    ]
    user_message = build_user_message(condensed, collapsed, notes, gap_warning=gap)

    yield sse("status", {"stage": "writing"})
    parts = []
    for chunk in stream_answer(user_message):
        parts.append(chunk)
        yield sse("delta", {"text": chunk})

    complete = is_complete(len(results), K, filtered)
    yield sse("done", {
        "answered": True,
        "complete": complete,
        "asks_for_advice": router_output.asks_for_advice,
    })

    _log({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": condensed,
        "raw_question": question,
        "history_length": history_length,
        "routing": routing,
        "filters": {
            "park_codes": park_codes,
            "exclude_park_codes": exclude_park_codes,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "min_per_park": min_per_park,
        },
        "k": K,
        "retrieved": [{"incident_id": r["incident_id"], "distance": r["distance"]} for r in results],
        "n_retrieved": len(results),
        "n_after_collapse": len(collapsed),
        "complete": complete,
        "notes": notes,
        "prompt": user_message,
        "answer": "".join(parts),
        "source": "web",
    })


def safe_stream(question, history):
    """Wrap stream_ask so an exception becomes an `error` event instead of a cut-off
    stream the browser can't explain."""
    try:
        yield from stream_ask(question, history)
    except Exception as exc:  # noqa: BLE001 - report anything to the browser
        print(f"[api] error answering {question!r}:")
        traceback.print_exc()
        yield sse("error", {"message": "Something went wrong while answering. Please try again."})


@app.post("/api/ask")
def ask_endpoint(request: AskRequest):
    history = [turn.model_dump() for turn in request.history]
    return StreamingResponse(
        safe_stream(request.question, history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built front end, if there is one.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        file = FRONTEND_DIST / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
