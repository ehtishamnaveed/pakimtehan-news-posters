# Live News: step-by-step production deployment

Sites: `pakimtehan.com` (website) · `dashboard.pakimtehan.com` (dashboard) · `api.dashboard.pakimtehan.com` (API server).
All three are on the same Namecheap hosting, so the API server can write into the website's folder.

Rules for this deployment:
- Do the steps in order. Each step ends with a **Check**; do not continue until it passes.
- Nothing here starts the daily poster run. The Cloudflare schedule stays off until Step 10.
- Keep every token in a password manager. Never paste tokens into chat, files or commits.

Before you start you need: this laptop with `git`, `node`, `npm` and `wrangler` (logged in with `wrangler login`),
your cPanel login, and your GitHub login.

---

## Step 1. Make three folders and note the paths (cPanel → File Manager)

1. **Website folder.** The folder pakimtehan.com is served from, usually `/home/<user>/public_html`. Write it down.
2. **API app folder.** cPanel → *Setup Node.js App* → the app for `api.dashboard.pakimtehan.com`. Write down its path.
3. **News Posters folder.** In File Manager, go to `/home/<user>/` (NOT inside `public_html`) → *+ Folder* → name it `News Posters`
   (with the space) → right-click → *Change Permissions* → `750`.

Why outside `public_html`: approved posters must only be served through the API, never as raw files.
**Check:** you have three paths written down and the folder `/home/<user>/News Posters` exists.

## Step 2. Cloudflare Worker (the temporary poster store)

```bash
cd ~/Documents/GitHub/pakimtehan-news-posters/cloudflare/worker
wrangler login                       # only if it asks
openssl rand -hex 32                 # prints a new token: copy it to your password manager (call it STORE_TOKEN)
wrangler secret put STORE_TOKEN      # paste the token when asked
```

Create a GitHub token for the Worker (it starts the edit job):
GitHub → Settings → Developer settings → *Fine-grained tokens* → *Generate new token* →
Repository access: **Only select repositories** → `pakimtehan-news-posters` → Permissions → **Actions: Read and write** →
generate, copy it, then:

```bash
wrangler secret put GITHUB_TOKEN     # paste the fine-grained token
wrangler deploy
```

Afterwards open GitHub → Settings → Tokens and **delete the old classic token** that was pasted in chat.

Also set the same token for the GitHub Actions: repo `pakimtehan-news-posters` → Settings → *Secrets and variables* → Actions:
- Secret `POSTERS_STORE_TOKEN` = the STORE_TOKEN from above
- Variable `POSTERS_STORE_URL` = `https://pakimtehan-posters.<your-subdomain>.workers.dev`

**Check:**
```bash
curl https://pakimtehan-posters.<your-subdomain>.workers.dev/health          # prints: pakimtehan-posters: alive
curl -H "Authorization: Bearer <STORE_TOKEN>" https://pakimtehan-posters.<your-subdomain>.workers.dev/usage
# prints {"ok":true,"posters":0,"files":0,...}
```
Do NOT set `DEV_SKIP_DISPATCH` on the real Worker, and leave `crons = []` in `wrangler.toml` for now.

## Step 3. Push the posters repo

```bash
cd ~/Documents/GitHub/pakimtehan-news-posters
git push origin main
```
The Worker starts the GitHub jobs from `main`, so the new templates, story fields and edit logic must be there.
Pushing does not start any run.
**Check:** GitHub shows the latest commit on `main` ("Add production deploy checklist for Live News" or newer).

## Step 4. API server (api.dashboard.pakimtehan.com)

1. **Get the new code onto the hosting.** Push the `pi_user_server` branch you deploy from, then update the app folder the way you
   normally do (cPanel *Git Version Control* → *Update from remote*, or upload the changed files).
2. **Set the environment** (cPanel → *Setup Node.js App* → your app → *Environment variables*). Add or change:

   | Name | Value |
   |---|---|
   | `NEWS_POSTERS_STORE_URL` | `https://pakimtehan-posters.<your-subdomain>.workers.dev` |
   | `NEWS_POSTERS_STORE_TOKEN` | the STORE_TOKEN from Step 2 |
   | `NEWS_POSTERS_STORAGE_DIR` | `/home/<user>/News Posters` |
   | `NEWS_SEO_WEBROOT` | the website folder from Step 1, e.g. `/home/<user>/public_html` |
   | `NEWS_SITE_URL` | `https://pakimtehan.com` |
   | `ALLOWED_ORIGINS` | must include `https://pakimtehan.com`, `https://www.pakimtehan.com`, `https://dashboard.pakimtehan.com` |
   | `NEWS_INDEXNOW_KEY` | optional, any 8–128 character key (tells Bing about new pages at once) |

   Delete these if they exist: `NEWS_POSTERS_GITHUB_REPO`, `NEWS_POSTERS_GITHUB_BRANCH`, `NEWS_POSTERS_GITHUB_TOKEN`,
   `NEWS_POSTERS_SYNC_CRON`, `NEWS_POSTERS_SYNC_DAYS`, `NEWS_POSTERS_LOCAL_DIR`. Never set `DISABLE_SUBSCRIPTION_CRON`.
3. Click **Restart** on the Node app.

