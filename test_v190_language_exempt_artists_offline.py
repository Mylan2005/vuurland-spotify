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
    "v119_is_german_title": lambda title: title == "Ich liebe dich",
}
for name in (
    "v190_is_language_exempt_artist",
    "v191_is_german_vocal_risk",
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
    assert not ns["v140_is_unwanted_language_title"]("Blóðberg", artist), artist
    assert not ns["indie_select_blocks_german"](artist, "Blóðberg"), artist
    assert not ns["v131_block_nonlatin_east_asian"](artist, "夜"), artist
    assert not ns["is_confirmed_german_vocal"](artist, "Blóðberg"), artist
    assert ns["v106_language_decision"](artist, "Blóðberg") == "allow", artist
    # Niemand, ook geen favoriet, krijgt toegang voor duidelijk Duits.
    assert ns["v191_is_german_vocal_risk"](artist, "Ich liebe dich"), artist
    assert ns["v140_is_unwanted_language_title"]("Ich liebe dich", artist), artist
    assert ns["indie_select_blocks_german"](artist, "Ich liebe dich"), artist
    assert ns["v106_language_decision"](artist, "Ich liebe dich") == "block", artist

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

assert ns["is_confirmed_german_vocal"]("Sigur Rós", "Ich liebe dich")
assert ns["is_confirmed_german_vocal"]("Tomte", "Die Schönheit der Chance")
assert 'RADIO_SOURCE_ORDER = ("vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled", "dreampop_radio", "indie_select", "dkfm_edge", "dark_edge", "dkfm_shoegaze", "dkfm_classic")' in src
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in src
assert 'item.get("source") == "dark_edge" and not dark_edge_track_allowed(artist, title)' in src
assert "if v190_is_language_exempt_artist(artist):" in src
# Duitse nummers uit 12 door gebruiker aangeleverde RadioBox-weekoverzichten
# (Indie Select en Dreampop Radio, november 2026): exact dezelfde
# Duitse-titel/confirmed-vocal checks gelden voor ALLE bronnen.
v119_titles = next(n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "V119_GERMAN_TITLES"
                           for t in n.targets))
vocal_titles = next(n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "GERMAN_VOCAL_RADIO_TRACKS"
                            for t in n.targets))
real_ns = {
    "re": re,
    "V119_GERMAN_TITLES": frozenset(ast.literal_eval(v119_titles.value.args[0])),
    "GERMAN_VOCAL_RADIO_TRACKS": frozenset(ast.literal_eval(vocal_titles.value.args[0])),
}
for name in ("v119_title_normalize", "v119_is_german_title",
             "is_confirmed_german_vocal"):
    exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                 "<" + name + ">", "exec"), real_ns)
new_german = [
    ("Thees Uhlmann", "17 Worte"),
    ("Gloria", "Eigenes Berlin"),
    ("Peter Licht", "Wettentspannen"),
    ("Nouvelle Vague", "Eisbar"),
    ("1. Futurologischer Congress", "Nur mit Dir"),
    ("Public Service Broadcasting", "Im Licht"),
]
for artist, title in new_german:
    assert real_ns["v119_is_german_title"](title), (artist, title)
    assert real_ns["is_confirmed_german_vocal"](artist, title), (artist, title)
assert real_ns["v119_is_german_title"]("Eigenes Berlin (Live)")
assert real_ns["v119_is_german_title"]("Eisbär")
assert real_ns["v119_is_german_title"]("Wettentspannen (Remix)")
for artist, title in [
    ("The Notwist", "Pick Up The Phone"),
    ("Urlaub In Polen", "The Velvet Blues"),
    ("Schneider TM", "The Light 3000"),
    ("Monta", "Farewell Dear Ghost"),
    ("Maximilian Hecker", "Over"),
    ("The Chemical Brothers", "Hey Boy Hey Girl"),
]:
    assert not real_ns["v119_is_german_title"](title), (artist, title)
    assert not real_ns["is_confirmed_german_vocal"](artist, title), (artist, title)
print("✅ 6 Duitse opnames uit Indie Select geweerd; Dreampop en Engelstalige tracks behouden.")

print("✅ Sigur Rós, Ólafur Arnalds en Cocteau Twins welkom; Duitse zang blijft voor iedereen geblokkeerd.")
