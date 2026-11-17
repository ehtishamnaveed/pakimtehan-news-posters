# Where we are (keep under ~80 lines; replace stale lines, don't append history)

Last updated: 2026-11-13

## How posters are made now
- GitHub Action `.github/workflows/free-ai-posters.yml` runs the pipeline with free AI
  (`ai_editor.py`: Gemini 3.6 Flash -> 3.5 Flash-Lite -> NVIDIA NIM -> OpenRouter -> Cloudflare).
- 15 posters per run (`config/sources.yaml` -> `posters_per_day`), JPEG q90 4:4:4 (~235 KB each).
- Output: stored in the Cloudflare Worker `pakimtehan-posters` (D1 database `pakimtehan-posters`)
  with all values + the photo, id `<date>_<HHMM batch>-<nn>`. GitHub no longer stores posters.

## Worker (`cloudflare/worker/`, https://pakimtehan-posters.ehtisham-bsit597.workers.dev)
- **PAUSED (13 Nov): Worker cron removed (`crons = []`) until the client meeting.** Crons take
  up to 15 min to propagate: set test times 20+ min ahead. GitHub's own cron was removed (never fired).
- Storage API (Bearer STORE_TOKEN): list/get/file/edit/render/delete posters, state (seen links, last_run).
- Edits: dashboard -> server -> Worker `POST /posters/<id>/edit` -> starts `poster-edit.yml` ->
  `edit.py` re-renders with the admin's exact text/photo -> rev+1 -> server sync shows it pending again.
- Secrets: GITHUB_TOKEN (dispatch), STORE_TOKEN. Same STORE_TOKEN in GitHub secret
  POSTERS_STORE_TOKEN and in `~/.config/pakimtehan-posters/store.env` (local server, mode 600).
- Old worker `pakimtehan-posters-trigger` deleted.

## Live News + local test setup (17 Nov, not committed/deployed yet)
- Each poster is also a Live News story: AI writes `category`, `breaking`, `key_points`, `body`; `sources` come from
  the real article links (`story.py`). Two new no-photo designs: `typographic` (blue) and `impact` (yellow).
- Server (`pi_user_server`) has NO poster table any more: pending = Worker/D1 (read live); approve writes
  `<News Posters dir>/<date>/<id>.jpg + .json` and deletes it from D1; reject deletes from D1; take down moves
  to `_taken-down/`. Public API `/api/v3/live-news[/:slug[/related]]`; admin batch `POST /admin/news-posters/batch`.
  Worker has new `POST /posters/:id/story` (story-only edits, no re-render) and `DEV_SKIP_DISPATCH`.
- Dashboard: select + batch approve/reject/edit (category, breaking), full edit form incl. story fields.
- Website branch `agent/2026-11-17-live-news`: `src/lib/liveNews.js` now calls the API (sample = VITE_LIVE_NEWS_SAMPLE=true).
- LOCAL: Worker `wrangler dev --local --port 8787 --compatibility-date 2026-09-28` (secrets in .dev.vars),
  `.venv-local/bin/python seed_local.py` seeds posters, `python edit.py` (env from ~/.config/pakimtehan-posters/local.env)
  stands in for the GitHub edit Action. Server .env has local Worker URL; website/dashboard `.env.local` point at :4000.
- BEFORE PRODUCTION: `wrangler deploy` (new endpoint), set server env STORE_URL/TOKEN/STORAGE_DIR, delete the
  website/dashboard `.env.local`, apply nothing in MySQL (old `news_posters` table is unused: drop it by hand).

## Branches
- `main` only is used now. `daily-posters-test` (old test output) is no longer written; can be deleted.
  Tag `archive/daily-posters` keeps the 12 Nov routine output.

## Open items
- Replace the classic GitHub token (pasted in chat) with a fine-grained one: this repo only,
  Actions read/write. `cd cloudflare/worker && wrangler secret put GITHUB_TOKEN`, then revoke the old one.
- Decide the Worker schedule: every 2 h for testing (`23 */2 * * *`) or daily production (`40 2 * * *`).
- Photo-library keys (PEXELS/UNSPLASH/PIXABAY) are not set as repo secrets.
- `docs/Pak-Imtehan-Poster-Automation.pdf` is untracked (not committed).

## Budget notes
- Daily run: ~7 min Actions; edit run: ~2 min (Chromium install). 2,000 free min/month (private repo).
- Gemini per run: ~18 requests, ~31k input tokens.
- D1 free: 5 GB, 100k writes/day. Each poster ~0.6 MB (image + photo as base64); rows deleted on
  approve/reject, so storage stays small.
