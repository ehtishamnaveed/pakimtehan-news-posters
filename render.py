"""Render poster JSON into 1080x1350 JPEGs using the HTML templates.

JPEG quality 90 with full-resolution colour (4:4:4), so coloured headline words stay sharp:
~290 KB per poster instead of ~700 KB as PNG, and accepted by every social network.

Usage:
    python render.py samples/today.json          # renders every poster in the file into out/
    python render.py samples/today.json --html   # also keep the filled HTML (for debugging)

Each poster object:
    template   one of TEMPLATES (or "random")
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
TEMPLATES = ["breaking-photo", "navy-card", "editorial", "newspaper", "typographic", "brief-light"]
JPEG_OPTS = dict(quality=90, subsampling=0, optimize=True, progressive=True)
NEEDS_PHOTO = {"breaking-photo", "navy-card", "brief-light"}

env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))


def headline_html(p):
    text, hi = p["headline"], p.get("highlight") or ""
    if hi and hi in text:
        a, b = text.split(hi, 1)
        return Markup(f"{escape(a)}<mark>{escape(hi)}</mark>{escape(b)}")
    return escape(text)


def pick_template(p, rng=random):
    t = p.get("template", "random")
    if t == "random" or t not in TEMPLATES:
        pool = TEMPLATES if p.get("image") else [x for x in TEMPLATES if x not in NEEDS_PHOTO]
        t = rng.choice(pool)
    if t in NEEDS_PHOTO and not p.get("image"):
        t = "typographic"
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
            html = env.get_template(f"{t}.html").render(p=data, root=ROOT.as_uri())
            html_path = out_dir / f"{i:02d}-{t}.html"
            html_path.write_text(html, encoding="utf-8")
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.wait_for_selector("body[data-ready='1']", timeout=15000)
            img = out_dir / f"{i:02d}-{t}.jpg"
            Image.open(io.BytesIO(page.screenshot(type="png"))).convert("RGB").save(img, "JPEG", **JPEG_OPTS)
            if not keep_html:
                html_path.unlink()
            results.append({"file": str(img), "template": t, **{k: p.get(k) for k in ("headline", "source")}})
            print(f"rendered {img.name}")
        browser.close()
    return results


if __name__ == "__main__":
    src = Path(sys.argv[1])
    posters = json.loads(src.read_text(encoding="utf-8"))
    render(posters, ROOT / "out", src.parent, keep_html="--html" in sys.argv)
