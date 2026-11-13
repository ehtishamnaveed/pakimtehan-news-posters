// Starts the "Daily posters (free AI)" GitHub Action on a Cloudflare cron, because GitHub's own
// scheduler never fired for this repo. Secret: GITHUB_TOKEN (wrangler secret put GITHUB_TOKEN).
const REPO = "ehtishamnaveed/pakimtehan-news-posters";
const WORKFLOW = "free-ai-posters.yml";

async function dispatch(env) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "pakimtehan-posters-trigger",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  const text = await r.text();
  console.log(`dispatch -> HTTP ${r.status} ${text.slice(0, 200)}`);
  if (r.status !== 204) throw new Error(`GitHub dispatch failed: HTTP ${r.status}`);
}

export default {
  async scheduled(event, env, ctx) {
    console.log(`cron "${event.cron}" fired at ${new Date(event.scheduledTime).toISOString()}`);
    await dispatch(env);
  },
  // No public trigger: visiting the URL only says the worker is alive.
  async fetch() {
    return new Response("pakimtehan posters trigger: alive\n");
  },
};
