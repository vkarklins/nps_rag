"""
Find the incidents most similar to a question.

retrieve() embeds the question with the same function and model used for the incidents
(generate_embeddings), then asks Postgres for the k nearest incidents by cosine distance.
The caller passes in the database connection, so one connection can serve many questions.
It can optionally be limited to some parks, exclude some parks, and/or be limited to a
date range (hard filters in the SQL).

collapse_duplicates() is applied to the results afterwards: some reports are copied onto
several park pages, and identical copies would otherwise fill several of the k slots.
"""

from pgvector import Vector
from psycopg2.extras import RealDictCursor

from rag_nps.get_embeddings import generate_embeddings

# `<=>` is pgvector's cosine distance: 0 means identical direction, larger means less similar.
# Sorting by the `distance` alias means the query vector is sent to the database only once.
# Each optional filter follows the pattern "(filter IS NULL OR condition)": when the filter is
# NULL the parenthesis is true and removes nothing; otherwise the condition must hold.
# The casts (::text[], ::date) give Postgres a type even when Python sends None.
SEARCH_SQL = """
SELECT incident_id, park_code, park_name, incident_date, title, source_url, body,
       embedding <=> %(query)s AS distance
FROM incidents
WHERE embedding IS NOT NULL
  AND (%(park_codes)s::text[] IS NULL OR park_code = ANY(%(park_codes)s::text[]))
  AND (%(exclude_park_codes)s::text[] IS NULL
       OR NOT (park_code = ANY(%(exclude_park_codes)s::text[])))
  AND (%(start_date)s::date IS NULL OR incident_date >= %(start_date)s::date)
  AND (%(end_date)s::date IS NULL OR incident_date <= %(end_date)s::date)
ORDER BY distance
LIMIT %(k)s
"""


def retrieve(conn, question, k=10, *, park_codes=None, exclude_park_codes=None,
             start_date=None, end_date=None):
    """Return the k incidents closest to `question`, nearest first, as a list of dicts.

    Optional hard filters (leave as None for no filter):
      park_codes          list of park codes such as ["YOSE", "GRCA"]; only those parks are searched
      exclude_park_codes  list of park codes to leave out; applied after park_codes, so a park
                          in both lists is excluded
      start_date          earliest incident_date to include (a date or an ISO string "2018-01-01")
      end_date            latest incident_date to include (inclusive)
    Incidents with no date are left out whenever a date bound is given.
    """
    [query_embedding] = generate_embeddings([question])

    params = {
        "query": Vector(query_embedding),
        "k": k,
        "park_codes": park_codes or None,  # an empty list means "no filter", not "no parks"
        "exclude_park_codes": exclude_park_codes or None,  # empty list: exclude nothing
        "start_date": start_date,
        "end_date": end_date,
    }
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(SEARCH_SQL, params)
        return [dict(row) for row in cur.fetchall()]


def collapse_duplicates(results):
    """Drop results whose body is identical to a nearer result, and note where the copies were."""
    kept = []
    first_by_body = {}  # body text -> the kept result with that body
    for row in results:
        first = first_by_body.get(row["body"])
        if first is None:
            first = {**row, "also_in": []}
            first_by_body[row["body"]] = first
            kept.append(first)
        else:
            first["also_in"].append(row["incident_id"])
    return kept
