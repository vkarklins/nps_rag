# RAG for NPS Safety Queries

A retrieval-augmented generation (RAG) app that answers questions about safety incidents in
U.S. National Parks. Answers are grounded in, and cite, National Park Service Morning Report
incident narratives (deaths, injuries, rescues, wildlife encounters, law enforcement).

## How it works

1. **Data:** about 12,100 incident reports for 62 national park codes (Sequoia and Kings Canyon share one), scraped from the
   Morning Report archive on [npshistory.com](https://npshistory.com).
2. **Storage:** one chunk per incident in PostgreSQL with
   [pgvector](https://github.com/pgvector/pgvector), embedded with OpenAI `text-embedding-3-small`.
3. **Per question:**
   - **Condense:** follow-up questions are rewritten into standalone questions using the recent conversation.
   - **Route:** an LLM classifies the question (retrieval, aggregate, off-topic,
     needs clarification) and extracts park, state and date filters.
   - **Retrieve:** the 30 nearest incidents by cosine distance, with the filters applied, and exact duplicates
     collapsed.
   - **Answer:** an LLM answers only from the retrieved reports, citing each one. Notes
     tell it which filters were applied, whether the results are complete, and when a date range
     falls in the dataset's Sept 2015 - Mar 2017 gap.
4. **Interfaces:** a command-line chat, and a React web UI that streams answers from a FastAPI
   backend.

Every question is logged to `logs/answers.jsonl` (routing, filters, retrieved IDs and distances,
prompt, answer).

## Project layout

| Path | What's there |
|---|---|
| `src/rag_nps/scrape_incidents.py` | Scrapes the park pages into `data/incidents.jsonl` |
| `src/rag_nps/load_incidents.py` | Loads the JSONL into the `incidents` table |
| `src/rag_nps/get_embeddings.py` | Embeds every incident that doesn't have an embedding yet (resumable) |
| `src/rag_nps/retrieval.py` | Vector search with park/date filters and duplicate collapsing |
| `src/rag_nps/parks.py` | Park code → name and states lookup |
| `src/rag_nps/condense.py` | Rewrites follow-ups into standalone questions |
| `src/rag_nps/router.py` | Query classification and filter extraction |
| `src/rag_nps/answer.py` | Answer prompt, notes and generation |
| `src/rag_nps/pipeline.py` | `ask()`: condense → route → retrieve → answer, plus logging |
| `src/rag_nps/cli.py` | Command-line chat |
| `src/rag_nps/api.py` | FastAPI server (`POST /api/ask`, SSE streaming); serves the built frontend |
| `frontend/` | React (Vite) chat UI; see [`frontend/README.md`](frontend/README.md) |
| `fixes.sql` | Manual data corrections to apply after loading |
| `evals/questions.json` | Test questions with expected router labels |
| `tests/` | pytest suite for the scraper |
| `tests/manual/` | Diagnostic scripts (router, condense, answer and retrieval checks; mock API) |

## Setup

Requires Python 3.12+, [Poetry](https://python-poetry.org/), PostgreSQL with the pgvector
extension, Node 20.19+ or 22.12+ (for the frontend), and an OpenAI API key.

```bash
poetry install
cp .env.example .env        # then fill in the DB settings and OPENAI_API_KEY
```

### Build the database

Create the table (once):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE incidents (
    incident_id     text PRIMARY KEY,
    park_code       text NOT NULL,
    park_name       text NOT NULL,
    source_url      text NOT NULL,
    seq             integer NOT NULL,
    incident_date   date,
    date_raw        text,
    incident_number text,
    title           text,
    header_lines    text[] NOT NULL,
    body            text NOT NULL,
    embedding       vector(1536)
);
CREATE INDEX ON incidents (park_code);
CREATE INDEX ON incidents (incident_date);
```

Then scrape, load, fix and embed (`data/` is not committed):

```bash
poetry run python -m rag_nps.scrape_incidents
poetry run python -m rag_nps.load_incidents
psql -d <db name> -f fixes.sql
poetry run python -m rag_nps.get_embeddings
```

## Running

Command line:

```bash
poetry run python -m rag_nps.cli
```

Web UI (one process, served at http://localhost:8000):

```bash
cd frontend && npm install && npm run build && cd ..
poetry run uvicorn rag_nps.api:app --port 8000
```

See [`frontend/README.md`](frontend/README.md) for the two-terminal development setup and a mock
backend that runs without the database or OpenAI.

Tests (pytest is not a project dependency yet):

```bash
poetry add --group dev pytest    # one-time
poetry run pytest
```

## Limitations

- The source archive holds roughly 80-90% of all Morning Reports, and has no reports from
  September 2015 to March 2017. "No reports found" does not mean nothing happened.
- Report dates are when a report was written, which may differ from when the event happened.
- Each answer is based on the 30 closest reports, not every report, so the app declines to count or rank
  incidents.
- Park names reflect current designations (e.g. Pinnacles was a National Monument before 2013).
- The app shares only what the incident reports say. It is not a source of safety advice, so
  check nps.gov or ask a ranger before your visit.
