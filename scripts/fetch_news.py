#!/usr/bin/env python3
"""
fetch_news.py – Daily Brief generator for My daily companion
-----------------------------------------------------------
• Pulls up to 5 headlines per category (Politics, Tech & AI, Finance & Economy, Innovation)
  from NewsAPI.org, mixing US + selected EU countries.
• Builds a <article> HTML block with clickable titles + 1‑2 sentence snippet.
• Optional extra section "Client Watch" driven by repo variable CLIENT_KEYWORD.

Required secrets / variables in GitHub Actions:
  NEWS_KEY         – NewsAPI key (secret)
  CLIENT_KEYWORD   – optional free‑text query for client monitoring (variable)
"""
import datetime as _dt
import html as _html
import os as _os
import sys as _sys
import textwrap as _tw
from typing import List, Dict

import requests as _r

API_KEY = _os.getenv("NEWS_KEY")
if not API_KEY:
    _sys.exit("❌ NEWS_KEY secret not set in GitHub repo")

CLIENT_Q = _os.getenv("CLIENT_KEYWORD", "").strip()

# Categories we surface and their NewsAPI categories
CATS = {
    "World Politics": "general",   # NewsAPI lacks explicit politics cat – use general and query later? keep as is
    "Tech & AI": "technology",
    "Finance & Economy": "business",
    "Innovation": "science",
}

# Countries to blend (ISO‑2). Free NewsAPI allows only one country per request.
_US = ["us"]
_EU = ["gb", "fr", "de", "it", "es", "nl"]
COUNTRY_ROLL = _US + _EU

_ENDPOINT_TOP = "https://newsapi.org/v2/top-headlines"
_ENDPOINT_EVERY = "https://newsapi.org/v2/everything"

_HEADERS = {"User-Agent": "daily‑brief‑bot/1.0"}


def _fetch_top(country: str, category: str) -> List[Dict]:
    params = {
        "apiKey": API_KEY,
        "country": country,
        "category": category,
        "pageSize": 20,
        "language": "en",
    }
    try:
        resp = _r.get(_ENDPOINT_TOP, params=params, headers=_HEADERS, timeout=10)
        data = resp.json()
        if data.get("status") != "ok":
            raise RuntimeError(data.get("message", "unknown error"))
        return data.get("articles", [])
    except Exception as exc:
        print(f"⚠️  top-headlines error for {country}/{category}: {exc}")
        return []


def _dedup(arts: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for a in arts:
        t = a.get("title")
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(a)
    return out


def _select_snippet(a: Dict) -> str:
    cand = a.get("description") or a.get("content") or ""
    # Clean trailing [...] pieces
    cand = cand.split("[+")[0].strip()
    return _html.escape(cand[:300])


def get_headlines(category_code: str) -> List[Dict]:
    batch = []
    for cty in COUNTRY_ROLL:
        batch.extend(_fetch_top(cty, category_code))
    uniq = _dedup(batch)
    return uniq[:5]  # take first 5 distinct


def build_category_block(header: str, code: str) -> str:
    items_html = []
    for art in get_headlines(code):
        title = _html.escape(art.get("title", ""))
        url = art.get("url", "#")
        snippet = _select_snippet(art)
        items_html.append(f"<li><a href=\"{url}\" target=\"_blank\">{title}</a><br><p class=\"snippet\">{snippet}</p></li>")
    return _tw.dedent(f"""
        <article>
            <h2>{header}</h2>
            <ul>
                {'\n                '.join(items_html)}
            </ul>
        </article>""")


def build_client_block(q: str) -> str:
    params = {
        "apiKey": API_KEY,
        "q": q,
        "language": "en",
        "pageSize": 5,
        "sortBy": "publishedAt",
    }
    try:
        data = _r.get(_ENDPOINT_EVERY, params=params, headers=_HEADERS, timeout=10).json()
        if data.get("status") != "ok":
            raise RuntimeError(data.get("message", "err"))
        lis = []
        for a in data.get("articles", [])[:5]:
            title = _html.escape(a.get("title", ""))
            url = a.get("url", "#")
            snippet = _select_snippet(a)
            lis.append(f"<li><a href=\"{url}\" target=\"_blank\">{title}</a><br><p class=\"snippet\">{snippet}</p></li>")
        if not lis:
            return ""
        return _tw.dedent(f"""
            <article>
                <h2>🔍 Client Watch – {_html.escape(q)}</h2>
                <ul>
                    {'\n                '.join(lis)}
                </ul>
            </article>""")
    except Exception as exc:
        print(f"⚠️ Client fetch error: {exc}")
        return ""


def build_daily_brief() -> str:
    today = _dt.date.today().strftime("%d %b %Y")
    parts = [
        _tw.dedent(f"""
            <article>
                <h2>🗞️ Daily Brief – {today}</h2>
            </article>""")
    ]
    for hdr, code in CATS.items():
        parts.append(build_category_block(hdr, code))
    if CLIENT_Q:
        client_block = build_client_block(CLIENT_Q)
        if client_block:
            parts.append(client_block)
    return "\n".join(parts)


def inject_into_index(block: str):
    idx_path = "index.html"
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        _sys.exit("index.html not found at repo root")

    insert_pos = html.lower().rfind("</section>")
    if insert_pos == -1:
        _sys.exit("</section> tag not found in index.html; cannot inject news block")

    updated = html[:insert_pos] + block + html[insert_pos:]
    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(updated)
    print("✅ index.html updated")


if __name__ == "__main__":
    brief_block = build_daily_brief()
    inject_into_index(brief_block)
