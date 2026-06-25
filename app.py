"""
Project Prism -- main console.

Views (driven by the ?view= query param, so every view is a real,
linkable URL -- clicking a topic link or a "view full session" link
navigates the browser, which Streamlit picks up via st.query_params):

    ask     - cross-source Q&A (default)
    debate  - the cosmic debate engine
    browse  - drill into any source -> any session -> full transcript
    learn   - what is channeling, profiles of each source, glossary
    topic   - a single topic's cross-source mentions, or the full topic
              index if no ?name= is given

Run: streamlit run app.py
"""

import os
from collections import defaultdict

import chromadb
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

from parsers.base import SOURCE_KEYS
from theme import inject_theme, page_header, frequency_strip_html, nav_bar, ENTITIES, ENTITY_ORDER
from debate_engine import run_debate, generate_followup_turn
from scraper import load_all_sessions
from linkify import linkify, topics_available
from rate_limit import check_rate_limit
from ensure_data import ensure_data
from utils import soften_all_caps, humanize_redactions
from learn_content import (
    WHAT_IS_CHANNELING, SOURCE_PROFILES, FAQ_SECTIONS, CHANNELER_PROFILES,
    DENSITY_CHART, HISTORICAL_TIMELINE,
)
import json as _json

load_dotenv()

CHROMA_DIR = "processed_data/chroma_db"
COLLECTION_NAME = "prism_transcripts"
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMENSIONS = 768
GENERATION_MODEL = "gemini-3.5-flash"
RESULTS_PER_SOURCE = 3

# Rate limits -- tune these to your actual budget/traffic comfort.
# Debate rounds cost ~6x a single Ask call (one per entity), so its
# per-client cap is set much lower accordingly.
ASK_PER_CLIENT_MAX, ASK_WINDOW = 20, 3600          # 20 questions/hour/client
DEBATE_PER_CLIENT_MAX, DEBATE_WINDOW = 5, 3600      # 5 full debates/hour/client
FOLLOWUP_PER_CLIENT_MAX, FOLLOWUP_WINDOW = 15, 3600  # 15 follow-ups/hour/client
GLOBAL_MAX, GLOBAL_WINDOW = 300, 3600               # 300 LLM-calling actions/hour, site-wide
TOPIC_INDEX_PATH = "processed_data/topic_index.json"
SESSIONS_PER_PAGE = 40

SOURCE_DISPLAY_NAMES = {key: ENTITIES[key]["display_name"] for key in SOURCE_KEYS}


# ---------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------

@st.cache_resource
def get_genai_client():
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        st.error("No GEMINI_API_KEY found. Add it to a .env file: GEMINI_API_KEY=your_key_here")
        st.stop()
    return genai.Client()


@st.cache_resource
def get_collection():
    if not os.path.isdir(CHROMA_DIR):
        st.error(f"No index found at {CHROMA_DIR}. Run `python embed.py` first.")
        st.stop()
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        return chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception:
        st.error(f"Couldn't open collection '{COLLECTION_NAME}'. Run `python embed.py` first.")
        st.stop()


@st.cache_data
def get_sessions_grouped():
    """source -> {session_uid: session_dict}, for the Browse view."""
    sessions = load_all_sessions()
    grouped = defaultdict(dict)
    for s in sessions:
        grouped[s["source"]][s["session_uid"]] = s
    return grouped


@st.cache_data
def get_topic_index():
    if not os.path.exists(TOPIC_INDEX_PATH):
        return {}
    with open(TOPIC_INDEX_PATH, "r", encoding="utf-8") as f:
        return _json.load(f)


def browse_link(source: str, uid: str) -> str:
    return f"?view=browse&source={source}&uid={uid}"


# ---------------------------------------------------------------------
# Q&A retrieval + synthesis
# ---------------------------------------------------------------------

def _flatten_html(html: str) -> str:
    """See debate engine's identical helper -- avoids Streamlit's
    markdown parser silently turning concatenated HTML blocks into a
    literal code block. Kept local here too since this module builds its
    own HTML blocks independently."""
    return "".join(line.strip() for line in html.strip().splitlines())


def embed_query(client, query: str):
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=[query],
        config=types.EmbedContentConfig(output_dimensionality=EMBED_DIMENSIONS),
    )
    return result.embeddings[0].values


