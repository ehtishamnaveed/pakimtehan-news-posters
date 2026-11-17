"""Live News story fields that travel with every poster (headline/summary/why are shared with the poster itself).

The website's Live News section shows the poster plus a story page. The extra fields are:
    category    one of CATEGORIES (the website's filter ids; "breaking" is a flag, not a category)
    breaking    true only when the source calls it breaking / developing
    key_points  2-3 short bullet points
    body        safe Markdown subset: paragraphs, "## Heading", "- bullets", "**bold**"
    sources     [{label, url}] built from the real article links, never written by the AI
Everything here is plain text; the server and website sanitise it again before use.
"""
import re

CATEGORIES = ["pakistan-affairs", "international-affairs", "politics-governance", "economy", "geopolitics",
              "security-defence", "science-technology", "climate-environment", "education"]

# Syllabus topic -> category, used when the AI gives no (or an unknown) category.
_FROM_TOPIC = {
    "economy": "economy", "budget": "economy", "finance": "economy", "trade": "economy",
    "security": "security-defence", "defence": "security-defence", "nuclear": "security-defence",
    "technology": "science-technology", "science": "science-technology",
    "environment": "climate-environment", "climate": "climate-environment",
    "education": "education",
    "geopolitics": "geopolitics", "sanctions": "geopolitics", "foreign policy": "geopolitics",
    "international": "international-affairs",
    "governance": "politics-governance", "constitution": "politics-governance", "politics": "politics-governance",
    "pakistan": "pakistan-affairs",
}


def guess_category(syllabus):
    for topic in syllabus or []:
        low = topic.lower()
        for key, cat in _FROM_TOPIC.items():
            if key in low:
                return cat
    return "pakistan-affairs"


def clean_text(v, n):
    return re.sub(r"[ \t]+", " ", str(v or "").replace("\r", "")).strip()[:n]


def normalize_story(p, sources=None):
    """Fill/repair the story fields on poster dict `p` in place; returns p."""
    from select_template import TONES, default_tone  # local import: select_template reads the catalog
    cat = str(p.get("category") or "").strip()
    p["category"] = cat if cat in CATEGORIES else guess_category(p.get("syllabus"))
    p["breaking"] = p.get("breaking") is True
    # Poster extras the design selector uses: a headline figure and a quotation (already checked against the source text).
    sv, sl = clean_text(p.pop("stat_value", "") or (p.get("stat") or {}).get("value", ""), 8), clean_text(p.pop("stat_label", "") or (p.get("stat") or {}).get("label", ""), 50)
    p["stat"] = {"value": sv, "label": sl} if sv else None
    p["quote"] = clean_text(p.get("quote"), 130)
    p["speaker"] = clean_text(p.get("speaker"), 60) if p["quote"] else ""
    p["tone"] = p.get("tone") if p.get("tone") in TONES else default_tone(p)
    pts = p.get("key_points") if isinstance(p.get("key_points"), list) else []
    p["key_points"] = [clean_text(x, 140) for x in pts if clean_text(x, 140)][:4]
    body = clean_text(p.get("body"), 3000)
    if not body:  # fallback: only what the poster already says
        body = p.get("summary", "")
        if p.get("why"):
            body += f"\n\n## Why it matters for CSS and PMS\n\n{p['why']}"
    p["body"] = body
    if sources is not None:
        p["sources"] = sources
    return p
