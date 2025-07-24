#!/usr/bin/env python3
"""
fetch_news.py – Daily Brief generator for My daily companion
-----------------------------------------------------------
• Pulls up to 5 headlines per category (Politics, Tech & AI, Finance & Economy, Innovation)
  from NewsAPI.org, mixing US + selected EU countries.
• Builds a <article> HTML block with clickable titles, a 1‑2 sentence snippet,
  and an inline « Voir la suite → » link.
• Optional extra section "Client Watch" driven by repo variable CLIENT_KEYWORD.

Required secrets / variables in GitHub Actions:
  NEWS_KEY         – NewsAPI key (secret)
  CLIENT_KEYWORD   – optional free‑text query for client monitoring (variable)
"""
import datetime as _dt
import html as _html
import os as _os
import re as _re
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
    "World Politics": "general",
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
_HEADERS = {"User-Agent": "daily-brief-bot/2.0"}


def _fetch_top(country: str, category: str) -> List[Dict]:
    params = {
        "apiKey": API_KEY,
        "country": country,
        "category": category,
        "pageSize": 20,
        "language": "en",
    }
    try:
        data = _r.get(_ENDPOINT_TOP, params=params, headers=_HEADERS, timeout=12).json()
        if data.get("status") != "ok":
            raise RuntimeError(data.get("message", "unknown error"))
        return data.get("articles", [])
    except Exception as exc:
        print(f"⚠️ top-headlines error {country}/{category}: {exc}")
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


def _snippet(a: Dict) -> str:
    cand = a.get("description") or a.get("content") or ""
    cand = cand.split("[+")[0].strip()
    return _html.escape(cand[:280])


def _fmt_li(art: Dict) -> str:
    title = _html.escape(art.get("title", ""))
    url = art.get("url", "#")
    snippet = _snippet(art)
    return (
        f"<li><strong><a href=\"{url}\" target=\"_blank\">{title}</a></strong><br>"
        f"<p class=\"snippet\">{snippet} <a href=\"{url}\" target=\"_blank\">Voir la suite →</a></p></li>"
    )


def get_headlines(code: str) -> List[Dict]:
    batch: List[Dict] = []
    for cty in COUNTRY_ROLL:
        batch.extend(_fetch_top(cty, code))
    return _dedup(batch)[:5]


def build_category_block(hdr: str, code: str) -> str:
    items = [_fmt_li(a) for a in get_headlines(code)]
    return _tw.dedent(f"""
        <article>
            <h2>{hdr}</h2>
            <ul>
                {'\n                '.join(items)}
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
        data = _r.get(_ENDPOINT_EVERY, params=params, headers=_HEADERS, timeout=15).json()
        if data.get("status") != "ok":
            raise RuntimeError(data.get("message", "err"))
        lis = [_fmt_li(a) for a in data.get("articles", [])[:5]]
        if not lis:
            return ""
        return _tw.dedent(f"""
            <article>
                <h2>🔍 Client Watch – {_html.escape(q)}</h2>
                <ul>
                    {'\n                    '.join(lis)}
                </ul>
            </article>""")
    except Exception as exc:
        print(f"⚠️ Client fetch error: {exc}")
        return ""


def build_daily_brief() -> str:
    today = _dt.date.today().strftime("%d %b %Y")
    parts = [_tw.dedent(f"""
            <article>
                <h2>🗞️ Daily Brief – {today}</h2>
            </article>""")]
    for hdr, code in CATS.items():
        parts.append(build_category_block(hdr, code))
    if CLIENT_Q:
        blk = build_client_block(CLIENT_Q)
        if blk:
            parts.append(blk)
    return "\n".join(parts)


def inject_into_index(block: str):
    idx = "index.html"
    try:
        html = open(idx, "r", encoding="utf-8").read()
    except FileNotFoundError:
        _sys.exit("index.html not found")

    # inject right before closing tag of section with id="posts"
    m = _re.search(r"</section>\s*<!--\s*posts end\s*-->", html, _re.I)
    if not m:
        # fallback: take first </section> after id="posts"
        m = _re.search(r"id=\"posts\"[\s\S]*?</section>", html, _re.I)
        if not m:
            _sys.exit("<section id='posts'> not found")
        end_idx = m.end() - len("</section>")
    else:
        end_idx = m.start()

    updated = html[:end_idx] + block + html[end_idx:]
    open(idx, "w", encoding="utf-8").write(updated)
    print("✅ Brief injected in #posts")


if __name__ == "__main__":
    inject_into_index(build_daily_brief())
