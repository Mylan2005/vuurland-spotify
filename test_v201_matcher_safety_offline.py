"""Offline v201 regressions: nonempty structural identities and clear diagnosis."""
import ast
import re
from pathlib import Path
from v194_matcher_metadata import canonical_artist, artist_join_key

source = (Path(__file__).parent / "vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)

def standalone(name, namespace):
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    exec(compile(module, "vuurland_sync.py", "exec"), namespace)
    return namespace[name]

spell = standalone("v101_safe_title_spelling", {"re": re})
assert spell("???") == ""
assert spell("!!!") == ""
assert spell("Do You Realise?") == spell("Do You Realize!")
assert spell("Run?") != spell("Stay!")

namespace = {
    "v80_unicode_search_text": lambda text: text,
    "v194_canonical_artist": canonical_artist,
    "v194_artist_join_key": artist_join_key,
}
diagnose = standalone("v82_match_diagnosis", namespace)
candidate = lambda artist, title: {
    "artists": [{"name": artist}], "name": title, "is_playable": True,
}
assert diagnose([candidate("The Decemberists", "Rise To Me")],
                "Decemberists, The", "Rise To Me") == "veiligheidscontrole_of_ambiguiteit"
assert diagnose([candidate("The Decemberists", "Rise To Me - Live")],
                "Decemberists, The", "Rise To Me") == "titel_of_versie_verschilt"
assert diagnose([candidate("Other Band", "Rise To Me")],
                "Decemberists, The", "Rise To Me") == "artiestcredits_of_rangschikking"
assert diagnose([candidate("The Decemberists", "Rise To Me")],
                "Decemberists, The", "??") == "onbruikbare_titelmetadata"

# The two independent structural-identity paths now require nonempty values.
assert "or (bool(wanted_identity) and wanted_identity == spotify_identity)" in source
assert "and wanted_base_identity == spotify_base_identity)" in source
assert "if not left_tokens or not right_tokens:" in source
assert "if (primary_artist_exact and v201_spelling_left" in source
assert "and v201_spelling_left == v201_spelling_right" in source
assert "max_additions_per_round = 1" in source
print("✅ v201: empty punctuation-only titles rejected and artist alias diagnosis accurate.")
