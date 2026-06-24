"""
Orchestrator for the Project Prism ingestion pipeline.

For each source in parsers.base.SOURCE_KEYS (ra, seth, quo,
michael, hathors):
    1. Walk raw_inputs/<source>/{docs,pdfs,links}/ for manifest files
       (docs.txt / pdfs.txt / urls.txt) AND loose files dropped directly
       in those folders.
    2. Read each one with readers.read_any() -> raw text.
    3. Hand the raw text to that source's parser.parse() -> list of
       SessionRecords (one parse() call may return many sessions if the
       file contains a whole book).
    4. Chunk each session with chunker.build_chunks_for_session().
    5. Write that source's chunks to processed_data/by_source/<source>.json

EACH SOURCE OWNS ITS OWN OUTPUT FILE. This matters at scale: this
project's full corpus (1,700+ Q'uo/Hatonn/Latwii transcripts, decades of
decades of Michael sessions...) will eventually run
into the tens of thousands of chunks. One combined JSON file at that size
becomes slow to read/write on every run AND was the root cause of an
earlier bug class (re-scraping one source could silently wipe data from
others if the merge logic wasn't exactly right). Splitting by source
makes that bug structurally impossible -- there's no shared file to
half-overwrite. embed.py reads all the per-source files and combines them
in memory at index time.

Run: python scraper.py
Run a single source only: python scraper.py --source seth
"""

import argparse
import json
import os
import traceback

from readers import read_source_list, read_any
from parsers.base import get_parser, SOURCE_KEYS
from chunker import build_chunks_for_session

RAW_INPUTS_DIR = "raw_inputs"
OUTPUT_DIR = "processed_data/by_source"
SESSIONS_DIR = "processed_data/sessions"

SUBFOLDERS = {
    "docs": "docs.txt",
    "pdfs": "pdfs.txt",
    "links": "urls.txt",
}


def gather_sources_for(source_key: str):
    """Returns a list of (item, base_dir) tuples to feed into read_any()
    for one source folder, pulled from manifest files AND loose files."""
    items = []
    source_dir = os.path.join(RAW_INPUTS_DIR, source_key)

    for subfolder, manifest_name in SUBFOLDERS.items():
        folder_path = os.path.join(source_dir, subfolder)
        if not os.path.isdir(folder_path):
            continue

        manifest_path = os.path.join(folder_path, manifest_name)
        for entry in read_source_list(manifest_path):
            items.append((entry, folder_path))

        for filename in sorted(os.listdir(folder_path)):
            if filename == manifest_name:
                continue
            full_path = os.path.join(folder_path, filename)
            if not os.path.isfile(full_path):
                continue

            if subfolder == "links" and filename.lower().endswith(".txt"):
                print(f"[WARNING] '{full_path}' is a .txt file in the links/ "
                      f"folder but isn't named '{manifest_name}', so it will "
                      f"be read as a literal document, NOT as a list of URLs "
                      f"to fetch. If this file contains a list of links, "
                      f"rename it to '{manifest_name}'.")

            items.append((filename, folder_path))

    return items


def dedupe_session_uid(session_dict: dict, seen_uids: dict, source_key: str):
    """If this session_uid has already been seen (almost always means the
    same session got scraped from two different links/files -- e.g. a
    duplicate URL, or the same book added twice), rename it so the run
    doesn't crash, and print a clear warning so the duplicate SOURCE can
    be tracked down and removed."""
    uid = session_dict["session_uid"]
    if uid not in seen_uids:
        seen_uids[uid] = session_dict["source_file"]
        return session_dict

    original_source = seen_uids[uid]
    new_source = session_dict["source_file"]
    suffix = 2
    new_uid = f"{uid}_dup{suffix}"
    while new_uid in seen_uids:
        suffix += 1
        new_uid = f"{uid}_dup{suffix}"

    print(f"[{source_key.upper()}] WARNING: duplicate session_uid '{uid}' -- "
          f"first seen in '{original_source}', also found in '{new_source}'. "
          f"Renamed second occurrence to '{new_uid}'. You probably have the "
          f"same session scraped from two sources -- worth checking for a "
          f"duplicate link/file.")

    session_dict["session_uid"] = new_uid
    seen_uids[new_uid] = new_source
    return session_dict


def process_source(source_key: str, verbose: bool = True):
    parse_fn = get_parser(source_key)
    items = gather_sources_for(source_key)
    all_chunks = []
    all_sessions = []  # full, unchunked text -- needed for the Browse view
    seen_uids = {}  # scoped per-source, since uids are already source-prefixed

    if verbose:
        print(f"[{source_key.upper()}] {len(items)} source item(s) found")

    for item, base_dir in items:
        try:
            raw_text = read_any(item, base_dir)
        except Exception as exc:
            print(f"[{source_key.upper()}] FAILED reading '{item}': "
                  f"{type(exc).__name__}: {exc}")
            print(traceback.format_exc())
            continue

        if not raw_text or not raw_text.strip():
            print(f"[{source_key.upper()}] No text extracted from '{item}'")
            continue

        try:
            session_records = parse_fn(raw_text, item)
        except Exception as exc:
            print(f"[{source_key.upper()}] PARSE ERROR on '{item}': "
                  f"{type(exc).__name__}: {exc}")
            print(traceback.format_exc())
            continue

        if verbose:
            print(f"[{source_key.upper()}] '{item}' -> {len(session_records)} session(s)")

        for record in session_records:
            session_dict = record.to_dict()
            session_dict = dedupe_session_uid(session_dict, seen_uids, source_key)
            all_sessions.append(session_dict)
            chunks = build_chunks_for_session(session_dict)
            all_chunks.extend(chunks)

    return all_chunks, all_sessions


def save_source_output(source_key: str, chunks: list):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{source_key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] {len(chunks)} chunks written to {path}")


def save_session_output(source_key: str, sessions: list):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = os.path.join(SESSIONS_DIR, f"{source_key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] {len(sessions)} full sessions written to {path}")


def load_all_sessions() -> list:
    """Used by the Browse view -- full, unchunked session text (no
    overlap duplication, unlike reconstructing from chunks)."""
    all_sessions = []
    if not os.path.isdir(SESSIONS_DIR):
        return all_sessions
    for filename in sorted(os.listdir(SESSIONS_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(SESSIONS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_sessions.extend(json.load(f))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[WARNING] Couldn't read {path}: {exc}")
    return all_sessions


def load_all_chunks() -> list:
    """Used by embed.py -- reads every per-source file and combines them
    in memory. Nothing on disk needs to hold the combined view."""
    all_chunks = []
    if not os.path.isdir(OUTPUT_DIR):
        return all_chunks
    for filename in sorted(os.listdir(OUTPUT_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(OUTPUT_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_chunks.extend(json.load(f))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[WARNING] Couldn't read {path}: {exc}")
    return all_chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=SOURCE_KEYS, default=None,
                         help="Process only this source (default: all sources)")
    args = parser.parse_args()

    sources_to_run = [args.source] if args.source else SOURCE_KEYS

    for source_key in sources_to_run:
        chunks, sessions = process_source(source_key)
        save_source_output(source_key, chunks)
        save_session_output(source_key, sessions)
        print()  # spacer between sources when running all 6


if __name__ == "__main__":
    main()
