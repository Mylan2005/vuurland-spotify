"""v231: geverifieerde artiestnaamswijziging Chappaqua Wrestling → CQ Wrestling."""
import ast
from pathlib import Path

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
aliases = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ARTIST_ALIASES" for t in node.targets):
        aliases = ast.literal_eval(node.value)
        break
assert aliases is not None
assert aliases["chappaqua wrestling"] == ["CQ Wrestling"]
assert "chappaqua wrestle" not in aliases

fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
          and n.name == "find_spotify_track")
body = ast.get_source_segment(src, fn)
# Bestaande gerichte zoekhint én artiestidentiteitscontrole krijgen de alias.
assert "search_artist_aliases = ARTIST_ALIASES.get(" in body
assert "search_artist_aliases[0]" in body
assert "alias_key(spotify_primary_artist)" in body
assert "for alias in search_artist_aliases" in body
assert "primary_artist_exact = True" in body
# Geen URI geforceerd: titel, versie en regio worden nog steeds getoetst.
assert "search_title_structural_equivalent" in body
assert "is_playable" in body
assert 'params={"market": "from_token"}' in body
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
print("✅ v231: CQ Wrestling officiële alias, bestaande veiligheid en Spotify-quota intact.")
