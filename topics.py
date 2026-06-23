"""
Hybrid topic detection for internal linking: a curated glossary of the
most important recurring concepts, PLUS automatic detection of recurring
capitalized terms across the corpus. Either kind becomes a clickable
internal link (?view=topic&name=...) wherever it appears in displayed
text.

CURATED_TOPICS is the part worth hand-editing over time -- add an entry
any time you notice an important concept that automatic detection either
missed or under-prioritized. Each entry maps a canonical display name to
a list of alias strings that should all resolve to the same topic page
(case-insensitive, whole-word matched).
"""

import re
from collections import defaultdict
from typing import Dict, List

# -----------------------------------------------------------------
# Curated glossary -- canonical_name -> [aliases]. The canonical name
# itself does NOT need to be repeated in the alias list.
# -----------------------------------------------------------------
CURATED_TOPICS: Dict[str, List[str]] = {
    "Pyramids": ["pyramid", "pyramids", "great pyramid", "giza"],
    "Atlantis": ["atlantis", "atlantean", "atlanteans"],
    "Lemuria": ["lemuria", "lemurian", "lemurians"],
    "Roswell": ["roswell"],
    "Reincarnation": ["reincarnation", "past life", "past lives", "rebirth"],
    "Karma": ["karma", "karmic"],
    "Densities": ["density", "densities", "third density", "fourth density",
                   "fifth density", "sixth density"],
    "Service to Others": ["service to others", "service-to-others", " sto "],
    "Service to Self": ["service to self", "service-to-self", " sts "],
    "Overleaves": ["overleaves", "overleaf", "soul age", "soul role"],
    "Akashic Records": ["akashic records", "akashic record"],
    "DNA": ["dna", "genetic manipulation", "genetic engineering"],
    "Ascension": ["ascension", "ascend", "ascending"],
    "Free Will": ["free will", "law of confusion"],
    "Wanderers": ["wanderer", "wanderers"],
    "Extraterrestrials": ["extraterrestrial", "extraterrestrials", "alien",
                           "aliens", "ufo", "ufos"],
    "Crystals": ["crystal", "crystals", "crystal skull", "crystal skulls"],
    "Chakras": ["chakra", "chakras"],
    "Law of One": ["law of one"],
    "Confederation": ["confederation", "confederation of planets", "the confederation"],
    "All That Is": ["all that is"],
    "Indigo Children": ["indigo child", "indigo children", "starseed", "starseeds"],
    "Maldek": ["maldek"],
    "Guardians": ["guardian", "guardians"],
    "Social Memory Complex": ["social memory complex"],
    "Mind/Body/Spirit Complex": ["mind/body/spirit complex", "mind body spirit complex"],
    "Logos": ["logos", "sub-logos", "sub logos"],
    "Orion Group": ["orion group", "orion empire", "orion crusade"],
    "Yahweh": ["yahweh"],
    "Distortion": ["distortion", "distortions"],
    "The Creator": ["creator", "the creator", "one infinite creator",
                     "one creator", "infinite creator"],
    "Adonai": ["adonai"],
    "Jesus": ["jesus"],
    "Christ": ["christ", "christ consciousness"],
    "Hatonn": ["hatonn"],
    "Latwii": ["latwii"],
    "Aspects": ["aspects", "aspect psychology"],
    "Probable Selves": ["probable self", "probable selves", "probable reality", "probable realities"],
    "Framework 1 and 2": ["framework 1", "framework 2"],
    "Spacious Present": ["spacious present"],
    "Value Fulfillment": ["value fulfillment"],
    "Causal Plane": ["causal plane"],
    "Essence Twin": ["essence twin", "essence twins"],
    "Agape": ["agape"],
    "Tao": ["tao", "the tao"],
    "Akashic Plane": ["akashic plane"],
    "Cadre": ["cadre", "cadres"],
}

# Channeler/participant names that automatic detection should never treat
# as a "topic" -- they're people, not subjects, and would otherwise show
# up constantly given how often a transcript names its own participants.
NAME_BLOCKLIST = {
    "carla rueckert", "don elkins", "jim mccarty", "jane roberts",
    "robert butts", "laura knight-jadczyk", "tom kenyon", "austin",
    "trisha", "gary", "frank", "candy",
}

