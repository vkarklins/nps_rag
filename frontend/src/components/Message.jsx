import { useMemo, useState } from "react";
import { groupSources, parseAnswer } from "../citations.js";
import Sources from "./Sources.jsx";

// Same wording as cli.py.
const PARTIAL_RESULTS_FOOTER =
  "This answer is based on the reports that best match your question, not every relevant report in the dataset.";
const ADVICE_NOTICE =
  "I can only share what incident reports say, not general safety advice. For guidance before your visit, check the park's website (nps.gov) or ask a ranger.";

const STAGES = {
  condensing: "Reading the conversation",
  routing: "Understanding your question",
  searching: "Searching 12,105 incident reports",
  writing: "Writing the answer",
};

function Thinking({ stage }) {
  return (
    <div className="thinking" role="status">
      <span className="pulse" />
      <span key={stage} className="stage-text">
        {STAGES[stage] || "Working"}
      </span>
      <span className="dots3">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}

/** Renders **bold** inside a text run; everything else is plain text. */
function Rich({ text }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export default function AssistantMessage({ msg }) {
  const [highlight, setHighlight] = useState(null);
  const streaming = !msg.done && !msg.error;

  const { paragraphs, numbers, unknown } = useMemo(
    () => parseAnswer(msg.text, msg.incidents, { streaming }),
    [msg.text, msg.incidents, streaming]
  );
  const groups = useMemo(() => groupSources(numbers, msg.incidents), [numbers, msg.incidents]);

  const jumpTo = (n) => {
    const el = document.getElementById(`src-${msg.id}-${n}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlight(null);
    requestAnimationFrame(() => setHighlight(n));
  };

  const showAdvice = msg.done?.answered && msg.done?.asks_for_advice;
  const showPartial = msg.done?.complete === false;
  const searchedParks = msg.meta?.parks || [];
  const rewritten =
    msg.meta && msg.meta.question.trim() !== msg.meta.raw_question.trim() ? msg.meta.question : null;

  return (
    <article className={`msg assistant ${msg.done && !msg.done.answered ? "decline" : ""}`}>
      {(rewritten || searchedParks.length > 0) && (
        <div className="context-line">
          {rewritten && (
            <span className="chip subtle" title="Your follow-up, rewritten as a standalone question">
              Searched for: “{rewritten}”
            </span>
          )}
          {searchedParks.slice(0, 4).map((p) => (
            <span className="chip" key={p.code}>
              {p.name}
            </span>
          ))}
          {searchedParks.length > 4 && <span className="chip">+{searchedParks.length - 4} parks</span>}
        </div>
      )}

      {paragraphs.length === 0 && streaming && <Thinking stage={msg.stage} />}

      <div className={`answer ${streaming ? "streaming" : ""}`}>
        {paragraphs.map((segments, pi) => (
          <p key={pi}>
            {segments.map((seg, si) => {
              if (seg.type === "text") return <Rich key={si} text={seg.text} />;
              if (seg.type === "cite")
                return (
                  <button
                    key={si}
                    className="cite"
                    onClick={() => jumpTo(seg.n)}
                    title={`Source ${seg.n}`}
                    aria-label={`Source ${seg.n}`}
                  >
                    {seg.n}
                  </button>
                );
              return (
                <sup key={si} className="cite unknown" title={`${seg.id} was not among the retrieved reports`}>
                  ?
                </sup>
              );
            })}
            {streaming && pi === paragraphs.length - 1 && <span className="caret" />}
          </p>
        ))}
      </div>

      {msg.error && <p className="error">{msg.error}</p>}

      {(showAdvice || showPartial || unknown.size > 0) && (
        <aside className="footnotes">
          {showAdvice && (
            <p>
              <span className="fn-mark">†</span>
              {ADVICE_NOTICE}
            </p>
          )}
          {showPartial && (
            <p>
              <span className="fn-mark">*</span>
              {PARTIAL_RESULTS_FOOTER}
            </p>
          )}
          {msg.done && unknown.size > 0 && (
            <p>
              <span className="fn-mark">?</span>
              Cited report ID(s) not in the retrieved set: {[...unknown].join(", ")}
            </p>
          )}
        </aside>
      )}

      <Sources msgId={msg.id} groups={groups} highlight={highlight} />
    </article>
  );
}
