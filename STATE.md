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

## Server and dashboard (other repos, not committed yet; review and commit there)
- `pi_user_server`: syncs from the Worker (NEWS_POSTERS_STORE_URL/TOKEN); approve copies image to
  NEWS_POSTERS_STORAGE_DIR then deletes from Worker; reject deletes from Worker; edit endpoints
  (`GET .../:id/source`, `PUT .../:id/edit-photo` raw image, `POST .../:id/edit`).
  Production DB needs `schema/news-posters-editing.sql` once (applied to local `pi_local` already).
- `pi_user_dashboard`: News Posters page with "Request changes" form.
- `pak-imtehan-website`: download name change only.

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
