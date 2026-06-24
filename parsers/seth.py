"""
Parser for The Seth Material (Jane Roberts channeling "Seth").

Format observed in the source texts (Seth book transcripts, e.g. "Dreams,
Evolution, and Value Fulfillment"):

    SESSION 898 -- January 30, 1980  9:28 p.m.  WEDNESDAY
    (... session body, often with parenthetical notes from Robert Butts ...)
    NOTE. Session 897 ...

Sessions are announced by a line starting with "SESSION <number>" (all
caps), usually followed by an em-dash/en-dash and a date, then a clock
time and weekday. Everything up to the NEXT "SESSION <number>" header
belongs to that session.

Jane Roberts (channeler) and Robert Butts (her husband, who recorded and
annotated nearly every session) appear in virtually all Seth sessions, so
they're used as sane defaults. Override is_solo/co-host detection only if
you find evidence otherwise in the text.
"""

import re
from typing import List
from parsers.base import SessionRecord
from utils import clean_text_preserve_lines, clean_text, normalize_date

SESSION_HEADER_RE = re.compile(
    r'^SESSION\s+(\d+)\b[^\n]*$',
    re.MULTILINE
)

DATE_RE = re.compile(
    r'(January|February|March|April|May|June|July|August|September|October|'
    r'November|December)\s+\d{1,2},\s*\d{4}',
    re.IGNORECASE
)

DEFAULT_PARTICIPANTS = ["Jane Roberts", "Robert Butts"]


def parse(raw_text: str, source_file: str) -> List[SessionRecord]:
    preserved = clean_text_preserve_lines(raw_text)
    if not preserved.strip():
        return []

    headers = list(SESSION_HEADER_RE.finditer(preserved))

    # Fallback: no recognizable session headers found at all -- return the
    # whole thing as one record rather than silently dropping the text.
    if not headers:
        return [SessionRecord(
            source="seth",
            session_uid=f"seth_unstructured_{abs(hash(source_file)) % 100000}",
            text=clean_text(preserved),
            channeler="Jane Roberts",
            entity="Seth",
            participants=DEFAULT_PARTICIPANTS,
            source_file=source_file,
        )]

    records = []
    for i, match in enumerate(headers):
        session_number = match.group(1)
        start = match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(preserved)
        block = preserved[start:end]

        date_match = DATE_RE.search(block[:300])  # date is near the header line
        raw_date = date_match.group(0) if date_match else ""
        iso_date = normalize_date(raw_date) if raw_date else ""

        participants = list(DEFAULT_PARTICIPANTS)
        # Seth sessions occasionally name a third party (e.g. a visiting
        # friend). Cheap heuristic: look for "and <Name>" near top of block.
        guest_match = re.search(r'\band\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b', block[:500])
        if guest_match and guest_match.group(1) not in participants:
            participants.append(guest_match.group(1))

        records.append(SessionRecord(
            source="seth",
            session_uid=f"seth_{session_number.zfill(4)}",
            text=clean_text(block),
            channeler="Jane Roberts",
            entity="Seth",
            session_number=session_number,
            date=iso_date or raw_date,
            participants=participants,
            source_file=source_file,
        ))

    return records
