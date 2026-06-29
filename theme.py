"""
Shared visual theme for Project Prism. One token system, injected into
every page, so the Q&A view and the Debate view feel like one instrument
rather than two different demos stapled together.

Concept: these are channeled TRANSMISSIONS, recorded across 50 years on
real instruments (reel-to-reel tape, typewriters, session logbooks). The
UI is styled like a receiver console for five different frequencies, not
generic new-age gradients/crystal clipart.
"""

import streamlit as st

# ---------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------

INK = "#0B0D12"          # base background -- near-black, faintly blue-green
PANEL = "#14171D"        # raised panel / card background
PANEL_RAISED = "#191D24"
SIGNAL = "#E8E6DE"       # primary text -- warm phosphor white
MUTED = "#8B8F98"        # secondary text
LINE = "#262A33"         # hairline borders/dividers
ACCENT = "#D6A24B"       # default accent (Ra amber) for buttons etc.

ENTITIES = {
    "ra": {
        "display_name": "Ra",
        "subtitle": "The Law of One",
        "color": "#D6A24B",
        "channeler": "Carla Rueckert",
    },
    "seth": {
        "display_name": "Seth",
        "subtitle": "The Seth Material",
        "color": "#4FA8A0",
        "channeler": "Jane Roberts",
    },
    "quo": {
        "display_name": "Q'uo",
        "subtitle": "The Q'uo Transcripts",
        "color": "#9388C9",
        "channeler": "Carla Rueckert / Jim McCarty",
    },
    "michael": {
        "display_name": "Michael",
        "subtitle": "The Michael Teachings",
        "color": "#7FA66B",
        "channeler": "Various channels",
    },
    "hathors": {
        "display_name": "The Hathors",
        "subtitle": "Hathor Planetary Messages",
        "color": "#C97FA0",
        "channeler": "Tom Kenyon",
    },
}

ENTITY_ORDER = ["ra", "seth", "quo", "michael", "hathors"]


