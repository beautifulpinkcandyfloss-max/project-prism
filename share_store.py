"""
Persistent storage for shareable Ask-the-Archive results. When someone
asks a question, the question text, the synthesized answer, and the
retrieved source chunks all get saved to a small JSON file keyed by a
short hash. The hash becomes a query parameter (?ask=<hash>) that
anyone can use to replay the exact same result without re-running the
LLM -- which makes shares cheap (no extra Gemini calls per click) and
gives the linked page a stable identity over time.

KNOWN LIMITATION: Streamlit Cloud's free-tier filesystem is EPHEMERAL --
saved shares persist across page loads on the same boot, but get wiped
on every redeploy or container restart. That's typically every few hours
to days, depending on traffic. For shares that need to survive
indefinitely, the right next step is to write to durable object storage
(S3, Cloudflare R2) instead of local disk -- the function signatures
here are deliberately simple enough that you can swap the storage
backend without touching anything else. The same flagged ephemeral
behaviour applies to processed_data/ before ensure_data() runs, so
nothing here is new in kind.
"""

import hashlib
import json
import os
import time
from typing import Optional

SHARES_DIR = "processed_data/shares"
HASH_LENGTH = 8


def _make_hash(question: str) -> str:
    """Generate a short stable hash from the question plus the current
    time. Including the time means two identical questions asked at
    different moments get different hashes (no accidental overwrites),
    while a single moment's hash stays stable across the function call.
    8 characters of hex gives ~1 trillion possible values -- collision
    probability is negligible for any realistic usage."""
    seed = f"{question}|{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:HASH_LENGTH]


def save_share(question: str, answer: str, source_chunks: list) -> str:
    """Persist a single Ask result and return its hash. The hash is the
    only thing the caller needs to keep -- everything else can be
    reconstructed from disk via load_share()."""
    os.makedirs(SHARES_DIR, exist_ok=True)
    share_id = _make_hash(question)

    payload = {
        "id": share_id,
        "question": question,
        "answer": answer,
        "source_chunks": source_chunks,
        "saved_at": time.time(),
    }
    path = os.path.join(SHARES_DIR, f"{share_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return share_id


def load_share(share_id: str) -> Optional[dict]:
    """Return the saved share, or None if no such share exists (which
    can happen legitimately on Streamlit Cloud's free tier if the
    container has restarted since the share was saved -- see the
    module docstring). Always uses an allowlist character check on
    share_id to keep this safe from path traversal even though it
    only ever comes from URL parameters in practice."""
    if not share_id or not share_id.isalnum() or len(share_id) > HASH_LENGTH + 4:
        return None
    path = os.path.join(SHARES_DIR, f"{share_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
