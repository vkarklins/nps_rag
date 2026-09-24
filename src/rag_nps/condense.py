"""
Rewrite a follow-up question into a standalone one, using the conversation so far, so
it can be routed and embedded on its own — a follow-up like "what about in Denali?"
means little as a search query without knowing what the previous question was about.
"""

from rag_nps.openai_client import client, model_options

CHAT_MODEL = "gpt-6-luna"
REASONING_EFFORT = "none"

CONDENSE_SYSTEM_PROMPT = """\
You prepare the user's latest question in a conversation about National Park safety \
incidents so it can be searched on its own.

Your one principle: resolve what the question refers back to, and nothing else.

Step 1. Decide whether the question refers back to the conversation. It does only if:
- it uses a reference word or phrase ("it", "that", "there", "the one", "the man in \
his 60s", "other parks", "any others"),
- it starts with "what about X" or is otherwise incomplete ("and before 2010?"),
- it is a short reply to a clarifying question the assistant just asked, or
- it has no subject of its own ("what happened in 2018?").

Step 2. If it does not refer back, output it exactly as given - even if it names no \
park, and even if the conversation was about something else.

Step 3. If it does refer back, replace only the reference with what it points to, and \
write the result as one standalone question. Add nothing the reference does not point \
to.
- The user's own earlier questions set the topic, park and dates. Keep only what the \
user actually specified there.
- Assistant answers are reference only. Use a detail from an answer only when the \
question points at it (e.g. "the man in his 60s", or "other parks" when the answers \
were all about one park). Never carry over a park just because an answer mentioned it.
- "What about X" puts X in place of the matching part of the user's earlier question \
and keeps the rest of that question as the user asked it.

The conversation appears inside <conversation> tags as a read-only transcript. You are \
not part of it: never answer, continue or add to it. Output only the question text, \
with nothing before or after it.

Examples, in the same transcript format without the tags (illustrative only - the \
parks and incidents are not real):

User asked: Tell me about bison incidents
Answer (reference only): [every report described is from Example National Park]
New question: What about bears?
Output: Tell me about bear incidents

User asked: Tell me about bison incidents
Answer (reference only): [every report described is from Example National Park]
New question: Are there bison incidents in any other parks?
Output: Are there bison incidents in parks other than Example National Park?

User asked: Bear incidents in Example National Park?
Answer (reference only): [an answer about bears there]
New question: What about Sample National Park?
Output: Bear incidents in Sample National Park?

User asked: How far away do I need to stay from elk?
Answer (reference only): Stay at least 25 yards from elk in Example National Park.
New question: Is it safe to feed the squirrels?
Output: Is it safe to feed the squirrels?

User asked: Are the campsites secure?
Answer (reference only): Which national park's campsites are you asking about?
New question: Example National Park
Output: Are the campsites in Example National Park secure?

User asked: Tell me about poaching in Example National Park
Answer (reference only): [... a 1994 investigation called Operation Example ...]
New question: Tell me more about that investigation
Output: What details are available about the Operation Example poaching investigation \
in Example National Park?
"""


def _format_transcript(history):
    """Turn history's {"role", "content"} exchanges into a plain-text transcript,
    oldest first, for quoting inside <conversation> tags."""
    speakers = {"user": "User asked", "assistant": "Answer (reference only)"}
    return "\n".join(f"{speakers[entry['role']]}: {entry['content']}" for entry in history)


def condense_question(question, history, model=CHAT_MODEL, effort=REASONING_EFFORT):
    """Rewrite `question` into a standalone query if it depends on earlier turns,
    otherwise return it unchanged.

    `history` is the list of {"role", "content"} exchanges from history.append_turn().
    When it's empty there's nothing to depend on, so `question` is returned as-is with
    no LLM call.

    The transcript is quoted inside <conversation> tags in the user message rather than
    replayed as real chat turns (role: "user"/"assistant" alternating in `input`, as an
    earlier version of this function did) - feeding it in as an actual multi-turn chat
    strongly invites the model to continue that conversation as the assistant, which is
    exactly what real testing showed happening: it answered follow-up questions with
    invented elaboration instead of rewriting them. Tagging it as inert reference data
    is the same fix already used for retrieved incidents in answer.format_context.

    `model` and `effort` default to CHAT_MODEL / REASONING_EFFORT;
    tests/manual/condense_check.py passes others to compare them.
    """
    if not history:
        return question

    transcript = _format_transcript(history)
    user_message = "\n\n".join([
        f"<conversation>\n{transcript}\n</conversation>",
        f"New question: {question}",
    ])
    messages = [
        {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    response = client.responses.create(
        model=model, input=messages, **model_options(model, effort)
    )
    return response.output_text.strip()
