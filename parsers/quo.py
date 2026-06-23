"""
Parser for L/L Research's "Conscious Channeling" archive
(https://www.llresearch.org/channeling/transcripts).

IMPORTANT: despite the folder being named "quo", this archive is NOT
exclusively Q'uo. It includes Hatonn, Latwii, and others -- L/L Research
channels several different Confederation entities in this conscious
(non-trance) format, and which one shows up varies session to session.
So rather than hardcoding entity="Q'uo", we DETECT which entity actually
spoke by searching for self-identifying phrases that are a structural
constant across all of them, regardless of which one it is:
    "I am Q'uo..."
    "We are those of Q'uo..."
    "We are the principle known to you as Q'uo..."
Whichever name appears most often via these self-identification patterns
is the entity for that session.

One URL = one whole session (e.g.
https://www.llresearch.org/channeling/2026/0517). The page's <title> tag
("May 17, 2026 - Homecoming Gathering Meditation - L/L Research") becomes
the first line of the fetched text via readers.read_url_html(), and is
the most reliable place to pull the date from.

Multiple different L/L Research members serve as the channel/instrument
across a single session (it rotates -- "(Jim channeling)", "(Austin
channeling)", etc.), so we collect ALL of them rather than assuming one
fixed channeler the way ra.py and seth.py can.
"""

import re
from collections import Counter
from typing import List
from parsers.base import SessionRecord
from utils import clean_text_preserve_lines, clean_text, normalize_date

TITLE_DATE_RE = re.compile(
    r'^([A-Za-z]+ \d{1,2},\s*\d{4})\s*-\s*L/L Research',
    re.IGNORECASE
)
# Sometimes there's a subtitle between the date and the site name:
# "May 17, 2026 - Homecoming Gathering Meditation - L/L Research"
TITLE_DATE_SUBTITLE_RE = re.compile(
    r'^([A-Za-z]+ \d{1,2},\s*\d{4})\s*-\s*.+?\s*-\s*L/L Research',
    re.IGNORECASE
)

SELF_ID_RE = re.compile(
    r"(?:I am|We are(?: those of| the principle known to you as)?)\s+"
    r"([A-Z][A-Za-z']{1,20})\b[,.\s]",
)

INSTRUMENT_RE = re.compile(r"\(([A-Za-z]+)\s+channeling\)", re.IGNORECASE)


def _extract_date(preserved: str) -> str:
    head = preserved[:300]
    match = TITLE_DATE_SUBTITLE_RE.search(head) or TITLE_DATE_RE.search(head)
    if match:
        return normalize_date(match.group(1))
    return ""


def _extract_entity(text: str) -> str:
    matches = SELF_ID_RE.findall(text)
    # Filter out common false positives the regex pattern might catch
    # (e.g. "I am aware", "We are amazed") by requiring the captured word
    # to look like a name rather than a common adjective/verb.
    blocklist = {"aware", "amazed", "honored", "grateful", "here", "with",
                 "now", "also", "very", "not", "so", "this", "those"}
    candidates = [m for m in matches if m.lower() not in blocklist]
    if not candidates:
        return "Q'uo"  # safest default for this archive if detection fails
    counts = Counter(candidates)
    return counts.most_common(1)[0][0]


def _extract_channelers(text: str) -> List[str]:
    names = INSTRUMENT_RE.findall(text)
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    return seen


def parse(raw_text: str, source_file: str) -> List[SessionRecord]:
    preserved = clean_text_preserve_lines(raw_text)
    if not preserved.strip():
        return []

    date = _extract_date(preserved)
    entity = _extract_entity(preserved)
    channelers = _extract_channelers(preserved)

    # session_uid: date-based, since this archive isn't sequentially
    # numbered the way Ra is. scraper.py's dedupe_session_uid() handles
    # the rare case of two different sessions sharing a date.
    uid_date = date or "undated"
    session_uid = f"quo_{uid_date}"

    return [SessionRecord(
        source="quo",
        session_uid=session_uid,
        text=clean_text(preserved),
        channeler=", ".join(channelers) if channelers else None,
        entity=entity,
        date=date,
        participants=channelers,
        source_file=source_file,
    )]
