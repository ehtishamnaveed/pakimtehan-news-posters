# Moving the poster routine to the client's Claude account

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
   `api.openverse.org`, `live.staticflickr.com`, `pypi.org` and the Playwright CDN.
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
- Run `schema/news-posters.sql` once (production doesn't auto-create tables).
- Add these to the production `.env`:
  - `NEWS_POSTERS_GITHUB_REPO=<owner>/pakimtehan-news-posters`
  - `NEWS_POSTERS_GITHUB_BRANCH=daily-posters`
  - `NEWS_POSTERS_GITHUB_TOKEN=<fine-grained token: this repo only, Contents read-only>`
- Never set `DISABLE_SUBSCRIPTION_CRON` in production. It is for laptops only.
- The poster PNGs are stored in `storage/news-posters/` (or `NEWS_POSTERS_STORAGE_DIR`). Keep it on
  persistent disk and include it in backups.

## 4. If the repo owner changes
Update `NEWS_POSTERS_GITHUB_REPO` and issue a new token. Nothing else references the owner, except
`scripts/local-stack.sh` (the local test launcher).
