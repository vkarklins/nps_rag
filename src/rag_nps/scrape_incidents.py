#!/usr/bin/env python3
"""
Scrape NPS incident reports for the 63 U.S. National Parks from npshistory.com.

Source: https://npshistory.com/morningreport/  (Incidents -> "View Incidents By Park")

Each park has ONE page (e.g. .../incidents/cave.htm) holding every incident
report extracted from the NPS Morning Reports / Coalition Reports, oldest first.
This script:

  1. Reads the park dropdown on the index page and keeps only the National Parks.
  2. Downloads each park's incident page (politely, cached on disk).
  3. Splits each page into individual incidents and writes them as JSON Lines,
     ready for the chunking / embedding step.

Outputs (under --out-dir, default <project root>/data):
  raw/<page>.htm     raw HTML exactly as downloaded (so re-parsing never needs the network)
  incidents.jsonl    one incident per line
  parks.json         manifest: one entry per downloaded page, plus a run summary

Usage (from the project root):
  poetry add requests beautifulsoup4          # one-time
  poetry run python -m rag_nps.scrape_incidents                 # full run (~2 min at the default delay)
  poetry run python -m rag_nps.scrape_incidents --only cave,yell
  poetry run python -m rag_nps.scrape_incidents --parse-only    # re-parse cached HTML, no network
  poetry run python -m rag_nps.scrape_incidents --refresh       # ignore the cache and re-download
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

INDEX_URL = "https://npshistory.com/morningreport/"
USER_AGENT = "rag-nps-learning-project/0.1 (personal, non-commercial learning project)"
EXPECTED_PARKS = 63
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "data"  # <project root>/data

log = logging.getLogger("nps-scraper")

# --------------------------------------------------------------------------- #
# 1. Choosing the parks
# --------------------------------------------------------------------------- #

# Dropdown labels look like "Acadia NP (ACAD)" or "Denali NP & Pres (DENA)".
# This matches the plain "NP" and "NP & Pres" units and deliberately NOT
# "NPres" (national preserve), "NHP", "NMP", "NM", "NRA", etc.
NP_LABEL_RE = re.compile(r"\bNP(?: & Pres)?\s*\((?P<code>[A-Z0-9]+)\)\s*$")

# Two of the 63 national parks are not labelled "NP" in the dropdown:
#   "Redwood N & SP (REDW)"                    -> Redwood National Park
#   "National Park of American Samoa (NPSA)"   -> National Park of American Samoa
EXTRA_PARK_CODES = {"REDW", "NPSA"}
LABEL_CODE_RE = re.compile(r"\((?P<code>[A-Z0-9]+)\)\s*$")


def select_parks(index_html: str, index_url: str = INDEX_URL) -> list[dict]:
    """Return [{'name', 'code', 'url', 'page'}] for every National Park option."""
    soup = BeautifulSoup(index_html, "html.parser")
    select = soup.find("select", attrs={"name": "gourl"})
    if select is None:
        raise RuntimeError("Could not find the park dropdown <select name='gourl'> on the index page")

    parks = []
    for opt in select.find_all("option"):
        label = " ".join(opt.get_text().split())
        value = (opt.get("value") or "").strip()
        if not value or value == "#":
            continue
        m = NP_LABEL_RE.search(label)
        code = m.group("code") if m else None
        if code is None:
            m2 = LABEL_CODE_RE.search(label)
            if m2 and m2.group("code") in EXTRA_PARK_CODES:
                code = m2.group("code")
        if code is None:
            continue
        url = urljoin(index_url, value)
        parks.append({"name": label, "code": code, "url": url, "page": Path(url).stem})
    return parks


def group_by_page(parks: list[dict]) -> dict[str, dict]:
    """
    Group parks by the page they live on. Sequoia and Kings Canyon share one page (seki.htm)
    and one unit code (SEKI), so 63 parks -> 62 pages. Every page gets a single park_code;
    `dropdown_labels` keeps each dropdown entry that pointed at the page, so the manifest
    still shows that both Sequoia and Kings Canyon were selected.
    """
    pages: dict[str, dict] = {}
    for p in parks:
        entry = pages.setdefault(p["page"], {"page": p["page"], "url": p["url"], "park_code": p["code"],
                                             "dropdown_labels": []})
        if entry["park_code"] != p["code"]:
            log.warning("Page %s is used by parks with different codes (%s vs %s); keeping %s",
                        p["page"], entry["park_code"], p["code"], entry["park_code"])
        entry["dropdown_labels"].append(p["name"])
    return pages


TITLE_PREFIX_RE = re.compile(r"^\s*NPS Incident Reports\s*-\s*", re.I)


def park_name_from_title(title: str) -> str:
    """
    '<title>NPS Incident Reports - Carlsbad Caverns National Park</title>' -> 'Carlsbad Caverns National Park'.
    A few pages cover several units ('North Cascades National Park / Lake Chelan National Recreation
    Area / Ross Lake National Recreation Area'); we keep the first, which is the park.
    """
    name = unescape(TITLE_PREFIX_RE.sub("", title))
    return " ".join(name.split(" / ")[0].split())


# --------------------------------------------------------------------------- #
# 2. Downloading (polite + cached)
# --------------------------------------------------------------------------- #


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=4,
        backoff_factor=2.0,  # 0s, 4s, 8s, 16s ...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def decode_html(raw: bytes) -> str:
    """The site sends no charset. Pages are ASCII/UTF-8 today; fall back to cp1252 for old content."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def fetch_cached(session: requests.Session, url: str, cache_path: Path, *, refresh: bool,
                 parse_only: bool, delay: float) -> tuple[bytes, bool]:
    """Return (raw_bytes, downloaded_now)."""
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes(), False
    if parse_only:
        raise FileNotFoundError(f"--parse-only but {cache_path} is not cached")
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    time.sleep(delay)  # only sleep after real network requests
    return resp.content, True


