"""Design selection tests. Run:  python -m unittest discover -s tests -v   (from the repo root)"""
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import select_template as st  # noqa: E402
from story import normalize_story  # noqa: E402


def story(**kw):
    base = {"headline": "PM Shehbaz calls for grant-based climate finance for vulnerable countries", "category": "climate-environment",
            "syllabus": ["Climate"], "summary": "x", "why": "y", "source": "Dawn"}
    base.update(kw)
    return normalize_story(base)


class Catalog(unittest.TestCase):
    def test_every_design_has_a_layout_file(self):
        for t in st.CATALOG:
            self.assertTrue((ROOT / "templates" / f"{t['layout']}.html").exists(), t["id"])

    def test_ids_are_unique_and_valid(self):
        ids = [t["id"] for t in st.CATALOG]
        self.assertEqual(len(ids), len(set(ids)))
        for t in st.CATALOG:
            self.assertIn(t.get("photo"), ("required", "optional", "none"), t["id"])
            for tone in t.get("tones", []):
                self.assertIn(tone, st.TONES, t["id"])

    def test_only_website_blues_and_white(self):
        """Client requirement: only the website's blues, navy and white. No yellow, red, black, green, violet, orange or cream."""
        import colorsys
        import re
        for f in (ROOT / "templates").glob("*"):
            for m in re.finditer(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", f.read_text(encoding="utf-8", errors="ignore")):
                h = m.group(1)
                h = "".join(c * 2 for c in h) if len(h) == 3 else h
                r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
                hue, sat, val = colorsys.rgb_to_hsv(r, g, b)
                hue *= 360
                blue = 195 <= hue <= 255 and sat >= 0.12
                white = sat < 0.12 and val > 0.85
                self.assertTrue(blue or white, f"{f.name}: #{m.group(1)} is not a website blue or white")

    def test_enough_variety(self):
        self.assertGreaterEqual(len(st.CATALOG), 30)
        self.assertGreaterEqual(len({t["family"] for t in st.CATALOG}), 8)


class Eligibility(unittest.TestCase):
    def test_photo_required_designs_need_a_photo(self):
        for _ in range(40):
            pick = st.choose(story(), False, rng=random.Random(_))
            self.assertNotEqual(st.BY_ID[pick]["photo"], "required")

    def test_number_designs_only_with_a_number(self):
        for _ in range(40):
            pick = st.choose(story(), True, rng=random.Random(_))
            self.assertNotIn("stat", st.BY_ID[pick].get("needs", []))
        with_stat = story(stat_value="22GW", stat_label="rooftop solar added")
        picks = {st.choose(with_stat, False, rng=random.Random(i)) for i in range(60)}
        self.assertTrue(any("stat" in st.BY_ID[p].get("needs", []) for p in picks))

    def test_quote_designs_only_with_a_quote(self):
        for i in range(40):
            self.assertNotIn("quote", st.BY_ID[st.choose(story(), True, rng=random.Random(i))].get("needs", []))
        quoted = story(quote="We will not accept debt traps", speaker="Prime Minister", tone="statement")
        picks = Counter(st.choose(quoted, True, rng=random.Random(i)) for i in range(60))
        self.assertTrue(any("quote" in st.BY_ID[p].get("needs", []) for p in picks))


class Fit(unittest.TestCase):
    def test_breaking_security_prefers_urgent_designs(self):
        p = story(category="security-defence", breaking=True, headline="Two oil tankers disabled by explosions in the Strait of Hormuz")
        fams = Counter(st.BY_ID[st.choose(p, True, rng=random.Random(i))]["family"] for i in range(80))
        self.assertGreater(fams["breaking"] + fams["politics"] + fams["security"], 60)

    def test_remembrance_prefers_solemn(self):
        p = story(category="security-defence", tone="solemn", headline="Nation honours its fallen soldiers")
        picks = Counter(st.choose(p, True, rng=random.Random(i)) for i in range(120))
        self.assertGreater(picks["solemn-dusk"] + picks["quote-navy"] + picks["statement-navy"] + picks["bold-navy"], 60)

    def test_climate_good_news_is_not_dark_and_urgent(self):
        p = story(category="climate-environment", tone="hopeful")
        for i in range(60):
            self.assertNotIn(st.choose(p, True, rng=random.Random(i)), ("bold-blue", "bold-navy"))


class Variety(unittest.TestCase):
    def test_a_batch_never_repeats_a_design(self):
        posts = [story(category=c) for c in ("economy", "economy", "economy", "geopolitics", "education", "climate-environment")]
        used = []
        for p in posts:
            used.append(st.choose(p, True, in_batch=used, rng=random.Random(3)))
        self.assertEqual(len(used), len(set(used)))

    def test_recent_designs_are_avoided(self):
        p = story(category="economy")
        first = Counter(st.choose(p, True, rng=random.Random(i)) for i in range(100)).most_common(1)[0][0]
        after = Counter(st.choose(p, True, recent=[first] * 3, rng=random.Random(i)) for i in range(100))
        self.assertLess(after[first], 40)

    def test_a_day_of_posters_uses_many_designs(self):
        recent, seen = [], set()
        rng = random.Random(11)
        cats = ["economy", "geopolitics", "pakistan-affairs", "education", "science-technology", "security-defence", "climate-environment"]
        for hour in range(24):
            batch = []
            for k in range(3):
                p = story(category=cats[(hour * 3 + k) % len(cats)], breaking=(hour % 5 == 0 and k == 0))
                batch.append(st.choose(p, bool(k % 2 == 0), in_batch=batch, recent=recent, rng=rng))
            recent = (recent + batch)[-st.RECENT_KEEP:]
            seen.update(batch)
        self.assertGreaterEqual(len(seen), 18)


class Normalise(unittest.TestCase):
    def test_defaults_and_cleaning(self):
        p = story(stat_value="", quote="", tone="nonsense")
        self.assertIsNone(p["stat"])
        self.assertIn(p["tone"], st.TONES)
        q = story(quote="Hello there", speaker="Minister")
        self.assertEqual(q["speaker"], "Minister")


if __name__ == "__main__":
    unittest.main()
