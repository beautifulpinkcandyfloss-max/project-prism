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
# Comprehensive English stopword list -- sourced from the widely-used
# NLTK English stopwords corpus, plus a handful of channeled-text
# specifics that the corpus doesn't catch ("indeed", "thus", "hence",
# "moreover", "perhaps" -- the kind of formal sentence-initial
# connectors that show up constantly in this kind of material).
#
# Baked in as a literal Python set rather than downloaded at runtime so
# this module stays self-contained and doesn't depend on a network call
# every time the index gets rebuilt.
COMMON_WORD_BLOCKLIST = {
    # --- NLTK English stopwords (the standard ~180-word list) ---
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "you're", "you've", "you'll", "you'd", "your", "yours", "yourself",
    "yourselves", "he", "him", "his", "himself", "she", "she's", "her",
    "hers", "herself", "it", "it's", "its", "itself", "they", "them",
    "their", "theirs", "themselves", "what", "which", "who", "whom",
    "this", "that", "that'll", "these", "those", "am", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having",
    "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for",
    "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "can", "will", "just", "don", "don't", "should",
    "should've", "now", "d", "ll", "m", "o", "re", "ve", "y", "ain",
    "aren", "aren't", "couldn", "couldn't", "didn", "didn't", "doesn",
    "doesn't", "hadn", "hadn't", "hasn", "hasn't", "haven", "haven't",
    "isn", "isn't", "ma", "mightn", "mightn't", "mustn", "mustn't",
    "needn", "needn't", "shan", "shan't", "shouldn", "shouldn't", "wasn",
    "wasn't", "weren", "weren't", "won", "won't", "wouldn", "wouldn't",

    # --- Channeled-text additions: formal/archaic connectors and very
    # common short responses that recur constantly in this kind of
    # transcript but aren't in the standard NLTK list ---
    "indeed", "thus", "hence", "moreover", "furthermore", "nevertheless",
    "however", "therefore", "perhaps", "maybe", "certainly", "clearly",
    "obviously", "absolute", "absolutely", "instead", "still", "yet",
    "yes", "okay", "alright", "ok", "thank", "thanks", "please", "well",
    "let", "go", "going", "gone", "come", "coming", "came", "say", "said",
    "says", "saying", "see", "saw", "seen", "seeing", "know", "knew",
    "known", "knowing", "think", "thought", "thinking", "feel", "felt",
    "feeling", "want", "wanted", "wanting", "give", "gave", "given",
    "giving", "take", "took", "taken", "taking", "make", "made", "making",
    "find", "found", "finding", "tell", "told", "telling", "ask", "asked",
    "asking", "true", "false", "right", "wrong", "first", "second",
    "third", "fourth", "fifth", "last", "next", "today", "tomorrow",
    "yesterday", "thing", "things", "way", "ways", "time", "times",
    "good", "great", "many", "much", "great", "small", "large", "big",
    "little", "new", "old", "young", "long", "short", "high", "low",
    "every", "everything", "everyone", "something", "someone", "anything",
    "anyone", "nothing", "whatever", "whoever", "whenever", "wherever",

    # --- Words specifically reported as still leaking through ---
    "according", "could", "should", "would", "without", "through",
    "throughout", "within", "whose", "allow", "allowed", "allowing",
    "work", "works", "worked", "working", "self", "part", "parts",
    "across", "around", "among", "amongst", "behind", "beyond", "beside",
    "besides", "above", "below", "during", "despite", "regarding",
    "concerning", "via", "vs", "etc", "i.e", "e.g",

    # --- Months and weekdays. These are technically proper nouns and
    # pass every noun-shape test, but they're never useful as topic
    # pages -- linking every mention of "Monday" or "December" is just
    # noise. ---
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",

    # --- Discourse markers and sentence-initial connectors that get
    # capitalized because of grammar, not because they're nouns.
    # Surfaced by inspecting a real generated topic_aliases.json: the
    # blocklist, the noun-shape heuristic, AND the mid-sentence check
    # all let these through because they often DO appear capitalized
    # mid-sentence inside quoted dialogue. Belt-and-suspenders: just
    # blocklist them by name. ---
    "yeah", "note", "imagine", "look", "remember", "speaking", "moving",
    "consider", "simply", "actually", "usually", "finally",
    "consequently", "rather", "even", "also", "another", "though",
    "although", "sometimes", "listen", "free", "back",
    "introduction", "session", "chapter", "book",
    # More discourse markers / generic nouns surfaced in the same review
    "since", "others", "three", "four", "form", "rest", "question",
    "mark", "biblical", "intelligent", "children",
}


