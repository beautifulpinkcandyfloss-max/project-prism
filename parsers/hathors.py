"""
Parser for Hathor material -- handles TWO different real shapes:

1. WEBSITE SINGLE-MESSAGE STYLE (tomkenyon.com -- e.g.
   https://tomkenyon.com/destabilization). One URL = one message,
   monologue-style, no questioner. Two signals to pull structure from:

   TITLE: the page's <title> tag follows a consistent breadcrumb format
   that becomes the first line of fetched text, e.g.:
       "Tom Kenyon \u00bb Destabilization"
   Falls back to humanizing the URL slug if that's missing.

   DATE: messages are very often self-cited using the exact pattern
   "channeled through Tom Kenyon, February 7, 2016" -- the most reliable
   signal. Falls back to scanning for any date near the top, and leaves
   date empty (no slug-date fallback exists for this source) if neither
   is found.

2. BOOK/CHAPTER STYLE (a scanned PDF book, e.g. "The Hathor Material" by
   Tom Kenyon & Virginia Essene). Unlike the website messages, this is
   real DIALOGUE -- "Virginia: <question>" / "Hathors: <answer>" -- split
   into numbered chapters, not dated messages. The split point is
   "Chapter <N>", which (because of how the PDF/OCR extraction ran
   together) often shows up EMBEDDED mid-paragraph rather than cleanly on
   its own line -- so this can't use the line-anchored MULTILINE approach
   the other book-dump parsers (ra.py, seth.py) use; it searches for
   "Chapter <N>" anywhere in the flattened text instead. A stray page
   number frequently sits immediately before the chapter heading (an OCR
   artifact) and gets trimmed off the end of the previous chapter's text.
   No per-chapter date exists in a book like this -- date is left empty
   rather than fabricated.
"""

import re
from typing import List, Optional
from parsers.base import SessionRecord
from utils import clean_text_preserve_lines, clean_text, normalize_date

TITLE_RE = re.compile(r'^Tom Kenyon\s*[\u00bb»>]\s*(.+?)\s*$', re.MULTILINE)

DATE_RE = re.compile(
    r'(January|February|March|April|May|June|July|August|September|October|'
    r'November|December)\s+\d{1,2},\s*\d{4}',
    re.IGNORECASE
)

CHANNELED_THROUGH_RE = re.compile(
    r'channeled through Tom Kenyon,?\s*(' + DATE_RE.pattern + r')',
    re.IGNORECASE
)

DEFAULT_PARTICIPANTS = ["Tom Kenyon"]

# --- Book/chapter tier ---
# A genuine chapter heading is always followed by a capitalized title
# ("Chapter 1. Introduction", "Chapter 3 Feeling and..."). A casual
# in-text reference ("before we complete Chapter 1?") is followed by
# ordinary punctuation instead -- requiring a capital letter right after
# is what tells the two apart.
CHAPTER_RE = re.compile(r'\bChapter\s+(\d+)\.?\s+(?=[A-Z])', re.IGNORECASE)
TRAILING_PAGE_NUMBER_RE = re.compile(r'\s+\d{1,3}\s*$')  # stray page number right before a chapter break
BOOK_CHANNELER = "Tom Kenyon and Virginia Essene"
BOOK_PARTICIPANTS = ["Tom Kenyon", "Virginia Essene"]
MIN_CHAPTER_MATCHES_FOR_BOOK_TIER = 2  # need to see this pattern recur to trust it's a real book, not a one-off mention


def _slug_from_source(source_file: str) -> str:
    tail = source_file.rstrip("/").split("/")[-1]
    if tail.lower().endswith(".html"):
        tail = tail[:-5]
    return tail


def _humanize_slug(slug: str) -> str:
    words = re.split(r'[-_]', slug)
    return " ".join(w.capitalize() for w in words if w)


def _extract_title_and_strip(raw_text: str, source_file: str) -> tuple:
    match = TITLE_RE.search(raw_text[:300])
    if match:
        title = match.group(1).strip()
        remainder = raw_text[:match.start()] + raw_text[match.end():]
        return title, remainder
    return _humanize_slug(_slug_from_source(source_file)), raw_text


def _extract_date(raw_text: str) -> Optional[str]:
    cited_match = CHANNELED_THROUGH_RE.search(raw_text)
    if cited_match:
        return normalize_date(cited_match.group(1))

    general_match = DATE_RE.search(raw_text[:1500])
    if general_match:
        return normalize_date(general_match.group(0))

    return None


def _parse_book_chapters(preserved: str, source_file: str) -> List[SessionRecord]:
    matches = list(CHAPTER_RE.finditer(preserved))
    if len(matches) < MIN_CHAPTER_MATCHES_FOR_BOOK_TIER:
        return []

    records = []
    for i, match in enumerate(matches):
        chapter_number = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(preserved)
        block = preserved[start:end]

        # Trim a stray page number off the very end (an OCR artifact that
        # lands right before the NEXT chapter heading, i.e. at the end of
        # THIS slice since we sliced up to that next match's start).
        block = TRAILING_PAGE_NUMBER_RE.sub('', block)

        records.append(SessionRecord(
            source="hathors",
            session_uid=f"hathors_chapter_{chapter_number.zfill(3)}",
            text=clean_text(block),
            channeler=BOOK_CHANNELER,
            entity="The Hathors",
            session_number=chapter_number,
            date="",
            participants=list(BOOK_PARTICIPANTS),
            source_file=source_file,
        ))

    return records


def parse(raw_text: str, source_file: str) -> List[SessionRecord]:
    preserved = clean_text_preserve_lines(raw_text)
    if not preserved.strip():
        return []

    # --- Tier 1: book/chapter style ---
    book_records = _parse_book_chapters(preserved, source_file)
    if book_records:
        return book_records

    # --- Tier 2: website single-message style ---
    title, body_without_title = _extract_title_and_strip(preserved, source_file)
    date = _extract_date(preserved)
    slug = _slug_from_source(source_file)

    session_uid = f"hathors_{date}" if date else f"hathors_{slug}"

    cleaned_text = clean_text(body_without_title)
    full_text = f"{title}. {cleaned_text}" if title else cleaned_text

    return [SessionRecord(
        source="hathors",
        session_uid=session_uid,
        text=full_text,
        channeler="Tom Kenyon",
        entity="The Hathors",
        date=date or "",
        participants=list(DEFAULT_PARTICIPANTS),
        source_file=source_file,
    )]
