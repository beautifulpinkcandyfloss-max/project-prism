"""
Shared schema + registry for all source parsers.

EVERY parser (ra.py, seth.py, quo.py, michael.py, hathors.py)
must expose a function:

    def parse(raw_text: str, source_file: str) -> List[SessionRecord]

`raw_text` is the output of readers.read_any() -- i.e. line-breaks-preserved,
NOT yet flattened. It may contain ONE session or MANY sessions concatenated
(this is very common -- e.g. a single .txt file containing an entire book
with dozens of sessions back to back). Your job in parse() is to:

  1. Find the boundaries between sessions (regex on session headers/dates).
  2. For each session, pull out the structured metadata you can find
     (date, session number, channeler, participants, location).
  3. Clean the session's body text with utils.clean_text().
  4. Return one SessionRecord per session.

If you can't confidently find structure, it's fine to return the WHOLE
raw_text as a single SessionRecord with whatever metadata you could find
(even none) -- better to have one big imperfect record than to crash or
silently drop content. Never throw the text away.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SessionRecord:
    source: str                       # "ra", "seth", "quo", "michael", "hathors"
    session_uid: str                  # stable unique id, e.g. "seth_0897"
    text: str                         # cleaned, flattened session text
    channeler: Optional[str] = None   # e.g. "Jane Roberts", "Carla Rueckert"
    entity: Optional[str] = None      # e.g. "Seth", "Ra", "Q'uo"
    session_number: Optional[str] = None
    date: Optional[str] = None        # ISO format if parseable, else raw string
    participants: List[str] = field(default_factory=list)
    location: Optional[str] = None
    source_file: str = ""             # original filename/URL this came from

    def to_dict(self):
        return {
            "session_uid": self.session_uid,
            "source": self.source,
            "channeler": self.channeler,
            "entity": self.entity,
            "session_number": self.session_number,
            "date": self.date,
            "participants": self.participants,
            "location": self.location,
            "source_file": self.source_file,
            "text": self.text,
        }


# -----------------------------------------------------------------
# Registry: maps the raw_inputs/<key>/ folder name to its parser module.
# Add an entry here the moment you create a new parsers/<name>.py file.
# -----------------------------------------------------------------

def get_parser(source_key: str):
    """Lazy import so a half-finished parser module doesn't break the others."""
    if source_key == "ra":
        from parsers import ra
        return ra.parse
    if source_key == "seth":
        from parsers import seth
        return seth.parse
    if source_key == "quo":
        from parsers import quo
        return quo.parse
    if source_key == "michael":
        from parsers import michael
        return michael.parse
    if source_key == "hathors":
        from parsers import hathors
        return hathors.parse
    raise KeyError(f"No parser registered for source '{source_key}'")


SOURCE_KEYS = ["ra", "seth", "quo", "michael", "hathors"]
