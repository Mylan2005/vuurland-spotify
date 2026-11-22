"""Offline integrated regressions for v261. No Spotify/API/network/state changes."""
import ast
import re
from pathlib import Path
from v261_matcher_metadata import abbreviated_title_feature, safe_contraction_replacement

assert abbreviated_title_feature("Are You Bored Yet? (f Clairo)") == ("Are You Bored Yet?", "Clairo")
assert abbreviated_title_feature("flowin (feat. Sam Wise)") is None  # existing full-credit parser
assert abbreviated_title_feature("f Clairo") is None
assert abbreviated_title_feature("Song (f DJ Mix)") is None
assert abbreviated_title_feature("Song (Live)") is None
assert abbreviated_title_feature("Song (f X)") is None
assert abbreviated_title_feature("Song (f Sam Wise)") == ("Song", "Sam Wise")
assert safe_contraction_replacement("Ill", "I'll") is None
assert safe_contraction_replacement("dont", "don't") == "don't"

src = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
matcher = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
               and x.name == "find_spotify_track")
scope = {
    "re": re,
    "abbreviated_title_feature": abbreviated_title_feature,
    "safe_contraction_replacement": safe_contraction_replacement,
    "_numbered_title_equivalent": lambda x: x,
}
for name in ("split_title_feature", "spotify_search_title_variant"):
    node = next(x for x in ast.walk(matcher)
                if isinstance(x, ast.FunctionDef) and x.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, "vuurland_sync.py", "exec"), scope)

split = scope["split_title_feature"]
query_title = scope["spotify_search_title_variant"]
assert split("Are You Bored Yet? (f Clairo)") == ("Are You Bored Yet?", "Clairo")
assert split("flowin (feat. Sam Wise)") == ("flowin", "Sam Wise")
assert split("Ill") == ("Ill", None)
assert split("Handle with Care") == ("Handle with Care", None)
assert query_title("Ill") == "Ill"
assert query_title("dont") == "don't"

# Explicit aliases are catalog-name search/validation alternatives,
# never a genre-wide relaxation or free fuzzy match.
assert '"da ze": ["Daze"]' in src
assert '"fink uk": ["Fink"]' in src
assert '"gypsy and the cat": ["GATC"]' in src
assert '"so much 4 gravity": ["So Much for Gravity"]' in src
# Historical recovery is source-proven, bounded by the EXISTING v203 6h gate.
from v203_matcher_upgrade_requeue import applicable_rules
assert "v261_ambiguous_ill_title" in applicable_rules("The Indelicates", "Ill")
assert "v261_abbreviated_required_guest" in applicable_rules("Wallows", "Are You Bored Yet? (f Clairo)")
assert "v261_verified_catalog_alias" in applicable_rules("DA/ZE", "Mellow")
assert "v261_verified_catalog_alias" in applicable_rules("Fink (UK)", "Berlin Sunrise")
assert "v261_verified_catalog_alias" in applicable_rules("Gypsy & The Cat", "Broken Kites")
assert "v261_verified_catalog_alias" in applicable_rules("So Much 4 Gravity", "Gotta Get Out of This Town")
assert "v261_ambiguous_ill_title" not in applicable_rules("Example", "Will")
assert "v261_abbreviated_required_guest" not in applicable_rules("Example", "Song (Live)")
assert "v261_verified_catalog_alias" not in applicable_rules("Unknown Band", "Mellow")
print("v261 integrated offline matcher and bounded retry tests passed")
