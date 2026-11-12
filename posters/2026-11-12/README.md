# Posters for 2026-11-12

**No posters were produced today.**

`python build.py fetch` returned 0 headlines from all 27 channels, on two attempts. Every
request to `news.google.com` is refused by the cloud environment's network proxy
(`CONNECT tunnel failed, response 403`). With no `headlines.txt` content, the routine cannot
write posts, because posts may use only facts from the fetched headlines.

**To fix:** allow `news.google.com` (and any other feed hosts in `config/sources.yaml`) in this
routine's cloud environment network settings, then re-run the routine.

Nothing was invented or filled in. Merging this PR changes no poster content.
