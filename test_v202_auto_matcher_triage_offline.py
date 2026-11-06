"""Offline regressions for automatic matcher issue/report analysis (no API)."""
import json
import tempfile
from pathlib import Path
from v202_auto_matcher_triage import (
    summarize, issue_body, candidates_from_log, classify, same_artist
)

assert same_artist("Decemberists, The", "The Decemberists")
assert not same_artist("The Decemberists", "Decemberists Tribute")
assert classify("The Decemberists", "Rise To Me",
                [("The Decemberists", "Rise To Me")]) == \
       "gelijke_artiest_en_titel_nader_controleren"
assert classify("Tired Pony", "All Things At Once",
                [("Tired Pony", "All Things All At Once")]) == \
       "mogelijke_titelvariant_handmatig_verifieren"
assert classify("Hyper Nova", "Lost In Space",
                [("Other Band", "Other Song")]) == "geen_duidelijke_kandidaat"
assert candidates_from_log("A — Song | B — Song - Live") == [
    ("A", "Song"), ("B", "Song - Live")]
assert not candidates_from_log("not a spotify preview")

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    root.joinpath("run1").mkdir()
    root.joinpath("run2").mkdir()
    a = root / "run1" / "vuurland_matcher_rapport.json"
    b = root / "run2" / "vuurland_matcher_rapport.json"
    a.write_text(json.dumps({"records": [
        {"artiest": "Decemberists, The", "titel": "Rise To Me",
         "afgewezen_kandidaten": "The Decemberists — Rise To Me | The Decemberists — Rise To Me - Live",
         "laatste_spotify_query": "artist:Decemberists Rise To Me"},
        {"artiest": "Tired Pony", "titel": "All Things At Once",
         "afgewezen_kandidaten": "Tired Pony — All Things All At Once"},
        {"artiest": "Tired Pony", "titel": "All Things At Once"}
    ]}), encoding="utf-8")
    b.write_text(json.dumps({"records": [
        {"artiest": "Decemberists, The", "titel": "Rise To Me",
         "afgewezen_kandidaten": "The Decemberists — Rise To Me"}
    ]}), encoding="utf-8")
    bad = root / "bad" / "vuurland_matcher_rapport.json"
    bad.parent.mkdir()
    bad.write_text("{", encoding="utf-8")
    cache = {
        "__v51_radio_unmatched": {"decemberists the|||rise to me": {
            "artist": "Decemberists, The", "title": "Rise To Me",
            "source": "indie_select", "failed_at": 100}},
        "__v51_radio_failed_searches": {"decemberists the|||rise to me": 3},
    }
    original = json.dumps(cache, sort_keys=True)
    report = summarize(cache, [a, b, bad])
    assert json.dumps(cache, sort_keys=True) == original  # never modifies cache
    assert report["read_report_files"] == 2
    assert len(report["invalid_report_files"]) == 1
    assert report["unique_failures"] == 2
    december = next(x for x in report["records"] if x["artist"] == "Decemberists, The")
    pony = next(x for x in report["records"] if x["artist"] == "Tired Pony")
    assert december["run_reports"] == 2 and december["source"] == "indie_select"
    assert pony["run_reports"] == 1
    assert not any(row["approved"] for row in report["records"])
    text = issue_body(report)
    assert "Geen Spotify-match is automatisch goedgekeurd" in text
    assert "The Decemberists — Rise To Me" not in text  # previews kept in downloadable JSON
    assert len(text) < 10000
print("✅ v202: offline issue triage, duplicate runs and matcher guardrails pass.")
