"""Find free photos for the posters — several free libraries, tried in order.

Providers (first usable wins, merged until we have enough candidates):
  1. Pexels            PEXELS_API_KEY         Pexels Licence (best stock quality)
  2. Unsplash          UNSPLASH_ACCESS_KEY    Unsplash Licence
  3. Pixabay           PIXABAY_API_KEY        Pixabay Content Licence
  4. Openverse         no key                 Flickr CC0 / PD / CC BY / CC BY-SA
  5. Wikimedia Commons no key                 CC0 / PD / CC BY / CC BY-SA

* Only licences that allow commercial use and putting text over the photo.
* Never photos from the news outlets themselves (copyrighted).
* Every provider is retried with backoff, so a transient 429/5xx no longer
  costs a poster its photo.

We download a few candidates per poster; the editor (AI or human) looks at the
contact sheet and picks one, or none.
"""
import html
import os
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image

UA = {"User-Agent": "PakImtehanPosters/1.0 (+https://pakimtehan.com)"}  # Flickr returns 403 to agents containing "Bot"
TIMEOUT = 35
RETRY_ON = {408, 425, 429, 500, 502, 503, 504}
MIN_BYTES = 40_000
MIN_WIDTH = 1000

OPENVERSE = "https://api.openverse.org/v1/images/"
PEXELS = "https://api.pexels.com/v1/search"
PIXABAY = "https://pixabay.com/api/"
UNSPLASH = "https://api.unsplash.com/search/photos"
COMMONS = "https://commons.wikimedia.org/w/api.php"


def _get(url, params=None, headers=None, attempts=4):
    """GET with backoff. Returns a 200 Response, or None after giving up."""
    err = None
    for i in range(attempts):
        try:
            r = requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            err = f"HTTP {r.status_code}"
            if r.status_code not in RETRY_ON:
                return None
        except Exception as e:  # noqa: BLE001 - network hiccups, truncated reads
            err = e
        if i < attempts - 1:
            time.sleep((2, 6, 12, 20)[i])
    print(f"  request failed for {url.split('?')[0]}: {err}")
    return None


def _pexels(query, want):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    r = _get(PEXELS, params=dict(
        query=query, orientation="landscape", size="medium",
        per_page=max(want * 3, 10)), headers={"Authorization": key})
    if r is None:
        return []
    out = []
    for it in (r.json().get("photos") or [])[:want]:
        src = it.get("src") or {}
        url = src.get("large2x") or src.get("large") or src.get("original")
        if not url:
            continue
        out.append({"url": url, "credit": f"{it.get('photographer') or 'Pexels'} / Pexels",
                    "source": it.get("url"), "title": it.get("alt") or ""})
    return out


def _openverse(query, want):
    r = _get(OPENVERSE, params=dict(
        q=query, source="flickr", license="cc0,pdm,by,by-sa", aspect_ratio="wide",
        mature="false", page_size=15))
    if r is None:
        return []
    out = []
    for it in (r.json().get("results") or [])[:want]:
        # Flickr hands out the 1024px "_b" size for these suffixes
        url = re.sub(r"(_[a-z])?\.jpg$", "_b.jpg", it.get("url") or "")
        if not url:
            continue
        lic = f"CC {str(it.get('license') or '').upper()} {it.get('license_version') or ''}".strip()
        lic = {"CC CC0 1.0": "CC0", "CC PDM 1.0": "Public Domain"}.get(lic, lic)
        who = (it.get("creator") or "Flickr")[:40]
        out.append({"url": url, "credit": f"{who} / Flickr, {lic}",
                    "source": it.get("foreign_landing_url"), "title": it.get("title") or ""})
    return out


def _pixabay(query, want):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    r = _get(PIXABAY, params=dict(
        key=key, q=query, image_type="photo", orientation="horizontal",
        safesearch="true", min_width=MIN_WIDTH, per_page=max(want * 3, 10)))
    if r is None:
        return []
    out = []
    for it in (r.json().get("hits") or [])[:want]:
        url = it.get("largeImageURL") or it.get("webformatURL")
        if not url:
            continue
        out.append({"url": url, "credit": f"{it.get('user') or 'Pixabay'} / Pixabay",
                    "source": it.get("pageURL"), "title": it.get("tags") or ""})
    return out


