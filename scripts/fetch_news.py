#!/usr/bin/env python3
"""
fetch_news.py – Daily Brief from Swiss / EU RSS (no API limit)
"""

import datetime as dt, html, re, sys, textwrap as tw, feedparser

CATS = {
    "World Politics": [
        # RSS feeds covering EU / Swiss politics
        "https://www.swissinfo.ch/service/rss/rss?cid=44628456",          # swissinfo.ch politics
        "https://www.letemps.ch/rss/feed",                                # Le Temps
        "https://www.ft.com/world/europe?format=rss"                      # FT Europe
    ],
    "Tech & AI": [
        "https://www.handelszeitung.ch/taxonomy/term/14774/feed",         # Handelszeitung Digital
        "https://www.nzz.ch/digital.rss"                                  # NZZ Digital
    ],
    "Finance & Economy": [
        "https://www.handelsblatt.com/contentexport/feed/finance.rss",
        "https://www.nzz.ch/wirtschaft.rss"
    ],
    "Innovation": [
        "https://www.swissinfo.ch/service/rss/rss?cid=41842338",          # Innovation (swissinfo)
        "https://www.sciencealert.com/feed"                               # ScienceAlert EU friendly
    ],
}

CLIENT_QUERY = sys.argv[1] if len(sys.argv) > 1 else ""  # you can pass keyword in workflow args

def _fmt_item(entry):
    title = html.escape(entry.title)
    link  = entry.link
    snippet = html.escape(re.sub("<[^>]+>", "", entry.get("summary", "")))[:260]
    return f"<li><strong><a href=\"{link}\" target=\"_blank\">{title}</a></strong><br><p class=\"snippet\">{snippet} <a href=\"{link}\" target=\"_blank\">Voir la suite →</a></p></li>"

def section(name, feeds):
    seen = set()
    items_html = []
    for url in feeds:
        for e in feedparser.parse(url).entries[:10]:
            if e.title in seen: continue
            seen.add(e.title)
            items_html.append(_fmt_item(e))
            if len(items_html) == 5: break
        if len(items_html) == 5: break
    return tw.dedent(f"""
        <article>
            <h2>{name}</h2>
            <ul>
                {'\\n                '.join(items_html)}
            </ul>
        </article>""")

def client_block(q):
    if not q: return ""
    gnews = f"https://gnews.io/api/v4/search?q={q}&lang=en&country=ch&token=demo"  # replace demo with your token if you want
    entries = feedparser.parse(gnews).entries[:5]
    if not entries: return ""
    lis = [_fmt_item(e) for e in entries]
    return tw.dedent(f"""
        <article>
            <h2>🔍 Client Watch – {html.escape(q)}</h2>
            <ul>
                {'\\n                '.join(lis)}
            </ul>
        </article>""")

def build_brief():
    today = dt.date.today().strftime("%d %b %Y")
    parts = [f"<article><h2>🗞️ Daily Brief – {today}</h2></article>"]
    parts += [section(h, f) for h, f in CATS.items()]
    if CLIENT_QUERY:
        parts.append(client_block(CLIENT_QUERY))
    return "\\n".join(parts)

# --- inject into index.html (same logic as before) ------------------------
# ── replace the old inject() with this version ────────────────────────────────
def inject(block: str):
    """Insert DAILY BRIEF; tolerant if <section id="posts"> is absent."""
    START, END = "<!-- DAILY BRIEF START -->", "<!-- DAILY BRIEF END -->"

    try:
        html = open("index.html", encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit("index.html missing")

    # remove previous brief
    html = re.sub(f"{START}[\\s\\S]*?{END}", "", html, flags=re.I)

    # 1️⃣ try inside section id="posts"
    match = re.search(
        r'<section[^>]*id=[\'"]posts[\'"][\\s\\S]*?</section>',
        html,
        re.I,
    )
    if match:
        insert_at = match.end() - len("</section>")
    else:
        # 2️⃣ fallback: just before closing </main> (or EOF)
        m2 = html.lower().rfind("</main>")
        insert_at = m2 if m2 != -1 else len(html)
        print("⚠️  id='posts' not found – using fallback position")

    wrapped = f"{START}\n{block}\n{END}"
    new_html = html[:insert_at] + wrapped + html[insert_at:]
    open("index.html", "w", encoding="utf-8").write(new_html)
    print("✅ Daily Brief injected successfully")

