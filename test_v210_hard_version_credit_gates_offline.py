"""v210: explicitly requested featured guest and live recording cannot downgrade."""
import ast
from pathlib import Path

sync = (Path(__file__).parent / "vuurland_sync.py").read_text("utf8")
ast.parse(sync)
assert "_v208_had_explicit_parenthesized_guest = _v208_feature_artist != artist" in sync
assert """if missing_feature_count:
            # v210: de nieuwe v208-haakjesfeat""" in sync
assert """if _v208_had_explicit_parenthesized_guest or _v211_had_confirmed_guest:
                continue""" in sync
assert """if (artist.strip().casefold() == "simon & garfunkel"
                and title.strip().casefold()
                    == "for emily, whenever i may find her (live)"
                and spotify_version != "live"):
            continue""" in sync
assert sync.index("if _v208_had_explicit_parenthesized_guest or _v211_had_confirmed_guest:") < sync.index("feature_tier = 1 if explicit_feature_count")
assert sync.index('and spotify_version != "live"') < sync.index("# v94: a radio title")
assert 'max_additions_per_round = 1' in sync
assert '"market": "from_token"' in sync
print("✅ v210: explicitly marked guest requires full credit; exact requested live song can never select studio")
