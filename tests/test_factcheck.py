import json
import tempfile
import time
import unittest
from pathlib import Path

import factcheck as fc


class SameStory(unittest.TestCase):
    def test_reworded_same_event(self):
        self.assertTrue(fc.same_story("Jensen Huang resigns as Nvidia CEO after 33 years",
                                      "Jensen Huang quits Nvidia after 33 years as chief executive"))

    def test_different_events(self):
        self.assertFalse(fc.same_story("IMF approves new loan tranche for Pakistan",
                                       "Floods displace thousands in Sindh districts"))


class Numbers(unittest.TestCase):
    EV = "The IMF approved $1.2 billion on Friday. Inflation fell to 4.5% in October, Reuters said."

    def test_supported(self):
        p = {"headline": "IMF approves $1.2 billion", "summary": "Inflation fell to 4.5%."}
        self.assertEqual(fc.unsupported_numbers(p, self.EV), [])

    def test_invented_number(self):
        p = {"headline": "IMF approves $1.5 billion", "summary": "Inflation fell to 4.5%."}
        self.assertEqual(fc.unsupported_numbers(p, self.EV), ["1.5"])

    def test_fixed_heading_ignored(self):
        p = {"headline": "IMF approves $1.2 billion", "body": "Text.\n\n## Why it matters for CSS and PMS\n\nOk."}
        self.assertEqual(fc.unsupported_numbers(p, self.EV), [])

    def test_thousands_separator(self):
        self.assertEqual(fc.unsupported_numbers({"headline": "12,000 evacuated"}, "About 12000 people were evacuated"), [])


class Memory(unittest.TestCase):
    def test_remember_and_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.json"
            fc.remember([{"headline": "IMF approves loan tranche for Pakistan", "summary": "x", "links": ["http://a"]}], path)
            recent = fc.load_recent(path)
            self.assertTrue(fc.repeat_of("IMF board approves Pakistan loan tranche", recent))
            self.assertFalse(fc.repeat_of("Floods hit Sindh districts", recent))

    def test_old_entries_expire(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.json"
            path.write_text(json.dumps([{"h": "Old story headline words here", "t": int(time.time()) - 20 * 86400}]))
            self.assertEqual(fc.load_recent(path), [])


if __name__ == "__main__":
    unittest.main()
