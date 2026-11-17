"""v259 offline safety tests: manual additions, oldest wins, no playlist writes."""
from pathlib import Path
import unittest
from unittest.mock import Mock

import v259_daily_dedup_audit as d


def row(uri, added, title="Song", artist="Band"):
    return {"added_at": added, "item": {
        "uri": uri, "name": title, "artists": [{"name": artist}]}}


class DailyDedupTests(unittest.TestCase):
    def test_oldest_across_volumes_and_same_volume(self):
        a = "spotify:track:" + "A"*22
        b = "spotify:track:" + "B"*22
        volumes = [
            {"number": 1, "id": "1"*22, "snapshot_id": "v1", "items": [
                row(a, "2020-01-01T00:00:00Z"), row(b, "2020-02-01T00:00:00Z")]},
            {"number": 2, "id": "2"*22, "snapshot_id": "v2", "items": [
                row(a, "2026-01-01T00:00:00Z"),
                row(a, "2026-02-01T00:00:00Z"),
                row(b, "2026-01-01T00:00:00Z"),
                row("spotify:track:"+"C"*22, "2026-02-01T00:00:00Z",
                    title="Song")]},
        ]
        report = d.audit(volumes, generated="fixed")
        self.assertEqual(report["repeat_occurrences"], 3)
        self.assertEqual(report["exact_uri_duplicates"][0]["keep"]["volume"], 1)
        self.assertTrue(all(g["removal_approved"] is False
                            for g in report["exact_uri_duplicates"]))
        self.assertEqual(report["removed"], 0)
        self.assertIn("ALLEEN-LEZEN", d.markdown(report))
        self.assertEqual(len(report["different_uri_same_title_REVIEW_ONLY"]), 1)

    def test_added_date_overrides_manual_reordering(self):
        uri = "spotify:track:"+"X"*22
        v = [{"number":2, "id":"2"*22,"snapshot_id":"s","items":[
            row(uri,"2026-03-01T00:00:00Z"),
            row(uri,"2026-01-01T00:00:00Z")]}]
        result = d.audit(v)
        self.assertEqual(result["exact_uri_duplicates"][0]["keep"]["position"],1)

    def test_missing_date_falls_back_and_marks_uncertain(self):
        uri = "spotify:track:"+"X"*22
        v = [{"number":1, "id":"1"*22,"snapshot_id":"s","items":[
            row(uri,None), row(uri,"2026-01-01T00:00:00Z")]}]
        group = d.audit(v)["exact_uri_duplicates"][0]
        self.assertFalse(group["oldest_verified_by_added_at"])
        self.assertEqual(group["keep"]["position"],0)

    def test_no_delete_or_mutation_possible(self):
        source = Path("v259_daily_dedup_audit.py").read_text(encoding="utf-8")
        for danger in ("session.delete(", "session.put(", "session.patch(",
                       "session.request(", "remove_tracks(", "playlist_replace("):
            self.assertNotIn(danger, source)
        self.assertIn("permissions:", Path(".github/workflows/vuurland-v259-dagelijkse-dubbels.yml").read_text())

    def test_playlist_mapping_requires_both_volumes(self):
        m = {"__vuurland_volume_playlists": {"1":d.VOLUME_1,"2":"2"*22}}
        self.assertEqual(len(d.volume_ids(m)),2)
        with self.assertRaises(ValueError):
            d.volume_ids({"__vuurland_volume_playlists":{"1":d.VOLUME_1}})

    def test_pagination_fail_closed_if_snapshot_changes(self):
        class FakeSession:
            def __init__(self):
                self.n = 0
            def get(self, url, params=None, headers=None, timeout=None):
                self.n += 1
                if self.n == 1: return Reply({"snapshot_id":"before"})
                if self.n == 2: return Reply({"total":1,"items":[row("spotify:track:"+"A"*22,"2026-01-01T00:00:00Z")]})
                return Reply({"snapshot_id":"after"})
        class Reply:
            status_code = 200
            def __init__(self, body): self.body = body
            def raise_for_status(self): pass
            def json(self): return self.body
        with self.assertRaises(RuntimeError):
            d.read_volume(FakeSession(),"token",1,"1"*22,pause=0)


if __name__=="__main__":
    unittest.main()
