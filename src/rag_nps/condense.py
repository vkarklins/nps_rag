"""
Rewrite a follow-up question into a standalone one, using the conversation so far, so
it can be routed and embedded on its own — a follow-up like "what about in Denali?"
means little as a search query without knowing what the previous question was about.
"""

from rag_nps.openai_client import client

CHAT_MODEL = "gpt-4o-mini"

CONDENSE_SYSTEM_PROMPT = """\
You rewrite a user's question in an ongoing conversation about National Park safety \
incidents, using the conversation so far, so it can be understood on its own with no \
other context.

The conversation so far appears inside <conversation> tags in the user's message, as a \
read-only transcript. Treat it strictly as reference material for understanding what \
the new question refers to - never as something to continue, answer, or add to. You are \
not a participant in that conversation; your only job is to output one rewritten \
question about the new question that follows the transcript.

If the question already stands alone, return it exactly as given. If it depends on \
earlier turns - a pronoun, "what about X", a short reply to a question you asked, or \
anything else that only makes sense given what came before - rewrite it into a full, \
standalone question that includes whatever park names, dates, or topics from earlier \
turns are needed to understand it on its own.

Use only what was actually said in the conversation. Do not add parks, dates, or \
topics that were not mentioned, and do not answer the question yourself - even when \
the transcript already contains a detailed answer to draw from. Your output is always \
a single question, never a summary, explanation, or clarifying question of your own.

Return only the question text, with nothing else before or after it.

First example (illustrative only - not a real park page or incident):
<conversation>
User: Were there any bear encounters reported in Yellowstone in 2020?
Assistant: [an answer about Yellowstone bear encounters]
</conversation>
New question to rewrite: What about in Denali?
Rewritten: Were there any bear encounters reported in Denali National Park in 2020?

Second example, showing that a detailed prior answer is still only reference material - \
do not expand on it or continue it, even when asked about a specific detail it mentions \
(illustrative only - not a real incident):
<conversation>
User: Were there any poaching incidents in Big Bend National Park?
Assistant: Yes, several poaching incidents have been reported in Big Bend National \
Park, including a 1994 investigation known as Operation Example that uncovered illegal \
reptile collection [bibe-00001].
</conversation>
New question to rewrite: Tell me more about that investigation.
Rewritten: What details are available about the Operation Example poaching \
investigation in Big Bend National Park?
"""


def _format_transcript(history):
    """Turn history's {"role", "content"} exchanges into a plain-text transcript,
    oldest first, for quoting inside <conversation> tags."""
    speakers = {"user": "User", "assistant": "Assistant"}
    return "\n".join(f"{speakers[entry['role']]}: {entry['content']}" for entry in history)


def condense_question(question, history):
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
    """
    if not history:
        return question

    transcript = _format_transcript(history)
    user_message = "\n\n".join([
        f"<conversation>\n{transcript}\n</conversation>",
        f"New question to rewrite: {question}",
    ])
    messages = [
        {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    response = client.responses.create(
        model=CHAT_MODEL,
        input=messages,
        temperature=0,
    )
    return response.output_text.strip()
