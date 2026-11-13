# Pak Imtehan news posters

Daily news posters for pakimtehan.com. Python does the fetching, photo search and rendering; Claude
does the editing. Posters are produced by the GitHub Action `.github/workflows/free-ai-posters.yml`
(free AI via `ai_editor.py`) and stored in the Cloudflare Worker `pakimtehan-posters` (D1) with every
value used to render them. GitHub does not store posters. `ROUTINE.md` is the older Claude-routine
flow, kept for reference.

Poster life cycle: daily run -> Worker (pending) -> dashboard (`pi_user_dashboard`, served by
`pi_user_server`) -> admin edits (Worker starts `.github/workflows/poster-edit.yml` -> `edit.py`
re-renders with the admin's exact text/photo, rev+1) -> approve (server copies the image to its own
disk on Namecheap, deletes it from the Worker) or reject (deleted from the Worker).

- `templates/` holds 6 HTML poster templates (1080×1350) with brand tokens in `base.css`. Fonts are
  bundled in `assets/fonts/`, so rendering works offline.
- `config/sources.yaml` lists the client's 27 channels and topics, and settings such as `posters_per_day`.
- `build.py fetch | photos | render` are the pipeline steps. `render.py` turns posts into JPEGs.
- `store.py` talks to the Worker's storage API; `edit.py` applies dashboard edits.
- `posters/<date>/` and `work/` are local scratch output and are never committed.
- `cloudflare/worker/` is the Worker: cron that starts the daily Action (GitHub's own scheduler
  never fired for this repo), the D1 storage API (`schema.sql`) and the edit dispatcher.
  Deploy with `cd cloudflare/worker && wrangler deploy`.

## Every session in this folder

1. **Start:** read `STATE.md` only (short "where we are"). Don't reread old transcripts or the whole repo.
2. **Find code:** use the graph first (`graphify query`, `graphify explain`, `graphify path`, rules below).
3. **Never start the poster workflow yourself** (`gh workflow run`) unless the user asks: runs must come
   from the Cloudflare Worker's schedule. Never write tokens or secrets into files or commits.
4. **After changing code:** `graphify update .` (free, AST only). The git hooks also do this on commit.
5. **After changing docs/markdown/PDF:** rebuild the semantic part:
   `set -a && . ~/.env && set +a && graphify extract . --backend gemini --token-budget 6000 && graphify cluster-only . --backend=gemini`
6. **End of each task:** update `STATE.md` (replace stale lines, keep it short), commit and push `main`.
7. Suggest a new session for each new task: a long session re-sends every earlier message on each turn.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
