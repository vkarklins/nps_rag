"""
Replay logged answer prompts through generate_answer with several models, and write
the answers side by side, with the full text of every cited report, to a Markdown file
for reading and judging.

Diagnostic tool, not part of the app. Needs the OpenAI API but not the database: each
case is a line in logs/answers.jsonl (0-based line number) whose logged "prompt" field
is the exact user message the answer model saw. The current SYSTEM_PROMPT is used, so
this also shows how today's prompt handles older questions.

Usage (from the project root):
    poetry run python tests/manual/answer_check.py
"""

import json
import re
from datetime import datetime
from pathlib import Path

from rag_nps.answer import SYSTEM_PROMPT, generate_answer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "answers.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "evals" / "output"

MODELS = ["gpt-6-luna"]

# (log line, what to check when reading the answers)
CASES = [
    # Detail errors found in earlier reviews.
    (100, "olym-00312: the Lake Crescent kayaker was 37, not 34"),
    (108, "yell-00681: the children escaped; a different person was thrown"),
    (113, "288 violations / 80 Lacey Act are from bibe-00088 (1994), not the 1996 follow-up"),
    (116, "grca-00860: three heat deaths in total (72 on South Kaibab; 67 and 68 on North Kaibab)"),
    (148, "yell-00681 again; the 43-year-old is yell-00486 - check each citation fits its claim"),
    (150, "grca-00240 happened in Kaibab National Forest, outside the park"),
    (153, "no uncited general claims (e.g. about the park's response)"),
    (154, "yell-00390's mauling happened north of the park"),
    # Declines and wording: these should not get worse.
    (14, "rule 3: mountain lion reports must not be presented as bear attacks"),
    (106, "complete set of 12: no Bridalveil incident in 2018; may say so firmly"),
    (109, "all 30 reports are Yellowstone: 'couldn't find', never 'none exist'; no citation dump"),
    (124, "the shelter advice comes from grca-00671 and must be cited"),
]

CITATION_RE = re.compile(r"\[([a-z]+-\d+)\]")
INCIDENT_RE = re.compile(r'<incident id="([^"]+)">\n(.*?)\n</incident>', re.S)


def cited_ids(answers):
    """Incident IDs cited in any of the answers, in order of first appearance."""
    seen = []
    for answer in answers:
        for incident_id in CITATION_RE.findall(answer):
            if incident_id not in seen:
                seen.append(incident_id)
    return seen


def main():
    now = datetime.now()
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    out = [f"# Answer check {now:%Y-%m-%d %H:%M}", "", f"Models: {', '.join(MODELS)}", ""]

    for line_no, check in CASES:
        entry = json.loads(lines[line_no])
        prompt = entry["prompt"]
        reports = dict(INCIDENT_RE.findall(prompt))
        print(f"line {line_no}: {entry['question']}")
        answers = {model: generate_answer(SYSTEM_PROMPT, prompt, model=model) for model in MODELS}

        out += [f"## Line {line_no}: {entry['question']}", "", f"**Check:** {check}", ""]
        out += ["**Search notes:** " + " ".join(note for note in entry["notes"] if note), ""]
        for model, answer in answers.items():
            out += [f"### {model}", "", answer, ""]
        out += ["### Cited reports", ""]
        for incident_id in cited_ids(answers.values()):
            text = reports.get(incident_id)
            if text is None:
                out += [f"**{incident_id}**: NOT IN THE PROMPT - cited but never retrieved", ""]
            else:
                out += [f"**{incident_id}**", "", "```", text.strip(), "```", ""]
        out += ["**Notes:**", "", "---", ""]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"answer_check_{now:%Y%m%d_%H%M%S}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"saved {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
