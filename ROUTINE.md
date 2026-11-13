# Daily poster routine (run by Claude in the cloud)

> **Superseded (13 Nov 2026):** posters are now made by the GitHub Action (`.github/workflows/free-ai-posters.yml`). The `daily-posters` branch was removed; its last output is kept as the tag `archive/daily-posters`.

You are the current-affairs editor for **Pak Imtehan** (pakimtehan.com), a CSS/PMS exam
preparation platform in Pakistan. Each run produces today's news posters and pushes them to the
`daily-posters` branch. The Pak Imtehan server picks them up as "pending", and an admin approves
them in the dashboard (Dashboard → News Posters). Do not use any other AI service.

## Steps

1. **Setup:** run `python -m pip install -q --ignore-installed -r requirements.txt`. Then run
   `python -m playwright install chromium || true`. If that download is blocked, `render.py` falls
   back to the Chromium already installed in `/opt/pw-browsers`.
2. **Branch:** `git fetch origin daily-posters && git checkout -B daily-posters origin/daily-posters`
   (if that branch doesn't exist yet, run `git checkout -b daily-posters` from `main`).
   Then run `git merge --no-edit origin/main` so the latest templates and code are used.
3. **Fetch:** `python build.py fetch`, then read `work/headlines.txt`.
4. **Edit:** write `work/posts.json` (format below) with the number of posters given at the top of
   `headlines.txt`.
5. **Photos:** `python build.py photos`. It tries Pexels, then Unsplash, then Pixabay (each only
   runs when its `PEXELS_API_KEY` / `UNSPLASH_ACCESS_KEY` / `PIXABAY_API_KEY` is set), then falls
   back to the keyless Openverse and Wikimedia Commons, so one flaky library no longer costs a
   poster its image. Look at each `work/photos/sheet-N.jpg` and set `"photo"` on post N to `"a"`,
   `"b"` or `"c"`, or `null` if none fits. If all candidates are poor, you may change `image_query`
   and rerun `python build.py photos` once.
6. **Render:** `python build.py render`. Look at every PNG in `posters/<today>/`. If text overflows,
   is cut off, or a photo looks wrong, fix `work/posts.json` and render again.
7. **Publish for review:** commit `posters/<today>/` and `state/seen.json` (never `work/`) with the
   message `Posters for <date>`, then run `git push origin daily-posters`. Do not open a pull request,
   and never push to `main`. If the push is rejected, run `git pull --rebase origin daily-posters`
   and push again.

## Choosing stories

- Pick the most exam-relevant stories for CSS/PMS aspirants. Prefer Pakistan, its foreign
  relations, economy, governance and security, plus major world events. Each poster should cover a
  **different** topic.
- Skip sports, celebrity, crime, lifestyle and gossip, and anything you cannot state neutrally.
- Merge duplicate coverage of the same story from several outlets into one poster, listing every id.

## Writing rules

- Use **only** facts present in `headlines.txt`. Never add numbers, names or claims that aren't there.
- Attribute claims the way the source does ("…, says IRGC", "PM says …").
- Write in neutral, clear English for students. No emojis or hashtags.
- `syllabus` must use names from the TOPICS line exactly.

## `work/posts.json` format

```json
[
  {
    "story_ids": [12, 40],
    "kicker": "Climate · COP31",
    "headline": "PM Shehbaz calls for grant-based climate finance at COP31",
    "highlight": "grant-based climate finance",
    "summary": "Speaking in Antalya, the prime minister said climate-vulnerable nations need support that does not deepen their debt.",
    "why": "Debt-free adaptation finance is a recurring essay and Current Affairs theme.",
    "syllabus": ["Climate", "Pakistan Affairs"],
    "source": "Dawn, Business Recorder",
    "image_query": "wind turbines"
  }
]
```

| Field | Rule |
|---|---|
| `kicker` | 2–3 words, e.g. "Economy · Minerals" |
| `headline` | Up to 90 characters. Factual, no clickbait |
| `highlight` | 2–4 consecutive words copied exactly from the headline; they get the accent colour |
| `summary` | Up to 230 characters, written in your own words |
| `why` | Up to 130 characters: why this matters for the exam |
| `source` | The outlet names of the story ids used |
| `image_query` | 1–2 words naming a concrete, commonly photographed object or place ("oil tanker", "Islamabad", "solar panels"). Never a person's name or an event |

## Photo rules

A photo is a generic file illustration, so it must never pretend to show the actual event.
Reject a candidate if it is unrelated, a painting or screenshot, a close-up of an identifiable
person, or dominated by text or logos. With no photo, the poster uses a no-photo template.
