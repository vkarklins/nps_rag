"""
Route a fixed set of questions through route_query with several model/effort
configurations, compare each result with the expected label (and, for some cases, the
expected filters), and write the results side by side to a Markdown file.

Diagnostic tool, not part of the app. Needs the OpenAI API but not the database.
Cases come from three places:
  - every question in evals/questions.json, using its expected_label, plus expected
    filters for a few
  - questions from logs/answers.jsonl that were misrouted or exercise the exclusion
    fields, as the router actually saw them (the condensed question)
  - hand-written cases for labels and filters nothing else covers

Usage (from the project root):
    poetry run python tests/manual/router_check.py
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rag_nps.router import route_query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = PROJECT_ROOT / "evals" / "questions.json"
OUTPUT_DIR = PROJECT_ROOT / "evals" / "output"

# (model, reasoning effort) pairs to compare side by side.
CONFIGS = [("gpt-6-luna", "none")]

FILTER_FIELDS = [
    "park_codes", "states", "exclude_park_codes", "exclude_states", "start_date", "end_date",
]


@dataclass
class Case:
    id: str
    question: str
    labels: tuple          # acceptable labels; usually just one
    filters: dict = field(default_factory=dict)  # only the fields worth checking
    note: str = ""
    advice: bool | None = None  # expected asks_for_advice; None means not checked


# Expected filters for questions.json cases where the filters are the point.
QUESTION_FILTERS = {
    "q02": {"park_codes": [], "states": ["CA"]},
    "q13": {"park_codes": ["YELL"], "start_date": "2019-01-01", "end_date": "2019-12-31"},
    "q14": {"park_codes": ["YOSE"], "start_date": "2016-01-01", "end_date": "2016-12-31"},
    "q22": {"park_codes": ["ZION", "YOSE"], "states": []},
    "q47": {"park_codes": ["ROMO"], "start_date": "2015-01-01", "end_date": "2015-12-31"},
}

HOW_TO = "how-to question about a park hazard: retrieval, not off_topic"

EXTRA_CASES = [
    # From logs/answers.jsonl (line number in the id), as the router saw them.
    Case("log102", "Are the campsites secure?", ("needs_clarification", "retrieval"),
         note="either is acceptable; the clarifying flow worked"),
    Case("log122", "What are the signs of flash flooding in slot canyons like Zion?",
         ("retrieval",), note="4o-mini used states ['UT']; check the filters by eye"),
    Case("log123", "What are the signs of hypothermia and how can it be treated in sudden "
         "alpine weather conditions?", ("retrieval",), note=HOW_TO, advice=True),
    Case("log126", "Have there been any reported bison incidents in national parks other "
         "than Yellowstone?", ("retrieval",),
         {"park_codes": [], "exclude_park_codes": ["YELL"]}, advice=False),
    Case("log128", "What should I do if I see a grizzly bear?", ("retrieval",), note=HOW_TO,
         advice=True),
    Case("log143", "Tell me about bison incidents that did not occur in Yellostone",
         ("retrieval",), {"park_codes": [], "exclude_park_codes": ["YELL"]},
         note="typo in 'Yellostone' is the user's"),
    Case("log163", "How do I recognize and treat hypothermia in sudden alpine weather?",
         ("retrieval",), note=HOW_TO, advice=True),
    Case("log164", "What should I do if I get caught in a lightning storm above the tree "
         "line?", ("retrieval",), note=HOW_TO + "; went to retrieval in log 124", advice=True),
    Case("log165", "How much water per hour do I need to drink while hiking in Death "
         "Valley?", ("retrieval",), {"park_codes": ["DEVA"]}, note=HOW_TO, advice=True),
    Case("log166", "What gear do I need to hike safely on ice trails in Rocky Mountain "
         "National Park?", ("retrieval",), {"park_codes": ["ROMO"]}, note=HOW_TO, advice=True),
    Case("log167", "What should I do if I realize I am lost on a backcountry trail?",
         ("retrieval",), note=HOW_TO, advice=True),
    Case("log169", "How do I signal for help if my cell phone has no service?",
         ("retrieval",), note=HOW_TO, advice=True),
    Case("log171", "Do I need to wear a life jacket while paddleboarding on Lake Mead?",
         ("retrieval",), {"park_codes": []},
         note=HOW_TO + "; Lake Mead is not in the park table, so no code", advice=True),
    Case("log174", "what happens in Kobuk Valley", ("needs_clarification", "retrieval"),
         note="either is acceptable"),
    Case("log176", "What dangerous incidents happen in Kobuk Valley?", ("retrieval",),
         {"park_codes": ["KOVA"]}, advice=False),
    # Hand-written.
    Case("h01", "Have there been any bear encounters in Yellowstone?", ("retrieval",),
         {"park_codes": ["YELL"], "states": []}, advice=False),
    Case("h02", "Were there any drownings in Grand Canyon in 2018?", ("retrieval",),
         {"park_codes": ["GRCA"], "start_date": "2018-01-01", "end_date": "2018-12-31"},
         advice=False),
    Case("h03", "Have there been wildlife attacks in Everglades since 2020?", ("retrieval",),
         {"park_codes": ["EVER"], "start_date": "2020-01-01", "end_date": None}),
    Case("h04", "How many people have died in Yosemite?", ("aggregate",)),
    Case("h14", "Is it safe to swim in the Merced River in Yosemite?", ("retrieval",),
         {"park_codes": ["YOSE"]}, advice=True),
    Case("h15", "What happened to the hikers who were rescued from Half Dome?",
         ("retrieval",), {"park_codes": ["YOSE"]}, advice=False,
         note="asks what happened, not what to do"),
    Case("h05", "What are the entrance fees for Yellowstone?", ("off_topic",)),
    Case("h06", "tell me about the parks", ("needs_clarification",)),
    Case("h07", "incidents", ("needs_clarification",)),
    Case("h08", "bubbles", ("off_topic", "needs_clarification"),
         note="either is acceptable"),
    Case("h09", "write a basic hello world function in JavaScript", ("off_topic",)),
    Case("h10", "Heat incidents in Death Valley but not in any California parks",
         ("retrieval",),
         {"park_codes": ["DEVA"], "states": [], "exclude_park_codes": [],
          "exclude_states": ["CA"]},
         note="log 127's case: exclude the state, don't list CA parks; the app then says "
              "no parks match"),
    Case("h11", "Have there been rockfall incidents in parks outside Utah?", ("retrieval",),
         {"park_codes": [], "states": [], "exclude_park_codes": [], "exclude_states": ["UT"]},
         advice=False),
    Case("h12", "Bear incidents in Montana parks other than Glacier", ("retrieval",),
         {"states": ["MT"], "exclude_park_codes": ["GLAC"], "exclude_states": []}),
    Case("h13", "Which hikes in Zion have no flash flood risk?", ("retrieval",),
         {"park_codes": ["ZION"], "exclude_park_codes": [], "exclude_states": []},
         note="a hazard to avoid, not a place: excludes nothing"),
]


def load_cases():
    cases = []
    for q in json.loads(QUESTIONS_PATH.read_text(encoding="utf-8")):
        expected = q["expected_label"] or "retrieval"
        note = q["stresses"] if q["expected_label"] else (
            q["stresses"] + " (no expected_label; borderline policy says retrieval)")
        cases.append(Case(q["id"], q["question"], (expected,),
                          QUESTION_FILTERS.get(q["id"], {}), note))
    return cases + EXTRA_CASES


def wrong_fields(result, case):
    """Descriptions of the checked fields (filters and asks_for_advice) that don't match;
    lists compare as sets."""
    wrong = []
    if case.advice is not None and result.asks_for_advice != case.advice:
        wrong.append(f"asks_for_advice {result.asks_for_advice!r}, expected {case.advice!r}")
    for name, expected in case.filters.items():
        actual = getattr(result, name)
        if isinstance(expected, list):
            ok = sorted(actual or []) == sorted(expected)
        else:
            ok = actual == expected
        if not ok:
            wrong.append(f"{name} {actual!r}, expected {expected!r}")
    return wrong


def describe(result):
    """The label, asks_for_advice when true, and every non-empty filter field."""
    parts = [result.label.value]
    if result.asks_for_advice:
        parts.append("asks_for_advice=True")
    for name in FILTER_FIELDS:
        value = getattr(result, name)
        if value:
            parts.append(f"{name}={value}")
    return ", ".join(parts)


def main():
    now = datetime.now()
    cases = load_cases()
    labels = [f"{i}. {model} (effort: {effort})" for i, (model, effort) in enumerate(CONFIGS, 1)]
    stats = {label: {"label_ok": 0, "filters_ok": 0, "filters_checked": 0, "errors": 0,
                     "seconds": []} for label in labels}
    rows = []  # (case, {label: (result or None, error, seconds, label_ok, wrong)})

    for case in cases:
        print(f"{case.id}: {case.question}")
        outcomes = {}
        for (model, effort), label in zip(CONFIGS, labels):
            start = time.perf_counter()
            try:
                result, error = route_query(case.question, model=model, effort=effort), None
            except Exception as exc:  # keep going; one failed call shouldn't end the run
                result, error = None, f"{type(exc).__name__}: {exc}"
            seconds = time.perf_counter() - start
            s = stats[label]
            s["seconds"].append(seconds)
            if result is None:
                s["errors"] += 1
                outcomes[label] = (None, error or "no parsed output", seconds, False, [])
                continue
            label_ok = result.label.value in case.labels
            wrong = wrong_fields(result, case)
            s["label_ok"] += label_ok
            if case.filters or case.advice is not None:
                s["filters_checked"] += 1
                s["filters_ok"] += not wrong
            outcomes[label] = (result, None, seconds, label_ok, wrong)
        rows.append((case, outcomes))

    out = [f"# Router check {now:%Y-%m-%d %H:%M}", "", f"Configs: {', '.join(labels)}", "",
           "## Summary", ""]
    for label, s in stats.items():
        summary = (f"{label}: labels {s['label_ok']}/{len(cases)} right, filters/advice "
                   f"{s['filters_ok']}/{s['filters_checked']} right, {s['errors']} errors, "
                   f"avg {sum(s['seconds']) / len(s['seconds']):.1f}s, "
                   f"max {max(s['seconds']):.1f}s")
        out.append(f"- {summary}")
        print(summary)

    out += ["", "## Cases where any config is wrong", "",
            "| Case | Question | Expected | " + " | ".join(labels) + " |",
            "|---|---|---|" + "---|" * len(labels)]
    for case, outcomes in rows:
        if all(o[3] and not o[4] for o in outcomes.values()):
            continue
        cells = []
        for result, error, _, label_ok, wrong in outcomes.values():
            if result is None:
                cells.append("ERROR")
            else:
                mark = "✓" if label_ok else "✗"
                cells.append(f"{mark} {result.label.value}" + (" (fields ✗)" if wrong else ""))
        question = case.question.replace("|", "/")
        out.append(f"| {case.id} | {question} | {' / '.join(case.labels)} | "
                   + " | ".join(cells) + " |")

    out += ["", "## All cases", ""]
    for case, outcomes in rows:
        out += [f"### {case.id}: {case.question}", "",
                f"**Expected:** {' or '.join(case.labels)}"
                + (f"; {case.filters}" if case.filters else "")
                + (f"; asks_for_advice={case.advice}" if case.advice is not None else "")]
        if case.note:
            out.append(f"*{case.note}*")
        out.append("")
        for label, (result, error, seconds, label_ok, wrong) in outcomes.items():
            if result is None:
                out.append(f"- **{label}** ({seconds:.1f}s): ERROR - {error}")
                continue
            mark = "✓" if label_ok and not wrong else "✗"
            out.append(f"- **{label}** ({seconds:.1f}s): {mark} {describe(result)}")
            for problem in wrong:
                out.append(f"  - wrong field: {problem}")
            if result.clarifying_question:
                out.append(f"  - clarifying question: {result.clarifying_question}")
            out.append(f"  - reason: {result.reason}")
        out.append("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"router_check_{now:%Y%m%d_%H%M%S}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"saved {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
