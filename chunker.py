"""
Turns a SessionRecord's full text into overlapping chunks suitable for
embedding. Chunking happens AFTER session-splitting (not before), so every
chunk inherits accurate session metadata (channeler, date, session_uid...).

Paragraph-aware: tries to break on paragraph/sentence boundaries near the
target size rather than hard-cutting mid-sentence, and uses a sliding
overlap so a Q&A exchange that straddles a chunk boundary isn't orphaned.
"""

import re
from typing import List, Dict

DEFAULT_CHUNK_WORDS = 350
DEFAULT_OVERLAP_WORDS = 60


def split_sentences(text: str) -> List[str]:
    # Simple, dependency-free sentence splitter. Good enough for transcripts;
    # swap for nltk/spacy later if you want higher precision.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z(])', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_session_text(
    text: str,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> List[str]:
    sentences = split_sentences(text)
    chunks = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence.split())
        if current and current_len + sentence_len > chunk_words:
            chunks.append(' '.join(current))
            # carry the tail of the previous chunk forward as overlap
            overlap = []
            overlap_len = 0
            for s in reversed(current):
                wlen = len(s.split())
                if overlap_len + wlen > overlap_words:
                    break
                overlap.insert(0, s)
                overlap_len += wlen
            current = overlap
            current_len = overlap_len

        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(' '.join(current))

    return chunks


def build_chunks_for_session(session_dict: Dict, chunk_words: int = DEFAULT_CHUNK_WORDS,
                              overlap_words: int = DEFAULT_OVERLAP_WORDS) -> List[Dict]:
    """Returns a list of chunk dicts, each carrying the session's metadata
    plus its own chunk_id and text -- ready to hand to embed.py."""
    text_chunks = chunk_session_text(session_dict["text"], chunk_words, overlap_words)
    chunks = []
    for idx, chunk_text in enumerate(text_chunks):
        chunk = {k: v for k, v in session_dict.items() if k != "text"}
        chunk["chunk_id"] = f"{session_dict['session_uid']}_c{idx:02d}"
        chunk["text"] = chunk_text
        chunks.append(chunk)
    return chunks
