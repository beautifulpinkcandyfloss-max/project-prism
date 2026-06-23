"""
Shared cleaning utilities used by readers.py and every parser in parsers/.

Important design choice: clean_text_preserve_lines() keeps line breaks intact.
Session boundaries, speaker labels ("RA:", "JOE:", "(Q)"), and date headers
almost always sit at the START of a line in these transcripts. If you collapse
everything to one space-joined string (like the old clean_text() did), you
destroy the exact signal your parser needs to split text into sessions.

Use clean_text_preserve_lines() in every parser. Only use clean_text() (fully
flattened) on the FINAL text of an already-split session, right before storing
it / chunking it -- never before splitting.
"""

import re

# Common mojibake patterns: a UTF-8 multi-byte character (most often
# smart quotes, em/en dashes, ellipses) gets misread as Latin-1/cp1252
# somewhere upstream (PDF extraction is the usual culprit -- some PDFs
# encode text with custom font mappings that confuse the decoder), and
# the result is garbled sequences like "Qâ\x80\x99uo" instead of "Q'uo".
# This is best-effort: it covers the patterns actually seen in this
# project's data, not an exhaustive mojibake fixer. If you spot a new
# garbled pattern, add it here.
MOJIBAKE_REPLACEMENTS = {
    "\u00e2\u20ac\u2122": "\u2019",   # â€™ -> '
    "\u00e2\u20ac\u02dc": "\u2018",   # â€˜ -> '
    "\u00e2\u20ac\u0153": "\u201c",   # â€œ -> "
    "\u00e2\u20ac\ufffd": "\u201d",   # â€\x9d -> "
    "\u00e2\u20ac\u201d": "\u2014",   # â€" -> —
    "\u00e2\u20ac\u201c": "\u2013",   # â€" -> –
    "\u00e2\u20ac\u00a6": "\u2026",   # â€¦ -> …
    "\u00c3\u00a9": "\u00e9",          # Ã© -> é
    "\u00c3\u00a8": "\u00e8",          # Ã¨ -> è
    "\u00c3\u00a0": "\u00e0",          # Ã  -> à
    "\u00c3\u00bc": "\u00fc",          # Ã¼ -> ü
    "\u00c3\u00b6": "\u00f6",          # Ã¶ -> ö
    "\u00c3\u00b1": "\u00f1",          # Ã± -> ñ
}


def fix_mojibake(text: str) -> str:
    if not text:
        return text
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


NAV_KEYWORDS = {
    "home", "about", "contact", "privacy", "terms", "faq", "help",
    "search", "menu", "sitemap", "site map", "login", "log in",
    "sign in", "subscribe", "press", "careers", "cookies",
}

# Boilerplate that shows up on scanned-book front/back matter -- title
# pages, copyright pages, ISBN/Library of Congress blocks, order forms.
# This is real, recurring, identifiable junk regardless of which
# particular scanned book it came from, so it's worth filtering out
# generically rather than per-book.
BOOK_BOILERPLATE_SUBSTRINGS = {
    "digitized by the internet archive", "kahle/austin foundation",
    "all rights reserved", "library of congress", "catalog card number",
    "manufactured in the united states", "printed on recycled paper",
    "order form", "share foundation", "isbn",
    "without written permission", "quote brief",
    "stored in a retrieval system", "transmitted in any form",
    "photocopying, recording", "reproduce illustrations in a review",
}

PRINTING_HISTORY_RE = re.compile(
    r'^(first|second|third|fourth|fifth|sixth)\s+printing\b', re.IGNORECASE
)
PHONE_NUMBER_RE = re.compile(r'\(\d{3}\)\s*\d{3}[\s-]\d{4}')
COPYRIGHT_LINE_RE = re.compile(r'copyright\s*[\u00a9c]', re.IGNORECASE)


def is_book_boilerplate_line(line: str) -> bool:
    normalized = line.strip().lower()
    if not normalized:
        return False
    if any(s in normalized for s in BOOK_BOILERPLATE_SUBSTRINGS):
        return True
    if COPYRIGHT_LINE_RE.search(normalized):
        return True
    if PRINTING_HISTORY_RE.match(normalized):
        return True
    if PHONE_NUMBER_RE.search(line):
        return True
    if line.count('$') >= 2:
        return True  # price-list table row (order forms, catalogs)
    return False


def is_navigation_line(line: str) -> bool:
    normalized = line.strip().lower()
    if not normalized:
        return True
    if re.fullmatch(r'[\-=_\.]{2,}', normalized):
        return True
    if len(normalized.split()) <= 6 and any(k in normalized for k in NAV_KEYWORDS):
        return True
    if re.match(r'^(page|slide)\s*\d+(\s*of\s*\d+)?$', normalized):
        return True
    if is_book_boilerplate_line(line):
        return True
    return False


