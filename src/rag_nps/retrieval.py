"""
Find the incidents most similar to a question.

retrieve() embeds the question with the same function and model used for the incidents
(generate_embeddings), then asks Postgres for the k nearest incidents by cosine distance.
The caller passes in the database connection, so one connection can serve many questions.
It can optionally be limited to some parks, exclude some parks, and/or be limited to a
date range (hard filters in the SQL).

When the caller passes min_per_park (used when a question names two or more parks), each
filtered park is guaranteed its nearest min_per_park reports even if other parks fill the top
k, so one park can't crowd another out entirely. See _keep_minimums().

collapse_duplicates() is applied to the results afterwards: some reports are copied onto
several park pages, and identical copies would otherwise fill several of the k slots.
"""

from pgvector import Vector
from psycopg2.extras import RealDictCursor

from rag_nps.get_embeddings import generate_embeddings

# `<=>` is pgvector's cosine distance: 0 means identical direction, larger means less similar.
# The query vector is sent to the database only once (in `scored`).
# Each optional filter follows the pattern "(filter IS NULL OR condition)": when the filter is
# NULL the parenthesis is true and removes nothing; otherwise the condition must hold.
# The casts (::text[], ::date) give Postgres a type even when Python sends None.
#
# Two rankings in one pass (like a race's overall place and age-group place):
# overall_rank numbers every matching report by distance; park_rank restarts at 1 for each
# park (PARTITION BY park_code). The query returns the overall top k plus each park's nearest
# min_per_park, so a park crowded out of the top k still gets a few slots. With
# min_per_park = 0 the second condition matches nothing, so the result is just the top k.
# The rankings are computed in `ranked`, a separate step, because WHERE can't use a column
# computed in the same SELECT.
SEARCH_SQL = """
WITH scored AS (
    SELECT incident_id, park_code, park_name, incident_date, title, source_url, body,
           embedding <=> %(query)s AS distance
    FROM incidents
    WHERE embedding IS NOT NULL
      AND (%(park_codes)s::text[] IS NULL OR park_code = ANY(%(park_codes)s::text[]))
      AND (%(exclude_park_codes)s::text[] IS NULL
           OR NOT (park_code = ANY(%(exclude_park_codes)s::text[])))
      AND (%(start_date)s::date IS NULL OR incident_date >= %(start_date)s::date)
      AND (%(end_date)s::date IS NULL OR incident_date <= %(end_date)s::date)
), ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY distance) AS overall_rank,
           ROW_NUMBER() OVER (PARTITION BY park_code ORDER BY distance) AS park_rank
    FROM scored
)
SELECT * FROM ranked
WHERE overall_rank <= %(k)s OR park_rank <= %(min_per_park)s
ORDER BY distance
"""


def retrieve(conn, question, k=10, *, park_codes=None, exclude_park_codes=None,
             start_date=None, end_date=None, min_per_park=0):
    """Return the k incidents closest to `question`, nearest first, as a list of dicts.

    Optional hard filters (leave as None for no filter):
      park_codes          list of park codes such as ["YOSE", "GRCA"]; only those parks are searched
      exclude_park_codes  list of park codes to leave out; applied after park_codes, so a park
                          in both lists is excluded
      start_date          earliest incident_date to include (a date or an ISO string "2018-01-01")
      end_date            latest incident_date to include (inclusive)
      min_per_park        guarantee each park in park_codes its nearest min_per_park reports,
                          even when other parks fill the top k (0, the default, means no
                          guarantee: plain top k). Capped at k // len(park_codes) so the
                          guaranteed rows always fit in k.
    Incidents with no date are left out whenever a date bound is given.
    Returns at most k rows; fewer only when fewer than k incidents match the filters.
    """
    [query_embedding] = generate_embeddings([question])

    if park_codes:
        min_per_park = min(min_per_park, k // len(park_codes))
    else:
        min_per_park = 0  # no parks to guarantee anything to

    params = {
        "query": Vector(query_embedding),
        "k": k,
        "park_codes": park_codes or None,  # an empty list means "no filter", not "no parks"
        "exclude_park_codes": exclude_park_codes or None,  # empty list: exclude nothing
        "start_date": start_date,
        "end_date": end_date,
        "min_per_park": min_per_park,
    }
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(SEARCH_SQL, params)
        rows = [dict(row) for row in cur.fetchall()]
    return _keep_minimums(rows, k, min_per_park)


def _keep_minimums(rows, k, min_per_park):
    """Trim the query's rows back to k, keeping every park's nearest min_per_park.

    `rows` arrive nearest first. Protected rows (park_rank <= min_per_park) are always kept;
    the remaining slots are filled from the other rows, nearest first. When there are more
    than k rows, the ones dropped are the farthest rows of parks that had more than their
    minimum. The two rank columns are removed, so callers get the same keys as before.
    """
    protected = [r for r in rows if r["park_rank"] <= min_per_park]
    others = [r for r in rows if r["park_rank"] > min_per_park]
    kept = protected + others[: k - len(protected)]
    kept.sort(key=lambda r: r["distance"])
    for r in kept:
        del r["overall_rank"], r["park_rank"]
    return kept


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