def inject_theme():
    st.markdown(f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --ink: {INK};
            --panel: {PANEL};
            --panel-raised: {PANEL_RAISED};
            --signal: {SIGNAL};
            --muted: {MUTED};
            --line: {LINE};
            --accent: {ACCENT};
        }}

        .stApp {{
            background: var(--ink);
            color: var(--signal);
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
        }}

        h1, h2, h3, h4 {{
            font-family: 'Space Grotesk', sans-serif !important;
            letter-spacing: -0.01em;
        }}

        /* Eyebrow label above the main title */
        .prism-eyebrow {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.75rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 0.25rem;
        }}

        .prism-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.4rem;
            font-weight: 700;
            color: var(--signal);
            margin: 0;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }}

        .prism-baseline {{
            height: 1px;
            background: linear-gradient(90deg, var(--line) 0%, transparent 100%);
            margin: 1.1rem 0 1.6rem 0;
        }}

        .prism-subtitle {{
            color: var(--muted);
            font-size: 0.95rem;
            margin-top: -0.3rem;
        }}

        /* Inputs */
        .stTextInput input, .stTextArea textarea {{
            background: var(--panel) !important;
            color: var(--signal) !important;
            border: 1px solid var(--line) !important;
            font-family: 'IBM Plex Mono', monospace !important;
        }}

        .stButton button {{
            background: var(--accent) !important;
            color: #14110A !important;
            border: none !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-weight: 600 !important;
            letter-spacing: 0.02em;
            border-radius: 4px !important;
        }}

        .stButton button:hover {{
            filter: brightness(1.1);
        }}

        /* Nav radio styled as console tabs */
        div[role="radiogroup"] {{
            gap: 0.4rem;
        }}

        /* Hairline divider used between sections */
        .prism-hr {{
            height: 1px;
            background: var(--line);
            border: none;
            margin: 1.6rem 0;
        }}

        /* Source/turn card */
        .prism-card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 3px solid var(--card-accent, var(--accent));
            border-radius: 6px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.9rem;
        }}

        .prism-card-label {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--card-accent, var(--muted));
            margin-bottom: 0.4rem;
        }}

        .prism-card-body {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.92rem;
            line-height: 1.55;
            color: var(--signal);
        }}

        .prism-meta {{
            font-family: 'Inter', sans-serif;
            font-size: 0.78rem;
            color: var(--muted);
            margin-top: 0.5rem;
        }}

        /* Frequency strip -- the signature element on the debate page */
        .freq-strip {{
            display: flex;
            gap: 6px;
            margin: 0.4rem 0 1.6rem 0;
        }}

        .freq-band {{
            flex: 1;
            height: 6px;
            border-radius: 3px;
            background: var(--band-color, var(--line));
            opacity: 0.25;
            transition: opacity 0.4s ease, box-shadow 0.4s ease;
        }}

        .freq-band.active {{
            opacity: 1;
            box-shadow: 0 0 14px var(--band-color, var(--accent));
            animation: prism-pulse 1.1s ease-in-out infinite;
        }}

        @keyframes prism-pulse {{
            0%, 100% {{ opacity: 0.7; }}
            50% {{ opacity: 1; }}
        }}

        .freq-labels {{
            display: flex;
            gap: 6px;
            margin-bottom: 1.4rem;
        }}

        .freq-label {{
            flex: 1;
            text-align: center;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.68rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--label-color, var(--muted));
            opacity: 0.7;
        }}

        .freq-label.active {{
            opacity: 1;
        }}

        /* Tuning placeholder while a persona's turn is generating */
        .tuning {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.85rem;
            color: var(--muted);
        }}

        .tuning-dots span {{
            animation: tuning-blink 1.4s infinite;
        }}
        .tuning-dots span:nth-child(2) {{ animation-delay: 0.2s; }}
        .tuning-dots span:nth-child(3) {{ animation-delay: 0.4s; }}

        @keyframes tuning-blink {{
            0%, 80%, 100% {{ opacity: 0.2; }}
            40% {{ opacity: 1; }}
        }}

        /* Top nav bar -- link-based, drives the query-param router */
        .prism-nav {{
            display: flex;
            gap: 1.6rem;
            margin-bottom: 1.8rem;
            border-bottom: 1px solid var(--line);
            padding-bottom: 0.8rem;
        }}

        .prism-nav a {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.85rem;
            font-weight: 500;
            letter-spacing: 0.02em;
            color: var(--muted);
            text-decoration: none;
            padding-bottom: 0.3rem;
        }}

        .prism-nav a.active {{
            color: var(--signal);
            border-bottom: 2px solid var(--accent);
        }}

        .prism-nav a:hover {{
            color: var(--signal);
        }}

        /* Site-wide disclaimer footer */
        .prism-footer {{
            margin-top: 3rem;
            padding: 1.2rem 0;
            border-top: 1px solid var(--line);
            font-family: 'Inter', sans-serif;
            font-size: 0.78rem;
            line-height: 1.55;
            color: var(--muted);
            text-align: center;
        }}

        .prism-footer a {{
            color: var(--accent);
            text-decoration: none;
        }}

        .prism-footer a:hover {{
            text-decoration: underline;
        }}

        /* Internal topic links inline within transcript/answer text */
        a.prism-topic-link {{
            color: var(--accent);
            text-decoration: none;
            border-bottom: 1px dotted var(--accent);
        }}

        a.prism-topic-link:hover {{
            border-bottom-style: solid;
        }}

        /* Browse: source tiles + session list rows.
           NOTE: these use <span style="display:block"> rather than <div>
           for content nested inside <a> tags -- a <div> (block content)
           nested inside an <a> (inline content) is technically a valid
           HTML5 exception, but not every renderer implements that
           exception, and getting it wrong silently splits one link into
           multiple broken fragments. A block-styled <span> sidesteps the
           ambiguity entirely while looking identical. */
        .prism-tile {{
            display: block;
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 3px solid var(--card-accent, var(--accent));
            border-radius: 6px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.7rem;
            text-decoration: none;
        }}

        .prism-tile-title {{
            display: block;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            color: var(--signal);
            font-size: 1.05rem;
        }}

        .prism-tile-meta {{
            display: block;
            font-family: 'Inter', sans-serif;
            color: var(--muted);
            font-size: 0.82rem;
            margin-top: 0.2rem;
        }}

        .prism-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: 0.55rem 0.9rem;
            margin-bottom: 0.4rem;
            text-decoration: none;
        }}

        .prism-row-date {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.82rem;
            color: var(--signal);
        }}

        .prism-row-arrow {{
            color: var(--muted);
        }}

        /* Glossary/topic chip grid on the Learn page */
        .prism-chip-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.8rem 0 1.6rem 0;
        }}

        .prism-chip {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: var(--signal);
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.3rem 0.8rem;
            text-decoration: none;
        }}

        .prism-chip:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}

        /* Streamlit chrome cleanup */
        #MainMenu, footer, header {{ visibility: hidden; }}
        .block-container {{ padding-top: 2.2rem; max-width: 880px; }}
    </style>
    """, unsafe_allow_html=True)


NAV_ITEMS = [
    ("ask", "Ask the Archive"),
    ("debate", "Cosmic Debate Engine"),
    ("browse", "Browse"),
    ("learn", "Learn"),
]


def nav_bar(active_view: str):
    links = "".join(
        f'<a href="?view={key}" target="_self" class="{"active" if key == active_view else ""}">{label}</a>'
        for key, label in NAV_ITEMS
    )
    st.markdown(f'<div class="prism-nav">{links}</div>', unsafe_allow_html=True)


def page_header(eyebrow: str, title_html: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="prism-eyebrow">{eyebrow}</div>
    <div class="prism-title">{title_html}</div>
    {f'<div class="prism-subtitle">{subtitle}</div>' if subtitle else ''}
    <div class="prism-baseline"></div>
    """, unsafe_allow_html=True)


