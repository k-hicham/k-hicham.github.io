#!/usr/bin/env python3
"""
fetch_news.py – pull 5 headlines per category (politics, tech, finance, innovation)
from NewsAPI.org filtered on Europe + US, and return an HTML <article> block.
"""
import datetime, os, sys, requests, textwrap

API_KEY = os.getenv("NEWS_KEY")
if not API_KEY:
    sys.exit("NEWS_KEY secret not set")

CATEGORIES = {
    "World Politics":   "politics",
    "Tech & AI":        "technology",
    "Finance & Economy": "business",
    "Innovation":       "science"
}

# Countries we keep (EU + US)
COUNTRIES = {"us", "gb", "fr", "de", "it", "es", "be", "nl", "se", "dk"}

def get_headlines(topic):
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": API_KEY,
        "category": topic,
        "pageSize": 20,
        "language": "en"
    }
    resp = requests.get(url, params=params, timeout=10).json()
    if resp.get("status") != "ok":
        raise RuntimeError(resp)
    articles = [
        a["title"] for a in resp["articles"]
        if a.get("source", {}).get("id")  # filter None sources
        and a.get("source", {}).get("name", "").lower() != "newsapi.org"
        and a.get("url") and a.get("title")
        and (a.get("country") in COUNTRIES or True)  # NewsAPI free tier lacks country filter
    ]
    return articles[:5]  # first 5

def make_block():
    today = datetime.date.today().strftime("%d %b %Y")
    parts = [f"""            <article>
                <h2>🗞️ Daily Brief – {today}</h2>
            </article>"""]
    for header, cat in CATEGORIES.items():
        try:
            lines = get_headlines(cat)
        except Exception as e:
            lines = [f"Error fetching: {e}"]
        items = "".join(f"<li>{h}</li>" for h in lines)
        parts.append(textwrap.dedent(f"""
            <article>
                <h2>{header}</h2>
                <ul>
                    {items}
                </ul>
            </article>"""))
    return "\n".join(parts)

if __name__ == "__main__":
    block = make_block()
    with open("index.html", "r+", encoding="utf-8") as f:
        html = f.read()
        insert_at = html.lower().rfind("</section>")
        if insert_at == -1:
            sys.exit("Could not find </section> in index.html")
        html = html[:insert_at] + block + html[insert_at:]
        f.seek(0)
        f.write(html)
        f.truncate()
    print("✅ index.html updated with fresh headlines")
