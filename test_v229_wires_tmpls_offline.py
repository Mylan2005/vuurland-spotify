"""v229: exact bevestigde WIRES//TMPLS-catalogusmatch zonder vrije fuzzy matching."""
import ast
from pathlib import Path

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
assignments = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id in {"ARTIST_ALIASES", "V81_VERIFIED_CATALOG_TRACKS"}:
            assignments[node.targets[0].id] = ast.literal_eval(node.value)

aliases = assignments["ARTIST_ALIASES"]
locators = assignments["V81_VERIFIED_CATALOG_TRACKS"]
artist = "Wires to the Temples"
title = "Smeared/Aura"
id_ = "74VpqnAOJM1ha2XKFbdFYG"

assert aliases["wires to the temples"] == ["WIRES//TMPLS"]
assert locators[(artist.casefold(), title.casefold())] == id_
assert len(id_) == 22 and id_.isalnum()
assert ("wires to the temples", "other song") not in locators
assert ("another artist", "smeared/aura") not in locators

# The existing search uses this alias not only for search, but also for
# primary-artist candidate validation; the locator is still passed through
# the exact common track validation.
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
          and n.name == "find_spotify_track")
body = ast.get_source_segment(src, fn)
assert "search_artist_aliases = ARTIST_ALIASES.get(" in body
assert "alias_key(spotify_primary_artist)" in body
assert "for alias in search_artist_aliases" in body
assert "catalog_id = v81_catalog_locator(*v101_original_key)" in body
assert 'spotify_request(\n            "GET", f"/tracks/{catalog_id}"' in body
assert 'params={"market": "from_token"}' in body
assert "primary_artist_exact = True" in body
print("✅ v229: exacte Spotify-ID, gecontroleerde artiestalias, bestaande veiligheidschecks.")
