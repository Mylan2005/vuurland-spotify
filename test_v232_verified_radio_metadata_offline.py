"""v232: exact bewijs voor twee cataloguscorrecties, geen vrije match."""
import ast
from pathlib import Path
from v232_verified_radio_metadata import verified_radio_metadata

cases = (
    ("VAR", "VAR - Run", "VAR", "Run"),
    ("Cranes", "Rкverie", "Cranes", "Rêverie"),
)
for source_artist, source_title, expected_artist, expected_title in cases:
    assert verified_radio_metadata(source_artist, source_title) == (expected_artist, expected_title)
    assert verified_radio_metadata(source_artist.lower(), source_title.lower()) == (
        source_artist.lower(), expected_title)

# Geen globale variant: behoud echte remixes, andere nummers, andere artiesten.
for artist, title in (
    ("VAR", "VAR - Run (Live)"),
    ("VAR", "VAR - Running"),
    ("VAR", "Run (Remix)"),
    ("Cranes", "Reverie (Live)"),
    ("Cranes", "Rêverie (Remix)"),
    ("Other Band", "VAR - Run"),
    ("Other Band", "Rкverie"),
):
    assert verified_radio_metadata(artist, title) == (artist, title)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
matcher = ast.get_source_segment(src, next(n for n in tree.body
    if isinstance(n, ast.FunctionDef) and n.name == "find_spotify_track"))
assert matcher.index("v101_original_key") < matcher.index("v232_radio_metadata(artist, title)")
assert matcher.index("v232_radio_metadata(artist, title)") < matcher.index("v194_canonical_artist(artist)")
assert "v81_catalog_locator(*v101_original_key)" in matcher
assert "primary_artist_exact" in matcher
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in src
print("✅ v232: VAR / Cranes alleen exacte metadata; bestaande Spotify-veiligheid.")
