# Pak Imtehan news posters

Daily news posters for pakimtehan.com. Python does the fetching, photo search and rendering; Claude
does the editing. To produce today's posters, follow `ROUTINE.md` exactly.

- `templates/` holds 6 HTML poster templates (1080×1350) with brand tokens in `base.css`. Fonts are
  bundled in `assets/fonts/`, so rendering works offline.
- `config/sources.yaml` lists the client's 27 channels and topics, and settings such as `posters_per_day`.
- `build.py fetch | photos | render` are the pipeline steps. `render.py` turns posts into PNGs.
- `posters/<date>/` holds the output that gets committed. `work/` is scratch and is never committed.
