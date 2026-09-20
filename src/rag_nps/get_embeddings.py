"""
Fill in the `embedding` column of the `incidents` table.

Selects every incident whose embedding is NULL, builds one text per incident (park name +
header lines + body), embeds the texts in batches with OpenAI, and commits after each batch.
Safe to re-run: finished rows are no longer NULL, so an interrupted run picks up where it
left off instead of paying to embed the same incidents twice.

generate_embeddings() is also meant to be imported by the query app, so questions get
embedded with exactly the same model as the incidents.

Usage (from the project root):
    poetry run python -m rag_nps.get_embeddings
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pgvector import Vector
from psycopg2.extras import execute_batch

from rag_nps.db_connect import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions, matching vector(1536)
BATCH_SIZE = 100  # ~100 incidents is roughly 30k tokens: well under the per-request limits

# The SDK retries rate-limit (429) and transient server errors with backoff; its default is
# 2 retries, which is thin for a job that makes a couple hundred requests back to back.
client = OpenAI(api_key=API_KEY, max_retries=5)

PENDING_SQL = """
SELECT incident_id, park_name, header_lines, body
FROM incidents
WHERE embedding IS NULL
ORDER BY incident_id
"""

UPDATE_SQL = "UPDATE incidents SET embedding = %s WHERE incident_id = %s"


def build_embedding_text(park_name, header_lines, body):
    """The one place that defines what an incident looks like to the embedding model.

    Park name goes first because header_lines often only has an abbreviation ("Indiana Dunes
    NL") or none at all. header_lines carry the date and title. Changing this changes every
    embedding, so if you edit it, re-embed everything (UPDATE incidents SET embedding = NULL).
    """
    return "\n".join([park_name, *header_lines, "", body.strip()])


def generate_embeddings(texts):
    """Embed a list of strings; returns a list of vectors in the same order as `texts`."""
    if not texts:
        return []
    if any(not text.strip() for text in texts):
        raise ValueError("cannot embed an empty string")  # the API rejects empty inputs

    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)

    # Each result carries the position of its input; sort on it rather than trusting the order.
    ordered = sorted(response.data, key=lambda item: item.index)
    if len(ordered) != len(texts):
        raise RuntimeError(f"sent {len(texts)} texts but got {len(ordered)} embeddings back")
    return [item.embedding for item in ordered]


def main():
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:  # commits when the block ends, closing the transaction
            cur.execute(PENDING_SQL)
            pending = cur.fetchall()

        total = len(pending)
        print(f"{total} incidents need embeddings")

        for start in range(0, total, BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            texts = [
                build_embedding_text(park_name, header_lines, body)
                for _, park_name, header_lines, body in batch
            ]

            # The network call happens outside any transaction, so nothing stays open on the
            # database while we wait on OpenAI.
            embeddings = generate_embeddings(texts)

            params = [
                (Vector(embedding), incident_id)
                for embedding, (incident_id, *_) in zip(embeddings, batch)
            ]
            with conn, conn.cursor() as cur:  # one commit per batch keeps finished work
                execute_batch(cur, UPDATE_SQL, params)

            print(f"embedded {start + len(batch)}/{total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
