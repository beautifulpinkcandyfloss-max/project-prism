# Project Prism - Ingestion Pipeline

## Folder structure

Drop your raw materials into the matching source folder:

    raw_inputs/<source>/docs/    -- .txt and .docx files (or a docs.txt manifest of filenames/URLs)
    raw_inputs/<source>/pdfs/    -- .pdf files (or a pdfs.txt manifest)
    raw_inputs/<source>/links/   -- a urls.txt manifest, one URL per line

Where <source> is one of: ra, seth, quo, cassiopaea, michael, hathors

You can either drop files directly into a folder, OR list filenames/URLs
in the matching manifest file (docs.txt / pdfs.txt / urls.txt) -- both are
read automatically.

## Running it

    python scraper.py                  # process all 6 sources
    python scraper.py --source seth    # process just one source while you're
                                        # still building/testing its parser

## How the pipeline fits together

    readers.py    -> reads a file/URL, returns raw text (line breaks intact)
    parsers/*.py   -> takes raw text, splits it into sessions, extracts metadata
    chunker.py     -> splits each session's text into overlapping embed-ready chunks
    scraper.py     -> orchestrates the above and writes processed_data/cleaned_transcripts.json

## Writing/finishing a parser (parsers/<source>.py)

`seth.py` is a complete, working example -- use it as your template. Each
of the other five (ra.py, quo.py, cassiopaea.py, michael.py, hathors.py)
currently has a SAFE FALLBACK: if you run the scraper before finishing a
parser, it won't crash or lose data -- it just returns the whole raw text
as a single unstructured session. Replace the fallback in each file with
real session-splitting logic once you've inspected your actual scraped
text and confirmed the header/date patterns mentioned in that file's
docstring.

Test a single parser in isolation before running it on your full archive:

    from parsers.seth import parse
    records = parse(raw_text, "some_file.txt")
    for r in records:
        print(r.session_uid, r.date, r.participants)

## Output schema

processed_data/cleaned_transcripts.json is a flat list of CHUNKS (not
sessions) -- each chunk carries its full parent session metadata plus a
unique chunk_id, ready to hand straight to an embedding step:

    {
      "session_uid": "seth_0898",
      "source": "seth",
      "channeler": "Jane Roberts",
      "entity": "Seth",
      "session_number": "898",
      "date": "1980-01-30",
      "participants": ["Jane Roberts", "Robert Butts"],
      "location": null,
      "source_file": "...",
      "chunk_id": "seth_0898_c00",
      "text": "..."
    }