# --------------------------------------------------------------------------- #
# 3. Parsing a park page into incidents
# --------------------------------------------------------------------------- #
#
# Page layout (all pages use the same template):
#
#   ...<b>INCIDENTS</b><hr></td></tr>
#   <tr><td ...>
#   <p>Monday, June 23, 1986<br>              <- first incident: header <p> has NO leading <br>
#   Carlsbad Cavern - Flash Flood</p>
#   <p>body paragraph ...</p>
#   <p><br>Friday, September 14, 1990<br>     <- later incidents: header <p> starts with <br>
#   90-307 - Carlsbad Caverns (NM) - Successful Rescue</p>
#   <p>body paragraph ...</p>
#   ...
#
# Real-world messiness handled here (found by surveying all 62 pages):
#   * ~140 mid-page headers have no leading <br> (e.g. "<p>July 13, 2022<br>...")
#   * some header lines are separated by a newline instead of <br>
#   * date typos: "19B9", "May 18. 1998", "October 28 , 1991"
#   * date suffixes: "- MEMORIAL DAY", "(Delayed)", "- REVISED", "<b>April 15, 2026</b>"
#   * headers with 3-4 lines (two dates, or two parks) and, rarely, body text inside the header <p>
#   * bodies containing <ul>/<li>, <blockquote>, <table>, links

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
_MONTH_ALT = "|".join(MONTHS)
_WEEKDAY = r"(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,\s+)?"
# Lenient: tolerates "May 18. 1998", "October 28 , 1991" and a garbled year like "19B9".
DATE_LOOSE = _WEEKDAY + rf"(?:{_MONTH_ALT})\s+\d{{1,2}}\s*[.,]\s*\d[\dA-Za-z]{{3}}"
DATE_LOOSE_RE = re.compile(DATE_LOOSE, re.I)
DATE_PARTS_RE = re.compile(rf"(?P<month>{_MONTH_ALT})\s+(?P<day>\d{{1,2}})\s*[.,]\s*(?P<year>\d{{4}})", re.I)

# A new incident starts at a <p> that is either
#   (a) led by <br>                    : <p><br>Friday, September 14, 1990<br>...
#   (b) a bare date line + line break  : <p>July 13, 2022<br>...   (optionally <b>-wrapped, with a
#                                        short suffix such as "(Delayed)" or "- REVISED")
HEADER_START_RE = re.compile(
    r"<p>\s*<br\s*/?>"
    r"|"
    r"<p>\s*(?:<b>)?\s*" + DATE_LOOSE + r"(?:\s*\([^)<\n]{1,40}\)|\s+-\s+[^<\n]{1,40})?\s*(?:</b>)?\s*(?:<br\s*/?>|\n)",
    re.I,
)

INCIDENT_NO_RE = re.compile(r"(?<![\d-])(\d{2}-\d{1,4})\s+-\s")

_BR, _PARA = "", ""  # private-use markers that survive whitespace collapsing


