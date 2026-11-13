"""Free-AI editor: does the Claude editor's job with free models, so the daily run can go on GitHub Actions.

    python ai_editor.py check    # one tiny request per provider; exits non-zero if none work
    python ai_editor.py write    # work/headlines.txt -> work/posts.json  (story choice + text)
    python ai_editor.py photos   # look at work/photos/sheet-N.jpg and set "photo" on each post

Providers are tried in order until one returns valid output (AI_PROVIDERS overrides). Gemini is the
primary editor; NVIDIA NIM and OpenRouter are independent backups, so a Gemini quota error no longer
kills the run:
    gemini:gemini-3.6-flash, gemini:gemini-3.5-flash-lite,
    nvidia:nvidia/nemotron-3-ultra-550b-a55b, openrouter:nvidia/nemotron-3-ultra-550b-a55b:free,
    cloudflare:@cf/google/gemma-4-26b-a4b-it
Keys come from the environment only: GEMINI_API_KEY, NVIDIA_API_KEY, OPENROUTER_API_KEY,
CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN.
"""
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
# gemini-3.5-flash was retired and is auto-routed to gemini-3.6-flash; call the live name directly.
# Gemini stays first (best quality, and one batch a day is a single call). NVIDIA NIM is the backup,
# OpenRouter is a second backup serving the same Nemotron models on a separate free quota, so a
# Gemini 429 no longer ends the run.
NVIDIA_TEXT = "nvidia/nemotron-3-ultra-550b-a55b"
NVIDIA_VISION = "nvidia/nemotron-3.5-super-vl-120b-a12b"
OPENROUTER_TEXT = "nvidia/nemotron-3-ultra-550b-a55b:free"
OPENROUTER_VISION = "nvidia/nemotron-3.5-super-vl:free"

OPENAI_COMPAT = {
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", {}),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                   {"HTTP-Referer": "https://pakimtehan.com", "X-Title": "Pak Imtehan posters"}),
}

DEFAULT_PROVIDERS = (f"gemini:gemini-3.6-flash,gemini:gemini-3.5-flash-lite,"
                     f"nvidia:{NVIDIA_TEXT},nvidia:{NVIDIA_VISION},"
                     f"openrouter:{OPENROUTER_TEXT},"
                     f"cloudflare:@cf/google/gemma-4-26b-a4b-it")
# Photo picks: Flash-Lite first. In the 13 Nov run 3.6 Flash returned 429/timeouts on 13 of 15 picks
# and spent ~980 thinking tokens on each a/b/c answer; Flash-Lite answered every one in seconds.
VISION_PROVIDERS = (f"gemini:gemini-3.5-flash-lite,gemini:gemini-3.6-flash,"
                    f"nvidia:{NVIDIA_VISION},openrouter:{OPENROUTER_VISION}")

EDITOR_PROMPT = """You are the current-affairs editor for Pak Imtehan (pakimtehan.com), a CSS/PMS exam
preparation platform in Pakistan. From the headlines below, choose the {n} most exam-relevant stories
and write one poster for each.

Choosing stories:
- Prefer Pakistan, its foreign relations, economy, governance and security, plus major world events.
- Each poster must cover a DIFFERENT topic.
- Skip sports, celebrity, crime, lifestyle and gossip, and anything you cannot state neutrally.
- If several outlets report the same story, merge them into one poster and list every id.

Writing rules:
- Use ONLY facts present in the headline/teaser text. Never add numbers, names or claims that are not there.
- Attribute claims the way the source does ("..., says IRGC", "PM says ...").
- Neutral, clear English for students. No emojis, no hashtags.

Return ONLY a JSON array with exactly {n} objects, each with these keys:
  "story_ids":   list of ids (integers) from the HEADLINES list used for this poster
  "kicker":      2-3 words, e.g. "Economy · Minerals"
  "headline":    max 90 characters, factual, no clickbait
  "highlight":   2-4 consecutive words copied EXACTLY from your headline
  "summary":     max 230 characters, in your own words
  "why":         max 130 characters: why it matters for CSS/PMS aspirants
  "syllabus":    1-3 items copied exactly from TOPICS
  "source":      outlet names of the ids used, comma separated
  "image_query": 1-2 words naming a concrete, commonly photographed object or place
                 (e.g. "oil tanker", "Islamabad", "solar panels"); never a person's name or an event

{headlines}
"""