def _unsplash(query, want):
    key = os.environ.get("UNSPLASH_ACCESS_KEY") or os.environ.get("UNSPLASH_API_KEY")
    if not key:
        return []
    r = _get(UNSPLASH, params=dict(
        query=query, per_page=max(want * 3, 10), orientation="landscape",
        content_filter="high"), attempts=2)
    if r is None:
        return []
    out = []
    for it in (r.json().get("results") or [])[:want]:
        urls = it.get("urls") or {}
        url = urls.get("regular") or urls.get("full")
        if not url:
            continue
        who = ((it.get("user") or {}).get("name") or "Unsplash")[:40]
        out.append({"url": url, "credit": f"{who} / Unsplash",
                    "source": (it.get("links") or {}).get("html"),
                    "title": it.get("alt_description") or it.get("description") or "",
                    "_unsplash_download": (it.get("links") or {}).get("download_location")})
    return out


def _commons(query, want):
    r = _get(COMMONS, params=dict(
        action="query", format="json", generator="search",
        gsrsearch=f"filetype:bitmap {query}", gsrnamespace=6, gsrlimit=max(want * 4, 12),
        prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=1600))
    if r is None:
        return []
    ok_licence = re.compile(r"^(cc0|cc[- ]by|public domain|pd\b|no restrictions)", re.I)
    out = []
    pages = (r.json().get("query") or {}).get("pages") or {}
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licence = html.unescape(re.sub("<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value") or "")).strip()
        if not ok_licence.match(licence):
            continue
        w, h = info.get("width") or 0, info.get("height") or 0
        if not w or not h or w / h < 1.15:  # posters want landscape
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        who = html.unescape(re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value") or "")).strip()
        title = re.sub(r"^File:|\.\w+$", "", p.get("title") or "").replace("_", " ")
        out.append({"url": url, "credit": f"{who[:40] or 'Wikimedia'} / Wikimedia Commons, {licence}",
                    "source": info.get("descriptionurl"), "title": title[:80]})
        if len(out) >= want:
            break
    return out


PROVIDERS = [("pexels", _pexels), ("unsplash", _unsplash), ("pixabay", _pixabay),
             ("openverse", _openverse), ("commons", _commons)]


def _download(url, path):
    """Save `url` to `path` if it is a real, wide-enough photo. Returns its width or 0."""
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, stream=True)
        if r.status_code != 200 or not (r.headers.get("Content-Type") or "").startswith("image/"):
            return 0
        blob = r.content
    except Exception:
        return 0
    if len(blob) < MIN_BYTES:
        return 0
    path.write_bytes(blob)
    try:
        with Image.open(path) as im:
            width, height = im.size
    except Exception:
        path.unlink(missing_ok=True)
        return 0
    if width < MIN_WIDTH or width / max(height, 1) < 1.05:
        path.unlink(missing_ok=True)
        return 0
    return width


def candidates(query, dest_dir: Path, prefix: str, want=3):
    """Up to `want` photos for `query`, tried across every provider.

    Returns [{image, credit, image_source, title}], best provider first.
    """
    found, seen = [], set()
    if not query:
        return found
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name, provider in PROVIDERS:
        if len(found) >= want:
            break
        try:
            options = provider(query, want - len(found) + 2)
        except Exception as e:  # noqa: BLE001 - one bad provider must not stop the rest
            print(f"  {name} failed for {query!r}: {e}")
            continue
        for opt in options:
            url = opt["url"]
            if url in seen or len(found) >= want:
                continue
            seen.add(url)
            path = dest_dir / f"{prefix}-{chr(97 + len(found))}.jpg"
            if not _download(url, path):
                continue
            found.append({"image": str(path), "credit": opt["credit"],
                          "image_source": opt.get("source") or "", "title": opt.get("title") or "",
                          "_provider": name})
            if opt.get("_unsplash_download"):  # Unsplash guidelines: register the use
                try:
                    requests.get(opt["_unsplash_download"], headers=UA, timeout=10)
                except Exception:
                    pass
    if not found:
        print(f"  no photo found for {query!r} (tried {', '.join(n for n, _ in PROVIDERS)})")
    return found


def check():
    """Probe every provider so CI can fail fast when none of them work."""
    needed = {"pexels": ("PEXELS_API_KEY",), "unsplash": ("UNSPLASH_ACCESS_KEY", "UNSPLASH_API_KEY"),
              "pixabay": ("PIXABAY_API_KEY",)}
    usable = 0
    for name, provider in PROVIDERS:
        vars_ = needed.get(name)
        if vars_ and not any(os.environ.get(v) for v in vars_):
            print(f"  skipped {name}: {vars_[0]} not set")
            continue
        try:
            got = provider("solar panels", 3)
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED  {name} -> {e}")
            continue
        if got:
            usable += 1
            print(f"  usable  {name} ({len(got)} result(s), e.g. {got[0]['credit']})")
        else:
            print(f"  FAILED  {name} -> no results")
    print(f"  {usable} image provider(s) usable")
    return usable


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]:
        sys.exit(0 if check() else 1)
    print(__doc__)
