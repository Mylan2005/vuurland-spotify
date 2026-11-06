"""Offline regression for v197 multi-report aggregation. No Spotify/network."""
import csv
import json
import tempfile
from pathlib import Path
from v197_combine_matcher_reports import aggregate, identity, markdown

assert identity("Björk", "Song  (Live)") == identity("BJÖRK", "Song (Live)")
assert identity("Band", "Song (Live)") != identity("Band", "Song")
assert identity("Band", "My Song") != identity("Band", "My Song Remix")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    first = root / "vuurland_matcher_rapport_31.csv"
    with first.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "artiest", "titel", "bron", "status", "laatste_spotify_query",
            "afgewezen_kandidaten"))
        writer.writeheader()
        writer.writerows([
            {"artiest": "Björk", "titel": "Jóga", "bron": "vuurland",
             "status": "Geen betrouwbare Spotify-match", "afgewezen_kandidaten": "Wrong live"},
            {"artiest": "Björk", "titel": "Jóga", "bron": "vuurland",
             "status": "Geen betrouwbare Spotify-match"},
            {"artiest": "Band", "titel": "Song (Live)", "bron": "indie_select",
             "status": "Onzeker"},
        ])
    second = root / "matcher_report_32.json"
    second.write_text(json.dumps({"records": [
        {"artiest": "BJÖRK", "titel": "JÓGA", "status": "Geparkeerd",
         "laatste_spotify_query": "bjork joga"},
        {"artiest": "Band", "titel": "Song", "status": "Onzeker"},
    ]}), encoding="utf-8")
    broken = root / "matcher_report_invalid.json"
    broken.write_text("{", encoding="utf-8")
    data = aggregate([first, second, broken])
    assert data["gelezen_bestanden"] == 2
    assert data["unieke_nummers"] == 3
    assert len(data["fouten"]) == 1
    bjork = next(x for x in data["nummers"] if x["artiest"] == "Björk")
    assert bjork["rapporten"] == 2 and bjork["meldingen"] == 2
    assert "Wrong live" in bjork["afgewezen_kandidaten"]
    assert "Geparkeerd" in bjork["statussen"]
    assert "geen automatische matches" in markdown(data).lower()
    assert any(x["titel"] == "Song (Live)" for x in data["nummers"])
    assert any(x["titel"] == "Song" for x in data["nummers"])
    assert all("spotify_uri" not in x for x in data["nummers"])
print("✅ v197: reports grouped conservatively; originals untouched.")
