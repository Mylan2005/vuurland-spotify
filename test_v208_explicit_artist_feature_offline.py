"""v208: strict, offline regression for parenthesized featured artist metadata."""
import ast
from pathlib import Path
from v208_explicit_artist_feature import canonical_explicit_artist_feature as fix
from v203_matcher_upgrade_requeue import applicable_rules

from v208_explicit_artist_feature import (
    verified_symbolic_plusminus as plusminus,
    verified_report_album_hint as album_hint,
    verified_report_search_query as report_query,
)

# Proven songs on the exact original album + exact Spotify symbol-only artist.
assert plusminus("PlusMinus", "Rewrite the Story", "+/-", "Rewrite the Story", "Jumping the Tracks")
assert plusminus("PlusMinus", "Jumping the Tracks", "+/-", "Jumping the Tracks", "Jumping the Tracks")
for x in [
    ("PlusMinus", "Rewrite the Story", "+/-", "Running The Distance", "Jumping the Tracks"),
    ("PlusMinus", "Rewrite the Story", "Unknown", "Rewrite the Story", "Jumping the Tracks"),
    ("PlusMinus", "Rewrite the Story", "+/-", "Rewrite the Story - Live", "Jumping the Tracks"),
    ("PlusMinus", "Rewrite the Story", "+/-", "Rewrite the Story", "Another Album"),
    ("PlusMinus", "Rewrite", "+/-", "Rewrite", "Jumping the Tracks"),
    ("SomeOtherBand", "Rewrite the Story", "+/-", "Rewrite the Story", "Jumping the Tracks"),
    ("PlusMinus", "Jumping the Tracks", "+/-", "Jumping the Tracks", "Jumping the Tracks - Live"),
]:
    assert not plusminus(*x), x
assert album_hint("PlusMinus", "Rewrite the Story") == "Jumping the Tracks"
assert album_hint("PlusMinus", "Jumping the Tracks") == "Jumping the Tracks"
assert album_hint("Isa And The Filthy Tongues", "Jim's Killer") == "Dark Passenger"
assert album_hint("Bluhm", "Midnight Hill") == "Midnight Hill"
assert report_query("PlusMinus", "Rewrite the Story") == 'track:"Rewrite the Story" album:"Jumping the Tracks"'
assert report_query("Bluhm", "Midnight Hill") == 'track:"Midnight Hill" album:"Midnight Hill"'
assert report_query("Clover", "The Things") is None
assert report_query("The Killers", "Mr Brightside (Live Acoustic)") is None
assert "v208_plusminus_exact_album_artist" in applicable_rules("PlusMinus", "Rewrite the Story")
assert "v208_plusminus_exact_album_artist" in applicable_rules("PlusMinus", "Jumping the Tracks")
assert "v208_verified_album_query" in applicable_rules("Bluhm", "Midnight Hill")
assert "v208_verified_album_query" in applicable_rules("Isa And The Filthy Tongues", "Jim's Killer")
assert not any(r.startswith("v208") for r in applicable_rules("PlusMinus", "Running the Distance"))
assert not any(r.startswith("v208") for r in applicable_rules("Bluhm", "Another Song"))

assert fix("UNKLE (feat. Ian Brown)") == "UNKLE feat. Ian Brown"
assert fix("UNKLE (featuring Ian Brown)") == "UNKLE feat. Ian Brown"
assert fix("UNKLE (ft. Ian Brown)") == "UNKLE feat. Ian Brown"
assert fix("UNKLE feat. Ian Brown") == "UNKLE feat. Ian Brown"
assert fix("UNKLE (feat. Thom Yorke)") == "UNKLE feat. Thom Yorke"
assert fix("Some Project (Live)") == "Some Project (Live)"
assert fix("UNKLE (feat. Ian Brown) - Live") == "UNKLE (feat. Ian Brown) - Live"
assert fix("UNKLE (feat. Ian Brown Remix)") == "UNKLE (feat. Ian Brown Remix)"
assert fix("UNKLE (Ian Brown)") == "UNKLE (Ian Brown)"
assert fix("Nick Cave & The Bad Seeds") == "Nick Cave & The Bad Seeds"
assert fix("UNKLE (feat. )") == "UNKLE (feat. )"
assert fix("UNKLE (feat. Ian Brown) (Live)") == "UNKLE (feat. Ian Brown) (Live)"
assert "v208_parenthesized_feature" in applicable_rules("UNKLE (feat. Ian Brown)", "Be There")
assert not any(r.startswith("v208") for r in applicable_rules("UNKLE", "Be There"))
assert not any(r.startswith("v208") for r in applicable_rules("UNKLE (feat. Ian Brown)", "Be There - Live"))

sync = (Path(__file__).parent / "vuurland_sync.py").read_text("utf-8")
ast.parse(sync)
assert sync.index("_v208_feature_artist = v208_artist_feature(artist)") < sync.index("    search_artists = re.split(", sync.index("def find_spotify_track("))
assert 'v208_plusminus_identity(' in sync
assert 'v208_report_query(artist, title)' in sync
assert 'wanted_artists = artist_parts(artist)' in sync
assert 'if missing_feature_count:' in sync
assert 'if (not primary_artist_exact' in sync
assert 'max_additions_per_round = 1' in sync
assert '"market": "from_token"' in sync
print("✅ v208: mandatory whole guest credit recognized, no other artist/title/version loosened")
