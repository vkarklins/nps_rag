"""
Replay real conversations from logs/answers.jsonl through condense_question with
several models, and print each model's rewrite side by side.

Diagnostic tool, not part of the app. Needs the OpenAI API but not the database.
Each case names a run of consecutive lines in answers.jsonl (0-based line numbers):
every line but the last becomes the conversation history, and the last line's raw
question is the one to condense.

Usage (from the project root):
    poetry run python tests/manual/condense_check.py
"""

import json
from pathlib import Path

from rag_nps.condense import condense_question

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "answers.jsonl"

MODELS = ["gpt-4o-mini", "gpt-6-luna"]

# (first line, last line, what a correct rewrite looks like)
CASES = [
    # Cases the prompt's examples were written to cover.
    (125, 126, "bison incidents in parks other than Yellowstone"),
    (140, 141, "bear incidents - no park named"),
    (140, 142, "bison incidents in parks other than Yellowstone"),
    (129, 131, "unchanged - no Yellowstone added"),
    (144, 145, "unchanged - no Yellowstone added"),
    (144, 147, "bear incidents in Yellowstone"),
    (118, 119, "unchanged - no 'while biking'"),
    (102, 103, "are the campsites in Yosemite secure"),
    (102, 106, "incidents at Bridalveil Fall in Yosemite in 2018"),
    # Held out: conversations no example was modeled on.
    (94, 97, "overheating incidents in Death Valley - Pinnacles dropped"),
    (94, 98, "overheating incidents in Death Valley before 2010"),
    (100, 101, "the Oconaluftee River kayaking incident (Great Smoky Mountains)"),
    (108, 110, "unchanged - Grand Teton named by the user"),
    (111, 113, "unchanged - Operation Rockcut is its own subject"),
    (111, 114, "undercover poaching investigations other than Operation Rockcut"),
    (111, 115, "unchanged - rattlesnakes"),
]


def build_history(entries):
    """Rebuild the CLI's history list from logged turns. The CLI stores each answer
    with citations already converted to [1], [2]...; the log keeps [incident-id]
    citations instead, a difference that shouldn't matter for condensing."""
    history = []
    for entry in entries:
        history.append({"role": "user", "content": entry["raw_question"]})
        history.append({"role": "assistant", "content": entry["answer"]})
    return history


def main():
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    for first, last, expected in CASES:
        *earlier, current = [json.loads(lines[i]) for i in range(first, last + 1)]
        history = build_history(earlier)
        question = current["raw_question"]
        print("=" * 100)
        print(f"lines {first}-{last}   expected: {expected}")
        for entry in earlier:
            print(f"  earlier:  {entry['raw_question']}")
        print(f"  question: {question}")
        for model in MODELS:
            rewritten = condense_question(question, history, model=model)
            shown = "(unchanged)" if rewritten == question else rewritten
            print(f"  {model:<12} {shown}")
        print()


if __name__ == "__main__":
    main()
