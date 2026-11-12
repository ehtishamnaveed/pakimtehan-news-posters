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


def main(src: Path, dst: Path, prefix: str = ""):
    dst.mkdir(parents=True, exist_ok=True)
    new = json.loads((src / "posters.json").read_text())
    manifest = dst / "posters.json"
    existing = json.loads(manifest.read_text()) if (prefix and manifest.exists()) else []
    for p in new:
        name = f"{prefix}-{p['png']}" if prefix else p["png"]
        shutil.copy(src / p["png"], dst / name)
        p["png"] = name
    manifest.write_text(json.dumps(existing + new, ensure_ascii=False, indent=1))
    if (src / "README.md").exists():
        shutil.copy(src / "README.md", dst / "README.md")
    print(f"{len(new)} poster(s) added to {dst} ({len(existing) + len(new)} total for the day)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
