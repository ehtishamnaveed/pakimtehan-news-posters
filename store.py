"""Client for the pakimtehan-posters Worker, where posters wait (in Cloudflare D1) until an admin
approves or rejects them in the dashboard. GitHub no longer stores posters.

Env: POSTERS_STORE_URL (e.g. https://pakimtehan-posters.<sub>.workers.dev), POSTERS_STORE_TOKEN.

    python store.py pull-state                       # Worker -> state/seen.json (links already used)
    python store.py push-state <date>                # state/seen.json -> Worker, last_run = <date>
    python store.py ran-today <date>                 # exit 0 if a batch for <date> is already stored
    python store.py upload <posters/DATE> <batch>    # store every poster of a rendered batch
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
SEEN = ROOT / "state" / "seen.json"


def _base():
    url, tok = os.environ.get("POSTERS_STORE_URL"), os.environ.get("POSTERS_STORE_TOKEN")
    if not (url and tok):
        sys.exit("POSTERS_STORE_URL and POSTERS_STORE_TOKEN must be set")
    return url.rstrip("/"), {"Authorization": f"Bearer {tok}"}


def api(method, path, body=None, attempts=3):
    """One Worker call with retries on network errors and 5xx. Returns the JSON reply."""
    base, headers = _base()
    for i in range(attempts):
        try:
            r = requests.request(method, base + path, headers=headers, json=body, timeout=60)
            if r.status_code < 500:
                data = r.json()
                if not data.get("ok"):
                    raise RuntimeError(f"{method} {path}: HTTP {r.status_code} {data.get('error')}")
                return data
            err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            err = str(e)
        if i < attempts - 1:
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{method} {path} failed: {err}")


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def get_file(poster_id, kind, dest):
    """Save one stored file (image | photo | edit_photo) to `dest`. Returns the path, or None."""
    try:
        data = api("GET", f"/posters/{poster_id}/file/{kind}")
    except RuntimeError as e:
        if "404" in str(e):
            return None
        raise
    Path(dest).write_bytes(base64.b64decode(data["b64"]))
    return Path(dest)


def edits():
    return api("GET", "/edits")["posters"]


def put_render(poster_id, data, image_path, photo_path=None, keep_photo=False):
    body = {"data": data, "image": b64(image_path), "keep_photo": keep_photo}
    if photo_path:
        body["photo"] = b64(photo_path)
    return api("PUT", f"/posters/{poster_id}/render", body)


def edit_failed(poster_id, error):
    return api("POST", f"/posters/{poster_id}/edit-failed", {"error": error})


def cmd_pull_state():
    seen = api("GET", "/state/seen")["value"] or []
    SEEN.parent.mkdir(exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=0))
    print(f"{len(seen)} seen link(s) -> {SEEN.relative_to(ROOT)}")


def cmd_push_state(date):
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else []
    api("PUT", "/state/seen", {"value": seen})
    api("PUT", "/state/last_run", {"value": date})
    print(f"{len(seen)} seen link(s) saved; last_run = {date}")


def cmd_ran_today(date):
    last = api("GET", "/state/last_run")["value"]
    print(f"last stored batch: {last}")
    sys.exit(0 if last == date else 1)


def cmd_upload(folder, batch):
    folder = Path(folder)
    date = folder.name
    posters = json.loads((folder / "posters.json").read_text())
    for p in posters:
        num = p["file"].split("-", 1)[0]  # "01-editorial.jpg" -> "01"
        poster_id = f"{date}_{batch}-{num}"
        data = {k: v for k, v in p.items() if k not in ("photo_file",)}
        data["batch"] = batch
        body = {"date": date, "data": data, "image": b64(folder / p["file"])}
        if p.get("photo_file"):
            body["photo"] = b64(folder / p["photo_file"])
        api("POST", f"/posters/{poster_id}", body)
        print(f"stored {poster_id}  {p['headline'][:70]}")
    print(f"{len(posters)} poster(s) stored for review")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"pull-state": cmd_pull_state, "push-state": cmd_push_state, "ran-today": cmd_ran_today,
     "upload": cmd_upload}[cmd](*args)
