"""
Surfaces CANDIDATE notable quotes from your own already-scraped archive,
for you to review and hand-pick a final "top 20" from -- this script
never invents or types quote text itself, it only extracts real
sentences that already exist in your data, the same way
build_topic_index.py's snippets do.

Why this works this way rather than me just writing a curated quotes
list directly: the actual quote TEXT is copyrighted material from
published books. Programmatically pulling candidates from data you
already possess and have rights to use (the same way the rest of this
app already displays excerpts throughout Ask/Browse/Debate) is very
different from me personally typing out remembered passages at length,
which I should not do.

Run:
    python find_quote_candidates.py
    python find_quote_candidates.py --source ra   # just one source

Writes processed_data/quote_candidates.json -- a ranked list per source
for you to read through. Once you've picked your favorites, add them
to processed_data/quotes_curated.json (see the schema note below) and
the Learn page's Quotes section will display them.
"""

import argparse
import json
import os
import re
from collections import defaultdict

from scraper import load_all_chunks
from linkify import _load as _load_topic_aliases, _alias_map
from parsers.base import SOURCE_KEYS

OUTPUT_PATH = "processed_data/quote_candidates.json"
CURATED_PATH = "processed_data/quotes_curated.json"

SENTENCE_RE = re.compile(r'[^.!?]*[.!?]+')

SELF_IDENTIFYING_RE = re.compile(
    r'^\s*(I am (Ra|Seth|Q\'?uo|Hatonn|Latwii|Michael)\b|We are (those of|the principle known to you as))',
    re.IGNORECASE
)

MIN_WORDS = 15
MAX_WORDS = 45
MAX_CANDIDATES_PER_SOURCE = 50


def _score_sentence(sentence: str, topic_aliases: dict) -> int:
    score = 0
    if SELF_IDENTIFYING_RE.search(sentence):
        score += 5
    lowered = sentence.lower()
    for alias in topic_aliases:
        if alias in lowered:
            score += 1
    return score


def find_candidates(chunks: list, source_filter: str = None) -> dict:
    _load_topic_aliases()
    from linkify import _alias_map as alias_map  # re-import after _load() populates it
    alias_map = alias_map or {}

    candidates_by_source = defaultdict(list)

    for chunk in chunks:
        source = chunk.get("source", "")
        if source_filter and source != source_filter:
            continue
        text = chunk.get("text", "")
        for match in SENTENCE_RE.finditer(text):
            sentence = match.group(0).strip()
            word_count = len(sentence.split())
            if word_count < MIN_WORDS or word_count > MAX_WORDS:
                continue
            score = _score_sentence(sentence, alias_map)
            if score == 0:
                continue
            candidates_by_source[source].append({
                "sentence": sentence,
                "score": score,
                "session_uid": chunk.get("session_uid"),
                "entity": chunk.get("entity"),
                "channeler": chunk.get("channeler"),
                "date": chunk.get("date"),
            })

    for source in candidates_by_source:
        seen = set()
        deduped = []
        for c in sorted(candidates_by_source[source], key=lambda c: c["score"], reverse=True):
            if c["sentence"] in seen:
                continue
            seen.add(c["sentence"])
            deduped.append(c)
        candidates_by_source[source] = deduped[:MAX_CANDIDATES_PER_SOURCE]

    return dict(candidates_by_source)


def ensure_curated_file_exists():
    if os.path.exists(CURATED_PATH):
        return
    os.makedirs(os.path.dirname(CURATED_PATH), exist_ok=True)
    with open(CURATED_PATH, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)
    print(f"[CREATED] {CURATED_PATH} (empty) -- this is what the Learn page's "
          f"Quotes section actually reads from. Schema for each entry:\n"
          f'  {{"quote": "...", "source": "ra", "entity": "Ra", '
          f'"session_uid": "ra_013", "date": "1981-02-10"}}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=SOURCE_KEYS, default=None)
    args = parser.parse_args()

    chunks = load_all_chunks()
    print(f"Loaded {len(chunks)} chunks")

    candidates = find_candidates(chunks, source_filter=args.source)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in candidates.values())
    print(f"\n[SAVED] {total} candidate quote(s) across {len(candidates)} source(s) -> {OUTPUT_PATH}")
    for source, items in candidates.items():
        print(f"  {source:12s} {len(items):4d} candidates")

    ensure_curated_file_exists()
    print(f"\nNext: open {OUTPUT_PATH}, read through the candidates, and copy your "
          f"favorites (just the 'sentence' field, with attribution) into {CURATED_PATH}.")


if __name__ == "__main__":
    main()
