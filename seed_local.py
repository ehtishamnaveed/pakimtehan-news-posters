"""Local testing only: render the sample posters (with Live News story fields) and store them in the LOCAL Worker.

    # terminal 1:  cd cloudflare/worker && wrangler dev --local --port 8787 --compatibility-date 2026-09-28
    # terminal 2:  python seed_local.py          (reads ~/.config/pakimtehan-posters/local.env)
    #              python edit.py                (apply dashboard edit requests, like the GitHub Action does)
"""
import datetime as dt
import json
import os
from pathlib import Path

from build import ROOT, save_photo
from render import render
from story import normalize_story
import store

env = Path.home() / ".config" / "pakimtehan-posters" / "local.env"
for line in env.read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ[k] = v

NOW = dt.datetime.now(dt.timezone(dt.timedelta(hours=5)))
posts = json.loads((ROOT / "samples" / "today.json").read_text())
extra = [
    {"kicker": "Geopolitics · Technology", "headline": "China accuses US of using spy claims to justify a technology blockade",
     "highlight": "technology blockade", "summary": "Beijing's foreign ministry said Washington is fabricating 'spy' narratives as a pretext for restricting China's access to advanced technology.",
     "why": "US-China tech rivalry shapes global supply chains and the strategic choices facing Pakistan.",
     "syllabus": ["Diplomacy", "Technology"], "source": "Dawn / AFP", "template": "typographic", "breaking": True},
    {"kicker": "Economy · Governance", "headline": "FBR expands use of AI to detect discrepancies in tax returns",
     "highlight": "use of AI", "summary": "The Federal Board of Revenue's automated system now scrutinises individual tax returns to flag factual and legal errors and discrepancies.",
     "why": "Digitising tax administration is central to debates on Pakistan's narrow tax base and reform.",
     "syllabus": ["Economy", "Politics", "Technology"], "source": "Dawn", "template": "impact"},
]
for p in posts + extra:
    p.setdefault("date", NOW.strftime("%-d %b %Y"))
    p["links"] = p.get("links") or ["https://www.dawn.com/"]
    normalize_story(p, sources=[{"label": (p.get("source") or "Source").split(",")[0][:60], "url": u} for u in p["links"]])
    p.setdefault("key_points", [p["summary"][:110]])

out = ROOT / "work" / "seed" / NOW.strftime("%Y-%m-%d")
out.mkdir(parents=True, exist_ok=True)
base = ROOT / "samples"
for r, p in zip(render(posts + extra, out, base), posts + extra):
    p["file"] = Path(r["file"]).name
    p["template"] = r["template"]
    p["regions"] = r.get("regions", {})
    if p.get("image"):
        p["photo_file"] = f"{Path(r['file']).stem}-photo.jpg"
        save_photo(base / p["image"], out / p["photo_file"])
        p["image"] = None
(out / "posters.json").write_text(json.dumps(posts + extra, ensure_ascii=False, indent=1))
store.cmd_upload(str(out), NOW.strftime("%H%M"))
