import { useEffect, useMemo, useRef, useState } from "react";
import { askStream } from "./api.js";
import { BIOMES, biomeStyle, dominantBiome } from "./biomes.js";
import { convertedText, parseAnswer } from "./citations.js";
import AssistantMessage from "./components/Message.jsx";
import Gallery from "./components/Gallery.jsx";
import Landscape from "./components/Landscape.jsx";

const MAX_HISTORY = 20; // same as history.MAX_HISTORY

const EXAMPLES = [
  "What bear encounters have been reported in Glacier?",
  "Have hikers suffered heat illness in Death Valley?",
  "What falls have happened at the Grand Canyon?",
  "What climbing accidents have happened on Denali?",
  "Any snorkeling or swimming incidents in the Virgin Islands?",
  "What should I know about thermal areas in Yellowstone?",
];

let nextId = 1;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [scene, setScene] = useState({ parks: [], source: "none" });
  const abortRef = useRef(null);
  const scrollRef = useRef(null);
  const stickToBottom = useRef(true);

  const biome = dominantBiome(scene.parks.map((p) => p.code));

  // Keep the newest text in view while streaming, unless the user has scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const onScroll = () => {
    const el = scrollRef.current;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const update = (id, fn) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)));

  async function send(question) {
    question = question.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    stickToBottom.current = true;

    const userMsg = { id: nextId++, role: "user", text: question };
    const botId = nextId++;
    const botMsg = {
      id: botId, role: "assistant", text: "", stage: "routing",
      incidents: new Map(), meta: null, done: null, error: null,
    };
    setMessages((ms) => [...ms, userMsg, botMsg]);

    const controller = new AbortController();
    abortRef.current = controller;
    let text = "";
    let incidents = new Map();
    let finished = false;

    try {
      await askStream({
        question,
        history,
        signal: controller.signal,
        onEvent: (event, data) => {
          switch (event) {
            case "status":
              update(botId, () => ({ stage: data.stage }));
              break;
            case "meta":
              update(botId, () => ({ meta: data }));
              if (data.parks.length) setScene({ parks: data.parks, source: "question", forId: botId });
              break;
            case "sources":
              incidents = new Map(data.incidents.map((i) => [i.incident_id, i]));
              update(botId, () => ({ incidents }));
              break;
            case "delta":
              text += data.text;
              update(botId, () => ({ text }));
              break;
            case "done":
              finished = true;
              update(botId, () => ({ done: data }));
              break;
            case "error":
              update(botId, () => ({ error: data.message }));
              break;
          }
        },
      });
    } catch (err) {
      if (err.name === "AbortError") {
        update(botId, () => ({ done: { answered: false, stopped: true } }));
      } else {
        update(botId, () => ({ error: "Couldn't reach the server. Is the API running?" }));
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }

    if (finished) {
      // Remember the exchange the way the CLI does: the displayed text, with [N] numbers.
      setHistory((h) =>
        [...h, { role: "user", content: question }, { role: "assistant", content: convertedText(text, incidents) }]
          .slice(-MAX_HISTORY)
      );
      // No park named in the question: theme the page after the parks the answer cited.
      setScene((current) => {
        if (current.source === "question" && current.forId === botId) return current;
        const { numbers } = parseAnswer(text, incidents);
        const cited = [];
        for (const id of numbers.keys()) {
          const inc = incidents.get(id);
          if (!cited.some((p) => p.code === inc.park_code)) {
            cited.push({ code: inc.park_code, name: inc.park_name });
          }
        }
        return cited.length ? { parks: cited, source: "cited", forId: botId } : current;
      });
    }
  }

  function reset() {
    abortRef.current?.abort();
    setMessages([]);
    setHistory([]);
    setScene({ parks: [], source: "none" });
  }

  const caption = useMemo(() => {
    if (scene.source === "question") return scene.parks.length === 1 ? "Your park" : "Parks in your question";
    if (scene.source === "cited") return "Parks in these reports";
    return "Park gallery";
  }, [scene]);

  return (
    <div className="app" style={biomeStyle(biome)} data-biome={biome}>
      <Landscape biome={biome} />

      <header className="topbar">
        <div className="brand">
          <svg viewBox="0 0 64 64" className="logo" aria-hidden="true">
            <path d="M6 50 L24 22 L32 33 L41 18 L58 50 Z" />
            <circle cx="47" cy="14" r="5" />
          </svg>
          <div>
            <h1>Trailhead</h1>
            <p className="tagline">Safety questions, answered from National Park Service incident reports</p>
          </div>
        </div>
        <div className="topbar-right">
          <span className="biome-pill" key={biome}>
            {BIOMES[biome].label}
          </span>
          {messages.length > 0 && (
            <button className="ghost" onClick={reset}>
              New conversation
            </button>
          )}
        </div>
      </header>

      <main className="layout">
        <section className="chat">
          <div className="scroll" ref={scrollRef} onScroll={onScroll}>
            {messages.length === 0 ? (
              <div className="welcome">
                <h2>What would you like to know before you go?</h2>
                <p>
                  Ask about accidents, wildlife encounters, rescues and other incidents from 12,105
                  reports across 62 national parks. Answers cite the reports they come from.
                </p>
                <div className="examples">
                  {EXAMPLES.map((q) => (
                    <button key={q} onClick={() => send(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) =>
                m.role === "user" ? (
                  <div className="msg user" key={m.id}>
                    <p>{m.text}</p>
                  </div>
                ) : (
                  <AssistantMessage key={m.id} msg={m} />
                )
              )
            )}
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask about safety incidents in a national park…"
              rows={1}
              aria-label="Your question"
            />
            {busy ? (
              <button type="button" className="send stop" onClick={() => abortRef.current?.abort()}>
                Stop
              </button>
            ) : (
              <button type="submit" className="send" disabled={!input.trim()}>
                Ask
              </button>
            )}
          </form>
        </section>

        <aside className="side">
          <Gallery parks={scene.parks} caption={caption} />
          <div className="about">
            <p>
              Answers are written by an AI model from incident reports retrieved for each question.
              Reports date back to 1986, with a gap from Sept 2015 to Mar 2017.
            </p>
          </div>
        </aside>
      </main>
    </div>
  );
}
