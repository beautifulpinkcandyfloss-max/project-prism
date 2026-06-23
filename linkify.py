"""
Turns recognized topic mentions in any displayed text into clickable
internal links (?view=topic&name=...), using the alias map built by
build_topic_index.py. Used wherever transcript passages, synthesis
answers, or debate turns get rendered.
"""

import json
import os
import re
import urllib.parse

ALIASES_PATH = "processed_data/topic_aliases.json"

_alias_map = None
_pattern = None


def _load():
    global _alias_map, _pattern
    if _alias_map is not None:
        return
    if not os.path.exists(ALIASES_PATH):
        _alias_map = {}
        _pattern = None
        return
    with open(ALIASES_PATH, "r", encoding="utf-8") as f:
        _alias_map = json.load(f)
    if not _alias_map:
        _pattern = None
        return
    sorted_aliases = sorted(_alias_map.keys(), key=len, reverse=True)
    _pattern = re.compile(
        r'\b(' + '|'.join(re.escape(a) for a in sorted_aliases) + r')\b',
        re.IGNORECASE
    )


def linkify(text: str, max_links_per_topic: int = 1) -> str:
    """Wraps the FIRST occurrence of each recognized topic per text block
    in a link, preserving the original matched text/casing exactly --
    only the wrapping is new. Limiting to one link per topic per block
    keeps dense passages readable instead of every single repeated
    mention turning blue.

    IMPORTANT: only call this on text that's about to go through
    st.markdown(..., unsafe_allow_html=True). If the surrounding code
    flattens HTML to a single line (see app.py's _flatten_html), call
    linkify() BEFORE flattening, since the <a> tags it inserts are plain
    single-line HTML and play fine with that fix."""
    _load()
    if not _pattern or not text:
        return text

    seen_canonicals = set()

    def replace(match):
        alias = match.group(1).lower()
        canonical = _alias_map.get(alias)
        if not canonical or canonical in seen_canonicals:
            return match.group(0)
        seen_canonicals.add(canonical)
        encoded = urllib.parse.quote(canonical)
        return (f'<a href="?view=topic&name={encoded}" target="_self" class="prism-topic-link">'
                f'{match.group(0)}</a>')

    return _pattern.sub(replace, text)


def topics_available() -> bool:
    _load()
    return bool(_alias_map)