PHOTO_PROMPT = """This contact sheet shows candidate photos labelled a, b, c for a news poster.
Headline: {headline}
Wanted photo: {query}
The photo is a generic illustration (credited as a file photo), so it must not pretend to show the
actual event. Reject a candidate that is unrelated, a painting/drawing/screenshot, a close-up of an
identifiable person's face, or dominated by text or logos, or shows foreign currency for a Pakistan story.
Reply with ONLY one of: a, b, c, none"""

SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "story_ids": {"type": "array", "items": {"type": "integer"}},
            "kicker": {"type": "string"}, "headline": {"type": "string"}, "highlight": {"type": "string"},
            "summary": {"type": "string"}, "why": {"type": "string"},
            "syllabus": {"type": "array", "items": {"type": "string"}},
            "source": {"type": "string"}, "image_query": {"type": "string"},
        },
        "required": ["story_ids", "kicker", "headline", "highlight", "summary", "why", "syllabus", "source", "image_query"],
    },
}


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def _gemini(model, prompt, image=None, json_mode=False, max_tokens=4096, timeout=180):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    parts = [{"text": prompt}]
    if image:
        parts.insert(0, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}})
    cfg = {"temperature": 0.3, "maxOutputTokens": max_tokens}
    if json_mode and not model.startswith("gemma"):  # Gemma on the Gemini API has no JSON mode
        cfg.update(responseMimeType="application/json", responseSchema=SCHEMA)
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": key}, timeout=timeout,
                      json={"contents": [{"role": "user", "parts": parts}], "generationConfig": cfg})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    d = r.json()
    cand = (d.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
    if not text:
        raise RuntimeError(f"empty response ({cand.get('finishReason')})")
    u = d.get("usageMetadata", {})
    print(f"    tokens: {u.get('promptTokenCount')} in / {u.get('candidatesTokenCount')} out"
          + (f" / {u['thoughtsTokenCount']} thinking" if u.get("thoughtsTokenCount") else ""))
    return text


def _cloudflare(model, prompt, image=None, json_mode=False, max_tokens=4096, timeout=180):
    acc, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not (acc and tok):
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set")
    if image:
        raise RuntimeError("vision not used on Cloudflare")
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}",
                      headers={"Authorization": f"Bearer {tok}"}, timeout=timeout,
                      json={"messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens, "temperature": 0.3})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    res = r.json().get("result") or {}
    text = res.get("response")
    if text is None and res.get("choices"):  # OpenAI-style shape
        text = res["choices"][0]["message"]["content"]
    if isinstance(text, (list, dict)):
        text = json.dumps(text)
    if not text:
        raise RuntimeError("empty response")
    return text


def _openai_compat(kind, model, prompt, image=None, json_mode=False, max_tokens=4096, timeout=180):
    """One adapter for every OpenAI-compatible endpoint (NVIDIA NIM, OpenRouter).

    Both providers serve the same Nemotron models, but on separate quota pools, so a 429 on one
    does not take out the other.
    """
    base, env, extra = OPENAI_COMPAT[kind]
    key = os.environ.get(env)
    if not key:
        raise RuntimeError(f"{env} not set")
    if image:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}},
        ]
    else:
        content = prompt
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens, "temperature": 0.3, "top_p": 0.95}
    # No response_format here: the prompt asks for a JSON *array*, and the json_object mode some
    # providers enforce would wrap it in an object. extract_json_array() handles prose/fences instead.
    r = requests.post(f"{base}/chat/completions",
                      headers={"Authorization": f"Bearer {key}", "Accept": "application/json", **extra},
                      timeout=timeout, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    d = r.json()
    choice = (d.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content")
    if isinstance(text, (list, dict)):
        text = json.dumps(text)
    if not text:
        raise RuntimeError(f"empty response ({choice.get('finish_reason')})")
    u = d.get("usage") or {}
    cost = u.get("cost")
    print(f"    tokens: {u.get('prompt_tokens')} in / {u.get('completion_tokens')} out"
          + (f" / ${cost}" if cost else ""))
    return text


def _nvidia(model, prompt, **kw):
    """NVIDIA NIM, called directly with an NVIDIA_API_KEY."""
    return _openai_compat("nvidia", model, prompt, **kw)


def _openrouter(model, prompt, **kw):
    """OpenRouter, same models on a separate free-tier quota."""
    return _openai_compat("openrouter", model, prompt, **kw)


# Minimum seconds between two requests to the same model. Gemini's free tier allows only a few
# requests per minute per model: in the 12 Nov run, back-to-back photo calls got 429s. 15 photo
# calls at this pace take ~2 min instead of hitting the limit.
MIN_GAP = {"gemini": 7.0}
_last_call = {}


def _pace(spec):
    gap = MIN_GAP.get(spec.split(":", 1)[0], 0)
    wait = _last_call.get(spec, 0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call[spec] = time.monotonic()


def call(spec, prompt, **kw):
    kind, model = spec.split(":", 1)
    fn = {"gemini": _gemini, "cloudflare": _cloudflare,
          "nvidia": _nvidia, "openrouter": _openrouter}[kind]
    for attempt in range(2):
        _pace(spec)
        try:
            return fn(model, prompt, **kw)
        except RuntimeError as e:
            msg = str(e)
            # 429 means the quota is gone for the day: waiting seconds cannot fix it, so move to the
            # next provider immediately. Only a 5xx (temporary server fault) is worth one quick retry.
            if attempt == 0 and re.search(r"HTTP 5\d\d", msg):
                time.sleep(3)
                continue
            raise


def probe(spec):
    """Is this provider usable right now? One 1-token request, no retries. -> (ok, detail)."""
    try:
        call(spec, "Reply with the single word OK.", max_tokens=16, timeout=30)
        return True, ""
    except Exception as e:  # noqa: BLE001 - any error means "not usable right now"
        msg = str(e)
        if "empty response" in msg:  # endpoint answered, it just had no room for text
            return True, ""
        return False, msg[:140]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def extract_json_array(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        raise ValueError("no JSON array in response")
    return json.loads(text[start:end + 1])


def validate(posts, n_items, topics, want):
    good = []
    used_ids = set()
    for p in posts if isinstance(posts, list) else []:
        if not isinstance(p, dict):
            continue
        ids = [i for i in p.get("story_ids", []) if isinstance(i, int) and 0 <= i < n_items]
        headline = str(p.get("headline", "")).strip()
        if not ids or not headline or used_ids & set(ids):
            continue
        hl = str(p.get("highlight", "")).strip()
        syllabus = [s for s in p.get("syllabus", []) if s in topics][:3] or ["Current Affairs"]
        good.append({
            "story_ids": ids,
            "kicker": str(p.get("kicker", "Current Affairs")).strip()[:40],
            "headline": headline[:110],
            "highlight": hl if hl and hl in headline else "",
            "summary": str(p.get("summary", "")).strip()[:300],
            "why": str(p.get("why", "")).strip()[:180],
            "syllabus": syllabus,
            "source": str(p.get("source", "")).strip()[:120],
            "image_query": str(p.get("image_query", "")).strip()[:40],
        })
        used_ids |= set(ids)
        if len(good) >= want:
            break
    return good


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check():
    """Stop the run before any expensive work if every AI provider is out of quota."""
    specs = [s.strip() for s in os.environ.get("AI_PROVIDERS", DEFAULT_PROVIDERS).split(",") if s.strip()]
    usable = []
    for spec in specs:
        ok, detail = probe(spec)
        print(f"  {'usable' if ok else 'FAILED':6s} {spec}" + ("" if ok else f"  -> {detail}"))
        if ok:
            usable.append(spec)
    if not usable:
        sys.exit("No AI provider is usable right now (quota exhausted or key problem). "
                 "Stopping now instead of spending runner minutes.")
    print(f"  {len(usable)}/{len(specs)} provider(s) usable")


def cmd_write():
    text = (WORK / "headlines.txt").read_text(encoding="utf-8")
    topics = [t.strip() for t in text.splitlines()[0].removeprefix("TOPICS:").split(",")]
    want = int(re.search(r"POSTERS WANTED:\s*(\d+)", text).group(1))
    n_items = len(json.loads((WORK / "headlines.json").read_text()))
    heads = json.loads((WORK / "headlines.json").read_text())
    prompt = EDITOR_PROMPT.format(n=want, headlines=text)
    # Cloudflare's free tier is 10,000 neurons/day: send it a shorter list (header + first 90 headlines).
    lines = text.splitlines()
    short_prompt = EDITOR_PROMPT.format(n=want, headlines="\n".join(lines[:5 + 90]))

    # ~180 output tokens per poster, plus room for Gemini thinking / Nemotron reasoning tokens,
    # which count against the same limit. 15 posters -> 15000. Cloudflare's free tier is smaller.
    need = max(1, -(-want * 4 // 5))  # accept 80% (12 of 15) rather than failing the whole run
    best = []

    def save(posts, spec):
        for p in posts:  # fill outlet names from the real ids if the model left them out
            if not p["source"]:
                p["source"] = ", ".join(dict.fromkeys(heads[i]["source"] for i in p["story_ids"]))
            p["_editor"] = spec
        (WORK / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=1))
        print(f"  {len(posts)} poster(s) written by {spec}")

    for spec in os.environ.get("AI_PROVIDERS", DEFAULT_PROVIDERS).split(","):
        spec = spec.strip()
        print(f"  trying {spec} ...")
        budget = 4096 if spec.startswith("cloudflare:") else max(8192, want * 600 + 6000)
        try:
            raw = call(spec, short_prompt if spec.startswith("cloudflare:") else prompt,
                       json_mode=True, max_tokens=budget)
            posts = validate(extract_json_array(raw), n_items, topics, want)
        except Exception as e:  # noqa: BLE001 - any failure means: try the next provider
            print(f"    failed: {str(e)[:160]}")
            continue
        if len(posts) < need:
            print(f"    only {len(posts)} valid poster(s) (need {need}), trying next provider")
            if len(posts) > len(best[0] if best else []):
                best = [posts, spec]
            continue
        save(posts, spec)
        return
    if best:  # nobody reached the target: publish the largest partial batch rather than nothing
        save(*best)
        return
    sys.exit("All AI providers failed; no posters written.")


def cmd_photos():
    posts = json.loads((WORK / "posts.json").read_text())
    providers = os.environ.get("AI_VISION_PROVIDERS", VISION_PROVIDERS).split(",")
    for i, p in enumerate(posts, 1):
        sheet = WORK / "photos" / f"sheet-{i}.jpg"
        labels = [chr(97 + j) for j in range(len(p.get("candidates", [])))]
        p["photo"] = None
        if not sheet.exists() or not labels:
            continue
        for spec in providers:
            try:
                ans = call(spec.strip(), PHOTO_PROMPT.format(headline=p["headline"], query=p.get("image_query", "")),
                           image=sheet.read_bytes(), max_tokens=1024, timeout=60).strip().lower()
            except Exception as e:  # noqa: BLE001
                print(f"  post {i}: {spec} failed: {str(e)[:120]}")
                continue
            m = re.search(r"\b(none|[abc])\b", ans)
            pick = m.group(1) if m else "none"
            p["photo"] = pick if pick in labels else None
            print(f"  post {i}: photo {p['photo'] or 'none'} (by {spec})")
            break
    (WORK / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"write": cmd_write, "photos": cmd_photos, "check": cmd_check}[sys.argv[1]]()
