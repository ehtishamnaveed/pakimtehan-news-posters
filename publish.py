"""Step 5 — hand finished posters over for approval.

Approval flow ("I approve, it goes live"):
  * SITE_API_URL + SITE_API_TOKEN set  -> each poster is POSTed to the Pak Imtehan backend
    with status "pending". The client approves it in his admin dashboard and it goes live.
    (The backend needs this endpoint added; see README "Website endpoint".)
  * TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID set -> a preview of each poster is sent to his phone.
  * Neither set -> posters just stay in out/<date>/ (and as a GitHub Actions artifact).
"""
import json
import os

import requests


def send_to_site(poster):
    url, token = os.environ.get("SITE_API_URL"), os.environ.get("SITE_API_TOKEN")
    if not (url and token):
        return None
    meta = {k: poster.get(k) for k in ("kicker", "headline", "summary", "why", "syllabus", "source", "links", "template", "credit", "date")}
    with open(poster["file"], "rb") as fh:
        r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=60,
                          data={"status": "pending", "meta": json.dumps(meta)},
                          files={"image": (os.path.basename(poster["file"]), fh, "image/jpeg")})
    r.raise_for_status()
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else {"status": r.status_code}


def notify_telegram(poster, note=""):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    caption = f"*{poster['headline']}*\n{poster['summary']}\n\nSource: {poster['source']}\n{note}".strip()
    with open(poster["file"], "rb") as fh:
        requests.post(f"https://api.telegram.org/bot{tok}/sendPhoto", timeout=60,
                      data={"chat_id": chat, "caption": caption[:1000], "parse_mode": "Markdown"},
                      files={"photo": fh})


def publish(posters):
    for p in posters:
        res = None
        try:
            res = send_to_site(p)
        except Exception as e:
            print(f"  site upload failed: {e}")
        note = "Waiting for your approval in the Pak Imtehan dashboard." if res else ""
        notify_telegram(p, note)
        print(f"  {'sent to site (pending)' if res else 'saved locally'}: {os.path.basename(p['file'])}")
