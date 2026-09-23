"""
Read logs/answers.jsonl and write a readable Markdown version to logs/answers_readable.md —
one section per logged question, with the huge assembled `prompt` field left out (everything
else, including the router's decision, the retrieved incident IDs/distances and the final
answer, is kept).

Diagnostic tool, not part of the app. Re-run any time after using the CLI to refresh the
readable version; it always overwrites the whole file from the current log.

Usage (from the project root):
    poetry run python tests/manual/view_answers.py
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "answers.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "logs" / "answers_readable.md"


def format_filters(filters):
    """Describe the filters dict in one line, or "none" if nothing was set."""
    parts = []
    if filters.get("park_codes"):
        parts.append(f'parks={", ".join(filters["park_codes"])}')
    if filters.get("start_date"):
        parts.append(f'from={filters["start_date"]}')
    if filters.get("end_date"):
        parts.append(f'to={filters["end_date"]}')
    return ", ".join(parts) if parts else "none"


def format_routing(routing):
    """Describe the router's decision in one line: label, anything it extracted, and why."""
    extracted = []
    if routing.get("park_codes"):
        extracted.append(f'parks={", ".join(routing["park_codes"])}')
    if routing.get("states"):
        extracted.append(f'states={", ".join(routing["states"])}')
    if routing.get("start_date"):
        extracted.append(f'from={routing["start_date"]}')
    if routing.get("end_date"):
        extracted.append(f'to={routing["end_date"]}')
    extracted_text = f' ({", ".join(extracted)})' if extracted else ""
    return f'`{routing["label"]}`{extracted_text} — {routing["reason"]}'


def write_entry(lines, entry):
    """Append one Markdown section for a single logged question/answer.

    Handles all three log shapes: pre-router entries (no "routing"), router decisions
    that never reached retrieval (no "filters"/"retrieved"/etc.), and full retrieval runs.
    """
    lines += [f'## {entry["timestamp"]}', ""]

    # raw_question is what the user typed; question is the condensed standalone version.
    raw = entry.get("raw_question")
    if raw and raw != entry["question"]:
        lines += [f"**Typed:** {raw}", ""]
        lines += [f'**Q (condensed, history={entry.get("history_length")}):** {entry["question"]}', ""]
    else:
        lines += [f'**Q:** {entry["question"]}', ""]

    if entry.get("routing"):
        lines += [f'Routed: {format_routing(entry["routing"])}', ""]

    if "filters" in entry:
        lines += [
            f'Filters: {format_filters(entry["filters"])}  |  k={entry["k"]}  |  '
            f'retrieved {entry["n_retrieved"]} → {entry["n_after_collapse"]} after collapsing',
            "",
            "**Retrieved:**",
            "",
        ]
        for rank, row in enumerate(entry["retrieved"], start=1):
            lines.append(f'{rank:>2}. {row["distance"]:.3f}  {row["incident_id"]}')
        lines.append("")
    else:
        lines += ["_No retrieval ran._", ""]

    notes = [n for n in entry.get("notes", []) if n]
    if notes:
        lines += ["**Notes:**", ""]
        lines += [f"- {n}" for n in notes]
        lines.append("")

    lines += ["**A:**", "", entry["answer"], "", "---", ""]


def main():
    if not LOG_PATH.exists():
        print(f"no log file at {LOG_PATH}")
        return

    entries = [
        json.loads(line)
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    lines = [f"# Answers log ({len(entries)} question{'s' if len(entries) != 1 else ''})", ""]
    for entry in entries:
        write_entry(lines, entry)

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(entries)} entries to logs/answers_readable.md")


if __name__ == "__main__":
    main()