# Multi-word capitalized phrases (1-3 words), used as automatic-detection
# candidates. Deliberately simple/dependency-free -- no NLP library
# required, just frequency + cross-source filtering to separate real
# recurring concepts from one-off capitalized noise.
CANDIDATE_RE = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b')

# Common English words that get capitalized purely because they start a
# sentence ("This is correct," "Would you," "There are...") -- without
# this filter, automatic detection mistakes ordinary grammar for proper
# nouns. Channeled texts are FULL of these sentence-initial connectors
# ("Now, we shall speak...", "Thus we see...", "Indeed, this is true.").
# If the FIRST word of a candidate phrase is in this set, the whole
# candidate is rejected -- a genuine proper noun phrase practically never
# starts with a function word like these.
COMMON_WORD_BLOCKLIST = {
    "this", "that", "these", "those", "there", "here",
    "and", "but", "or", "nor", "so", "yet", "if", "when", "while",
    "although", "though", "because", "since", "unless", "until", "after",
    "before", "once", "whenever", "wherever", "what", "where", "why",
    "how", "who", "whom", "whose", "which", "some", "many", "most",
    "each", "every", "such", "just", "only", "also", "even", "then",
    "than", "now", "very", "more", "less", "much", "all", "any", "no",
    "not", "do", "does", "did", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "i", "we", "you", "he", "she", "it",
    "they", "yes", "thank", "thanks", "indeed", "however", "therefore",
    "thus", "hence", "moreover", "furthermore", "nevertheless", "still",
    "instead", "perhaps", "maybe", "certainly", "clearly", "obviously",
    "would", "will", "should", "could", "can", "may", "might", "must",
    "let", "please", "well", "okay", "alright", "again", "first",
    "second", "third", "finally", "next", "last", "today", "tomorrow",
    "yesterday", "right", "true", "false", "ok",
}


def _is_likely_real_topic(phrase: str) -> bool:
    first_word = phrase.split()[0].lower()
    return first_word not in COMMON_WORD_BLOCKLIST


def _is_mid_sentence(text: str, match_start: int) -> bool:
    """True if this capitalized word is genuinely sitting in the MIDDLE
    of a sentence, not just capitalized because grammar put it at the
    start of one OR at the start of a quoted clause.

    A naive check (just "is the previous character not a period?") gets
    fooled constantly by quote marks, colons, and dashes: in 'Ra states,
    "Often this occurs..."', the word "Often" is capitalized because
    it's the first word of a quoted sentence, not because it's a proper
    noun -- but the character right before it is a quote mark, not a
    period, so a naive check would wrongly count it as "mid-sentence."
    At corpus scale this kind of false positive compounds badly: ANY
    word with even a handful of these slip-throughs gets added to the
    alias map, and linkify() then matches it case-insensitively
    EVERYWHERE in any displayed text afterward -- including completely
    ordinary lowercase usage in unrelated generated prose. So this
    explicitly excludes the punctuation marks that commonly introduce a
    fresh clause/quote (quotes, colons, dashes, parens) from counting as
    "mid-sentence," on top of the original period/question/exclamation
    exclusion."""
    SENTENCE_OR_CLAUSE_START_PUNCTUATION = set('.!?\u2026:\u2014\u2013-"\u201c\u201d\'\u2018\u2019([')
    i = match_start - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return False  # start of the whole text -- can't be mid-sentence
    return text[i] not in SENTENCE_OR_CLAUSE_START_PUNCTUATION


MIN_MID_SENTENCE_OCCURRENCES = 3