# --- Heuristic noun/proper-noun detection (Option C from the design
# discussion). The blocklist alone can't keep up at scale: ordinary
# English has too many adverbs, modal verbs, and common verbs to
# enumerate exhaustively. These rules instead look at the SHAPE of a
# word -- its suffixes and a small set of recognizable function-word
# patterns -- to ask "is this even plausibly a noun?" before considering
# it as a topic candidate. ---

# Words that end this way are very rarely nouns: adverbs ("absolutely",
# "clearly"), present participles when standalone ("according",
# "allowing"), past tense or past participles ("allowed", "tested"),
# comparatives/superlatives ("greater", "greatest"). Some real nouns DO
# end this way (e.g. "ending", "meeting", "building") -- those are
# rescued by NOUN_SUFFIX_ALLOWLIST below, where we list known nouny
# exceptions for the most likely-collision endings.
NOUN_LIKELY_NEGATIVE_SUFFIXES = (
    "ly",      # adverbs: clearly, obviously, absolutely
    "ward",    # adverbs: forward, backward, toward
    "wise",    # adverbs: likewise, otherwise
)

# Suffixes that often indicate verbs but can also be real nouns -- we
# block them by default UNLESS the word's also in NOUN_SUFFIX_ALLOWLIST.
NOUN_AMBIGUOUS_SUFFIXES = ("ing", "ed", "er", "est")

# Common words that LOOK verb-y or adverb-y by suffix but are actually
# nouns we want to preserve. Extend this if you see false rejections.
NOUN_SUFFIX_ALLOWLIST = {
    "being", "beings", "meeting", "meetings", "ending", "endings",
    "building", "buildings", "feeling", "feelings", "teaching",
    "teachings", "learning", "understanding", "reading", "writing",
    "channeling", "transmission",
    "creator", "ancestor", "elder", "elders", "father", "mother",
    "brother", "sister", "leader", "leaders", "teacher", "teachers",
    "messenger", "messengers", "water", "matter", "letter", "member",
    "members", "manner", "number", "answer", "wonder", "border",
    "center", "corner", "power", "powers", "tower", "towers",
    "flower", "flowers",
    # Additional -er/-ter ending real nouns surfaced when reviewing
    # the alias map: planet names, religious/abstract nouns, ordinary
    # nouns that ARE nouns despite the suffix shape.
    "jupiter", "mercury", "saturn", "venus",
    "master", "masters", "prayer", "prayers",
    "wanderer", "wanderers", "speaker", "speakers", "listener",
    "listeners", "believer", "believers", "follower", "followers",
    "monster", "monsters", "stranger", "strangers", "soldier",
    "soldiers", "warrior", "warriors", "carpenter", "carpenters",
    "chamber", "chambers", "river", "rivers", "summer", "winter",
    "weather", "feather", "leather",
}


def _looks_like_noun(word: str) -> bool:
    """Best-effort heuristic answer to 'is this word plausibly a noun?'
    Rejects words whose shape strongly suggests another part of speech
    (adverbs ending in -ly, present participles ending in -ing without
    being on the allowlist, etc.). Not perfect -- a real POS tagger
    would do better -- but cheap, dependency-free, and catches the
    long tail of garbage that no reasonable blocklist would cover."""
    lower = word.lower()

    if lower in NOUN_SUFFIX_ALLOWLIST:
        return True

    for suffix in NOUN_LIKELY_NEGATIVE_SUFFIXES:
        if lower.endswith(suffix) and len(lower) > len(suffix) + 1:
            return False

    for suffix in NOUN_AMBIGUOUS_SUFFIXES:
        if lower.endswith(suffix) and len(lower) > len(suffix) + 1:
            return False

    return True


def _is_likely_real_topic(phrase: str) -> bool:
    """A phrase qualifies as a real topic candidate only if:
      (a) NONE of its words is a stopword, AND
      (b) every word in it plausibly looks like a noun.

    The blocklist catches the high-frequency closed-class garbage
    (modals, pronouns, conjunctions); the noun-shape heuristic catches
    the open-class long tail (adverbs, verbs, participles) that no
    finite blocklist can keep up with at corpus scale."""
    words = phrase.split()
    if not words:
        return False
    for w in words:
        if w.lower() in COMMON_WORD_BLOCKLIST:
            return False
        if not _looks_like_noun(w):
            return False
    return True


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
