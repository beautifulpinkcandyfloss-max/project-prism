"""
Ensures processed_data/ (the built vector index, full sessions, topic
index, curated quotes) is present before the app starts. This data is
deliberately NOT tracked in git -- it's large, generated, and
re-buildable/re-downloadable, not source code -- so on a fresh Streamlit
Cloud deploy, this downloads and unpacks it from a GitHub Release asset
instead.

Setup (one-time, on your machine):
    1. Run your full pipeline locally as normal (run_pipeline.py, embed.py,
       build_topic_index.py, find_quote_candidates.py).
    2. Zip the result:
           Compress-Archive -Path processed_data -DestinationPath processed_data.zip
    3. On GitHub: your repo -> Releases -> "Create a new release" -> upload
       processed_data.zip as an ASSET (not as a tracked file) -> publish.
    4. Copy that asset's direct download link (right-click it on the
       release page). It looks like:
           https://github.com/<user>/<repo>/releases/download/<tag>/processed_data.zip
    5. On Streamlit Cloud: app settings -> Secrets -> add
           PRISM_DATA_URL = "<that link>"

Every time your underlying data changes, re-run the pipeline, re-zip,
upload as a NEW release (or replace the asset on the same release), and
the next deploy/reboot will pick up the fresh copy automatically.
"""

import os
import urllib.request
import zipfile


def _get_data_url() -> str:
    """Read PRISM_DATA_URL from any of the places it could legitimately
    live. Streamlit Cloud's documented behavior loads secrets into
    st.secrets[...], but only mirrors them as environment variables for
    some secret formats -- to be robust to both, check both sources, and
    also defer the streamlit import so this module is still usable
    outside Streamlit (e.g. for local testing)."""
    url = os.environ.get("PRISM_DATA_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st
        url = st.secrets.get("PRISM_DATA_URL", "").strip()
    except Exception:
        url = ""
    return url


MARKER_PATH = "processed_data/chroma_db"


def ensure_data():
    if os.path.isdir(MARKER_PATH):
        print("[ensure_data] processed_data/chroma_db already present -- nothing to do.")
        return

    url = _get_data_url()
    if not url:
        print("[ensure_data] WARNING: processed_data/chroma_db is missing and "
              "PRISM_DATA_URL is not set (checked both env vars and st.secrets). "
              "The app will have no content to search. See ensure_data.py docstring "
              "for the one-time setup steps.")
        return

    print(f"[ensure_data] Downloading prebuilt data from {url} ...")
    zip_path = "processed_data_download.zip"
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(".")
        print("[ensure_data] Done -- processed_data/ is now populated.")
    except Exception as exc:
        print(f"[ensure_data] FAILED to download/extract data: {type(exc).__name__}: {exc}")
        raise
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)


if __name__ == "__main__":
    ensure_data()
