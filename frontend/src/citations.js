// Turn streamed answer text with [incident_id] citations into display segments with
// sequential [N] numbers (same numbering rule as cli.convert_citations: order of first
// appearance). Runs on the whole text-so-far on every update, so a citation that is only
// half-received ("... [yose-00") is simply held back until its "]" arrives.

// One or more IDs in one bracket, e.g. [yose-00571] or [yose-00571, yose-00580].
const CITATION_RE = /\[([a-z]+-\d+(?:\s*,\s*[a-z]+-\d+)*)\]/g;
// A trailing "[" that could still become a citation.
const PARTIAL_RE = /\[[a-z0-9,\s-]*$/;

/**
 * Returns { paragraphs, numbers, unknown }:
 *   paragraphs  array of paragraphs; each is an array of segments
 *               { type: "text", text } | { type: "cite", id, n } | { type: "unknown", id }
 *   numbers     Map incident_id -> n, in citation order
 *   unknown     Set of cited ids that were not in the retrieved reports
 */
export function parseAnswer(text, incidentsById, { streaming = false } = {}) {
  let body = text;
  if (streaming) body = body.replace(PARTIAL_RE, "");

  const numbers = new Map();
  const unknown = new Set();

  const paragraphs = body
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((paragraph) => {
      const segments = [];
      let last = 0;
      for (const match of paragraph.matchAll(CITATION_RE)) {
        if (match.index > last) {
          segments.push({ type: "text", text: paragraph.slice(last, match.index) });
        }
        for (const id of match[1].split(/\s*,\s*/)) {
          if (!incidentsById.has(id)) {
            unknown.add(id);
            segments.push({ type: "unknown", id });
            continue;
          }
          if (!numbers.has(id)) numbers.set(id, numbers.size + 1);
          segments.push({ type: "cite", id, n: numbers.get(id) });
        }
        last = match.index + match[0].length;
      }
      if (last < paragraph.length) segments.push({ type: "text", text: paragraph.slice(last) });
      return segments;
    });

  return { paragraphs, numbers, unknown };
}

/** The answer text as the CLI shows it ([N] numbers), for conversation history. */
export function convertedText(text, incidentsById) {
  const { paragraphs } = parseAnswer(text, incidentsById);
  return paragraphs
    .map((segs) =>
      segs
        .map((s) => (s.type === "text" ? s.text : s.type === "cite" ? `[${s.n}]` : "[?]"))
        .join("")
    )
    .join("\n\n");
}

/**
 * Group cited incidents by source page (one page per park), in citation order —
 * the same grouping as cli.build_source_list.
 */
export function groupSources(numbers, incidentsById) {
  const groups = new Map();
  for (const [id, n] of numbers) {
    const incident = incidentsById.get(id);
    const key = incident.source_url;
    if (!groups.has(key)) {
      groups.set(key, {
        url: incident.source_url,
        parkName: incident.park_name,
        parkCode: incident.park_code,
        items: [],
      });
    }
    groups.get(key).items.push({ n, incident });
  }
  return [...groups.values()];
}

/**
 * Link to the report on its park page, using a text fragment (#:~:text=...) so browsers
 * that support it (Chrome, Edge, Safari) scroll to and highlight the report title.
 * Falls back to the plain page elsewhere.
 */
export function reportLink(incident) {
  if (!incident.title) return incident.source_url;
  const encode = (s) => encodeURIComponent(s).replace(/-/g, "%2D").replace(/,/g, "%2C");
  const title = encode(incident.title.trim());
  // Titles with an incident number ("99-53 - ...") are unique on their page. Generic ones
  // ("River fatality") can repeat, so anchor them with the date line printed just before
  // them on the page ("May 1, 1987") as a text-fragment prefix.
  if (splitTitle(incident.title).number || !incident.incident_date) {
    return `${incident.source_url}#:~:text=${title}`;
  }
  const d = new Date(`${incident.incident_date}T00:00:00`);
  const dateLine = d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
  return `${incident.source_url}#:~:text=${encode(dateLine)}-,${title}`;
}

/** "99-53 - Yellowstone - Bear Mauling" -> { number: "99-53", title: "Bear Mauling" }. */
export function splitTitle(title) {
  if (!title) return { number: null, title: "Untitled report" };
  const parts = title.split(" - ");
  if (parts.length >= 3 && /^\d{2,4}-\d+/.test(parts[0])) {
    return { number: parts[0], title: parts.slice(2).join(" - ") };
  }
  return { number: null, title };
}

export function formatDate(iso) {
  if (!iso) return "Undated";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}
