"""Find free photos via Openverse (no API key, no AI).

* Only licences that allow putting text over the photo: CC0, Public Domain, CC BY, CC BY-SA.
* Never photos from the news outlets themselves (copyrighted).
* We download a few candidates per poster; Claude looks at them and picks one (or none).
"""
import re
from pathlib import Path

import requests

UA = {"User-Agent": "PakImtehanPosters/1.0 (+https://pakimtehan.com)"}  # Flickr returns 403 to agents containing "Bot"
API = "https://api.openverse.org/v1/images/"


def search(query, page_size=15):
    err = None
    for _ in range(2):
        try:
            r = requests.get(API, headers=UA, timeout=35, params=dict(
                q=query, source="flickr", license="cc0,pdm,by,by-sa", aspect_ratio="wide",
                mature="false", page_size=page_size))
            return r.json().get("results", [])
        except Exception as e:
            err = e
    print(f"  image search failed for {query!r}: {err}")
    return []


def candidates(query, dest_dir: Path, prefix: str, want=3):
    """Download up to `want` usable candidates. Returns [{image, credit, image_source}]."""
    found = []
    for it in search(query):
        url = re.sub(r"(_[a-z])?\.jpg$", "_b.jpg", it["url"])  # Flickr 1024px size
        try:
            img = requests.get(url, headers=UA, timeout=20)
        except Exception:
            continue
        if img.status_code != 200 or len(img.content) < 80_000:
            continue
        path = dest_dir / f"{prefix}-{chr(97 + len(found))}.jpg"
        path.write_bytes(img.content)
        lic = f"CC {it['license'].upper()} {it.get('license_version') or ''}".strip()
        lic = {"CC CC0 1.0": "CC0", "CC PDM 1.0": "Public Domain"}.get(lic, lic)
        who = (it.get("creator") or "Flickr")[:40]
        found.append({"image": str(path), "credit": f"{who} / Flickr, {lic}",
                      "image_source": it["foreign_landing_url"], "title": it.get("title", "")})
        if len(found) >= want:
            break
    return found
