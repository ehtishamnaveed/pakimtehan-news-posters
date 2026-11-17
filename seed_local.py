"""Local testing only: render varied sample stories (designs picked by the selector) and store them in the LOCAL Worker.

    # terminal 1:  cd cloudflare/worker && wrangler dev --local --port 8787 --compatibility-date 2026-09-28
    # terminal 2:  python seed_local.py          (reads ~/.config/pakimtehan-posters/local.env)
    #              python edit.py                (apply dashboard edit requests, like the GitHub Action does)
"""
import datetime as dt
import json
import os
import random
from pathlib import Path

import store
from build import ROOT, assign_templates, save_photo
from render import render
from story import normalize_story

env = Path.home() / ".config" / "pakimtehan-posters" / "local.env"
for line in env.read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ[k] = v

NOW = dt.datetime.now(dt.timezone(dt.timedelta(hours=5)))
base = {p["headline"]: p for p in json.loads((ROOT / "samples" / "today.json").read_text())}
H = list(base.values())


def mk(i, **kw):
    p = dict(H[i % len(H)])
    p.pop("template", None)
    p.update(kw)
    return p


STORIES = [
    mk(0, tone="urgent", breaking=True, category="security-defence"),
    mk(1, tone="statement", category="climate-environment", quote="Climate-vulnerable nations need timely support that does not deepen their debt.", speaker="Prime Minister Shehbaz Sharif"),
    mk(2, tone="analytical", category="economy", image=None),
    mk(3, tone="data", category="science-technology", stat_value="22GW", stat_label="rooftop solar added in two years"),
    mk(4, tone="serious", category="geopolitics"),
    mk(5, tone="explainer", category="education", image=None),
    mk(0, headline="Nation honours the fallen as defence forces mark Martyrs Day", highlight="Martyrs Day", tone="solemn", category="security-defence", breaking=False),
    mk(3, headline="Pakistan's exports rise 18% as textile orders recover", highlight="rise 18%", tone="data", category="economy", stat_value="18%", stat_label="rise in exports", image=None),
]
for p in STORIES:
    p.setdefault("date", NOW.strftime("%-d %b %Y"))
    p["links"] = p.get("links") or ["https://www.dawn.com/"]
    normalize_story(p, sources=[{"label": (p.get("source") or "Source").split(",")[0][:60], "url": u} for u in p["links"]])
    p.setdefault("key_points", [p["summary"][:110]])

assign_templates(STORIES, random.Random(), [])
out = ROOT / "work" / "seed" / NOW.strftime("%Y-%m-%d")
out.mkdir(parents=True, exist_ok=True)
base_dir = ROOT / "samples"
for r, p in zip(render(STORIES, out, base_dir), STORIES):
    p["file"] = Path(r["file"]).name
    p["template"] = r["template"]
    p["regions"] = r.get("regions", {})
    if p.get("image"):
        p["photo_file"] = f"{Path(r['file']).stem}-photo.jpg"
        save_photo(base_dir / p["image"], out / p["photo_file"])
        p["image"] = None
    print(f"  {p['tone']:10s} {p['category']:22s} -> {p['template']}")
(out / "posters.json").write_text(json.dumps(STORIES, ensure_ascii=False, indent=1))
store.cmd_upload(str(out), NOW.strftime("%H%M"))
