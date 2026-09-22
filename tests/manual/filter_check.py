"""
Try retrieve() with filters on questions the k=30 run showed need them.

Diagnostic tool, not part of the app. Moved from src/rag_nps/ to tests/manual/ on 2026-09-21
to separate it from application code; it no longer runs as `python -m rag_nps.filter_check`.

Usage (from the project root):
    poetry run python tests/manual/filter_check.py
"""

import json
from pathlib import Path

from rag_nps.db_connect import get_connection
from rag_nps.retrieval import collapse_duplicates, retrieve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = PROJECT_ROOT / "evals" / "questions.json"
K = 30

# (question id, filters to pass to retrieve)
CASES = [
    ("q27", {"park_codes": ["YOSE"]}),
    ("q39", {"park_codes": ["GRCA"], "start_date": "2018-01-01", "end_date": "2018-12-31"}),
    ("q13", {"park_codes": ["YELL"], "start_date": "2019-01-01", "end_date": "2019-12-31"}),
]


def main():
    questions = {q["id"]: q for q in json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))}
    conn = get_connection()
    try:
        for question_id, filters in CASES:
            text = questions[question_id]["question"]
            results = collapse_duplicates(retrieve(conn, text, k=K, **filters))
            print("=" * 100)
            print(f"{question_id}  {text}")
            print(f"filters: {filters}   results: {len(results)}")
            for rank, row in enumerate(results, start=1):
                date = row["incident_date"] or "no date"
                title = row["title"] or "(no title)"
                print(f'{rank:>2}. {row["distance"]:.3f}  {row["incident_id"]:<11} {date}  {row["park_code"]}  {title}')
            print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
