"""Step 1 — collect today's headlines from the client's channels via RSS (free, no tokens)."""
import calendar
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import feedparser
import yaml

UA = "Mozilla/5.0 (X11; Linux x86_64) PakImtehanNewsBot/1.0"


def clean(text, limit=300):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def google_news_url(site):
    return f"https://news.google.com/rss/search?q={quote_plus(f'site:{site} when:1d')}&hl=en-PK&gl=PK&ceid=PK:en"


def _parse(url):
    f = feedparser.parse(url, agent=UA)
    return f.entries if not f.bozo or f.entries else []


def fetch_source(src, max_age_hours, max_items):
    """Direct RSS first; if it is missing, broken or stale, fall back to Google News for that site."""
    items = _collect(src, _parse(src["rss"]), "rss", max_age_hours, max_items) if src.get("rss") else []
    if items or not src.get("site"):
        return src["name"], "rss", items
    gn = _collect(src, _parse(google_news_url(src["site"])), "google-news", max_age_hours, max_items)
    return src["name"], "google-news", gn


def _collect(src, entries, via, max_age_hours, max_items):
    cutoff = time.time() - max_age_hours * 3600
    items = []
    for e in entries:
        ts = e.get("published_parsed") or e.get("updated_parsed")
        epoch = calendar.timegm(ts) if ts else None
        if epoch and epoch < cutoff:
            continue
        title = clean(e.get("title"), 200)
        if via == "google-news":  # Google News appends " - Outlet"
            title = re.sub(r"\s+-\s+[^-]+$", "", title)
        items.append({
            "source": src["name"],
            "title": title,
            "summary": clean(e.get("summary") or e.get("description")) if via == "rss" else "",
            "link": e.get("link"),
            "published": epoch,
        })
        if len(items) >= max_items:
            break
    return items


def fetch_all(config_path="config/sources.yaml", verbose=True):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    s = cfg["settings"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda src: fetch_source(src, s["max_age_hours"], s["max_per_source"]), cfg["sources"]))
    all_items, seen = [], set()
    for name, via, items in results:
        if verbose:
            print(f"  {name:32s} {len(items):3d} items via {via}")
        for it in items:
            key = re.sub(r"\W+", "", it["title"].lower())[:80]
            if key and key not in seen:
                seen.add(key)
                all_items.append(it)
    return all_items, cfg


if __name__ == "__main__":
    items, _ = fetch_all()
    print(f"\n{len(items)} unique headlines")
