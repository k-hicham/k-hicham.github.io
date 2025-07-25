#!/usr/bin/env python3
"""
fetch_news.py  –  Daily Brief (Swiss / EU RSS) + GNews fallback

• Pulls up to 5 articles per category:
      World Politics · Tech & AI · Finance & Economy · Innovation
  from curated Swiss / EU RSS feeds.
• If an RSS feed returns 0 items, the script falls back to GNews
  (free 300 req/day) using secret  GNEWS_KEY  and a simple keyword.
• Optional “Client Watch” block driven by variable  CLIENT_KEYWORD
  (or by passing an argument in the workflow).
• Injects/updates inside <section id="posts"> in  index.html.
  If that section doesn’t exist, it injects before </main>.
• Old brief (bounded by HTML comments) is removed automatically,
  so the block never duplicates.
"""

import datetime as dt
import html, os, re, sys, textwrap as tw

import feedparser         # pip install feedparser
import requests           # only needed for GNews fallback; already in runner

###############################################################################
#  CONFIGURE YOUR SOURCES HERE
###############################################################################

CATS = {
    "World Politics": [
        "https://www.swissinfo.ch/service/rss/rss?cid=44628456",
        "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
    ],
    "Tech & AI": [
        "https://www.nzz.ch/digital.rss",
        "https://www.handelszeitung.ch/taxonomy/term/14774/feed",
    ],
    "Finance & Economy": [
        "https://www.nzz.ch/wirtschaft.rss",
        "https://www.handelsblatt.com/contentexport/feed/finance.rss",
    ],
    "Innovation": [
        "https://www.sciencenews.org/feed",
        "https://www.swissinfo.ch/service/rss/rss?cid=41842338",
    ],
}

###############################################################################
#  OPTIONAL CLIENT WATCH
###############################################################################

CLIENT_QUERY = os.getenv("CLIENT_KEYWORD", "").strip()
# (you can also pass it as sys.argv[1] in the workflow step if you prefer)
if len(sys.argv) > 1:
    CLIENT_QUERY = " ".join(sys.argv[1:])

###############################################################################
#  GNEWS FALLBACK  (needs free API key  https://gnews.io)
###############################################################################

GNEWS_KEY = os.getenv("GNEWS_KEY", "").strip()
GNEWS_URL = (
    "https://gnews.io/api/v4/search?"
    "q={q}&lang={lang}&country=ch&max=10&token=" + GNEWS_KEY
)

###############################################################################
#  DEBUG switch – set to True to print feed counts in the log
###############################################################################
DEBUG = False

# --------------------------------------------------------------------------- #

def _fmt(entry) -> str:
    """Format one feedparser entry into a <li>"""
    title = html.escape(entry.title)
    link  = entry.link
    raw   = entry.get("summary", "") or entry.get("description", "")
    snippet = html.escape(re.sub("<[^>]+>", "", raw))[:260]
    return (
        f"<li><strong><a href=\"{link}\" target=\"_blank\">{title}</a></strong><br>"
        f"<p class=\"snippet\">{snippet} "
        f"<a href=\"{link}\" target=\"_blank\">Voir la suite →</a></p></li>"
    )


def _gnews_fallback(keyword: str, lang: str = "en"):
    """Return up to 5 entries from GNews for the given keyword."""
    if not GNEWS_KEY:
        return []  # Key not set → skip fallback
    url = GNEWS_URL.format(q=keyword, lang=lang)
    feed = feedparser.parse(url)
    if DEBUG:
        print(f"GNews {keyword!r} → {len(feed.entries)} items")
    return feed.entries[:5]


def _section(name: str, feeds: list[str]) -> str:
    """Build one category block, using fallback if necessary."""
    seen, items = set(), []

    for url in feeds:
        fp = feedparser.parse(url)
        if DEBUG:
            print(f"RSS  {url} → {len(fp.entries)} items")
        entries = fp.entries[:10] or _gnews_fallback(name.split()[0])
        for e in entries:
            if e.title in seen:
                continue
            seen.add(e.title)
            items.append(_fmt(e))
            if len(items) == 5:
                break
        if len(items) == 5:
            break

    if DEBUG:
        print(f"»» {name} final = {len(items)}")

    if not items:
        return ""  # skip empty category completely

    return tw.dedent(
        f"""
        <article>
            <h2>{name}</h2>
            <ul>
                {'\\n                '.join(items)}
            </ul>
        </article>
        """
    )


def _client_block(q: str) -> str:
    if not q:
        return ""
    entries = _gnews_fallback(q)
    if not entries:
        return ""
    lis = [_fmt(e) for e in entries]
    return tw.dedent(
        f"""
        <article>
            <h2>🔍 Client Watch – {html.escape(q)}</h2>
            <ul>
                {'\\n                '.join(lis)}
            </ul>
        </article>
        """
    )


def build_brief() -> str:
    today = dt.date.today().strftime("%d %b %Y")
    parts = [f"<article><h2>🗞️ Daily Brief – {today}</h2></article>"]
    for hdr, feeds in CATS.items():
        blk = _section(hdr, feeds)
        if blk:
            parts.append(blk)
    cb = _client_block(CLIENT_QUERY)
    if cb:
        parts.append(cb)
    return "\n".join(parts) if len(parts) > 1 else ""


# -------- inject into index.html ------------------------------------------ #
START, END = "<!-- DAILY BRIEF START -->", "<!-- DAILY BRIEF END -->"

try:
    html_txt = open("index.html", encoding="utf-8").read()
except FileNotFoundError:
    sys.exit("index.html missing")

# remove previous brief
html_txt = re.sub(f"{START}[\\s\\S]*?{END}", "", html_txt, flags=re.I)

brief_html = build_brief() or "<p><em>(No news fetched)</em></p>"
wrapped = f"{START}\n{brief_html}\n{END}"

# inject inside <section id="posts"> or fall back to </main>
m = re.search(r'<section[^>]*id=[\'"]posts[\'"][\\s\\S]*?</section>', html_txt, re.I)
if m:
    insert_at = m.end() - len("</section>")
else:
    if DEBUG:
        print("⚠️ id='posts' not found – inserting before </main>")
    end_main = html_txt.lower().rfind("</main>")
    insert_at = end_main if end_main != -1 else len(html_txt)

new_html = html_txt[:insert_at] + wrapped + html_txt[insert_at:]
open("index.html", "w", encoding="utf-8").write(new_html)

print("✅ Daily Brief injected –", len(brief_html), "chars")
