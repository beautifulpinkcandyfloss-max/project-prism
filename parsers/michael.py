"""
Parser for The Michael Teachings (michaelteachings.com transcript pages,
e.g. michael_teachings_transcripts/19-june-1973.html).

One URL = one session, same as the Q'uo/Ra single-page cases. But this
source has two real quirks the others don't:

1. NO speaker labels at all. By transcription convention, Michael's own
   words are rendered in ALL CAPS; the questioner's words are normal
   case. There's no "Michael:" or "Q:" prefix anywhere. We don't need to
   split this turn-by-turn for our schema (we store one text blob per
   session either way), so this is really just useful to know if you
   ever want to do turn-level analysis later -- not handled here.

2. Participant names are very often redacted in the original
   transcription itself (shown as "_____"), especially in the earliest
   (1973-78) sessions channeled by the original Yarbro circle. We do NOT
   try to recover these -- they're genuinely not present in the source,
   so leaving participants empty is the honest answer, not a parsing
   failure.

The date is NOT reliably in the page body text -- it's most reliably
read off the URL slug itself, e.g. "19-june-1973.html", "sept-08-1973.html",
"oct-2-1973.html", "april-3-1974.html". Slug formats vary (full month
name vs abbreviation, day-month-year vs month-day-year), so we detect
whichever token in the slug matches a known month name/abbreviation and
work out the other two from there, rather than assuming one fixed order.
"""

import re
from typing import List, Optional
from parsers.base import SessionRecord
from utils import clean_text, normalize_date

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

CHANNELED_BY_RE = re.compile(r'channeled by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.IGNORECASE)


def _slug_from_source(source_file: str) -> str:
    # Works whether source_file is a full URL or a local filename.
    tail = source_file.rstrip("/").split("/")[-1]
    return tail[:-5] if tail.lower().endswith(".html") else tail


def _parse_date_from_slug(slug: str) -> Optional[str]:
    parts = re.split(r'[-_]', slug.lower())
    month = day = year = None
    for i, part in enumerate(parts):
        if part in MONTHS:
            month = MONTHS[part]
            for other in parts[:i] + parts[i + 1:]:
                if other.isdigit():
                    if len(other) == 4:
                        year = int(other)
                    else:
                        day = int(other)
            break
    if month and day and year:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def parse(raw_text: str, source_file: str) -> List[SessionRecord]:
    cleaned = clean_text(raw_text)
    if not cleaned.strip():
        return []

    slug = _slug_from_source(source_file)
    date = _parse_date_from_slug(slug)

    channeler_match = CHANNELED_BY_RE.search(raw_text[:2000])
    channeler = channeler_match.group(1) if channeler_match else None

    session_uid = f"michael_{date}" if date else f"michael_{slug}"

    return [SessionRecord(
        source="michael",
        session_uid=session_uid,
        text=cleaned,
        channeler=channeler,
        entity="Michael",
        date=date or "",
        participants=[channeler] if channeler else [],
        source_file=source_file,
    )]
