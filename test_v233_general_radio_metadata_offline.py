"""v233: generalize structural RadioBox fixes without loosening Spotify safety."""
import ast
from pathlib import Path
from v233_general_radio_metadata import (
    normalize_radio_metadata, normalize_mixed_script_typos,
)

# Never hardcode artist/title pairs: these examples are intentionally
# unrelated to the two v232 verified exceptions.
for artist, title, expected in (
    ("VAR", "VAR - Run", "Run"),
    ("Example Artist", "Example Artist - A New Track", "A New Track"),
    ("Portishead", "portishead — Half Day Closing", "Half Day Closing"),
    ("The National", "  THE NATIONAL  –  Mistaken For Strangers", "Mistaken For Strangers"),
    ("Mojave 3", "Mojave 3 - Tomorrow's Taken (Live)", "Tomorrow's Taken (Live)"),
    ("Cranes", "Rеverie", "Reverie"),  # Cyrillic е, within Latin word
    ("New Order", "Bluе Monday", "Blue Monday"),
    ("Radiohead", "Nо Surprises", "No Surprises"),
    ("VAR", "VAR - Rеverie (Live)", "Reverie (Live)"),
):
    actual = normalize_radio_metadata(artist, title)
    assert actual == (artist, expected), (artist, title, actual, expected)

# No credit guessing, no removal when prefix is partial, no version loss.
for artist, title in (
    ("Portishead", "Portishead -"),  # incomplete separator
    ("VAR", "VAR - "),  # empty body
    ("The National", "National - Mistaken For Strangers"),
    ("VAR", "VAR - Run - Live"),  # preserved title includes version (not equal)
    ("Oasis", "Oasis - Oasis"),  # same word appears in the actual title
    ("Cranes", "Rкverie"),  # Cyrillic к is NOT unambiguous Latin lookalike
    ("Russian Artist", "Привет Мир"),  # fully Cyrillic title
    ("Russian Artist", "Другоe"),  # unknown Cyrillic chars = no partial rewrite
    ("VAR", "VAR remix"),
    ("King", "King Gizzard - Rattlesnake"),
):
    if (artist, title) == ("VAR", "VAR - Run - Live"):
        assert normalize_radio_metadata(artist, title) == (artist, "Run - Live")
    elif (artist, title) == ("Oasis", "Oasis - Oasis"):
        assert normalize_radio_metadata(artist, title) == (artist, "Oasis")
    else:
        assert normalize_radio_metadata(artist, title) == (artist, title), (artist, title)

# We do not silently rewrite all-Cyrillic tokens or English words normally.
assert normalize_mixed_script_typos("роман") == "роман"
assert normalize_mixed_script_typos("mуsic") == "mysic"
assert normalize_mixed_script_typos("Jumping") == "Jumping"

source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
matcher = ast.get_source_segment(source, next(n for n in tree.body
    if isinstance(n, ast.FunctionDef) and n.name == "find_spotify_track"))
assert matcher.index("v101_original_key") < matcher.index("v233_radio_metadata(artist, title)")
assert matcher.index("v233_radio_metadata(artist, title)") < matcher.index("v232_radio_metadata(artist, title)")
assert matcher.index("v232_radio_metadata(artist, title)") < matcher.index("v194_canonical_artist(artist)")
assert "v81_catalog_locator(*v101_original_key)" in matcher
assert "primary_artist_exact" in matcher
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
print("✅ v233: generieke structurele correcties + originele bronidentiteit behouden.")
