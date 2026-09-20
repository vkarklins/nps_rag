"""
Load data/incidents.jsonl (written by scrape_incidents.py) into the `incidents` table.

Rows go in with a NULL `embedding`; a later step fills that in.
Connection settings come from <project root>/.env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD).

Usage (from the project root):
    poetry run python -m rag_nps.load_incidents

Each run empties the table and reloads it inside ONE transaction, so a failure leaves the
old contents untouched. Because a reload would also erase stored embeddings, the script
refuses to run if any exist.
"""

import json
from pathlib import Path
from rag_nps.db_connect import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/rag_nps/load_incidents.py -> project root

# %(name)s placeholders are filled from each row dict by key. The JSON "date" field goes into
# the incident_date column; None becomes NULL; the header_lines list becomes a text[] array.
INSERT = """
INSERT INTO incidents (incident_id, park_code, park_name, source_url, seq, incident_date,
                       date_raw, incident_number, title, header_lines, body)
VALUES (%(incident_id)s, %(park_code)s, %(park_name)s, %(source_url)s, %(seq)s, %(date)s::date,
        %(date_raw)s, %(incident_number)s, %(title)s, %(header_lines)s, %(body)s)
"""

with open(PROJECT_ROOT / "data" / "incidents.jsonl", encoding="utf-8") as f:
    rows = [json.loads(line) for line in f]

conn = get_connection()

with conn, conn.cursor() as cur:  # commits on success, rolls back on any error
    # The guard: TRUNCATE below would silently destroy any embeddings already paid for.
    cur.execute("SELECT count(*) FROM incidents WHERE embedding IS NOT NULL")
    (n_embedded,) = cur.fetchone()
    if n_embedded:
        raise SystemExit(
            f"{n_embedded} incidents already have embeddings; reloading would erase them. "
            "If that's what you want, run `UPDATE incidents SET embedding = NULL;` in psql first."
        )

    cur.execute("TRUNCATE incidents")
    cur.executemany(INSERT, rows)

conn.close()
print(f"loaded {len(rows)} incidents")
