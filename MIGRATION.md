# Moving the poster routine to the client's Claude account

> **Superseded (13 Nov 2026):** posters are now made by the GitHub Action (`.github/workflows/free-ai-posters.yml`). The `daily-posters` branch was removed; its last output is kept as the tag `archive/daily-posters`.

The routine is tied to the Claude account that created it. These are the steps to move it.

## 1. Repository
- Transfer `pakimtehan-news-posters` to the client's GitHub, or add the client as a collaborator.
  The repo must stay reachable by the GitHub account the client connects to Claude.
- Keep both branches: `main` (code and templates) and `daily-posters` (the routine's output).

## 2. Client's Claude account (Pro or higher)
1. At claude.ai, open **Settings → Connectors → GitHub**. Connect GitHub and install the **Claude
   GitHub App** on the account or org that owns the repo.
2. At claude.ai/code, open **Environments** and set network access on the environment the routine
   uses to **Full**, or to a custom allowlist that includes the news sites, `news.google.com`,
   `api.openverse.org`, `live.staticflickr.com`, `api.pixabay.com`, `pixabay.com`, `cdn.pixabay.com`,
   `api.unsplash.com`, `images.unsplash.com`, `api.pexels.com`, `images.pexels.com`,
   `commons.wikimedia.org`, `api.wikimedia.org`, `upload.wikimedia.org`,
   `pypi.org` and the Playwright CDN.
   Without this, the run fetches 0 headlines.
3. Recreate the routine at claude.ai/code/routines:
   - Repository: `<owner>/pakimtehan-news-posters`
   - Schedule: `0 3 * * *` (08:00 Asia/Karachi)
   - Model: Sonnet (uses less of the plan's allowance than Opus)
   - Tools: Bash, Read, Write, Edit, Glob, Grep
   - Prompt: copy it from the current routine. It tells Claude to follow `ROUTINE.md` and push to
     `daily-posters`, never `main`, with no pull request.
4. Click **Run now** once and check that `posters/<today>/` appears on `daily-posters`.
5. Disable the old routine on the original account so the two don't both run.

## 3. Production server (pi_user_server)
- No database table is needed: pending posters live in the Cloudflare Worker (D1) and approved ones are
  files in the News Posters folder.
- Add these to the production `.env`:
  - `NEWS_POSTERS_STORE_URL=https://pakimtehan-posters.<subdomain>.workers.dev`
  - `NEWS_POSTERS_STORE_TOKEN=<the Worker secret STORE_TOKEN>`
  - `NEWS_POSTERS_STORAGE_DIR=/home/<cpanel-user>/News Posters` (outside `public_html`; keep it in backups)
- Never set `DISABLE_SUBSCRIPTION_CRON` in production. It is for laptops only.
- Redeploy the Worker (`cd cloudflare/worker && wrangler deploy`) so the story, apply and discard endpoints exist.

## 4. If the repo owner changes
Update `REPO` in `cloudflare/worker/worker.js` and the Worker's `GITHUB_TOKEN`, then `wrangler deploy`.
Nothing else references the owner.

## 5. Things to know (Claude docs, Nov 2026)
- Scheduled tasks ("routines") are a **research preview**. Behaviour, limits and settings may change.
  Check claude.ai/code/routines after Anthropic announcements.
- They are included in Pro, Max, Team and Enterprise. Each run uses the account's normal Claude
  usage: the same 5-hour and weekly limits as chat and Claude Code. The cloud VM has no separate charge.
- If the account is at its usage limit, the run is **rejected** until the window resets, unless
  usage credits (extra usage) are turned on. **Keep usage credits OFF** so nothing is ever billed extra.
- If the GitHub connection breaks, runs are skipped for up to 72 hours, and then the task
  **turns itself off**. If posters stop arriving, check the GitHub connection first.
- The routine belongs to one person's account and can't be transferred; recreate it (section 2).
