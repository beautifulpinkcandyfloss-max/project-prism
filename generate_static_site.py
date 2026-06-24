"""
Generates a real, static, crawlable HTML site from the SAME data the
Streamlit app already reads (processed_data/sessions, topic_index.json,
quotes_curated.json, learn_content.py). This is the actual fix for
discoverability -- not a Streamlit config tweak. Streamlit apps have no
real per-URL HTML for a crawler to read regardless of robots.txt or meta
tags; this script produces real .html files instead, one per session and
one per topic, each with a permanent URL, a real <title>, a real <meta
description>, and real <a href> links between pages.

DEPLOYMENT: this output is meant to sit ALONGSIDE the Streamlit app, not
replace it -- Streamlit stays the interactive tool; this static site is
the discovery layer. Two practical ways to serve it:

  1. Push static_site/ to any static host (Netlify, GitHub Pages,
     Cloudflare Pages) on its own subdomain or path, with Streamlit
     running separately for the interactive features.
  2. If you're running your own server with nginx in front of Streamlit
     anyway (you will need this regardless, for HTTPS), have nginx serve
     static_site/ directly at the root and reverse-proxy /app/ (or
     similar) through to Streamlit. This also solves the robots.txt /
     sitemap.xml problem, since nginx can serve real files at the root
     that Streamlit itself cannot.

Run:
    python generate_static_site.py
    python generate_static_site.py --base-url https://yourdomain.com
"""

import argparse
import html
import json
import os
import re

from scraper import load_all_sessions
from theme import ENTITIES, ENTITY_ORDER
from learn_content import (
    WHAT_IS_CHANNELING, SOURCE_PROFILES, FAQ_SECTIONS, CHANNELER_PROFILES,
    DENSITY_CHART, HISTORICAL_TIMELINE,
)

OUTPUT_DIR = "static_site"
TOPIC_INDEX_PATH = "processed_data/topic_index.json"
QUOTES_PATH = "processed_data/quotes_curated.json"

SITE_NAME = "Project Prism"
SITE_TAGLINE = "A searchable archive of channeled transcripts -- Ra, Seth, Q'uo, Michael, the Hathors."

ALLOWED_CRAWLERS = [
    "Googlebot", "Bingbot", "DuckDuckBot", "Slurp",
    "GPTBot", "ChatGPT-User", "Google-Extended", "ClaudeBot",
    "anthropic-ai", "PerplexityBot", "CCBot",
]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def esc(text) -> str:
    return html.escape(str(text or ""))


