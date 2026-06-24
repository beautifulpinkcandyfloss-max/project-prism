"""
Parser for The Law of One / The Ra Material (channeled by Carla Rueckert,
questioned by Don Elkins, recorded by Jim McCarty).

Handles TWO different raw-text shapes you're likely to scrape:

1. SINGLE-PAGE STYLE (llresearch.org/channeling/ra-contact/<n>) -- one URL
   = one whole session. The page's <title> tag ("The Ra Contact: Session
   101 - L/L Research") ends up as the very first line of the fetched
   text (readers.read_url_html() walks the whole document, head included),
   so we look for "Session <n>" near the TOP of the text and -- if found
   with no other session headers anywhere in the body -- treat the ENTIRE
   text as that one session.

2. BOOK-DUMP STYLE (a PDF/txt of a whole Law of One volume) -- many
   sessions concatenated, each announced by a header line like:
       SESSION 57
   sitting alone (all caps, just the word and number, sometimes with a
   date on the same or next line for session 1 specifically). We split on
   these the same way seth.py splits on "SESSION <n>".

Participants are constant across all 106 sessions (Don Elkins as
questioner, Carla Rueckert as instrument/channel, Jim McCarty as scribe),
so they're safe to hardcode as defaults.
"""

import re
from typing import List
from parsers.base import SessionRecord
from utils import clean_text_preserve_lines, clean_text, normalize_date

# Book-dump style: "SESSION 57" alone on its own line.
BOOK_HEADER_RE = re.compile(r'^SESSION\s+(\d+)\b[^\n]*$', re.MULTILINE | re.IGNORECASE)

# Single-page style: page title containing "Session <n>" near the top of
# the fetched text, e.g. "The Ra Contact: Session 101 - L/L Research".
TITLE_RE = re.compile(r'\bSession\s+(\d+)\b', re.IGNORECASE)

DATE_RE = re.compile(
    r'(January|February|March|April|May|June|July|August|September|October|'
    r'November|December)\s+\d{1,2},\s*\d{4}',
    re.IGNORECASE
)

DEFAULT_PARTICIPANTS = ["Don Elkins", "Carla Rueckert", "Jim McCarty"]


def _build_record(session_number: str, text: str, raw_date: str, source_file: str) -> SessionRecord:
    iso_date = normalize_date(raw_date) if raw_date else ""
    return SessionRecord(
        source="ra",
        session_uid=f"ra_{session_number.zfill(3)}",
        text=clean_text(text),
        channeler="Carla Rueckert",
        entity="Ra",
        session_number=session_number,
        date=iso_date or raw_date,
        participants=list(DEFAULT_PARTICIPANTS),
        source_file=source_file,
    )


def parse(raw_text: str, source_file: str) -> List[SessionRecord]:
    preserved = clean_text_preserve_lines(raw_text)
    if not preserved.strip():
        return []

    headers = list(BOOK_HEADER_RE.finditer(preserved))

    # --- Case 1: book-dump style, multiple sessions in one file ---
    if headers:
        records = []
        for i, match in enumerate(headers):
            session_number = match.group(1)
            start = match.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(preserved)
            block = preserved[start:end]
            date_match = DATE_RE.search(block[:400])  # date usually near the header
            raw_date = date_match.group(0) if date_match else ""
            records.append(_build_record(session_number, block, raw_date, source_file))
        return records

    # --- Case 2: single-page style, whole text is one session ---
    title_match = TITLE_RE.search(preserved[:300])
    if title_match:
        session_number = title_match.group(1)
        date_match = DATE_RE.search(preserved[:1000])
        raw_date = date_match.group(0) if date_match else ""
        return [_build_record(session_number, preserved, raw_date, source_file)]

    # --- Fallback: no recognizable structure at all ---
    return [SessionRecord(
        source="ra",
        session_uid=f"ra_unstructured_{abs(hash(source_file)) % 100000}",
        text=clean_text(preserved),
        channeler="Carla Rueckert",
        entity="Ra",
        participants=list(DEFAULT_PARTICIPANTS),
        source_file=source_file,
    )]
