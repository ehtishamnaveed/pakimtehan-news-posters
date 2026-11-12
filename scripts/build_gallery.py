"""Build the static test gallery (Cloudflare Pages) from a posters output branch checkout.

    python scripts/build_gallery.py <checkout-with-posters/> <site-dir>

Shows every generated poster, newest first, with its text, sources, template and which AI wrote it.
It is a read-only preview of what the pipeline creates; approval stays in the dashboard.
"""
import html
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKT = timezone(timedelta(hours=5))


def esc(v):
    return html.escape(str(v or ""))


def main(src: Path, site: Path):
    if site.exists():
        shutil.rmtree(site)
    (site / "p").mkdir(parents=True)
    shutil.copytree(ROOT / "assets" / "fonts", site / "fonts")
    shutil.copy(ROOT / "assets" / "logo-white.png", site / "logo.png")
    fonts_css = (ROOT / "assets" / "fonts.css").read_text()

    days = []
    for day_dir in sorted((src / "posters").glob("20??-??-??"), reverse=True):
        manifest = day_dir / "posters.json"
        if not manifest.exists():
            continue
        posters = json.loads(manifest.read_text())
        (site / "p" / day_dir.name).mkdir()
        items = []
        for p in reversed(posters):  # latest batch first within a day
            png = day_dir / p.get("png", "")
            if not png.is_file():
                continue
            shutil.copy(png, site / "p" / day_dir.name / png.name)
            items.append((f"p/{day_dir.name}/{png.name}", p))
        if items:
            days.append((day_dir.name, items))

    total = sum(len(i) for _, i in days)
    built = datetime.now(PKT).strftime("%-d %b %Y, %H:%M PKT")
    cards = []
    for day, items in days:
        label = datetime.strptime(day, "%Y-%m-%d").strftime("%A %-d %B %Y")
        cards.append(f'<h2 class="day">{esc(label)} <span>{len(items)} poster{"s" if len(items) != 1 else ""}</span></h2><div class="grid">')
        for src_png, p in items:
            links = " · ".join(f'<a href="{esc(l)}" target="_blank" rel="noopener nofollow">Source {i + 1}</a>'
                               for i, l in enumerate(p.get("links") or []))
            tags = "".join(f"<span class=tag>{esc(s)}</span>" for s in p.get("syllabus") or [])
            cards.append(f"""
<article class="card">
  <a class="img" href="{src_png}" target="_blank"><img src="{src_png}" alt="{esc(p.get('headline'))}" loading="lazy" width="1080" height="1350"></a>
  <div class="body">
    <div class="kicker">{esc(p.get('kicker'))}</div>
    <h3>{esc(p.get('headline'))}</h3>
    <p>{esc(p.get('summary'))}</p>
    {f'<p class="why"><b>Why it matters</b>{esc(p.get("why"))}</p>' if p.get('why') else ''}
    <div class="tags">{tags}</div>
    <div class="meta">
      <span>Source: {esc(p.get('source'))}</span>
      <span>Template: {esc(p.get('template'))} · AI: {esc((p.get('_editor') or 'claude').split(':')[-1])}</span>
      <span>{links}</span>
    </div>
  </div>
</article>""")
        cards.append("</div>")

    page = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Pak Imtehan · Poster pipeline (test)</title>
<style>
{fonts_css.replace('url(fonts/', 'url(fonts/')}
:root {{ --navy:#030a1a; --navy2:#0b1530; --blue:#2563eb; --blue3:#93c5fd; --ink:#0f172a; --muted:#475569; --line:#e2e8f0; --bg:#f5f7fb; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:Inter,system-ui,sans-serif; background:var(--bg); color:var(--ink); }}
header {{ background:radial-gradient(120% 120% at 50% 0%, #172554 0%, var(--navy) 70%); color:#fff; padding:28px 16px 36px; }}
.wrap {{ max-width:1200px; margin:0 auto; padding:0 16px; }}
header img {{ height:40px; }}
header h1 {{ margin-top:22px; font-size:clamp(26px,4vw,40px); font-weight:800; letter-spacing:-.02em; }}
header h1 span {{ color:#60a5fa; }}
header p {{ margin-top:10px; color:#bfdbfe; max-width:720px; line-height:1.55; }}
.badge {{ display:inline-block; margin-top:16px; border:1px solid rgba(147,197,253,.4); border-radius:999px; padding:6px 12px; font-size:13px; color:#dbeafe; }}
main {{ padding:32px 0 64px; }}
.day {{ display:flex; align-items:baseline; gap:12px; font-size:22px; font-weight:800; margin:28px 0 16px; }}
.day span {{ font-size:13px; font-weight:600; color:var(--muted); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:20px; }}
.card {{ background:#fff; border:1px solid var(--line); border-radius:18px; overflow:hidden; display:flex; flex-direction:column; }}
.img {{ display:block; aspect-ratio:4/5; background:var(--navy2); }}
.img img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.body {{ padding:16px; display:flex; flex-direction:column; gap:8px; flex:1; }}
.kicker {{ font-size:11px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; color:var(--blue); }}
h3 {{ font-size:17px; line-height:1.3; }}
.body p {{ font-size:14px; line-height:1.55; color:var(--muted); }}
.why {{ background:#eff6ff; color:#1e3a8a !important; border-radius:10px; padding:10px 12px; }}
.why b {{ display:block; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--blue); margin-bottom:2px; }}
.tags {{ display:flex; flex-wrap:wrap; gap:6px; }}
.tag {{ border:1px solid var(--line); border-radius:999px; padding:3px 9px; font-size:12px; color:var(--muted); }}
.meta {{ margin-top:auto; padding-top:10px; border-top:1px solid var(--line); display:flex; flex-direction:column; gap:4px; font-size:12px; color:var(--muted); }}
.meta a {{ color:var(--blue); }}
.empty {{ padding:48px 16px; text-align:center; color:var(--muted); }}
</style></head>
<body>
<header><div class="wrap">
  <img src="logo.png" alt="Pak Imtehan">
  <h1>Poster pipeline <span>test gallery</span></h1>
  <p>Everything the automated pipeline has generated, newest first. This is a private test preview; posters go live on pakimtehan.com only after approval in the dashboard.</p>
  <span class="badge">{total} posters · last updated {esc(built)}</span>
</div></header>
<main><div class="wrap">
{''.join(cards) if cards else '<p class="empty">No posters yet.</p>'}
</div></main>
</body></html>"""
    (site / "index.html").write_text(page, encoding="utf-8")
    (site / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n")
    print(f"gallery: {total} posters across {len(days)} day(s) -> {site}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
