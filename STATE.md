# Where we are (keep under ~80 lines; replace stale lines, don't append history)

Last updated: 2026-11-13

## How posters are made now
- GitHub Action `.github/workflows/free-ai-posters.yml` runs the pipeline with free AI
  (`ai_editor.py`: Gemini 3.6 Flash -> 3.5 Flash-Lite -> NVIDIA NIM -> OpenRouter -> Cloudflare).
- 15 posters per run (`config/sources.yaml` -> `posters_per_day`), JPEG q90 4:4:4 (~235 KB each).
- Output: branch `daily-posters-test`, one page per day:
  `posters/<date>/README.md` (every batch, newest first, batch label = Pakistan time).

## Scheduling
- GitHub's own cron never fired for this repo (checked 13 Nov: zero `schedule` runs ever).
- A Cloudflare Worker starts the Action instead: `cloudflare/trigger/` (worker `pakimtehan-posters-trigger`,
  deploy with `cd cloudflare/trigger && wrangler deploy`). GitHub token = Worker secret `GITHUB_TOKEN`.
- Confirmed working 13 Nov 12:40 PKT (run 43387480160, 15 JPEG posters).
- Current Worker cron: `40 7 * * *` (12:40 PKT, once a day, test). New/changed crons take up to
  15 min to reach Cloudflare: set test times 20+ min ahead.
- The workflow still also has GitHub cron `23 */2 * * *`; remove it once the Worker schedule is final
  (avoids duplicate runs if GitHub's scheduler ever wakes up).

## Branches
- `main` (code) and `daily-posters-test` (test output). `daily-posters` was deleted; its last output is
  tag `archive/daily-posters`.
- Repo variables: `POSTERS_OUT_BRANCH=daily-posters-test`, `POSTERS_TEST_MODE=true`.

## Open items
- Replace the classic GitHub token (it was pasted in chat) with a fine-grained one: this repo only,
  Actions read/write. Update with `wrangler secret put GITHUB_TOKEN`, then revoke the old one.
- Decide the Worker schedule: every 2 h for testing (`23 */2 * * *`) or daily production (`40 2 * * *`).
- Photo-library keys (`PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`, `PIXABAY_API_KEY`) are not set as repo
  secrets; only keyless Openverse + Wikimedia Commons are searched.
- Plan: send posters straight to the Pak Imtehan server API instead of storing them in the repo.
- Uncommitted JPEG support in other repos (review and commit there):
  `pi_user_server` (newsPosters.service.js, newsPoster.controller.js, NewsPoster.js),
  `pi_user_dashboard` (NewsPosters.jsx), `pak-imtehan-website` (CurrentAffairsPage.jsx).
- `docs/Pak-Imtehan-Poster-Automation.pdf` is untracked (not committed).

## Budget notes (per 15-poster run)
- ~7 min of Actions time (+1 min gate job); private repo has 2,000 free min/month.
- Gemini: ~18 requests, ~31k input tokens. Every-2-hours testing = ~96 Actions min/day.