def frequency_strip_html(active_key: str = None) -> str:
    """Returns the raw HTML for the five-band frequency strip (the
    signature element). Exposed separately from frequency_strip() so it
    can be embedded inside a larger accumulating HTML block -- needed for
    live-updating views like the debate page, where the whole transcript
    + strip get redrawn together in a single placeholder each turn."""
    bands = "".join(
        f'<div class="freq-band {"active" if key == active_key else ""}" '
        f'style="--band-color: {ENTITIES[key]["color"]}"></div>'
        for key in ENTITY_ORDER
    )
    labels = "".join(
        f'<div class="freq-label {"active" if key == active_key else ""}" '
        f'style="--label-color: {ENTITIES[key]["color"]}">{ENTITIES[key]["display_name"]}</div>'
        for key in ENTITY_ORDER
    )
    return f'<div class="freq-strip">{bands}</div><div class="freq-labels">{labels}</div>'


def frequency_strip(active_key: str = None):
    """Standalone render -- use when the strip doesn't need to live
    inside a larger accumulating placeholder."""
    st.markdown(frequency_strip_html(active_key), unsafe_allow_html=True)


SITE_FOOTER_HTML = """
<div class="prism-footer">
  Project Prism is a non-commercial, not-for-profit open-source educational
  research tool built for study and synthesis. All source materials belong
  entirely to L/L Research and their respective copyright holders. Please
  support the original archives at
  <a href="https://www.llresearch.org" target="_blank" rel="noopener">llresearch.org</a>.
</div>
"""


def site_footer():
    """Renders the standard site-wide disclaimer footer. Call once at
    the end of every page's render function."""
    st.markdown(SITE_FOOTER_HTML, unsafe_allow_html=True)