def clean_text_preserve_lines(text: str) -> str:
    """Strip nav junk and dead whitespace but KEEP line breaks AND
    paragraph breaks. Use this before any session-splitting /
    regex-on-line-start logic.

    Blank lines are preserved as a SINGLE blank-line marker between
    paragraphs (multiple consecutive blanks collapse to one, and no
    leading/trailing blank lines) rather than being dropped entirely --
    that paragraph-break information is what clean_text() below uses to
    avoid flattening an entire multi-paragraph session into one
    unreadable wall of text."""
    if not text:
        return ""
    text = fix_mojibake(text)
    text = text.replace('\xa0', ' ').replace('\r', '\n')
    lines = []
    prev_was_blank = True  # starts True so no leading blank line is kept
    for raw_line in text.splitlines():
        candidate = raw_line.strip()
        if not candidate:
            if not prev_was_blank:
                lines.append("")
                prev_was_blank = True
            continue
        if is_navigation_line(candidate):
            continue
        lines.append(candidate)
        prev_was_blank = False
    while lines and lines[-1] == "":
        lines.pop()
    return '\n'.join(lines)


def clean_text(text: str) -> str:
    """Flattens text for storage, but PARAGRAPH-AWARE: lines within the
    same paragraph (no blank line between them in the original) get
    joined with a single space, same as before -- but an actual
    paragraph break (a blank line in the source) is preserved as '\\n\\n'
    rather than being squashed into the same single unbroken line as
    everything else. Use this only on a SINGLE session's text, after it
    has already been split out."""
    if not text:
        return ""
    preserved = clean_text_preserve_lines(text)

    paragraphs = []
    current = []
    for line in preserved.splitlines():
        if line == "":
            if current:
                paragraphs.append(' '.join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(' '.join(current))

    flat = '\n\n'.join(paragraphs)
    flat = re.sub(r'page\s*\d+\s*of\s*\d+', ' ', flat, flags=re.IGNORECASE)
    flat = re.sub(r'page\s*\d+', ' ', flat, flags=re.IGNORECASE)
    flat = re.sub(r'[-=]{3,}', ' ', flat)
    flat = re.sub(r'[ \t]+', ' ', flat)          # collapse horizontal whitespace only --
    flat = re.sub(r'\n{3,}', '\n\n', flat)        # never more than one blank line between paragraphs
    return flat.strip()


_KNOWN_ACRONYMS = {
    "dna", "rna", "sto", "sts", "ufo", "ufos", "nasa", "usa", "uk", "tv",
    "id", "ok", "cia", "fbi", "et", "ets",
}


def soften_all_caps(text: str) -> str:
    """For text written in ALL CAPS as a real transcription convention
    (e.g. the Michael Teachings, where the channeled entity's words are
    rendered in full caps to distinguish them from the questioner's
    normal-case words), convert to sentence case for readability at
    DISPLAY time -- the stored data itself stays verbatim/faithful to
    the source; this is purely a presentation transform.

    Applied per-sentence, so a document that mixes normal-case and
    all-caps sections (exactly what these transcripts do) only touches
    the genuinely all-caps parts. Rather than trying to maintain an
    ever-growing blocklist of ordinary short words ("WANT", "TELL",
    "HEAR" are all <=4 letters too -- a blocklist never catches up), a
    short all-caps token is ONLY kept as-is if it's in a small, precise
    ALLOWLIST of known real acronyms (DNA, STO, UFO...). Anything not on
    that list gets lowercased, which is the safe default."""
    if not text:
        return text

    def fix_sentence(match):
        sentence = match.group(0)
        letters = [c for c in sentence if c.isalpha()]
        if len(letters) < 12:
            return sentence  # too short to safely judge -- likely just an acronym/label
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio < 0.85:
            return sentence  # not actually an all-caps run, leave untouched

        words = sentence.split(' ')
        fixed_words = []
        for w in words:
            core = w.strip('.,!?;:"\'')
            if core.lower() in _KNOWN_ACRONYMS:
                fixed_words.append(w)  # known real acronym -- keep as-is
            elif core.lower() == "i":
                fixed_words.append(w.replace(core, "I"))  # the pronoun "I" is always capitalized
            else:
                fixed_words.append(w.lower())
        result = ' '.join(fixed_words)
        for i, c in enumerate(result):
            if c.isalpha():
                result = result[:i] + c.upper() + result[i + 1:]
                break
        return result

    return re.sub(r'[^.!?]*[.!?]+|[^.!?]+$', fix_sentence, text)


def humanize_redactions(text: str) -> str:
    """Some sources (Michael Teachings especially) redact participant
    names in the original transcript with raw underscores ("_____").
    That's genuinely what's in the source -- not something to invent a
    name for -- but a readable placeholder displays better than a raw
    run of underscores. Safe to apply to any source: text without this
    pattern is simply unaffected."""
    if not text:
        return text
    return re.sub(r'_{3,}', '[name redacted]', text)


def normalize_date(raw_date: str) -> str:
    """Best-effort conversion of a free-text date into ISO 'YYYY-MM-DD'.
    Falls back to returning the original string if it can't be parsed --
    never raises, never silently drops data."""
    if not raw_date:
        return ""
    from datetime import datetime

    raw_date = raw_date.strip().strip(',')
    formats = [
        "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y", "%m/%d/%Y", "%m/%d/%y",
        "%Y-%m-%d", "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw_date  # couldn't parse -- keep original rather than lose it
