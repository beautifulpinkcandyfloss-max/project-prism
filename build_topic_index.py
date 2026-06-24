"""
Scans every chunk across all six sources and builds a reverse index:
    topic_name -> [ {chunk_id, source, session_uid, date, entity, snippet}, ... ]

This is what powers internal linking ("Pyramids" links to every passage,
across every source, that mentions it) and the Topics/Glossary directory
page. Run this any time your underlying data changes:

    python build_topic_index.py

Writes processed_data/topic_index.json and processed_data/topic_aliases.json
(the alias->canonical map, needed at render time to recognize mentions in
text and turn them into links).
"""

import json
import os
import re

from scraper import load_all_chunks
from topics import (
    CURATED_TOPICS, detect_automatic_topics, build_topic_alias_map, all_topic_names,
    find_review_candidates,
)

OUTPUT_INDEX = "processed_data/topic_index.json"
OUTPUT_ALIASES = "processed_data/topic_aliases.json"

SNIPPET_RADIUS = 80  # characters of context on each side of the match


def _extract_snippet(text: str, match_start: int, match_end: int, radius: int = SNIPPET_RADIUS) -> str:
    """Builds a snippet around a match WITHOUT cutting words in half.
    Expands the raw character window outward to the nearest word
    boundary on each side, and marks truncation with an ellipsis when
    the snippet doesn't reach the natural start/end of the text."""
    raw_start = max(0, match_start - radius)
    raw_end = min(len(text), match_end + radius)

    start = raw_start
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    end = raw_end
    while end < len(text) and text[end].isalnum():
        end += 1

    snippet = text[start:end].strip()
    if start > 0:
        snippet = "\u2026 " + snippet
    if end < len(text):
        snippet = snippet + " \u2026"
    return snippet


def build_index():
    chunks = load_all_chunks()
    print(f"Loaded {len(chunks)} chunks")

    automatic_topics = detect_automatic_topics(chunks)
    print(f"Automatically detected {len(automatic_topics)} additional topic(s) "
          f"beyond the {len(CURATED_TOPICS)} curated ones")

    alias_map = build_topic_alias_map(automatic_topics)
    topic_names = all_topic_names(automatic_topics)

    # One combined regex matching ANY alias, longest-first so multi-word
    # aliases (e.g. "great pyramid") win over shorter overlapping ones
    # (e.g. "pyramid") when both could match the same span.
    sorted_aliases = sorted(alias_map.keys(), key=len, reverse=True)
    pattern = re.compile(
        r'\b(' + '|'.join(re.escape(a) for a in sorted_aliases) + r')\b',
        re.IGNORECASE
    )

    topic_index = {name: [] for name in topic_names}
    seen_session_per_topic = {name: set() for name in topic_names}

    for chunk in chunks:
        text = chunk.get("text", "")
        matched_canonicals_this_chunk = set()
        for match in pattern.finditer(text):
            alias = match.group(1).lower()
            canonical = alias_map.get(alias)
            if not canonical or canonical in matched_canonicals_this_chunk:
                continue
            matched_canonicals_this_chunk.add(canonical)

            snippet = _extract_snippet(text, match.start(), match.end())

            session_uid = chunk.get("session_uid", "")
            # Avoid piling up many entries from the same session for one
            # topic -- one representative passage per session is enough
            # for the topic page to stay readable.
            if session_uid in seen_session_per_topic[canonical]:
                continue
            seen_session_per_topic[canonical].add(session_uid)

            topic_index[canonical].append({
                "chunk_id": chunk.get("chunk_id"),
                "source": chunk.get("source"),
                "session_uid": session_uid,
                "date": chunk.get("date"),
                "entity": chunk.get("entity"),
                "channeler": chunk.get("channeler"),
                "snippet": snippet,
            })

    # Drop topics that ended up with zero real mentions (curated topics
    # the user added that don't actually appear in the data yet)
    topic_index = {k: v for k, v in topic_index.items() if v}

    os.makedirs(os.path.dirname(OUTPUT_INDEX), exist_ok=True)
    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(topic_index, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_ALIASES, "w", encoding="utf-8") as f:
        json.dump(alias_map, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] {len(topic_index)} topics with at least one real mention "
          f"-> {OUTPUT_INDEX}")
    print(f"[SAVED] {len(alias_map)} aliases -> {OUTPUT_ALIASES}")

    ranked = sorted(topic_index.items(), key=lambda kv: len(kv[1]), reverse=True)
    print("\nTop 15 topics by number of distinct sessions referencing them:")
    for name, entries in ranked[:15]:
        sources = sorted(set(e["source"] for e in entries))
        print(f"  {name:25s} {len(entries):4d} sessions  (sources: {', '.join(sources)})")

    review = find_review_candidates(chunks)
    if review:
        print("\nCandidates worth REVIEWING for possible curation (NOT auto-included --\n"
              "single-source terms that recur a lot within one source; could be a real\n"
              "term like 'Maldek', or could just be an ordinary word that source's\n"
              "questioner uses often -- use your judgment, then add the real ones to\n"
              "CURATED_TOPICS in topics.py):")
        for phrase, source, session_count in review:
            print(f"  {phrase:25s} {source:12s} {session_count:4d} sessions")


if __name__ == "__main__":
    build_index()