def _fix_c1(text: str) -> str:
    """&#151; and friends decode to C1 control chars; map them the way browsers do (cp1252)."""
    return "".join(ch.encode("latin-1").decode("cp1252", errors="replace") if "\x80" <= ch <= "\x9f" else ch
                   for ch in text)


def html_to_text(fragment: str) -> str:
    """HTML fragment -> readable plain text. <br> -> newline, block elements -> blank line."""
    soup = BeautifulSoup(fragment, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with(_BR)
    for tag in soup.find_all(["p", "ul", "ol", "blockquote", "table", "div"]):
        tag.insert_before(_PARA)
        tag.insert_after(_PARA)
    for li in soup.find_all("li"):
        li.insert_before(_PARA + "- ")
        li.insert_after(_PARA)
    for row in soup.find_all("tr"):  # table rows become lines, cells are separated by " | "
        row.insert_after(_BR)
    for cell in soup.find_all(["td", "th"]):
        cell.insert_after(" | ")
    text = _fix_c1(soup.get_text())
    text = re.sub(r"[ \t\r\n\f\v ]+", " ", text)  # source is hard-wrapped; collapse it
    text = text.replace(_BR, "\n").replace(_PARA, "\n\n")
    lines = [re.sub(r"(?:\s*\|)+\s*$", "", ln).strip() for ln in text.split("\n")]  # dangling table pipes
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def content_region(page_html: str) -> str:
    """Return the HTML after the '<b>INCIDENTS</b>' banner, minus the closing page tables."""
    marker = page_html.find("<b>INCIDENTS</b>")
    if marker < 0:
        raise ValueError("no <b>INCIDENTS</b> marker found")
    banner_end = page_html.find("</td>", marker)
    td_open = re.compile(r"<td[^>]*>", re.I).search(page_html, banner_end)
    if td_open is None:
        raise ValueError("could not find the incidents <td>")
    content = page_html[td_open.end():]
    content = re.sub(r"\s*</td>\s*</tr>\s*</table>\s*</td>\s*</tr>\s*</table>\s*</body>\s*</html>\s*$",
                     "", content, flags=re.I)
    return content


def split_incidents(content: str) -> list[str]:
    """Cut the content region into one HTML chunk per incident."""
    starts = [m.start() for m in HEADER_START_RE.finditer(content)]
    if not starts:
        return []
    chunks = [content[a:b] for a, b in zip(starts, starts[1:] + [len(content)])]
    leading = content[:starts[0]]
    if leading.strip():  # anything before the first header we recognised: keep, don't lose it silently
        log.warning("  %d chars of content before the first recognised header (kept as its own chunk)",
                    len(leading.strip()))
        chunks.insert(0, leading)
    return chunks


def parse_incident(chunk: str) -> dict:
    """One incident chunk -> structured fields (header p = first <p>...</p>, rest = body)."""
    m = re.match(r"\s*<p>(.*?)</p>", chunk, re.S | re.I)
    if m:
        header_html, rest_html = m.group(1), chunk[m.end():]
    else:  # malformed: treat the whole chunk as body
        header_html, rest_html = "", chunk

    header_text = html_to_text(header_html)
    lines = [ln.strip() for ln in header_text.split("\n") if ln.strip()]

    # If the date line is glued to what follows (newline instead of <br>), split it off.
    date_raw = None
    if lines:
        dm = re.match(r"\s*" + DATE_LOOSE, lines[0], re.I)
        if dm:
            date_raw = dm.group(0).strip()
            remainder = lines[0][dm.end():].strip(" -–—")
            lines = [lines[0][:dm.end()].strip()] + ([remainder] if remainder else []) + lines[1:]
        else:
            date_raw = lines[0]  # unparseable header line 1: keep raw

    # A few headers have body text glued inside the header <p>; move very long lines to the body.
    header_lines, spill = [], []
    for i, ln in enumerate(lines):
        if i >= 1 and (len(ln) > 200 or len(header_lines) >= 5):
            spill = lines[i:]
            break
        header_lines.append(ln)

    iso = None
    pm = DATE_PARTS_RE.search(date_raw or "")
    if pm:
        try:
            iso = date(int(pm["year"]), MONTHS.index(pm["month"].capitalize()) + 1, int(pm["day"])).isoformat()
        except ValueError:
            iso = None

    inc_no = None
    nm = INCIDENT_NO_RE.search(" ".join(header_lines))
    if nm:
        inc_no = nm.group(1)

    body_parts = []
    if spill:
        body_parts.append("\n".join(spill))
    rest_text = html_to_text(rest_html)
    if rest_text:
        body_parts.append(rest_text)
    body = "\n\n".join(body_parts)

    return {
        "date_raw": date_raw,
        "date": iso,
        "incident_number": inc_no,
        "header_lines": header_lines,
        "title": header_lines[-1] if len(header_lines) >= 2 else None,
        "body": body,
    }


def parse_page(page_html: str, page: dict) -> list[dict]:
    chunks = split_incidents(content_region(page_html))
    out = []
    for seq, chunk in enumerate(chunks, start=1):
        rec = parse_incident(chunk)
        out.append({
            "incident_id": f"{page['page']}-{seq:05d}",
            "park_code": page["park_code"],
            "park_name": page["park_name"],
            "source_url": page["url"],
            "seq": seq,
            **rec,
        })
    return out


# --------------------------------------------------------------------------- #
# 4. Main
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds to sleep after each download (default 1.5)")
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--parse-only", action="store_true", help="never touch the network; use cached HTML only")
    ap.add_argument("--only", help="comma-separated page codes to process, e.g. cave,yell")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    raw_dir = args.out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()

    # --- index page -> park list
    index_raw, _ = fetch_cached(session, INDEX_URL, raw_dir / "_index.htm",
                                refresh=args.refresh, parse_only=args.parse_only, delay=args.delay)
    parks = select_parks(decode_html(index_raw), INDEX_URL)
    pages = group_by_page(parks)
    log.info("Selected %d national parks on %d distinct pages", len(parks), len(pages))
    if len(parks) != EXPECTED_PARKS:
        log.warning("Expected %d parks but selected %d - the dropdown may have changed. "
                    "Check select_parks()/EXTRA_PARK_CODES.", EXPECTED_PARKS, len(parks))
    shared = {k: v["dropdown_labels"] for k, v in pages.items() if len(v["dropdown_labels"]) > 1}
    if shared:
        log.info("Pages shared by several parks: %s", shared)

    wanted = {s.strip().lower() for s in args.only.split(",")} if args.only else None
    if wanted:
        unknown = wanted - set(pages)
        if unknown:
            log.error("Unknown page codes: %s", sorted(unknown))
            return 2
        pages = {k: v for k, v in pages.items() if k in wanted}

    # --- download + parse
    manifest, all_incidents, failures = [], [], []
    for i, (stem, page) in enumerate(pages.items(), start=1):
        try:
            raw, downloaded = fetch_cached(session, page["url"], raw_dir / f"{stem}.htm",
                                           refresh=args.refresh, parse_only=args.parse_only, delay=args.delay)
            html = decode_html(raw)
            title = (re.search(r"<title>(.*?)</title>", html, re.S | re.I) or [None, ""])[1].strip()
            page = {**page, "park_name": park_name_from_title(title) or page["park_code"]}
            incidents = parse_page(html, page)
        except Exception as exc:  # keep going; report at the end
            log.error("[%d/%d] %s FAILED: %s", i, len(pages), stem, exc)
            failures.append({"page": stem, "error": str(exc)})
            continue

        bad_dates = sum(1 for r in incidents if r["date"] is None)
        log.info("[%d/%d] %-6s %4d incidents%s  (%s)", i, len(pages), stem, len(incidents),
                 f", {bad_dates} unparsed date(s)" if bad_dates else "",
                 "downloaded" if downloaded else "cached")
        all_incidents.extend(incidents)
        manifest.append({
            **page,
            "page_title": title,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "downloaded_this_run": downloaded,
            "n_incidents": len(incidents),
            "n_unparsed_dates": bad_dates,
        })

    # --- write outputs
    inc_path = args.out_dir / "incidents.jsonl"
    with inc_path.open("w", encoding="utf-8") as fh:
        for rec in all_incidents:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_index": INDEX_URL,
        "n_parks_selected": len(parks),
        "n_pages": len(pages),
        "n_incidents": len(all_incidents),
        "n_unparsed_dates": sum(1 for r in all_incidents if r["date"] is None),
        "failures": failures,
    }
    (args.out_dir / "parks.json").write_text(
        json.dumps({"summary": summary, "parks": [p for p in parks], "pages": manifest},
                   indent=2, ensure_ascii=False),
        encoding="utf-8")

    log.info("Done: %d incidents from %d pages -> %s", len(all_incidents), len(manifest), inc_path)
    if failures:
        log.error("%d page(s) failed: %s", len(failures), [f["page"] for f in failures])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
