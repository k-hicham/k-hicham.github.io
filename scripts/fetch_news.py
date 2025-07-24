#!/usr/bin/env python3
"""
fetch_news.py – Daily Brief generator for My daily companion (v2.1)
------------------------------------------------------------------
• Builds a daily brief with clickable titles, snippet, « Voir la suite → »
  and an optional “Client Watch” section (driven by CLIENT_KEYWORD variable).
• Injects the brief *inside* <section id="posts"> and first removes any
  previous brief (bounded by HTML comments) to avoid duplication.

Environment expected by the GitHub Action
----------------------------------------
NEWS_KEY (secret)         – NewsAPI.org API key
CLIENT_KEYWORD (variable) – optional free‑text query (e.g. Purina OR "Nestlé Purina")
"""
import datetime as _dt
import html as _html
import os as _os
import re as _re
import sys as _sys
import textwrap as _tw
from typing import Dict, List

import requests as _r

API_KEY = _os.getenv("NEWS_KEY")
if not API_KEY:
    _sys.exit("❌ NEWS_KEY secret missing – add it as a repo secret")

CLIENT_Q = _os.getenv("CLIENT_KEYWORD", "").strip()

CATS = {
    "World Politics": "general",
    "Tech & AI": "technology",
    "Finance & Economy": "business",
    "Innovation": "science",
}

_US = ["us"]
_EU = ["gb", "fr", "de", "it", "es", "nl"]
COUNTRIES = _US + _EU

_ENDPOINT_TOP = "https://newsapi.org/v2/top-headlines"
_ENDPOINT_EVERY = "https://newsapi.org/v2/everything"
_HEADERS = {"User-Agent": "daily-brief-bot/2.1"}


def _api_get(url: str, **params):
    params["apiKey"] = API_KEY
    try:
        r = _r.get(url, params=params, headers=_HEADERS, timeout=12)
        data = r.json()
        if data.get("status") != "ok":
            raise RuntimeError(data.get("message", "unk error"))
        return data["articles"]
    except Exception as exc:
        print(f"⚠️ API error {url}: {exc}")
        return []


def _fetch_top(country: str, category: str):
    return _api_get(_ENDPOINT_TOP, country=country, category=category, pageSize=20, language="fr")


def _dedup(arts: List[Dict]):
    out, seen = [], set()
    for a in arts:
        t = a.get("title")
        if t and t not in seen:
            seen.add(t)
            out.append(a)
    return out


def _snippet(a: Dict):
    raw = a.get("description") or a.get("content") or ""
    raw = raw.split("[+")[0].strip()
    return _html.escape(raw[:260])


def _fmt_li(a: Dict):
    title = _html.escape(a.get("title", ""))
    url = a.get("url", "#")
    return (
        f"<li><strong><a href=\"{url}\" target=\"_blank\">{title}</a></strong><br>"
        f"<p class=\"snippet\">{_snippet(a)} <a href=\"{url}\" target=\"_blank\">Voir la suite →</a></p></li>"
    )


def _top_block(header: str, code: str):
    arts = []
    for cty in COUNTRIES:
        arts.extend(_fetch_top(cty, code))
    lis = [_fmt_li(a) for a in _dedup(arts)[:5]]
    return _tw.dedent(f"""
        <article>
            <h2>{header}</h2>
            <ul>
                {'\n                '.join(lis)}
            </ul>
        </article>""")


def _client_block(q: str):
    if not q:
        return ""
    arts = _api_get(_ENDPOINT_EVERY, q=q, language="en", pageSize=5, sortBy="publishedAt")
    if not arts:
        return ""
    lis = [_fmt_li(a) for a in arts[:5]]
    return _tw.dedent(f"""
        <article>
            <h2>🔍 Client Watch – {_html.escape(q)}</h2>
            <ul>
                {'\n                '.join(lis)}
            </ul>
        </article>""")


def build_brief():
    today = _dt.date.today().strftime("%d %b %Y")
    parts = [
        _tw.dedent(f"""
            <article>
                <h2>🗞️ Daily Brief – {today}</h2>
            </article>"""),
    ]
    parts.extend(_top_block(h, c) for h, c in CATS.items())
    cb = _client_block(CLIENT_Q)
    if cb:
        parts.append(cb)
    return "\n".join(parts)


MARKER_START = "<!-- DAILY BRIEF START -->"
MARKER_END = "<!-- DAILY BRIEF END -->"


def inject(block: str):
    path = "index.html"
    try:
        html = open(path, "r", encoding="utf-8").read()
    except FileNotFoundError:
        _sys.exit("index.html missing")

    # remove old brief
    html = _re.sub(f"{MARKER_START}[\s\S]*?{MARKER_END}", "", html, flags=_re.I)

    # find </section> within posts section
    m = _re.search(r"<section[^>]+id=\"posts\"[\s\S]*?</section>", html, _re.I)
    if not m:
        _sys.exit("<section id='posts'> not found")
    insert_pos = m.end() - len("</section>")

    wrapped = f"{MARKER_START}\n{block}\n{MARKER_END}"
    new_html = html[:insert_pos] + wrapped + html[insert_pos:]
    open(path, "w", encoding="utf-8").write(new_html)
    print("✅ Brief updated (links + snippet) & duplicates removed")


if __name__ == "__main__":
    inject(build_brief())
