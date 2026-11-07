"""v207 offline: only full verified identities + EXACT version are accepted."""
import ast
from pathlib import Path
from v207_verified_matcher_metadata import (
    verified_artist_search_name as search,
    verified_artist_identity as identity,
    verified_balthazar_castle_version as castle,
)

assert search("Fink (UK)", "Looking Too Closely") == "Fink"
assert search("fink (uk)", "Another Song") == "fink (uk)"
assert search("The Giraffe Told Me in My Dream", "Before") == "我夢見長頸鹿對我說"
assert search("The Giraffe Told Me in My Dream", "After") == "The Giraffe Told Me in My Dream"
assert search("Another Band", "Before") == "Another Band"
assert identity("Fink (UK)", "Fink", "Looking Too Closely", "Looking Too Closely")
assert identity("The Giraffe Told Me in My Dream", "我夢見長頸鹿對我說", "Before", "Before")
for artist, spotify, src, cand in [
    ("Fink (UK)", "Fink", "Looking Too Closely", "Looking Too Closely - Live In Berlin 2014"),
    ("Fink (UK)", "Fink", "Looking Too Closely", "Looking Too Closely - IIUII"),
    ("Fink (UK)", "Fink", "Looking Too Closely", "Looking Too Closely - Denmark Street Session"),
    ("Fink (US)", "Fink", "Looking Too Closely", "Looking Too Closely"),
    ("Fink (UK)", "Fink Tribute", "Looking Too Closely", "Looking Too Closely"),
    ("The Giraffe Told Me in My Dream", "我夢見長頸鹿對我說", "Before", "Before (Live)"),
    ("The Giraffe Told Me in My Dream", "我夢見長頸鹿對我說", "After", "Before"),
    ("The Giraffe Told Me in My Dream", "Another Band", "Before", "Before"),
]:
    assert not identity(artist, spotify, src, cand), (artist, spotify, src, cand)

source = "On a roll (Sand Castle Tapes version)"
target = "On A Roll - Sand Castle Tapes"
assert castle("BALTHAZAR", source, "Balthazar", target)
for spotify_name in [
    "On A Roll", "On A Roll - Live", "On A Roll - Sand Castle Tapes - Live",
    "On A Roll - Sand Castle Tapes Remix", "JAM 1 - Sand Castle Tapes version",
    "On A Roll - Sand Castle Tapes version", "On A Roll - Sand Castle Tape",
]:
    assert not castle("Balthazar", source, "Balthazar", spotify_name), spotify_name
assert not castle("Balthazar", "On a roll", "Balthazar", target)
assert not castle("Balthazar", source, "Balthazar Tribute", target)
assert not castle("Another Band", source, "Balthazar", target)

# Integration: the existing strict version, title, confidence, rate, and
# FIFO gates must remain in place. None may be replaced by alias-only success.
path = Path(__file__).parent / "vuurland_sync.py"
sync = path.read_text(encoding="utf-8")
ast.parse(sync)
assert "v207_artist_search_name(spotify_search_artist, title)" in sync
assert "v207_artist_identity(artist, spotify_primary_artist, title, item.get('name', ''))" in sync
assert "v207_exact_castle = v207_castle_version(" in sync
assert "spotify_named_variant = wanted_named_variant" in sync
assert "spotify_version = wanted_version" in sync
assert "structural_title_match = (\n            v207_exact_castle" in sync
assert "if wanted_named_variant and spotify_named_variant != wanted_named_variant:" in sync
assert 'max_additions_per_round = 1' in sync
assert '"market": "from_token"' in sync

from v203_matcher_upgrade_requeue import applicable_rules
assert "v207_fink_uk_exact_title" in applicable_rules("Fink (UK)", "Looking Too Closely")
assert "v207_giraffe_chinese_full_artist" in applicable_rules("The Giraffe Told Me in My Dream", "Before")
assert "v207_balthazar_castle_named_version" in applicable_rules("BALTHAZAR", "On a roll (Sand Castle Tapes version)")
assert not any(x.startswith("v207_") for x in applicable_rules("Fink (UK)", "Looking Too Closely - Live"))
assert not any(x.startswith("v207_") for x in applicable_rules("BALTHAZAR", "On A Roll"))
assert not any(x.startswith("v207_") for x in applicable_rules("The Giraffe Told Me in My Dream", "After"))

print("✅ v207: proven artist identity, exact catalog track, Sand Castle Tapes version and all safety gates.")