def detect_automatic_topics(chunks: List[dict], min_sources: int = 2,
                             min_sessions: int = 3, max_topics: int = 150) -> Dict[str, List[str]]:
    """Scans chunk text corpus-wide for capitalized phrases that recur
    across MULTIPLE DIFFERENT SOURCES (not just multiple times in one
    source) -- that cross-source recurrence is what makes something a
    genuinely shared topic worth linking automatically, rather than just
    a word one source's questioner happens to use a lot.

    NOTE -- single-source automatic detection was tried and reverted. The
    idea was sound (Ra-specific terms like "Maldek" deserve a topic page
    too), but the implementation kept failing the same way cross-source
    detection originally did: at large corpus size, ANY ordinary word
    eventually clears almost any simple frequency threshold within one
    source's questioner dialogue, the same way it eventually clears one
    across sources. Two different counting heuristics, same underlying
    failure mode. Source-specific terms are handled through
    CURATED_TOPICS instead now -- see build_topic_index.py's printed
    "candidates for review" list for terms worth manually promoting."""
    sources_by_phrase = defaultdict(set)
    sessions_by_phrase = defaultdict(set)
    mid_sentence_count = defaultdict(int)

    for chunk in chunks:
        text = chunk.get("text", "")
        source = chunk.get("source", "")
        session_uid = chunk.get("session_uid", "")
        for match in CANDIDATE_RE.finditer(text):
            normalized = match.group(1).strip()
            if normalized.lower() in NAME_BLOCKLIST:
                continue
            if len(normalized) < 4:
                continue
            if not _is_likely_real_topic(normalized):
                continue
            if _is_mid_sentence(text, match.start(1)):
                mid_sentence_count[normalized] += 1
            sources_by_phrase[normalized].add(source)
            sessions_by_phrase[normalized].add(session_uid)

    candidates = [
        (phrase, len(sources_by_phrase[phrase]), len(sessions_by_phrase[phrase]))
        for phrase in sources_by_phrase
        if len(sources_by_phrase[phrase]) >= min_sources
        and len(sessions_by_phrase[phrase]) >= min_sessions
        and mid_sentence_count[phrase] >= MIN_MID_SENTENCE_OCCURRENCES
    ]
    candidates.sort(key=lambda c: (c[1], c[2]), reverse=True)

    return {phrase: [phrase.lower()] for phrase, _, _ in candidates[:max_topics]}


def find_review_candidates(chunks: List[dict], min_single_source_sessions: int = 8,
                            max_candidates: int = 40) -> List[tuple]:
    """Does NOT add anything to the live alias map. Surfaces terms that
    recur heavily within a SINGLE source (the pattern real source-specific
    terminology like "Maldek" or "Overleaves" shows) so a human can look
    at the list and decide whether to promote individual ones into
    CURATED_TOPICS -- rather than trusting a frequency threshold to make
    that call automatically, which is exactly what kept going wrong.
    Returns [(phrase, source, session_count), ...] sorted by session_count."""
    sessions_by_source_by_phrase = defaultdict(lambda: defaultdict(set))
    mid_sentence_count = defaultdict(int)

    for chunk in chunks:
        text = chunk.get("text", "")
        source = chunk.get("source", "")
        session_uid = chunk.get("session_uid", "")
        for match in CANDIDATE_RE.finditer(text):
            normalized = match.group(1).strip()
            if normalized.lower() in NAME_BLOCKLIST or len(normalized) < 4:
                continue
            if not _is_likely_real_topic(normalized):
                continue
            if _is_mid_sentence(text, match.start(1)):
                mid_sentence_count[normalized] += 1
            sessions_by_source_by_phrase[normalized][source].add(session_uid)

    results = []
    for phrase, by_source in sessions_by_source_by_phrase.items():
        if mid_sentence_count[phrase] < MIN_MID_SENTENCE_OCCURRENCES:
            continue
        for source, sessions in by_source.items():
            if len(sessions) >= min_single_source_sessions:
                results.append((phrase, source, len(sessions)))

    results.sort(key=lambda r: r[2], reverse=True)
    return results[:max_candidates]


def build_topic_alias_map(automatic_topics: Dict[str, List[str]] = None) -> Dict[str, str]:
    """Flattens CURATED_TOPICS + automatic topics into {alias: canonical_name},
    all lowercase, for fast lookup. Curated entries always take priority --
    if an automatic candidate collides with a curated alias, the curated
    canonical name wins."""
    alias_map = {}

    if automatic_topics:
        for canonical, aliases in automatic_topics.items():
            alias_map[canonical.lower()] = canonical
            for alias in aliases:
                alias_map[alias.lower()] = canonical

    # curated entries applied last so they override any automatic collision
    for canonical, aliases in CURATED_TOPICS.items():
        alias_map[canonical.lower()] = canonical
        for alias in aliases:
            alias_map[alias.lower().strip()] = canonical

    return alias_map


def all_topic_names(automatic_topics: Dict[str, List[str]] = None) -> List[str]:
    names = set(CURATED_TOPICS.keys())
    if automatic_topics:
        names.update(automatic_topics.keys())
    return sorted(names)