def page(title: str, description: str, body: str, canonical_path: str, base_url: str) -> str:
    canonical_url = base_url.rstrip("/") + canonical_path
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical_url)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary">
<style>
  body {{ background:#0B0D12; color:#E8E6DE; font-family:Georgia,'Times New Roman',serif;
          max-width:760px; margin:0 auto; padding:2rem 1.2rem; line-height:1.6; }}
  a {{ color:#D6A24B; }}
  h1,h2,h3 {{ font-family:Helvetica,Arial,sans-serif; }}
  .meta {{ color:#8B8F98; font-size:0.85rem; }}
  .nav {{ font-family:Helvetica,Arial,sans-serif; font-size:0.85rem; margin-bottom:1.5rem; }}
  .nav a {{ margin-right:1rem; text-decoration:none; }}
  .card {{ border-left:3px solid #D6A24B; padding:0.6rem 1rem; margin:0.8rem 0; background:#14171D; }}
</style>
</head>
<body>
<div class="nav"><a href="/">Home</a> <a href="/topics/">Topics</a> <a href="/learn/">Learn</a></div>
{body}
</body>
</html>"""


def write_page(path: str, content: str):
    full_path = os.path.join(OUTPUT_DIR, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)


def build_session_pages(sessions: list, generated_urls: list, base_url: str):
    grouped = {key: [] for key in ENTITY_ORDER}
    for s in sessions:
        grouped.setdefault(s["source"], []).append(s)

    for source, items in grouped.items():
        entity_name = ENTITIES.get(source, {}).get("display_name", source)
        index_rows = []
        for s in sorted(items, key=lambda s: (s.get("date") or "", s.get("session_uid", ""))):
            label = s.get("date") or s.get("session_number") or s.get("session_uid")
            url_path = f"/sessions/{s['session_uid']}.html"
            index_rows.append(f'<div class="card"><a href="{url_path}">{esc(label)}</a></div>')

            text_preview = (s.get("text") or "")[:155]
            session_body = f"""
<h1>{esc(entity_name)} \u2014 {esc(s.get('date') or s.get('session_number') or s['session_uid'])}</h1>
<p class="meta">Channeled by {esc(s.get('channeler') or 'Unknown')} &middot;
Participants: {esc(', '.join(s.get('participants') or []) or 'Not recorded')}</p>
<div>{esc(s.get('text') or '').replace(chr(10)+chr(10), '</p><p>')}</div>
<p><a href="/sources/{source}/">&larr; All {esc(entity_name)} sessions</a></p>
"""
            write_page(f"sessions/{s['session_uid']}.html", page(
                title=f"{entity_name} \u2014 {s.get('date') or s.get('session_uid')} | {SITE_NAME}",
                description=text_preview or f"A {entity_name} session from {SITE_NAME}, an archive of channeled transcripts.",
                body=session_body,
                canonical_path=url_path,
                base_url=base_url,
            ))
            generated_urls.append(url_path)

        source_body = f"""
<h1>{esc(entity_name)}</h1>
<p class="meta">{len(items)} session(s) archived.</p>
{''.join(index_rows)}
"""
        write_page(f"sources/{source}/index.html", page(
            title=f"{entity_name} \u2014 All Sessions | {SITE_NAME}",
            description=f"Every archived {entity_name} session, with full transcript text.",
            body=source_body,
            canonical_path=f"/sources/{source}/",
            base_url=base_url,
        ))
        generated_urls.append(f"/sources/{source}/")


def build_topic_pages(generated_urls: list, base_url: str):
    if not os.path.exists(TOPIC_INDEX_PATH):
        print("[SKIP] No topic_index.json found -- run build_topic_index.py first.")
        return

    with open(TOPIC_INDEX_PATH, "r", encoding="utf-8") as f:
        topic_index = json.load(f)

    chips = []
    for name, entries in sorted(topic_index.items(), key=lambda kv: len(kv[1]), reverse=True):
        slug = slugify(name)
        chips.append(f'<a href="/topics/{slug}.html">{esc(name)} ({len(entries)})</a>')

        rows = []
        for e in sorted(entries, key=lambda e: e.get("date") or ""):
            url_path = f"/sessions/{e['session_uid']}.html"
            rows.append(f'<div class="card"><a href="{url_path}">'
                        f'{esc(e.get("entity"))} \u2014 {esc(e.get("date") or e["session_uid"])}</a>'
                        f'<p class="meta">{esc(e.get("snippet", ""))}</p></div>')

        topic_body = f"""
<h1>{esc(name)}</h1>
<p class="meta">{len(entries)} session(s) across the archive mention this topic.</p>
{''.join(rows)}
"""
        write_page(f"topics/{slug}.html", page(
            title=f"{name} -- across Ra, Seth, Q'uo, Michael, and the Hathors | {SITE_NAME}",
            description=f"Every passage across {SITE_NAME}'s archive that discusses {name}.",
            body=topic_body,
            canonical_path=f"/topics/{slug}.html",
            base_url=base_url,
        ))
        generated_urls.append(f"/topics/{slug}.html")

    index_body = f"<h1>Topics</h1><p>{' &middot; '.join(chips)}</p>"
    write_page("topics/index.html", page(
        title=f"All Topics | {SITE_NAME}",
        description="Browse every recognized topic across the Project Prism archive.",
        body=index_body,
        canonical_path="/topics/",
        base_url=base_url,
    ))
    generated_urls.append("/topics/")


def build_learn_pages(generated_urls: list, base_url: str):
    sections = {
        "overview": ("Overview", WHAT_IS_CHANNELING),
        "faq": ("FAQ", "\n".join(f"<h3>{esc(i['question'])}</h3><p>{esc(i['answer'])}</p>" for i in FAQ_SECTIONS)),
        "channelers": ("The Channelers", "\n".join(
            f"<h3>{esc(p['name'])}</h3><p class='meta'>Channeled {esc(p['channels'])}</p><p>{esc(p['body'])}</p>"
            for p in CHANNELER_PROFILES)),
        "densities": ("Density Chart", "\n".join(
            f"<h3>{esc(d['density'])} Density -- {esc(d['name'])}</h3><p>{esc(d['description'])}</p>"
            for d in DENSITY_CHART)),
        "timeline": ("Timeline", "\n".join(
            f"<h3>{esc(t['era'])}</h3><p><b>As claimed:</b> {esc(t['claimed_event'])}</p>"
            f"<p><b>Mainstream view:</b> {esc(t['mainstream_view'])}</p>"
            for t in HISTORICAL_TIMELINE)),
    }

    if os.path.exists(QUOTES_PATH):
        with open(QUOTES_PATH, "r", encoding="utf-8") as f:
            quotes = json.load(f)
        if quotes:
            sections["quotes"] = ("Quotes", "\n".join(
                f'<div class="card">&ldquo;{esc(q.get("quote"))}&rdquo;'
                f'<p class="meta">{esc(q.get("entity"))} \u2014 {esc(q.get("date") or "undated")}'
                f'{" -- <a href=\"/sessions/" + esc(q["session_uid"]) + ".html\">view session</a>" if q.get("session_uid") else ""}'
                f'</p></div>'
                for q in quotes))

    nav_links = " &middot; ".join(f'<a href="/learn/{key}.html">{label}</a>' for key, (label, _) in sections.items())

    for key, (label, body_html) in sections.items():
        full_body = f"<h1>{esc(label)}</h1><p class='meta'>{nav_links}</p>{body_html}"
        write_page(f"learn/{key}.html", page(
            title=f"{label} | Learn | {SITE_NAME}",
            description=f"{label}: {SITE_TAGLINE}",
            body=full_body,
            canonical_path=f"/learn/{key}.html",
            base_url=base_url,
        ))
        generated_urls.append(f"/learn/{key}.html")

    write_page("learn/index.html", page(
        title=f"Learn | {SITE_NAME}",
        description=f"What is channeling, who the channelers were, and a glossary of recurring concepts. {SITE_TAGLINE}",
        body=f"<h1>Learn</h1><p>{nav_links}</p>",
        canonical_path="/learn/",
        base_url=base_url,
    ))
    generated_urls.append("/learn/")


def build_home_page(generated_urls: list, base_url: str):
    source_links = "".join(
        f'<div class="card"><a href="/sources/{key}/">{esc(ENTITIES[key]["display_name"])}</a>'
        f'<p class="meta">{esc(ENTITIES[key]["subtitle"])}</p></div>'
        for key in ENTITY_ORDER
    )
    body = f"""
<h1>{SITE_NAME}</h1>
<p>{esc(SITE_TAGLINE)}</p>
{source_links}
"""
    write_page("index.html", page(
        title=f"{SITE_NAME} -- Channeled Transcript Archive (Ra, Seth, Q'uo, Michael, the Hathors)",
        description=SITE_TAGLINE,
        body=body,
        canonical_path="/",
        base_url=base_url,
    ))
    generated_urls.append("/")


def build_sitemap(generated_urls: list, base_url: str):
    urls_xml = "".join(
        f"<url><loc>{esc(base_url.rstrip('/') + url)}</loc></url>"
        for url in generated_urls
    )
    sitemap = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls_xml}</urlset>'
    write_page("sitemap.xml", sitemap)


def build_robots_txt(base_url: str):
    lines = []
    for agent in ALLOWED_CRAWLERS:
        lines.append(f"User-agent: {agent}\nAllow: /\n")
    lines.append("User-agent: *\nAllow: /\n")
    lines.append(f"Sitemap: {base_url.rstrip('/')}/sitemap.xml\n")
    write_page("robots.txt", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://example.com",
                         help="Your real domain once deployed, e.g. https://projectprism.com")
    args = parser.parse_args()

    sessions = load_all_sessions()
    print(f"Loaded {len(sessions)} sessions")

    generated_urls = []
    build_home_page(generated_urls, args.base_url)
    build_session_pages(sessions, generated_urls, args.base_url)
    build_topic_pages(generated_urls, args.base_url)
    build_learn_pages(generated_urls, args.base_url)
    build_sitemap(generated_urls, args.base_url)
    build_robots_txt(args.base_url)

    print(f"\n[DONE] {len(generated_urls)} pages generated in {OUTPUT_DIR}/")
    print(f"sitemap.xml and robots.txt written, base URL: {args.base_url}")
    print("\nRemember to re-run this whenever your underlying data changes, "
          "the same way you re-run build_topic_index.py.")


if __name__ == "__main__":
    main()
