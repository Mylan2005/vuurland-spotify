"""v190: drie favoriete artiesten mogen voorbij taalsignalen, niet voorbij dedupe/Spotify-veiligheid.

Volledig offline: alleen losse AST-functies, geen netwerk en geen statewijzigingen.
"""
import ast
import re
from pathlib import Path

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
functions = {
    n.name: n for n in tree.body
    if isinstance(n, ast.FunctionDef)
}
ns = {
    "re": re,
    "GERMAN_VOCAL_RADIO_TRACKS": {
        ("sigur rós", "ich liebe dich"),
        ("tomte", "die schönheit der chance"),
    },
    "INDIE_SELECT_GERMAN_TRACKS": frozenset(),
    # Opzettelijk strenge stubs: gewone tracks zouden geweigerd worden.
    "v150_is_unwanted_language": lambda artist, title: True,
    "v148_block_confirmed_romanian": lambda artist, title: False,
    "v143_unwanted_title": lambda title: True,
    "v119_is_german_title": lambda title: True,
}
for name in (
    "v190_is_language_exempt_artist",
    "v140_is_unwanted_language_title",
    "v131_block_nonlatin_east_asian",
    "indie_select_blocks_german",
    "is_confirmed_german_vocal",
    "v106_language_decision",
):
    assert name in functions, name
    exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                 "<" + name + ">", "exec"), ns)

preferred = (
    "Sigur Rós",
    "Sigur Ros",
    "Ólafur Arnalds",
    "Olafur Arnalds",
    "Cocteau Twins",
    "Cocteau Twins feat. Harold Budd",
    "Ólafur Arnalds & Nils Frahm",
)
for artist in preferred:
    assert ns["v190_is_language_exempt_artist"](artist), artist
    assert not ns["v140_is_unwanted_language_title"]("Ich liebe dich", artist), artist
    assert not ns["indie_select_blocks_german"](artist, "Ich liebe dich"), artist
    assert not ns["v131_block_nonlatin_east_asian"](artist, "夜"), artist
    assert not ns["is_confirmed_german_vocal"](artist, "Ich liebe dich"), artist
    assert ns["v106_language_decision"](artist, "Ich liebe dich") == "allow", artist

for artist in (
    "Muse",
    "Tomte",
    "Sigur Rós Tribute",
    "Olafur Arnalds Tribute",
    "Cocteau Twins Coverband",
    "Avicii feat. Sigur Rós",
):
    assert not ns["v190_is_language_exempt_artist"](artist), artist
    assert ns["v140_is_unwanted_language_title"]("Ich liebe dich", artist), artist
    assert ns["indie_select_blocks_german"](artist, "Ich liebe dich"), artist
    assert ns["v131_block_nonlatin_east_asian"](artist, "夜"), artist

assert ns["is_confirmed_german_vocal"]("Tomte", "Die Schönheit der Chance")
assert 'RADIO_SOURCE_ORDER = ("vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled", "dreampop_radio", "indie_select", "dkfm_edge", "dark_edge")' in src
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in src
assert 'item.get("source") == "dark_edge" and not dark_edge_track_allowed(artist, title)' in src
assert "if v190_is_language_exempt_artist(artist):" in src
print("✅ Sigur Rós, Ólafur Arnalds en Cocteau Twins mogen alle talen; geen Spotify-/dubbels-bypass.")
