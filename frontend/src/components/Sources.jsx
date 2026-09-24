import { useState } from "react";
import { formatDate, reportLink, splitTitle } from "../citations.js";

function SourceItem({ msgId, n, incident, highlighted }) {
  const [open, setOpen] = useState(false);
  const { number, title } = splitTitle(incident.title);
  return (
    <li id={`src-${msgId}-${n}`} className={`source ${highlighted ? "flash" : ""}`}>
      <span className="source-n">{n}</span>
      <div className="source-main">
        <a className="source-title" href={reportLink(incident)} target="_blank" rel="noreferrer">
          {title}
          <span className="ext" aria-hidden="true">↗</span>
        </a>
        <div className="source-meta">
          <span>Reported {formatDate(incident.incident_date)}</span>
          {number && <span>Incident {number}</span>}
          <button className="linkish" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
            {open ? "Hide excerpt" : "Read excerpt"}
          </button>
        </div>
        {open && <blockquote className="excerpt">{incident.body}</blockquote>}
      </div>
    </li>
  );
}

/** Cited reports, grouped by park page. */
export default function Sources({ msgId, groups, highlight }) {
  if (!groups.length) return null;
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);
  return (
    <section className="sources" aria-label="Sources">
      <h3>
        Sources <span className="count">{total}</span>
      </h3>
      <div className="source-groups">
        {groups.map((group) => (
          <div className="source-group" key={group.url}>
            <div className="group-head">
              <span className="group-park">{group.parkName}</span>
              <a href={group.url} target="_blank" rel="noreferrer" className="group-link">
                All reports for this park ↗
              </a>
            </div>
            <ol>
              {group.items.map(({ n, incident }) => (
                <SourceItem
                  key={incident.incident_id}
                  msgId={msgId}
                  n={n}
                  incident={incident}
                  highlighted={highlight === n}
                />
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}
