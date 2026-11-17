"""Render EVERY design in templates/catalog.yaml with sample stories and make contact sheets (a design review tool).

    python render_library.py            # -> out/library/sheet-1.jpg, sheet-2.jpg, ...   (and the single posters)
    python render_library.py breaking-photo bold-red     # only these ids
"""
import json
import sys

from PIL import Image, ImageDraw

from render import BY_ID, CATALOG, ROOT, render

SAMPLES = json.loads((ROOT / "samples" / "today.json").read_text(encoding="utf-8"))
IMG = {p["image"].split("/")[-1].split(".")[0]: p["image"] for p in SAMPLES if p.get("image")}


def story(i):
    """Sample stories with the extras the selector looks for (a number, a quotation)."""
    base = dict(SAMPLES[i % len(SAMPLES)])
    base["date"] = "17 Nov 2026"
    base.setdefault("syllabus", ["Economy", "Governance"])
    return base


def sample_for(entry, n):
    p = story(n)
    p["template"] = entry["id"]
    p.setdefault("highlight", "")
    p["stat"] = {"value": ["22GW", "$500", "1.1m", "48%"][n % 4], "label": ["rooftop solar added in two years", "monthly income raised", "people reached", "rise in exports"][n % 4]}
    p["quote"] = "Climate-vulnerable nations need timely support that does not deepen their debt."
    p["speaker"] = "Prime Minister Shehbaz Sharif"
    if entry.get("photo") == "none":
        p["image"] = None
    elif not p.get("image"):
        p["image"] = "img/cop.jpg"
    return p


def main(ids):
    out = ROOT / "out" / "library"
    out.mkdir(parents=True, exist_ok=True)
    entries = [BY_ID[i] for i in ids] if ids else CATALOG
    posts = [sample_for(e, n) for n, e in enumerate(entries)]
    results = render(posts, out, ROOT / "samples")
    W, H = 432, 540
    for si in range(0, len(results), 6):
        chunk = results[si:si + 6]
        sheet = Image.new("RGB", (W * 3, H * 2), "#ddd")
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(chunk):
            im = Image.open(r["file"]).convert("RGB").resize((W - 8, H - 8))
            x, y = (i % 3) * W, (i // 3) * H
            sheet.paste(im, (x + 4, y + 4))
            d.rectangle([x + 4, y + 4, x + 230, y + 26], fill="black")
            d.text((x + 10, y + 10), r["template"], fill="white")
        sheet.save(out / f"sheet-{si // 6 + 1}.jpg", quality=86)
    print(f"{len(results)} designs rendered -> out/library/")


if __name__ == "__main__":
    main(sys.argv[1:])
