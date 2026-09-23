"""
Bounded conversation history for the CLI's ask-loop.

append_turn() adds one question/answer exchange and enforces a fixed-size window: only
the most recent MAX_HISTORY entries are kept, oldest dropped first. Only question and
answer text is kept — never retrieved incidents — so history stays small regardless of
how long the conversation runs (see progress-and-next-steps.md, "Revisit later:
multi-part queries and conversational follow-ups", for why incidents are re-retrieved
fresh every turn instead of carried in history).
"""

MAX_HISTORY = 20  # entries, i.e. 10 question/answer exchanges


def append_turn(history, question, answer):
    """Return a new history list with one exchange appended, trimmed to MAX_HISTORY.

    Returns (new_history, trimmed): trimmed is True when this call dropped an older
    exchange to stay within MAX_HISTORY, so the caller can warn the user that earlier
    context is no longer available (every turn this is True, not just the first).
    """
    updated = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    trimmed = len(updated) > MAX_HISTORY
    return updated[-MAX_HISTORY:], trimmed
