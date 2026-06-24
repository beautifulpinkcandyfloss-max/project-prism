"""
Runs the full ingestion side of the pipeline in one command:

    1. For any source that has a link-discovery function (currently
       quo, michael), crawl its index pages and refresh
       raw_inputs/<source>/links/urls.txt.
    2. Run the scraper for every source, writing
       processed_data/by_source/<source>.json.

Does NOT run embed.py -- that's a separate step you run yourself once
you're happy with what's in processed_data/by_source/.

Run:
    python run_pipeline.py                  # discovery + scrape, all 6 sources
    python run_pipeline.py --source quo     # just one source
    python run_pipeline.py --skip-discovery # scrape only, using whatever
                                             # urls.txt already has (faster
                                             # if you're just iterating on a
                                             # parser and don't need to
                                             # re-crawl the index pages)
"""

import argparse

from parsers.base import SOURCE_KEYS
from discover_links import DISCOVERERS, _write_urls
from scraper import process_source, save_source_output, save_session_output


def run_discovery(source_key: str):
    if source_key not in DISCOVERERS:
        return  # this source has no crawler (ra, seth, hathors)

    print(f"\n--- Discovering links: {source_key} ---")
    try:
        urls = DISCOVERERS[source_key]()
    except Exception as exc:
        print(f"[{source_key.upper()}] Discovery failed: {exc}")
        print(f"[{source_key.upper()}] Continuing with whatever's already in "
              f"raw_inputs/{source_key}/links/urls.txt")
        return

    if not urls:
        print(f"[{source_key.upper()}] No URLs discovered this run.")
        return

    _write_urls(source_key, urls)


def run_scrape(source_key: str):
    print(f"\n--- Scraping: {source_key} ---")
    try:
        chunks, sessions = process_source(source_key)
    except Exception as exc:
        print(f"[{source_key.upper()}] Scraping failed: {exc}")
        return 0

    save_source_output(source_key, chunks)
    save_session_output(source_key, sessions)
    return len(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=SOURCE_KEYS, default=None,
                         help="Run only this source (default: all 6)")
    parser.add_argument("--skip-discovery", action="store_true",
                         help="Skip the link-crawling step, scrape using "
                              "whatever's already in urls.txt")
    args = parser.parse_args()

    sources = [args.source] if args.source else SOURCE_KEYS
    counts = {}

    for source_key in sources:
        if not args.skip_discovery:
            run_discovery(source_key)
        counts[source_key] = run_scrape(source_key)

    print("\n" + "=" * 40)
    print("PIPELINE SUMMARY")
    print("=" * 40)
    total = 0
    for source_key in sources:
        n = counts[source_key]
        total += n
        print(f"  {source_key:12s} {n:6d} chunks")
    print(f"  {'TOTAL':12s} {total:6d} chunks")
    print("=" * 40)
    print("\nNext step: python embed.py")


if __name__ == "__main__":
    main()
