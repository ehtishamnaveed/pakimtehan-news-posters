"""Choose the poster design for a story: by what the story IS, not at random.

Every design in templates/catalog.yaml is scored against the story:
  + its Live News category and its tone (urgent, serious, analytical, hopeful, solemn, explainer, data, statement)
  + whether the story has a photo, a striking number (`stat`) or a quotation (`quote`)
  + whether the headline is the right length for the design
  - how often the design was used recently (so a day's feed looks varied) and in the same batch (never twice)
Designs that need a number or a quote are only offered when the story has one. The final pick is made among the few best
fits, weighted by score, so the same kind of story gets related but not identical looks.
"""
import math
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CATALOG = yaml.safe_load((ROOT / "templates" / "catalog.yaml").read_text(encoding="utf-8"))["templates"]
BY_ID = {t["id"]: t for t in CATALOG}
TONES = ["urgent", "serious", "analytical", "hopeful", "solemn", "explainer", "data", "statement"]
RECENT_KEEP = 24  # how many recent picks the pipeline remembers


def default_tone(p):
    if p.get("breaking"):
        return "urgent"
    if p.get("quote"):
        return "statement"
    if p.get("stat"):
        return "data"
    return {"security-defence": "serious", "climate-environment": "hopeful", "education": "explainer",
            "economy": "analytical", "science-technology": "analytical"}.get(p.get("category"), "serious")


def eligible(entry, p, has_photo):
    if entry.get("photo") == "required" and not has_photo:
        return False
    if "stat" in entry.get("needs", []) and not (p.get("stat") or {}).get("value"):
        return False
    if "quote" in entry.get("needs", []) and not p.get("quote"):
        return False
    return True


def score(entry, p, has_photo, in_batch, recent):
    s = 0.0
    tone = p.get("tone") if p.get("tone") in TONES else default_tone(p)
    if p.get("category") in entry.get("categories", []):
        s += 3
    if tone in entry.get("tones", []):
        s += 3
    if p.get("breaking") and entry.get("family") == "breaking":
        s += 2
    if "stat" in entry.get("needs", []):
        s += 2
    elif (p.get("stat") or {}).get("value") and "data" in entry.get("tones", []):
        s += 1
    if "quote" in entry.get("needs", []):
        s += 3
    photo = entry.get("photo", "optional")
    if has_photo:
        s += {"required": 1.0, "optional": 0.5, "none": -1.5}[photo]
    elif photo == "none":
        s += 0.5
    lo, hi = entry.get("chars", [20, 120])
    n = len(p.get("headline", ""))
    s -= min(3.0, (lo - n) / 20 if n < lo else (n - hi) / 20 if n > hi else 0)
    s -= min(4.0, 1.5 * list(recent).count(entry["id"]))
    s -= 5.0 * list(in_batch).count(entry["id"])
    return s


def ranked(p, has_photo, in_batch=(), recent=(), exclude=()):
    pool = [t for t in CATALOG if t["id"] not in exclude and eligible(t, p, has_photo)]
    return sorted(((score(t, p, has_photo, in_batch, recent), t["id"]) for t in pool), reverse=True)


def choose(p, has_photo, in_batch=(), recent=(), rng=random, top=3, exclude=()):
    """Pick one design id. `rng` makes batches reproducible in tests."""
    order = ranked(p, has_photo, in_batch, recent, exclude)
    if not order:  # cannot happen with the always-eligible general designs, but never fail a poster over it
        return "typographic"
    best = order[:top]
    top_score = best[0][0]
    weights = [math.exp(sc - top_score) for sc, _ in best]
    return rng.choices([i for _, i in best], weights=weights, k=1)[0]
