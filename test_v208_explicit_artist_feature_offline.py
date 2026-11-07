"""v208: strict, offline regression for parenthesized featured artist metadata."""
import ast
from pathlib import Path
from v208_explicit_artist_feature import canonical_explicit_artist_feature as fix
from v203_matcher_upgrade_requeue import applicable_rules

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
assert 'wanted_artists = artist_parts(artist)' in sync
assert 'if missing_feature_count:' in sync
assert 'if (not primary_artist_exact' in sync
assert 'max_additions_per_round = 1' in sync
assert '"market": "from_token"' in sync
print("✅ v208: mandatory whole guest credit recognized, no other artist/title/version loosened")
