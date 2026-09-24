# Trailhead — React front end

Chat UI for the NPS safety RAG app. Streams answers from `src/rag_nps/api.py`.

## One-time setup

```bash
# from the project root
poetry add fastapi "uvicorn[standard]"
cd frontend && npm install        # needs Node 20.19+ or 22.12+
```

## Run (development: two terminals)

```bash
poetry run uvicorn rag_nps.api:app --reload --port 8000     # terminal 1, project root
cd frontend && npm run dev                                 # terminal 2 -> http://localhost:5173
```

## Run (presentation: one process)

```bash
cd frontend && npm run build && cd ..
poetry run uvicorn rag_nps.api:app --port 8000             # -> http://localhost:8000
```

`api.py` serves `frontend/dist` whenever it exists.

## Backup demo without the DB or OpenAI

```bash
poetry run uvicorn tests.manual.mock_api:app --port 8000
```

Uses real reports from `data/incidents.jsonl` with keyword search, and a canned answer
(labelled "Mock answer"). Nothing is logged.

## Where things live

| File | What it does |
|---|---|
| `src/api.js` | Reads the SSE stream from `POST /api/ask` |
| `src/citations.js` | `[incident_id]` → `[N]` while streaming, source grouping, report links |
| `src/biomes.js` | Park → landscape biome, and each biome's colours |
| `src/scenery.js` | Drawn landscape silhouettes for the background and placeholders |
| `src/parkPhotos.js` | Add your own park photos here (files go in `public/parks/`) |
| `src/components/Message.jsx` | Answer, citation markers, footnotes |
| `src/components/Sources.jsx` | Cited reports grouped by park, with links and excerpts |
| `src/components/Gallery.jsx` | Park gallery / slideshow |
