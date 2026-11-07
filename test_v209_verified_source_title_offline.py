"""v209: only the officially confirmed Simon & Garfunkel typo, keep live."""
import ast
from pathlib import Path
from v209_verified_source_title import verified_emily_live_source_title as fix
from v203_matcher_upgrade_requeue import applicable_rules

original = "For Emily, Wherever I May Find Her (live)"
corrected = "For Emily, Whenever I May Find Her (live)"
assert fix("Simon & Garfunkel", original) == corrected
assert fix("SIMON & GARFUNKEL", original.upper()) == corrected
for artist, title in [
    ("Simon & Garfunkel", "For Emily, Wherever I May Find Her"),
    ("Simon & Garfunkel", "For Emily, Wherever I May Find Her (Studio)"),
    ("Simon & Garfunkel", "For Emily, Wherever I May Find Her (Live 1967)"),
    ("Simon & Garfunkel", "For Emily, Wherever I May Find Her (Remix)"),
    ("Simon & Garfunkel", "For Emily, Whenever I May Find Her (live)"),
    ("Other Singer", original),
    ("Simon & Garfunkel", "For Emily, Whoever I May Find Her (live)"),
]:
    assert fix(artist, title) == title, (artist, title)
assert "v209_emily_live_exact_source_spelling" in applicable_rules(
    "Simon & Garfunkel", original)
assert not any(x.startswith("v209") for x in applicable_rules(
    "Simon & Garfunkel", "For Emily, Wherever I May Find Her"))
assert not any(x.startswith("v209") for x in applicable_rules(
    "Simon & Garfunkel", "For Emily, Wherever I May Find Her (studio)"))

sync = (Path(__file__).parent / "vuurland_sync.py").read_text("utf8")
ast.parse(sync)
assert "v209_emily_title(artist, title)" in sync
assert "wanted_version = requested_version(title)" in sync
assert "if spotify_version != wanted_version:" in sync
assert 'max_additions_per_round = 1' in sync
print("✅ v209: corrected one complete source typo, live recording constraint intact.")
