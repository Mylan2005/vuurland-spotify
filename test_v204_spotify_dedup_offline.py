"""v204: no automatic deletion of tracks with similar title/duration."""
import ast
import json
import tempfile
from pathlib import Path
from v204_spotify_dedup_review import analyze, markdown

def track(idchar, name, artist="Band", duration=200000, isrc=None):
    return {"uri": "spotify:track:" + idchar * 22, "name": name,
            "artists": [{"name": artist}], "duration_ms": duration,
            "external_ids": {"isrc": isrc} if isrc else {}}

sample = [
    {"track": track("A", "Song", isrc="USABC1234567")},
    {"track": track("A", "Song", isrc="USABC1234567")}, # exact URI
    {"item": track("B", "Song", isrc="USABC1234567")},  # same recording, different URI
    track("C", "Song", duration=200100, isrc="GBXYZ1234567"), # NOT safe to delete
    track("D", "Song - Live", duration=200100),
    track("E", "Song", artist="Other Band", duration=200100),
    track("F", "Song", duration=202001),  # >= 2 seconds
    track("G", "Song", duration=200001),  # no ISRC, caution
    track("H", "Song (Remix)", duration=200002),
    {"track": None}, None, {"name": "No id", "artists": [{"name":"Band"}]},
]
old = json.dumps(sample, sort_keys=True)
report = analyze(sample)
assert json.dumps(sample, sort_keys=True) == old
assert report["total_valid_tracks"] == 9 and report["skipped_unusable"] == 3
assert len(report["exact_uri_repetitions"]) == 1
assert report["exact_uri_repetitions"][0]["positions"] == [0, 1]
assert len(report["same_isrc_different_uri"]) == 1
assert report["same_isrc_different_uri"][0]["positions"] == [0, 1, 2]
review = report["same_artist_title_duration_REVIEW_ONLY"]
assert review and all(row["approved_for_removal"] is False for row in review)
assert all(3 not in x["positions"] or 4 not in x["positions"] for x in review)
assert all(5 not in x["positions"] and 6 not in x["positions"] and 8 not in x["positions"] for x in review)
assert report["spotify_requests"] == report["removed"] == 0
assert "niets verwijderd" in markdown(report).lower()
for invalid in ({}, "text", None):
    try: analyze(invalid)
    except ValueError: pass
    else: raise AssertionError("invalid playlist accepted")
# No source text may invoke Spotify, login, delete, or modify playlists.
source = (Path(__file__).parent / "v204_spotify_dedup_review.py").read_text(encoding="utf-8")
ast.parse(source)
assert "requests." not in source
assert "spotify_request(" not in source
assert "remove_tracks" not in source
print("✅ v204: URI/ISRC evidence, duration-review-only, no Spotify mutations.")