**Check:**
```bash
curl https://api.dashboard.pakimtehan.com/api/v3/live-news
# prints {"success":true,"items":[],"total":0,...}
```
and the app's log (cPanel → the app → *Open logs*, or `stderr.log`) shows `[NewsSeo] Writing Live News pages into /home/<user>/public_html`.
No database change is needed. The old `news_posters` table is unused; drop it by hand if it exists.

## Step 5. Dashboard (dashboard.pakimtehan.com)

On this laptop, local settings must not leak into the build:
```bash
cd ~/Documents/GitHub/pi_user_dashboard
mv .env.local .env.local.off          # if it exists
npm run build
mv .env.local.off .env.local          # put it back for local work
```
Upload everything inside `dist/` to the dashboard's folder in cPanel, replacing the old files.
**Check:** log in at `https://dashboard.pakimtehan.com`, open **News Posters**: it shows "No posters waiting for review" (and no red
"storage not configured" message).

## Step 6. Website (pakimtehan.com)

```bash
cd ~/Documents/GitHub/pak-imtehan-website
mv .env.local .env.local.off          # if it exists: it points the site at localhost
npm run build                         # needs Chrome/Chromium for the pre-render step
mv .env.local.off .env.local
```
Merge the `agent/2026-11-17-live-news` branch the way you normally do (pull request), then upload everything inside `dist/` to
`public_html`. Keep (do not delete) anything the API writes there: `_pages/live-news*`, `live-news/posters/`,
`live-news-sitemap.xml`, `news-sitemap.xml`. If a deploy removes them, the API recreates them within 20 minutes.
**Check:** `https://pakimtehan.com/live-news` opens and shows the sample posters. `public_html/spa.html` exists (the API needs it).

## Step 7. First real batch (do this when you are ready)

1. GitHub → repo → *Actions* → **Daily posters (free AI)** → *Run workflow* → *Run*. It takes about 7 minutes.
2. Dashboard → **News Posters**: the new posters appear under *Pending review*.
3. Open one → **Edit** → change a word → **Save changes** → back in the list click **Update poster image**. About a minute later the
   new image appears and the status returns to *Ready to review*.
4. Click **Approve**.

**Check:**
- cPanel → `News Posters/<date>/` holds `<id>.jpg` and `<id>.json`.
- `curl -H "Authorization: Bearer <STORE_TOKEN>" https://pakimtehan-posters.<sub>.workers.dev/usage` shows that poster is gone.
- `https://pakimtehan.com/live-news` lists the story, and clicking it opens `/live-news/<slug>` as a full page.

## Step 8. Check what Google will see

1. Open `https://pakimtehan.com/live-news/<slug>` → right-click → *View page source*. You must see the `<title>`, a
   `rel="canonical"` link, `application/ld+json` and the article text in the HTML.
2. Open `https://pakimtehan.com/live-news-sitemap.xml` and `https://pakimtehan.com/news-sitemap.xml`: both list the story.
3. Paste the story URL into Google's *Rich Results Test* (search.google.com/test/rich-results): it should detect a News article.

## Step 9. Tell the search engines (once)

- Google Search Console → *Sitemaps* → add `live-news-sitemap.xml` and `news-sitemap.xml` → Submit.
- Bing Webmaster Tools → import your site from Search Console. Optional: set `NEWS_INDEXNOW_KEY` (Step 4).
Indexing takes days to weeks; the sitemaps update by themselves after every approve, edit or take-down.

## Step 10. Turn on the daily schedule (after the client meeting)

Edit `cloudflare/worker/wrangler.toml`: set `crons = ["40 2 * * *"]` (07:40 Pakistan time), then:
```bash
cd ~/Documents/GitHub/pakimtehan-news-posters/cloudflare/worker && wrangler deploy
```
The change can take up to 15 minutes to take effect.

---

## If something goes wrong

| You see | Do this |
|---|---|
| Dashboard says storage is not configured | `NEWS_POSTERS_STORE_URL` / `_TOKEN` missing or wrong on the API app; restart it |
| Dashboard shows no posters after a run | Check the Actions run finished; check the token in the GitHub secret equals the Worker's STORE_TOKEN |
| "Update poster image" stays on *Updating image…* over 5 minutes | GitHub → Actions → **Poster edits**: look at the run; usually `GITHUB_TOKEN` on the Worker is wrong or expired |
| Approve fails | Check the News Posters folder exists and is writable by the Node app; read the app log |
| Website shows no stories / CORS error in the browser console | `ALLOWED_ORIGINS` is missing `https://pakimtehan.com`; fix and restart |
| Story pages not written | App log has no `[NewsSeo]` line → `NEWS_SEO_WEBROOT` unset; "spa.html not found" → wrong path or the website was not built with `npm run build` |
| Story page not served from the website | The `.htaccess` from the website build is missing in `public_html` (re-upload `dist/` including dotfiles) |
| Pages disappeared after a website deploy | Wait up to 20 minutes, or restart the Node app (it rebuilds at start) |

## Rollback
- Website / dashboard: re-upload the previous `dist/`.
- Server: redeploy the previous code. Approved stories stay safe in the News Posters folder.
- Stop writing pages for search engines: remove `NEWS_SEO_WEBROOT` and restart (existing pages stay).
