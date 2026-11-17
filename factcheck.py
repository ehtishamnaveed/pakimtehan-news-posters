"""Fact-check gate and repeat-story memory. A poster is only rendered if it passes BOTH.

Client rule (17 Nov): no poster may state anything the sources do not say, and no story gets a poster twice.
Nobody reads 15 posters a day, so this runs on its own, and when it cannot be sure it REJECTS the poster
(fails closed). The admin editor is for small wording changes, not for catching invented facts.

Gate 1 (here, no AI): every number in the poster text must appear in the evidence (the article text, or the
headline + teaser when the article cannot be read); every quotation is already checked by ai_editor.verify_extras.
Gate 2 (ai_editor.py verify): an independent model compares each claim with the evidence.

Repeat memory: headlines of every poster already made (approved, rejected or waiting) are kept in the Worker
state `recent_stories` for 14 days. A new story that matches one of them is dropped before the AI sees it
(build.py fetch), dropped again if the editor still picks it (validate), and checked once more by the verifier.
"""
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
RECENT_STORIES = ROOT / "state" / "recent_stories.json"
KEEP_DAYS = 14
KEEP_MAX = 600
UA = "Mozilla/5.0 (X11; Linux x86_64) PakImtehanNewsBot/1.0"

# ---------------------------------------------------------------------------
# Same story? (shared by fetch, editor validation and the verifier)
# ---------------------------------------------------------------------------

STOP = set("after amid over says said with from into that this their they have will would about against before between "
           "under what when where which while been were than then them also more most some such only just like "
           "pakistan pakistani pakistans news live update updates latest report reports".split())


def words(headline):
    return {w for w in re.findall(r"[a-z0-9]+", str(headline).lower()) if len(w) > 3 and w not in STOP}


def same_story(a, b):
    """Two headlines about one story, e.g. 'Jensen Huang resigns as Nvidia CEO...' and
    'Jensen Huang quits Nvidia after 33 years...' (13 Nov run)."""
    wa, wb = words(a), words(b)
    shared = wa & wb
    if len(shared) >= 3 and len(shared) / max(1, min(len(wa), len(wb))) >= 0.5:
        return True
    # short headlines: two distinctive shared words (names, places) out of a handful is the same story
    return len(shared) >= 2 and len(shared) / max(1, min(len(wa), len(wb))) >= 0.67 and min(len(wa), len(wb)) <= 4


def load_recent(path=RECENT_STORIES):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return []
    cutoff = time.time() - KEEP_DAYS * 86400
    return [r for r in data if isinstance(r, dict) and r.get("h") and r.get("t", 0) >= cutoff]


def remember(posters, path=RECENT_STORIES, now=None):
    """Add this run's posters to the memory (headline + summary + links), drop old ones."""
    now = now or time.time()
    recent = load_recent(path)
    for p in posters:
        recent.append({"h": p["headline"], "s": str(p.get("summary", ""))[:200], "t": int(now),
                       "l": [l for l in p.get("links", []) if l][:4]})
    recent = recent[-KEEP_MAX:]
    Path(path).parent.mkdir(exist_ok=True)
    Path(path).write_text(json.dumps(recent, ensure_ascii=False))
    return recent


def repeat_of(headline, recent, summary=""):
    """The earlier story this headline repeats, or None."""
    for r in recent:
        if same_story(headline, r["h"]):
            return r["h"]
    return None


# ---------------------------------------------------------------------------
# Evidence: what the sources actually say
# ---------------------------------------------------------------------------

def _article_text(url, timeout=12, limit=3500):
    """Readable text of one article (its <p> paragraphs), or '' if it cannot be read."""
    if not str(url).startswith(("http://", "https://")) or "news.google.com" in url:
        return ""  # Google News links are JavaScript redirects, not articles
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=timeout)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            return ""
        page = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>", " ", r.text)
        paras = [html.unescape(re.sub(r"<[^>]+>", " ", m)) for m in re.findall(r"(?is)<p[^>]*>(.*?)</p>", page)]
        paras = [re.sub(r"\s+", " ", t).strip() for t in paras]
        text = " ".join(t for t in paras if len(t) > 40)
        return text[:limit]
    except requests.RequestException:
        return ""


def gather_evidence(posts, heads, workers=8):
    """One evidence record per poster: headline + teaser of every merged story, plus the article text when readable."""
    jobs = {}
    for i, p in enumerate(posts):
        for sid in p["story_ids"][:3]:
            jobs[(i, sid)] = heads[sid]["link"]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        texts = dict(zip(jobs, ex.map(_article_text, jobs.values())))
    out = []
    for i, p in enumerate(posts):
        parts, articles = [], 0
        for sid in p["story_ids"]:
            h = heads[sid]
            parts.append(f"[{h['source']}] {h.get('title', '')}. {h.get('summary', '')}")
            art = texts.get((i, sid), "")
            if art:
                articles += 1
                parts.append(f"[{h['source']} article] {art}")
        out.append({"text": "\n".join(parts), "articles": articles, "outlets": len({heads[s]["source"] for s in p["story_ids"]})})
    return out


# ---------------------------------------------------------------------------
# Gate 1: numbers
# ---------------------------------------------------------------------------

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(text):
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(str(text))}


def claim_text(p):
    """Everything on the poster and story page that makes a claim (not the syllabus tags or fixed headings)."""
    body = re.sub(r"(?m)^#+\s.*$", "", str(p.get("body") or ""))  # "## Why it matters for CSS and PMS" is a fixed heading
    return " ".join([str(p.get("headline", "")), str(p.get("summary", "")), str(p.get("why", "")),
                     " ".join(map(str, p.get("key_points") or [])), body, str(p.get("quote", ""))])


def unsupported_numbers(p, evidence_text):
    """Numbers the poster states that no source states. Spelled-out numbers are left to the AI check."""
    known = numbers(evidence_text) | numbers(p.get("date", ""))
    out = []
    for n in sorted(numbers(claim_text(p))):
        if n not in known:
            out.append(n)
    return out


def check_numbers(posts, evidence):
    """-> list of (poster index, problem). Posters with a problem must not be published."""
    problems = []
    for i, (p, ev) in enumerate(zip(posts, evidence)):
        bad = unsupported_numbers(p, ev["text"])
        if bad:
            problems.append((i, "numbers not in the sources: " + ", ".join(bad)))
    return problems
