"""
Run every test question in evals/questions.json through retrieval, print what comes back,
and save the run to evals/output/ as JSON (full data) and Markdown (for reading and notes).

Usage (from the project root):
    poetry run python -m rag_nps.eval_retrieval
"""

import json
from datetime import datetime
from pathlib import Path

from rag_nps.db_connect import get_connection
from rag_nps.retrieval import collapse_duplicates, retrieve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = PROJECT_ROOT / "evals" / "questions.json"
OUTPUT_DIR = PROJECT_ROOT / "evals" / "output"
K = 30  # candidates to fetch per question, before identical copies are collapsed
TOP_K = 10  # the first TOP_K results are what earlier runs (k=10) showed; a marker follows them
PREVIEW_CHARS = 400  # how much of each body the Markdown report shows for the first TOP_K results
EXTRA_PREVIEW_CHARS = 200  # ... and for the rest, to keep the report readable


def print_question(question, results):
    """Print one question and its results, one compact line per result."""
    print("=" * 100)
    print(f'{question["id"]}  tier={question["tier"]}  expected={question["expected_label"]}')
    print(question["question"])
    print(f'(stresses: {question["stresses"]})')
    print()
    for rank, row in enumerate(results, start=1):
        if rank == TOP_K + 1:
            print(f"    --- ranks {TOP_K + 1} and beyond ---")
        date = row["incident_date"] or "no date"
        title = row["title"] or "(no title)"
        copies = f'  (+{len(row["also_in"])} identical)' if row["also_in"] else ""
        print(f'{rank:>2}. {row["distance"]:.3f}  {row["incident_id"]:<11} {date}  {row["park_code"]}  {title}{copies}')
    print()


def body_preview(body, limit):
    """Flatten an incident body to one line and cut it to `limit` characters."""
    flat = " ".join(body.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def write_json(path, run):
    """Save the whole run, including full bodies. default=str turns dates into text."""
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_markdown(path, run):
    """Save a readable report with body previews and an empty Notes line per question."""
    lines = [f'# Retrieval run {run["run_at"]}', "", f'k = {run["k"]} (identical copies collapsed afterwards)', ""]
    for entry in run["entries"]:
        question = entry["question"]
        lines += [
            f'## {question["id"]} (tier {question["tier"]}, expected: {question["expected_label"]})',
            "",
            f'**{question["question"]}**',
            "",
            f'Stresses: {question["stresses"]}',
            "",
        ]
        for rank, row in enumerate(entry["results"], start=1):
            if rank == TOP_K + 1:
                lines += ["---", "", f"*Ranks {TOP_K + 1} and beyond*", ""]
            date = row["incident_date"] or "no date"
            title = row["title"] or "(no title)"
            limit = PREVIEW_CHARS if rank <= TOP_K else EXTRA_PREVIEW_CHARS
            lines += [
                f'**{rank}. {row["distance"]:.3f}** `{row["incident_id"]}` {date} {row["park_code"]}: {title}',
                "",
            ]
            if row["also_in"]:
                lines += [f'Also appears as: {", ".join(row["also_in"])}', ""]
            lines += [f'> {body_preview(row["body"], limit)}', ""]
        lines += ["**Notes:**", "", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    print(f"running {len(questions)} question(s), k={K}")

    now = datetime.now()
    run = {"run_at": now.isoformat(timespec="seconds"), "k": K, "entries": []}

    conn = get_connection()
    try:
        for question in questions:
            results = collapse_duplicates(retrieve(conn, question["question"], k=K))
            print_question(question, results)
            run["entries"].append({"question": question, "results": results})
    finally:
        conn.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    write_json(OUTPUT_DIR / f"retrieval_{stamp}.json", run)
    write_markdown(OUTPUT_DIR / f"retrieval_{stamp}.md", run)
    print(f"saved evals/output/retrieval_{stamp}.json and .md")


if __name__ == "__main__":
    main()
