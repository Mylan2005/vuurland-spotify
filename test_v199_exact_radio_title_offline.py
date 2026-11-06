"""v199 offline: exact suffix rescue, no fuzzy candidate acceptance.

Never contacts Spotify or mutates a live playlist or queue.
"""
import ast
from pathlib import Path
from v194_matcher_metadata import canonical_title

positives = (
    ("Birkii", "Holy War - Birkii", "Holy War"),
    ("The 6ths With Lloyd Cole",
     "Human (featuring Lloyd Cole) - The 6ths With Lloyd Cole",
     "Human (featuring Lloyd Cole)"),
    ("Artist", "A - B - Artist", "A - B"),
    ("Artist", "A - B — Artist", "A - B"),
    ("Artist", "Song—Artist", "Song"),
    ("Artist", "Song –Artist", "Song"),
    ("Artist", "Song– Artist", "Song"),
    ("Artist", "Song - Another - Artist", "Song - Another"),
    ("The Decemberists", "The Engine Driver — The Decemberists", "The Engine Driver"),
)
for artist, title, expected in positives:
    assert canonical_title(artist, title) == expected, (artist, title)

negatives = (
    ("Artist", "Song - Other Artist"),
    ("Artist", "Song (Live) - Other Artist"),
    ("Artist", "Song - Artist Remix"),
    ("Artist", "Song - Artist featuring Someone"),
    ("Artist", "Song-Artist"),  # ordinary hyphen without spaces is ambiguous
    ("Artist", "Song - Artist - Live"),
    ("Artist", "Song—Artist & Guest"),
    ("Artist", "Song - Art"),
    ("Artist", "Song"),
    ("", "Song — "),
)
for artist, title in negatives:
    assert canonical_title(artist, title) == title.strip(), (artist, title)

# Version labels and the broader Spotify candidate guards remain unchanged.
source = (Path(__file__).resolve().parent / "vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
assert "v194_canonical_title(artist, title)" in source
assert "wanted_version == spotify_version" in source
assert "spotify_candidate_version(item)" in source
assert "primary_artist_exact" in source
assert "max_additions_per_round = 1" in source
print("✅ v199: complete trailing credits rescued; partial artists/mixes/live rejected.")
