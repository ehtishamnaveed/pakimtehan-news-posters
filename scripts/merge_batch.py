"""Add one rendered batch to the output branch checkout.

    python scripts/merge_batch.py <posters/DATE> <out/posters/DATE> [prefix]

Without a prefix the batch is copied as-is (one batch per day, production).
With a prefix (test mode, several runs a day) each PNG is renamed "<prefix>-<name>" and its
entry is appended to that day's posters.json, so earlier batches stay and the server imports
only the new files.
"""
import json
import shutil
import sys
from pathlib import Path


def write_readme(dst: Path, posters):
    """One page per day that GitHub renders: every batch, newest first, with the real file names."""
    batches = {}
    for p in posters:
        batches.setdefault(p["png"].split("-")[0] if p["png"][:4].isdigit() and "-" in p["png"][5:] else "", []).append(p)
    md = [f"# Pak Imtehan posters - {dst.name}\n", f"{len(posters)} poster(s) in {len(batches)} batch(es).\n"]
    for key in sorted(batches, reverse=True):
        md.append(f"## Batch {key[:2]}:{key[2:]} (Pakistan time)\n" if key else "## Batch\n")
        for p in batches[key]:
            links = " · ".join(f"[{j + 1}]({l})" for j, l in enumerate(p.get("links") or []))
            md += [f"### {p['headline']}", f"![{p.get('template', '')}]({p['png']})",
                   f"*{p.get('summary', '')}*  ",
                   f"Template: `{p.get('template', '')}` · Source: {p.get('source', '')} · "
                   f"Editor: `{p.get('_editor', '?')}`  ", f"Links: {links}\n"]
    (dst / "README.md").write_text("\n".join(md))


def main(src: Path, dst: Path, prefix: str = ""):
    dst.mkdir(parents=True, exist_ok=True)
    new = json.loads((src / "posters.json").read_text())
    manifest = dst / "posters.json"
    existing = json.loads(manifest.read_text()) if (prefix and manifest.exists()) else []
    for p in new:
        name = f"{prefix}-{p['png']}" if prefix else p["png"]
        shutil.copy(src / p["png"], dst / name)
        p["png"] = name
    allp = existing + new
    manifest.write_text(json.dumps(allp, ensure_ascii=False, indent=1))
    write_readme(dst, allp)
    print(f"{len(new)} poster(s) added to {dst} ({len(existing) + len(new)} total for the day)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
