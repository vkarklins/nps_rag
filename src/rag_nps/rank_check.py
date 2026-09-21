"""
Check how deep in the ranking specific incidents appear for specific test questions.

For each (question, incident) pair in CHECKS, this retrieves the K_DEEP nearest incidents for
the question and reports the rank and distance of the incident we expected to see. It answers:
would fetching more than 10 results (say 30) recover incidents the k=10 runs missed?

Usage (from the project root):
    poetry run python -m rag_nps.rank_check
"""

import json
from pathlib import Path

from rag_nps.db_connect import get_connection
from rag_nps.retrieval import retrieve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = PROJECT_ROOT / "evals" / "questions.json"
K_DEEP = 500  # how far down the ranking to look
K_TOP = 10  # what the current runs return
K_OVERFETCH = 30  # what we are considering fetching instead

# (question id, incident the k=10 run missed, what it is)
CHECKS = [
    ("q06", "zion-00309", "April 2026: hiker fell from the Angels Landing chains"),
    ("q06", "zion-00064", "1997: climbing fatality on Angels Landing"),
    ("q13", "yell-00533", "2019: two men peered into Old Faithful's spout"),
    ("q17", "zion-00077", "1998: Zion flash flood killed two hikers; body mentions slot canyons"),
]


def where(rank):
    """Say in words where a rank falls relative to the current and candidate k."""
    if rank is None:
        return f"NOT in the top {K_DEEP}"
    if rank <= K_TOP:
        return f"inside the top {K_TOP}"
    if rank <= K_OVERFETCH:
        return f"ranks {K_TOP + 1}-{K_OVERFETCH} (within k={K_OVERFETCH})"
    return f"beyond rank {K_OVERFETCH}"


def main():
    questions = {q["id"]: q for q in json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))}

    # Group the checks by question so each question is embedded and searched only once.
    checks_by_question = {}
    for question_id, incident_id, description in CHECKS:
        checks_by_question.setdefault(question_id, []).append((incident_id, description))

    conn = get_connection()
    try:
        for question_id, checks in checks_by_question.items():
            text = questions[question_id]["question"]
            results = retrieve(conn, text, k=K_DEEP)
            # incident_id -> (rank, distance); rank 1 is the nearest incident.
            found = {
                row["incident_id"]: (rank, row["distance"])
                for rank, row in enumerate(results, start=1)
            }

            print("=" * 100)
            print(f"{question_id}  {text}")
            print(
                f"distance at rank {K_TOP}: {results[K_TOP - 1]['distance']:.3f}   "
                f"at rank {K_OVERFETCH}: {results[K_OVERFETCH - 1]['distance']:.3f}"
            )
            for incident_id, description in checks:
                rank, distance = found.get(incident_id, (None, None))
                shown = f"rank {rank:>3}  distance {distance:.3f}" if rank else "rank  --"
                print(f"  {incident_id:<11} {shown}  {where(rank)}  ({description})")
            print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
