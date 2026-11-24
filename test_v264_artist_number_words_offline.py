"""v264: full artist identity, leading-number spelling; no Spotify calls."""
import ast
from pathlib import Path
from v261_matcher_metadata import equivalent_leading_number_artist as eq
assert eq("12 Drummers Drumming", "Twelve Drummers Drumming")
assert eq("3 Doors Down", "Three Doors Down")
assert eq("Twelve Drummers Drumming", "12 Drummers Drumming")
assert not eq("12 Drummers Drumming", "Eleven Drummers Drumming")
assert not eq("12 Drummers Drumming", "Twelve Drummers")
assert not eq("12 Drummers Drumming", "Twelve Drummers Drumming Live")
assert not eq("12 Drummers Drumming", "Twelve Drummers Drumming feat. Guest")
assert not eq("21 Doors Down", "Twenty One Doors Down")
assert not eq("Drummers 12 Drumming", "Drummers Twelve Drumming")
assert not eq("12 Drummers Drumming", "12 Drummers Drumming")
assert not eq("12 Drummers", "Twelve Drummers")  # too few proper-name words
src=Path("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
assert "equivalent_leading_number_artist(" in src
assert "and len(spotify_artist_objects) == 1" in src
from v203_matcher_upgrade_requeue import applicable_rules
assert "v264_complete_leading_artist_number" in applicable_rules("12 Drummers Drumming", "Shower Of Love")
assert "v264_complete_leading_artist_number" not in applicable_rules("12 Drummers Drumming", "Other Song")
assert "v264_complete_leading_artist_number" not in applicable_rules("11 Drummers Drumming", "Shower Of Love")
print("v264 exact artist number word safety tests passed")
