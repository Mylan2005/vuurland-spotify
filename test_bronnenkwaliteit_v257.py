"""v257 regression tests: queue-only analytics must not mutate data."""
import copy
import unittest

from bronnenkwaliteit_v257 import LIVE_SOURCES, build_report, markdown


class QualityTests(unittest.TestCase):
    def test_all_17_sources_and_archive(self):
        self.assertEqual(len(LIVE_SOURCES), 17)
        self.assertEqual(len(set(LIVE_SOURCES)), 17)
        data = [
            {"source": "radio_britannia", "artist": "A", "title": "B", "_v116_fifo_seq": 1},
            {"source": "radio_britannia", "artist": " a ", "title": "b", "_v116_fifo_seq": 2},
            {"source": "duyster", "artist": "C", "title": "D", "_v116_fifo_seq": 3},
        ]
        original = copy.deepcopy(data)
        result = build_report(data, timestamp="2026-11-17T00:00:00Z")
        self.assertEqual(data, original)
        self.assertEqual(len(result["sources"]), 18)
        britannia = next(x for x in result["sources"] if x["source"] == "radio_britannia")
        self.assertEqual((britannia["pending"], britannia["unique_pending_titles"],
                          britannia["duplicate_pending_titles"]), (2, 1, 1))
        self.assertIn("snapshot", markdown(result).lower())

    def test_unknown_and_fifo_problems_are_warnings(self):
        data = [
            {"source": "wbru", "artist": "A", "title": "B", "_v116_fifo_seq": 1},
            {"source": "wbru", "artist": "", "title": "B", "_v116_fifo_seq": 1},
            {"source": "other", "artist": "C", "title": "D", "_v116_fifo_seq": 9},
        ]
        result = build_report(data, timestamp="fixed")
        self.assertEqual(len(result["unknown_sources"]), 1)
        self.assertTrue(any("Dubbele FIFO" in x for x in result["warnings"]))
        self.assertEqual(next(x for x in result["sources"] if x["source"] == "wbru")["invalid_metadata"], 1)

    def test_requires_list(self):
        with self.assertRaises(ValueError):
            build_report({})


if __name__ == "__main__":
    unittest.main()
