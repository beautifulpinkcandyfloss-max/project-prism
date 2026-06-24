"""
Takes processed_data/cleaned_transcripts.json (the flat list of chunks
scraper.py produces) and:
  1. Embeds each chunk's text using Gemini's embedding model.
  2. Upserts each chunk + its embedding + its metadata into a persistent
     ChromaDB collection on disk.

Run after every scraper.py run that adds/changes data:
    python embed.py

Requires a Gemini API key. Put it in a .env file in the project root:
    GEMINI_API_KEY=your_key_here
(python-dotenv, already in requirements.txt, loads this automatically.)
"""

import os
import time
import sys
import streamlit as st
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

from scraper import load_all_chunks

load_dotenv()

CHROMA_DIR = "processed_data/chroma_db"
COLLECTION_NAME = "prism_transcripts"

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMENSIONS = 768          # smaller = cheaper/faster storage; fine for this corpus size
BATCH_SIZE = 50                 # chunks per embedding API call
MAX_RETRIES = 5


def load_chunks():
    """Reads every processed_data/by_source/<source>.json file and
    combines them in memory -- see scraper.py for why output is split
    per-source rather than one combined file."""
    return load_all_chunks()


def flatten_metadata(chunk: dict) -> dict:
    """ChromaDB metadata values must be str/int/float/bool -- no lists or
    None. Convert participants list -> comma-joined string, drop/convert
    anything else that isn't a primitive."""
    meta = {}
    for key, value in chunk.items():
        if key in ("text", "chunk_id"):
            continue  # text is stored separately; chunk_id is the doc id
        if value is None:
            meta[key] = ""
        elif isinstance(value, list):
            meta[key] = ", ".join(str(v) for v in value)
        else:
            meta[key] = value
    return meta


def embed_batch(client: genai.Client, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with retry/backoff on transient errors
    (rate limits, timeouts)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBED_DIMENSIONS,
                ),
            )
            return [e.values for e in result.embeddings]
        except Exception as exc:
            wait = min(2 ** attempt, 30)
            print(f"  [EMBED] attempt {attempt} failed ({exc}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Failed to embed batch after {MAX_RETRIES} attempts")


def build_index(chunks: list[dict]):
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError(
            "No GEMINI_API_KEY / GOOGLE_API_KEY found. Add one to a .env file "
            "in the project root (see embed.py docstring)."
        )

    client = genai.Client()
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

    total = len(chunks)
    print(f"[EMBED] {total} chunks to process in batches of {BATCH_SIZE}")

    for start in range(0, total, BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]

        # Defensive dedup: scraper.py now prevents duplicate chunk_ids at
        # the source, but if you're running embed.py against an older
        # cleaned_transcripts.json, guard here too rather than crashing.
        seen_in_batch = set()
        deduped_batch = []
        for c in batch:
            if c["chunk_id"] in seen_in_batch:
                print(f"  [EMBED] skipping duplicate chunk_id in batch: {c['chunk_id']}")
                continue
            seen_in_batch.add(c["chunk_id"])
            deduped_batch.append(c)
        batch = deduped_batch

        texts = [c["text"] for c in batch]
        ids = [c["chunk_id"] for c in batch]
        metadatas = [flatten_metadata(c) for c in batch]

        vectors = embed_batch(client, texts)

        collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

        done = min(start + BATCH_SIZE, total)
        print(f"[EMBED] {done}/{total} chunks indexed")

    prune_orphaned_ids(collection, chunks)

    print(f"\n[DONE] Collection '{COLLECTION_NAME}' now has {collection.count()} chunks "
          f"stored at {CHROMA_DIR}")
    return collection


def prune_orphaned_ids(collection, chunks: list[dict]):
    """upsert() only adds/updates -- it never removes anything. If you
    re-run a fixed parser, the OLD chunk_ids it used to produce (e.g. a
    big 'ra_unstructured_xxxxx' fallback record) stay in the index
    forever even after cleaned_transcripts.json no longer contains them,
    quietly polluting retrieval with stale data. This deletes anything
    in the collection that isn't in the current dataset."""
    current_ids = {c["chunk_id"] for c in chunks}
    try:
        existing = collection.get(include=[])
    except Exception as exc:
        print(f"[PRUNE] Couldn't read existing IDs to check for orphans: {exc}")
        return

    existing_ids = set(existing.get("ids", []))
    orphaned = existing_ids - current_ids

    if not orphaned:
        print("[PRUNE] No orphaned chunk IDs found -- index matches current data.")
        return

    collection.delete(ids=list(orphaned))
    print(f"[PRUNE] Removed {len(orphaned)} stale chunk(s) no longer present in "
          f"cleaned_transcripts.json (likely leftovers from an earlier parser version).")


def quick_test_query(query: str, n_results: int = 5):
    """Sanity-check the index without going through the full app. Run:
        python embed.py --query "how were the pyramids built"
    """
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    client = genai.Client()

    query_vector = embed_batch(client, [query])[0]
    results = collection.query(query_embeddings=[query_vector], n_results=n_results)

    print(f"\nTop {n_results} results for: '{query}'\n")
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        doc = results["documents"][0][i]
        distance = results["distances"][0][i]
        print(f"--- {i + 1}. [{meta.get('source')}] {meta.get('entity')} "
              f"(session {meta.get('session_number') or meta.get('session_uid')}, "
              f"{meta.get('date') or 'undated'}) -- distance {distance:.3f}")
        print(f"    channeler: {meta.get('channeler')} | participants: {meta.get('participants')}")
        print(f"    {doc[:220]}{'...' if len(doc) > 220 else ''}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2 and sys.argv[1] == "--query":
        quick_test_query(" ".join(sys.argv[2:]))
    else:
        chunks = load_chunks()
        build_index(chunks)
