"""Render poster JSON into 1080x1350 JPEGs using the HTML templates.

JPEG quality 90 with full-resolution colour (4:4:4), so coloured headline words stay sharp:
~290 KB per poster instead of ~700 KB as PNG, and accepted by every social network.

Usage:
    python render.py samples/today.json          # renders every poster in the file into out/
    python render.py samples/today.json --html   # also keep the filled HTML (for debugging)

Each poster object:
    template   a design id from templates/catalog.yaml (or "auto": the best fit for the story)
    kicker     short tag, e.g. "Climate · COP31"
    headline   the headline; `highlight` (optional) is a phrase inside it to colour
    summary    2-3 sentence summary in our own words
    why        one line: why it matters for CSS/PMS
    syllabus   list of syllabus areas, e.g. ["Pakistan Affairs", "Environment"]
    source     outlet name(s)
    date       display date
    image      local path or URL (optional; templates that need one are skipped without it)
    credit     photo credit line
"""
import io
import json
import random
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
from select_template import BY_ID, CATALOG, choose  # noqa: E402

TEMPLATES = [t["id"] for t in CATALOG]
JPEG_OPTS = dict(quality=90, subsampling=0, optimize=True, progressive=True)
NEEDS_PHOTO = {t["id"] for t in CATALOG if t.get("photo") == "required"}
NO_PHOTO_ONLY = {t["id"] for t in CATALOG if t.get("photo") == "none"}  # text-only designs; with a photo we prefer photo designs

env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
# Not Jinja slices: the dashboard's live preview draws these same templates with nunjucks, which has no [:n] (see livePoster.js)
env.filters["head"] = lambda items, n: list(items or [])[:n]


def headline_html(p):
    text, hi = p["headline"], p.get("highlight") or ""
    if hi and hi in text:
        a, b = text.split(hi, 1)
        return Markup(f"{escape(a)}<mark>{escape(hi)}</mark>{escape(b)}")
    return escape(text)


def pick_template(p, rng=random):
    """The design to use: the one named in the poster, else the best fit for the story (never random)."""
    t = p.get("template", "auto")
    has_photo = bool(p.get("image"))
    if t not in BY_ID:
        return choose(p, has_photo, rng=rng)
    if t in NEEDS_PHOTO and not has_photo:
        return choose(p, False, rng=rng)
    return t


def to_uri(path_or_url, base: Path):
    if not path_or_url or "://" in path_or_url:
        return path_or_url
    return (base / path_or_url).resolve().as_uri()


def launch_chromium(pw):
    """Use Playwright's own Chromium; if it isn't downloaded, use any preinstalled one."""
    try:
        return pw.chromium.launch()
    except Exception as first:
        import glob
        import shutil
        paths = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"), reverse=True)
        paths += [p for p in (shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome")) if p]
        for exe in paths:
            try:
                return pw.chromium.launch(executable_path=exe)
            except Exception:
                continue
        raise first


def render(posters, out_dir: Path, base: Path, keep_html=False):
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for i, p in enumerate(posters, 1):
            t = pick_template(p)
            data = dict(p, headline_html=headline_html(p), image=to_uri(p.get("image"), base),
                        syllabus=p.get("syllabus") or [], edition=p.get("edition", ""))
            entry = BY_ID[t]
            html = env.get_template(f"{entry['layout']}.html").render(p=data, root=ROOT.as_uri(), theme=entry.get("theme"))
            html_path = out_dir / f"{i:02d}-{t}.html"
            html_path.write_text(html, encoding="utf-8")
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.wait_for_selector("body[data-ready='1']", timeout=15000)
            # Where each editable field sits on the 1080x1350 image, so the dashboard can show which part of
            # the poster an edit will change. Several elements with the same data-field are merged.
            regions = page.evaluate("""() => {
              const out = {};
              document.querySelectorAll('[data-field]').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width < 2 || r.height < 2) return;
                const k = el.dataset.field, x1 = r.left, y1 = r.top, x2 = r.right, y2 = r.bottom, o = out[k];
                out[k] = o ? [Math.min(o[0], x1), Math.min(o[1], y1), Math.max(o[2], x2), Math.max(o[3], y2)] : [x1, y1, x2, y2];
              });
              return Object.fromEntries(Object.entries(out).map(([k, v]) => [k, [Math.round(Math.max(0, v[0])), Math.round(Math.max(0, v[1])), Math.round(Math.min(1080, v[2]) - Math.max(0, v[0])), Math.round(Math.min(1350, v[3]) - Math.max(0, v[1]))]]));
            }""")
            img = out_dir / f"{i:02d}-{t}.jpg"
            Image.open(io.BytesIO(page.screenshot(type="png"))).convert("RGB").save(img, "JPEG", **JPEG_OPTS)
            if not keep_html:
                html_path.unlink()
            results.append({"file": str(img), "template": t, "regions": regions, **{k: p.get(k) for k in ("headline", "source")}})
            print(f"rendered {img.name}")
        browser.close()
    return results


if __name__ == "__main__":
    src = Path(sys.argv[1])
    posters = json.loads(src.read_text(encoding="utf-8"))
    render(posters, ROOT / "out", src.parent, keep_html="--html" in sys.argv)
