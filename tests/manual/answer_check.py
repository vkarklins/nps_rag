"""
Replay logged answer prompts through answer_response with several model/effort
configurations, and write the answers side by side, with the full text of every cited
report, to a Markdown file for reading and judging.

Diagnostic tool, not part of the app. Needs the OpenAI API but not the database: each
case is a line in logs/answers.jsonl (0-based line number) whose logged "prompt" field
is the exact user message the answer model saw. The current SYSTEM_PROMPT is used, so
this also shows how today's prompt handles older questions.

Usage (from the project root):
    poetry run python tests/manual/answer_check.py
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path

from rag_nps.answer import SYSTEM_PROMPT, answer_response

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "answers.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "evals" / "output"

# (model, reasoning effort) pairs to compare side by side.
CONFIGS = [("gpt-6-luna", "medium"), ("gpt-6-luna", "medium")]

# Prompts logged before this change include the closest-match note, which the app no
# longer sends (see answer.completeness_note). It's removed on replay so every case is
# tested with the message the app sends today.
OLD_PARTIAL_NOTE = (
    "These are the closest matches to the question, not a complete list. There may "
    "be other relevant reports that are not shown."
)

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
    (156, "thro-00030 is in Theodore Roosevelt, not Yellowstone; yell-00279: the driver "
          "hit the bison - the bison did not charge"),
    # Held out: not looked at when the prompt was written.
    (69, "complete set of 7 (Grand Canyon, 2018): uses the reports; no closing caveat"),
    (72, "'were there many' question: says it can't tell how common; no 'numerous'"),
    (80, "complete set of 20 (Yellowstone bears, 2020): uses the reports; no closing caveat"),
    (117, "several Death Valley heat deaths: each outcome stated as its report states it"),
    (134, "how-to (mountain lion): only advice the reports state, cited, right park"),
    (151, "distances come from the cited reports, never the prompt example's 40 yards"),
    (152, "how-to (feeding squirrels): feeding-wildlife reports used and cited"),
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
    labels = [f"{i}. {model} (effort: {effort})" for i, (model, effort) in enumerate(CONFIGS, 1)]
    out = [f"# Answer check {now:%Y-%m-%d %H:%M}", "", f"Configs: {', '.join(labels)}", ""]
    totals = {label: {"seconds": 0.0, "output": 0, "reasoning": 0} for label in labels}

    for line_no, check in CASES:
        entry = json.loads(lines[line_no])
        prompt = entry["prompt"].replace(f"\n- {OLD_PARTIAL_NOTE}", "")
        notes = [note for note in entry["notes"] if note and note != OLD_PARTIAL_NOTE]
        reports = dict(INCIDENT_RE.findall(prompt))
        print(f"line {line_no}: {entry['question']}")

        answers = {}  # label -> (answer text, stats line)
        for (model, effort), label in zip(CONFIGS, labels):
            start = time.perf_counter()
            response = answer_response(SYSTEM_PROMPT, prompt, model=model, effort=effort)
            seconds = time.perf_counter() - start
            usage = response.usage
            reasoning = usage.output_tokens_details.reasoning_tokens
            answers[label] = (
                response.output_text,
                f"{seconds:.1f}s, {usage.output_tokens} output tokens ({reasoning} reasoning)",
            )
            totals[label]["seconds"] += seconds
            totals[label]["output"] += usage.output_tokens
            totals[label]["reasoning"] += reasoning

        out += [f"## Line {line_no}: {entry['question']}", "", f"**Check:** {check}", ""]
        out += ["**Search notes (as sent):** " + (" ".join(notes) or "(none)"), ""]
        for label, (answer, stats) in answers.items():
            out += [f"### {label}", "", f"*{stats}*", "", answer, ""]
        out += ["### Cited reports", ""]
        for incident_id in cited_ids(answer for answer, _ in answers.values()):
            text = reports.get(incident_id)
            if text is None:
                out += [f"**{incident_id}**: NOT IN THE PROMPT - cited but never retrieved", ""]
            else:
                out += [f"**{incident_id}**", "", "```", text.strip(), "```", ""]
        out += ["**Notes:**", "", "---", ""]

    out += ["## Totals", ""]
    for label, t in totals.items():
        summary = (f"{label}: {t['seconds']:.0f}s total, {t['output']} output tokens "
                   f"({t['reasoning']} reasoning)")
        out.append(f"- {summary}")
        print(summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"answer_check_{now:%Y%m%d_%H%M%S}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"saved {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
