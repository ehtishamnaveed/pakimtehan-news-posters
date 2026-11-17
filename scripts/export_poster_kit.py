"""Copy the poster templates, fonts, logos and design list into the dashboard, so its editor can draw the poster live.

    python scripts/export_poster_kit.py [path/to/pi_user_dashboard]

The dashboard renders the SAME templates (templates/*.html with nunjucks, a JavaScript twin of Jinja) and the same
CSS and fonts as render.py, so the live preview matches the final image. Run it again after changing a template
(it is the only copy step; the dashboard's public/poster-kit/ is generated, do not edit it by hand).
"""
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
dash = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "pi_user_dashboard"
out = dash / "public" / "poster-kit"
if out.exists():
    shutil.rmtree(out)
(out / "templates").mkdir(parents=True)
for f in (ROOT / "templates").iterdir():
    if f.suffix in (".html", ".css"):
        shutil.copy(f, out / "templates" / f.name)
shutil.copytree(ROOT / "assets", out / "assets")
catalog = yaml.safe_load((ROOT / "templates" / "catalog.yaml").read_text(encoding="utf-8"))["templates"]
(dash / "src" / "poster").mkdir(parents=True, exist_ok=True)  # bundled into the app (the dev server will not serve it from public/)
(dash / "src" / "poster" / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))
print(f"{len(catalog)} designs -> {out}")