def retrieve_context(client, collection, query: str, per_source: int = RESULTS_PER_SOURCE):
    query_vector = embed_query(client, query)
    all_results = []
    for source_key in SOURCE_KEYS:
        try:
            results = collection.query(
                query_embeddings=[query_vector], n_results=per_source,
                where={"source": source_key},
            )
        except Exception:
            continue
        ids = results.get("ids", [[]])[0]
        if not ids:
            continue
        for i in range(len(ids)):
            all_results.append({
                "chunk_id": ids[i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
    return all_results


def build_context_block(results: list) -> str:
    blocks = []
    for r in results:
        m = r["metadata"]
        header = (
            f"[Source: {SOURCE_DISPLAY_NAMES.get(m.get('source'), m.get('source'))} | "
            f"Entity: {m.get('entity')} | Channeler: {m.get('channeler')} | "
            f"Session: {m.get('session_number') or m.get('session_uid')} | "
            f"Date: {m.get('date') or 'undated'} | Participants: {m.get('participants')}]"
        )
        blocks.append(f"{header}\n{r['text']}")
    return "\n\n---\n\n".join(blocks)


QA_SYSTEM_INSTRUCTION = """You are the synthesis engine for Project Prism, an archive of \
channeled transcripts from sources claiming contact with non-physical or higher-density \
beings (Ra, Seth, Q'uo, Michael, the Hathors).

Write a comprehensive answer to the user's question, drawing ONLY on the passages provided. \
Attribute every claim to its source by name. Present each relevant perspective and note \
where they agree or diverge. Do not invent session numbers, dates, or names not present in \
the passages. If a source's passages don't meaningfully address the question, say so rather \
than forcing a connection. Write as your own synthesis, not in channeled-text register."""


def generate_answer(client, question: str, context_block: str) -> str:
    prompt = f"User's question: {question}\n\nRetrieved passages:\n\n{context_block}\n\nNow write the answer."
    response = client.models.generate_content(
        model=GENERATION_MODEL, contents=prompt,
        config=types.GenerateContentConfig(system_instruction=QA_SYSTEM_INSTRUCTION),
    )
    return response.text


# ---------------------------------------------------------------------
# Page: Ask
# ---------------------------------------------------------------------

def render_ask_page(client, collection):
    page_header(
        "Project Prism / Archive Query",
        "🔺 Ask the Archive",
        "One question, five channeled sources. See where they agree, and where they don't.",
    )

    question = st.text_input("Ask a question:", placeholder="How were the pyramids built?",
                              label_visibility="collapsed")
    ask_clicked = st.button("Ask", type="primary")

    if not ask_clicked:
        return
    if not question.strip():
        st.warning("Type a question first.")
        return

    allowed, limit_message = check_rate_limit(
        "asking questions", ASK_PER_CLIENT_MAX, ASK_WINDOW, GLOBAL_MAX, GLOBAL_WINDOW,
    )
    if not allowed:
        st.error(limit_message)
        return

    with st.spinner("Searching across all five sources..."):
        results = retrieve_context(client, collection, question)

    if not results:
        st.warning("No indexed content found. Run `python scraper.py` and `python embed.py` first.")
        return

    with st.spinner("Synthesizing answer..."):
        answer = generate_answer(client, question, build_context_block(results))

    st.markdown("#### Answer")
    st.markdown(linkify(answer), unsafe_allow_html=True)
    st.markdown('<hr class="prism-hr">', unsafe_allow_html=True)
    st.markdown(f"#### Sources &nbsp;<span style='color:var(--muted); font-size:0.8rem;'>"
                f"({len(results)} passages retrieved)</span>", unsafe_allow_html=True)

    by_source = {}
    for r in results:
        by_source.setdefault(r["metadata"].get("source", "unknown"), []).append(r)

    for source_key in SOURCE_KEYS:
        chunks = by_source.get(source_key)
        if not chunks:
            continue
        color = ENTITIES[source_key]["color"]
        st.markdown(f"<div style='color:{color}; font-family:Space Grotesk,sans-serif; "
                    f"font-weight:600; margin: 0.8rem 0 0.4rem 0;'>{SOURCE_DISPLAY_NAMES[source_key]}</div>",
                    unsafe_allow_html=True)
        for r in chunks:
            m = r["metadata"]
            session_label = m.get("session_number") or m.get("session_uid")
            with st.expander(f"Session {session_label} — {m.get('date') or 'undated'} "
                              f"(distance {r['distance']:.3f})"):
                raw_text = soften_all_caps(r["text"]) if source_key == "michael" else r["text"]
                if source_key == "michael":
                    raw_text = humanize_redactions(raw_text)
                body = linkify(raw_text).replace("\n", "<br>")
                link = browse_link(source_key, m.get("session_uid", ""))
                card_html = f"""
                <div class="prism-card" style="--card-accent: {color}; border-left: none; padding: 0;">
                    <div class="prism-meta">Channeler: {m.get('channeler') or 'Unknown'} &nbsp;|&nbsp;
                    Participants: {m.get('participants') or 'Unknown'}</div>
                    <div class="prism-card-body" style="margin-top:0.6rem;">{body}</div>
                    <div class="prism-meta" style="margin-top:0.6rem;">
                        <a href="{link}" target="_self" class="prism-topic-link">View full session &rarr;</a>
                    </div>
                </div>
                """
                st.markdown(_flatten_html(card_html), unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Page: Cosmic Debate
# ---------------------------------------------------------------------

def render_turn_card(turn: dict) -> str:
    chips = ""
    for c in turn["grounding_chunks"]:
        m = c["metadata"]
        session_label = m.get("session_number") or m.get("session_uid")
        link = browse_link(turn["entity_key"], m.get("session_uid", ""))
        chips += (f'<a href="{link}" target="_self" style="font-family:IBM Plex Mono,monospace; font-size:0.68rem; '
                  f'color:{turn["color"]}; border:1px solid {turn["color"]}40; '
                  f'border-radius:3px; padding:1px 6px; margin-right:4px; text-decoration:none;">'
                  f'Session {session_label}</a>')
    if not chips:
        chips = '<span style="font-size:0.72rem; color:var(--muted);">no closely matching archive passage</span>'

    followup_tag = (' &nbsp;\u00b7&nbsp; <span style="font-style:italic; opacity:0.7;">follow-up</span>'
                     if turn.get("is_followup") else "")

    raw_text = soften_all_caps(turn["text"]) if turn["entity_key"] == "michael" else turn["text"]
    if turn["entity_key"] == "michael":
        raw_text = humanize_redactions(raw_text)
    body = linkify(raw_text).replace("\n", "<br>")
    html = f"""
    <div class="prism-card" style="--card-accent: {turn['color']};">
        <div class="prism-card-label" style="--card-accent: {turn['color']};">
            {turn['display_name']} &nbsp;\u00b7&nbsp; channeled by {turn['channeler']}{followup_tag}
        </div>
        <div class="prism-card-body">{body}</div>
        <div class="prism-meta">{chips}</div>
    </div>
    """
    return _flatten_html(html)


def render_debate_page(client, collection):
    page_header(
        "Project Prism / Cosmic Debate Engine",
        "🔺 Tune In",
        "State a premise. Five frequencies respond, in their own voice, grounded in their own archive.",
    )

    if "debate_state" not in st.session_state:
        st.session_state.debate_state = {"premise": None, "turns": []}
    state = st.session_state.debate_state

    if not state["turns"]:
        premise = st.text_area("State a premise:", placeholder="Explain the concept of evil.",
                                label_visibility="collapsed", height=80, key="debate_premise")
        begin_clicked = st.button("Begin Transmission", type="primary", key="debate_begin")

        if not begin_clicked:
            st.markdown(frequency_strip_html(active_key=None), unsafe_allow_html=True)
            return
        if not premise.strip():
            st.warning("State a premise first.")
            st.markdown(frequency_strip_html(active_key=None), unsafe_allow_html=True)
            return

        allowed, limit_message = check_rate_limit(
            "starting debates", DEBATE_PER_CLIENT_MAX, DEBATE_WINDOW, GLOBAL_MAX, GLOBAL_WINDOW,
        )
        if not allowed:
            st.error(limit_message)
            st.markdown(frequency_strip_html(active_key=None), unsafe_allow_html=True)
            return

        state["premise"] = premise

    placeholder = st.empty()

    def render_transcript(active_key=None):
        cards_html = "".join(render_turn_card(t) for t in state["turns"])
        tuning_html = ""
        if active_key:
            name = ENTITIES[active_key]["display_name"]
            tuning_html = (
                f'<div class="tuning">Tuning into {name}'
                f'<span class="tuning-dots"><span>.</span><span>.</span><span>.</span></span></div>'
            )
        placeholder.markdown(
            frequency_strip_html(active_key) + cards_html + tuning_html,
            unsafe_allow_html=True,
        )

    if not state["turns"] and state["premise"]:
        # Initial round -- all five speak in order, full-length turns.
        render_transcript(active_key=ENTITY_ORDER[0])
        for turn in run_debate(client, collection, state["premise"]):
            state["turns"].append(turn)
            next_index = len(state["turns"])
            next_active = ENTITY_ORDER[next_index] if next_index < len(ENTITY_ORDER) else None
            render_transcript(active_key=next_active)
    else:
        render_transcript()

    if not state["turns"]:
        return

    # --- Follow-up section ---
    st.markdown('<hr class="prism-hr">', unsafe_allow_html=True)
    st.markdown("#### Ask a follow-up")
    st.markdown('<p class="prism-subtitle" style="margin-top:-0.4rem;">'
                'Push back, ask for more detail, or get a quick reaction -- replies stay short.</p>',
                unsafe_allow_html=True)

    display_to_key = {ENTITIES[k]["display_name"]: k for k in ENTITY_ORDER}
    target_label = st.selectbox("Direct your follow-up to:",
                                 ["All Five"] + [ENTITIES[k]["display_name"] for k in ENTITY_ORDER],
                                 key="followup_target")
    followup_text = st.text_input("Follow-up question:", key="followup_question",
                                   placeholder="Can you say more about that?")
    followup_clicked = st.button("Send Follow-up", key="followup_send")

    if followup_clicked:
        if not followup_text.strip():
            st.warning("Type a follow-up question first.")
        else:
            targets = ENTITY_ORDER if target_label == "All Five" else [display_to_key[target_label]]
            for entity_key in targets:
                allowed, limit_message = check_rate_limit(
                    "follow-up questions", FOLLOWUP_PER_CLIENT_MAX, FOLLOWUP_WINDOW,
                    GLOBAL_MAX, GLOBAL_WINDOW,
                )
                if not allowed:
                    st.error(limit_message)
                    break
                render_transcript(active_key=entity_key)
                turn = generate_followup_turn(
                    client, collection, entity_key, followup_text, state["premise"], state["turns"]
                )
                state["turns"].append(turn)
            render_transcript()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Start a New Debate", key="debate_reset"):
        st.session_state.debate_state = {"premise": None, "turns": []}
        st.rerun()


# ---------------------------------------------------------------------
# Page: Browse
# ---------------------------------------------------------------------

def render_browse_page():
    params = st.query_params
    source = params.get("source")
    uid = params.get("uid")
    page_num = int(params.get("page", "1") or "1")

    sessions_grouped = get_sessions_grouped()

    if not source:
        page_header("Project Prism / Browse", "🔺 Browse the Archive",
                    "Drill into any source, any session, full transcript.")
        for key in SOURCE_KEYS:
            count = len(sessions_grouped.get(key, {}))
            color = ENTITIES[key]["color"]
            subtitle = ENTITIES[key]["subtitle"]
            st.markdown(_flatten_html(f"""
            <a href="?view=browse&source={key}" target="_self" class="prism-tile" style="--card-accent: {color};">
                <span class="prism-tile-title">{ENTITIES[key]['display_name']}</span>
                <span class="prism-tile-meta">{subtitle} &nbsp;\u00b7&nbsp; {count} session(s) indexed</span>
            </a>
            """), unsafe_allow_html=True)
        return

    if source not in SOURCE_KEYS:
        st.error(f"Unknown source '{source}'.")
        return

    sessions = sessions_grouped.get(source, {})

    if not uid:
        color = ENTITIES[source]["color"]
        page_header("Project Prism / Browse",
                     f"🔺 {ENTITIES[source]['display_name']}",
                     f"{len(sessions)} session(s) \u00b7 channeled by {ENTITIES[source]['channeler']}")
        st.markdown('<a href="?view=browse" target="_self" class="prism-topic-link">&larr; All sources</a>',
                    unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        sorted_sessions = sorted(
            sessions.values(),
            key=lambda s: (s.get("date") or "", s.get("session_uid", "")),
        )

        total_pages = max(1, (len(sorted_sessions) - 1) // SESSIONS_PER_PAGE + 1)
        page_num = min(max(1, page_num), total_pages)
        start = (page_num - 1) * SESSIONS_PER_PAGE
        page_items = sorted_sessions[start:start + SESSIONS_PER_PAGE]

        for s in page_items:
            primary_label = s.get("date") or (
                f"Session {s.get('session_number')}" if s.get("session_number") else None
            ) or s["session_uid"]
            link = browse_link(source, s["session_uid"])
            st.markdown(_flatten_html(f"""
            <a href="{link}" target="_self" class="prism-row">
                <span class="prism-row-date">{primary_label}</span>
                <span class="prism-meta" style="margin:0;">{s['session_uid']}</span>
                <span class="prism-row-arrow">&rarr;</span>
            </a>
            """), unsafe_allow_html=True)

        if total_pages > 1:
            nav = " ".join(
                f'<a href="?view=browse&source={source}&page={p}" target="_self" class="prism-topic-link">{p}</a>'
                if p != page_num else f'<b>{p}</b>'
                for p in range(1, total_pages + 1)
            )
            st.markdown(f"<div style='margin-top:1rem;'>{nav}</div>", unsafe_allow_html=True)
        return

    session = sessions.get(uid)
    if not session:
        st.error(f"Session '{uid}' not found in source '{source}'.")
        return

    color = ENTITIES[source]["color"]
    page_header("Project Prism / Browse",
                 f"🔺 {session.get('date') or session.get('session_number') or uid}",
                 f"{ENTITIES[source]['display_name']} \u00b7 channeled by {session.get('channeler') or 'Unknown'}")
    st.markdown(f'<a href="?view=browse&source={source}" target="_self" class="prism-topic-link">'
                f'&larr; All {ENTITIES[source]["display_name"]} sessions</a>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    participants = session.get("participants") or []
    raw_text = soften_all_caps(session.get("text", "")) if source == "michael" else session.get("text", "")
    if source == "michael":
        raw_text = humanize_redactions(raw_text)
    body = linkify(raw_text).replace("\n", "<br>")
    participants_label = ', '.join(participants) if participants else 'Not recorded in original transcript'
    html = f"""
    <div class="prism-card" style="--card-accent: {color};">
        <div class="prism-meta">Participants: {participants_label}</div>
        <div class="prism-card-body" style="margin-top:0.6rem;">{body}</div>
    </div>
    """
    st.markdown(_flatten_html(html), unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Page: Topic
# ---------------------------------------------------------------------

def render_topic_page():
    params = st.query_params
    name = params.get("name")
    topic_index = get_topic_index()

    if not topics_available():
        page_header("Project Prism / Topics", "🔺 Topics", "")
        st.warning("No topic index found yet. Run `python build_topic_index.py` first.")
        return

    if not name:
        page_header("Project Prism / Topics", "🔺 All Topics",
                    f"{len(topic_index)} recognized topic(s), linked across every source that mentions them.")
        ranked = sorted(topic_index.items(), key=lambda kv: len(kv[1]), reverse=True)
        chips = "".join(
            f'<a href="?view=topic&name={t}" target="_self" class="prism-chip">{t} ({len(entries)})</a>'
            for t, entries in ranked
        )
        st.markdown(f'<div class="prism-chip-grid">{chips}</div>', unsafe_allow_html=True)
        return

    entries = topic_index.get(name)
    page_header("Project Prism / Topics", f"🔺 {name}",
                f"{len(entries) if entries else 0} session(s) mention this topic.")
    st.markdown('<a href="?view=topic" target="_self" class="prism-topic-link">&larr; All topics</a>',
                unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)

    if not entries:
        st.info("No mentions of this topic found in the current archive.")
        return

    sorted_entries = sorted(entries, key=lambda e: (e.get("date") or ""))
    for e in sorted_entries:
        color = ENTITIES.get(e["source"], {}).get("color", "#8B8F98")
        link = browse_link(e["source"], e["session_uid"])
        label = e.get("date") or e.get("session_uid")
        html = f"""
        <a href="{link}" target="_self" class="prism-tile" style="--card-accent: {color};">
            <span class="prism-tile-title">{SOURCE_DISPLAY_NAMES.get(e['source'], e['source'])} &nbsp;\u00b7&nbsp; {label}</span>
            <span class="prism-tile-meta">{e.get('snippet', '')}</span>
        </a>
        """
        st.markdown(_flatten_html(html), unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Page: Learn
# ---------------------------------------------------------------------

LEARN_SECTIONS = [
    ("overview", "Overview"),
    ("faq", "FAQ"),
    ("channelers", "The Channelers"),
    ("densities", "Density Chart"),
    ("timeline", "Timeline"),
    ("quotes", "Quotes"),
    ("glossary", "Glossary"),
]


def _learn_sub_nav(active: str):
    links = "".join(
        f'<a href="?view=learn&section={key}" target="_self" '
        f'class="{"active" if key == active else ""}">{label}</a>'
        for key, label in LEARN_SECTIONS
    )
    st.markdown(f'<div class="prism-nav" style="margin-top:-0.4rem;">{links}</div>',
                unsafe_allow_html=True)


def _render_learn_overview():
    st.markdown(WHAT_IS_CHANNELING)
    st.markdown('<hr class="prism-hr">', unsafe_allow_html=True)
    st.markdown("#### The Five Sources")
    for profile in SOURCE_PROFILES:
        color = ENTITIES[profile["key"]]["color"]
        html = f"""
        <div class="prism-card" style="--card-accent: {color};">
            <div class="prism-card-label" style="--card-accent: {color};">{profile['title']}</div>
            <div class="prism-meta" style="font-size:0.88rem; line-height:1.5; color:var(--signal);">{profile['body']}</div>
        </div>
        """
        st.markdown(_flatten_html(html), unsafe_allow_html=True)


def _render_learn_faq():
    for item in FAQ_SECTIONS:
        with st.expander(item["question"]):
            st.markdown(item["answer"])


def _render_learn_channelers():
    for profile in CHANNELER_PROFILES:
        color = ENTITIES.get(profile["key"].split("_")[0], {}).get("color", "#8B8F98")
        html = f"""
        <div class="prism-card" style="--card-accent: {color};">
            <div class="prism-card-label" style="--card-accent: {color};">
                {profile['name']} &nbsp;\u00b7&nbsp; channeled {profile['channels']}
            </div>
            <div class="prism-meta" style="font-size:0.88rem; line-height:1.5; color:var(--signal);">{profile['body']}</div>
        </div>
        """
        st.markdown(_flatten_html(html), unsafe_allow_html=True)


def _render_learn_densities():
    st.markdown("This numbered density system belongs specifically to the Ra/Confederation "
                "material (Ra, Q'uo, Hatonn, Latwii) -- Seth and Michael use different "
                "frameworks entirely, not directly equivalent to this one.")
    st.markdown("<br>", unsafe_allow_html=True)
    for d in DENSITY_CHART:
        html = f"""
        <div class="prism-card" style="--card-accent: #D6A24B;">
            <div class="prism-card-label" style="--card-accent: #D6A24B;">
                {d['density']} Density &nbsp;\u00b7&nbsp; {d['name']}
            </div>
            <div class="prism-meta" style="font-size:0.88rem; line-height:1.5; color:var(--signal);">{d['description']}</div>
        </div>
        """
        st.markdown(_flatten_html(html), unsafe_allow_html=True)


def _render_learn_timeline():
    st.markdown("Claimed events are shown alongside the mainstream historical/scientific "
                "view for comparison -- see the FAQ for why that distinction matters.")
    st.markdown("<br>", unsafe_allow_html=True)
    for t in HISTORICAL_TIMELINE:
        html = f"""
        <div class="prism-card" style="--card-accent: #9388C9;">
            <div class="prism-card-label" style="--card-accent: #9388C9;">{t['era']}</div>
            <div class="prism-meta" style="font-size:0.88rem; line-height:1.5; color:var(--signal);">
                <b>As claimed:</b> {t['claimed_event']}<br><br>
                <b>Mainstream view:</b> {t['mainstream_view']}
            </div>
        </div>
        """
        st.markdown(_flatten_html(html), unsafe_allow_html=True)


def _render_learn_quotes():
    curated_path = "processed_data/quotes_curated.json"
    if not os.path.exists(curated_path):
        st.info("No curated quotes yet. Run `python find_quote_candidates.py` to pull "
                "candidates from your own archive, review them, and add your favorites "
                "to processed_data/quotes_curated.json.")
        return
    with open(curated_path, "r", encoding="utf-8") as f:
        quotes = _json.load(f)
    if not quotes:
        st.info("processed_data/quotes_curated.json exists but is empty -- add your "
                "picked quotes there to see them here.")
        return
    for q in quotes:
        source = q.get("source", "")
        color = ENTITIES.get(source, {}).get("color", "#8B8F98")
        link = browse_link(source, q.get("session_uid", "")) if q.get("session_uid") else None
        link_html = (f'<a href="{link}" target="_self" class="prism-topic-link">View full session &rarr;</a>'
                     if link else "")
        html = f"""
        <div class="prism-card" style="--card-accent: {color};">
            <div class="prism-card-body" style="font-style:italic;">&ldquo;{linkify(q.get('quote', ''))}&rdquo;</div>
            <div class="prism-meta">{q.get('entity', '')} &nbsp;\u00b7&nbsp; {q.get('date') or 'undated'} &nbsp;\u00b7&nbsp; {link_html}</div>
        </div>
        """
        st.markdown(_flatten_html(html), unsafe_allow_html=True)


def _render_learn_glossary():
    st.markdown("Click any term to see every passage, across every source, that discusses it.")
    if topics_available():
        st.markdown('<a href="?view=topic" target="_self" class="prism-topic-link">Browse the full topic index &rarr;</a>',
                    unsafe_allow_html=True)
    else:
        st.info("Run `python build_topic_index.py` to enable the glossary.")


def render_learn_page():
    params = st.query_params
    section = params.get("section", "overview")
    if section not in dict(LEARN_SECTIONS):
        section = "overview"

    page_header("Project Prism / Learn", "🔺 Learn", "")
    _learn_sub_nav(section)

    if section == "faq":
        render_func = _render_learn_faq
    elif section == "channelers":
        render_func = _render_learn_channelers
    elif section == "densities":
        render_func = _render_learn_densities
    elif section == "timeline":
        render_func = _render_learn_timeline
    elif section == "quotes":
        render_func = _render_learn_quotes
    elif section == "glossary":
        render_func = _render_learn_glossary
    else:
        render_func = _render_learn_overview

    render_func()


# ---------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Project Prism — Channeled Transcript Archive",
        page_icon="🔺",
        layout="centered",
    )

    # Visible status during first-boot data download. We surface this in
    # the UI rather than relying on print() because some hosts
    # (Streamlit Cloud included) don't reliably show stdout in their app
    # log -- the user would see only the downstream "no index" error,
    # with no way to tell why. A visible spinner here makes the actual
    # state of the download obvious.
    import os as _os
    if not _os.path.isdir("processed_data/chroma_db"):
        from ensure_data import _get_data_url
        url_present = bool(_get_data_url())
        if not url_present:
            st.error(
                "First-boot setup hasn't completed: the prebuilt data zip URL "
                "(`PRISM_DATA_URL`) is not configured. Add it under the app's "
                "**Secrets** settings (see `ensure_data.py` docstring for the "
                "exact format), then reboot the app."
            )
            st.stop()
        with st.spinner("First-boot setup: downloading prebuilt archive data... "
                         "(this only happens once per deploy)"):
            try:
                ensure_data()
            except Exception as exc:
                st.error(f"Data download failed: {type(exc).__name__}: {exc}")
                st.stop()
        if not _os.path.isdir("processed_data/chroma_db"):
            st.error(
                "Data download completed without raising, but "
                "`processed_data/chroma_db` still isn't present. The zip may "
                "be malformed -- check that you zipped the `processed_data` "
                "folder ITSELF (not its contents) so the archive contains a "
                "top-level `processed_data/` directory."
            )
            st.stop()
    # Best-effort only -- this helps the browser tab title and, for some
    # platforms, link-preview cards when someone shares a URL. It does
    # NOT help Google/AI crawlers: Streamlit serves the same empty SPA
    # shell to every request regardless of what gets injected here after
    # the page loads, since crawlers read the initial HTML response, not
    # what JS adds afterward. Real crawlability is what static_site/
    # (via generate_static_site.py) is for.
    st.markdown(
        '<meta name="description" content="Project Prism: a searchable, cross-referenced '
        'archive of channeled transcripts from Ra, Seth, Q\'uo, Michael, and the Hathors, '
        'with AI synthesis and a multi-entity debate engine.">',
        unsafe_allow_html=True,
    )
    inject_theme()

    params = st.query_params
    view = params.get("view", "ask")
    nav_active = view if view in ("ask", "debate", "browse", "learn") else "browse"
    nav_bar(nav_active)

    if view == "debate":
        client = get_genai_client()
        collection = get_collection()
        render_debate_page(client, collection)
    elif view == "browse":
        render_browse_page()
    elif view == "topic":
        render_topic_page()
    elif view == "learn":
        render_learn_page()
    else:
        client = get_genai_client()
        collection = get_collection()
        render_ask_page(client, collection)


if __name__ == "__main__":
    main()
