"""Offline regressie voor de strikt gefilterde achtste bron Dark Edge.

Geen netwerk-/Spotify-aanvragen, geen toestandwijzigingen.
"""
import ast
from pathlib import Path

from dark_edge_filter import dark_edge_reject_reason, DARK_EDGE_APPROVED_ARTISTS

root = Path(__file__).resolve().parent
source = (root / "vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {node.name: node for node in tree.body
             if isinstance(node, ast.FunctionDef)}

# Muse, Nothing But Thieves, The Neighbourhood, Tame Impala en Placebo.
for artist, title in (
    ("MUSE", "Supermassive Black Hole"),
    ("Nothing But Thieves", "Real Love Song"),
    ("The Neighbourhood", "Daddy Issues"),
    ("Tame Impala", "The Less I Know The Better"),
    ("Placebo", "Every You Every Me"),
    ("Editors", "Magazine"),
    ("Interpol", "Obstacle 1"),
    ("Radiohead", "Creep"),
    ("Slowdive", "Sugar for the Pill"),
    ("DIIV", "Doused"),
):
    assert dark_edge_reject_reason(artist, title) is None, (artist, title)

# Nooit een onverwachte mainstream-, punk-, metal- of Roemeense artiest.
for artist, title in (
    ("Kylie Minogue", "In My Arms"),
    ("Sia", "Like a River Runs"),
    ("Avicii", "Levels"),
    ("The Offspring", "Self Esteem"),
    ("Metallica", "Enter Sandman"),
    ("Faith No More", "Motherfucker"),
    ("Alexandru Andries", "Cea mai frumoasa zi"),
    ("Robin and the Backstabbers", "Sat Dupa Sat"),
    ("Tati Falco", "Selva y mar"),
    ("Travka", "Distante"),
    ("Muse feat. Drake", "Supermassive Black Hole"),
):
    assert dark_edge_reject_reason(artist, title), (artist, title)

# Ook een toegelaten artiest kan een anderstalige titel hebben.
for artist, title in (
    ("Muse", "Cea mai frumoasa zi"),
    ("Muse", "Nu mai vreau"),
    ("Muse", "Ich liebe dich"),
    ("Placebo", "Je t'aime"),
    ("Radiohead", "No te vayas"),
    ("Editors", "Ti amo"),
    ("Interpol", "Ik ben hier"),
    ("Muse", "Привет"),
):
    assert dark_edge_reject_reason(artist, title), (artist, title)

assert "muse" in DARK_EDGE_APPROVED_ARTISTS
assert "nothing but thieves" in DARK_EDGE_APPROVED_ARTISTS
assert "kylie minogue" not in DARK_EDGE_APPROVED_ARTISTS

# Test echte intakeroute met gesimuleerde RadioBox-resultaten.
ns = {
    "dark_edge_reject_reason": dark_edge_reject_reason,
    "v140_is_unwanted_language_title": lambda title, artist: title == "global-language-block",
    "v131_block_nonlatin_east_asian": lambda artist, title: False,
    "DARK_EDGE_SOURCE_URL": "https://example.invalid/",
    "get_radiobox_tracks": lambda *args: [
        ("Muse", "Supermassive Black Hole"),
        ("Kylie Minogue", "In My Arms"),
        ("Alexandru Andries", "Cea mai frumoasa zi"),
        ("Nothing But Thieves", "Real Love Song"),
        ("Muse", "Nu mai vreau"),
        ("Muse", "global-language-block"),
    ],
}
for name in ("dark_edge_track_allowed", "get_dark_edge_tracks"):
    exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                 "<" + name + ">", "exec"), ns)
assert ns["get_dark_edge_tracks"]() == [
    ("Muse", "Supermassive Black Hole"),
    ("Nothing But Thieves", "Real Love Song"),
]

order = next(node.value for node in tree.body
             if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "RADIO_SOURCE_ORDER"
                     for t in node.targets))
assert len(ast.literal_eval(order)) == 8
assert ast.literal_eval(order)[-1] == "dark_edge"
sync_text = ast.get_source_segment(source, functions["sync"])
collector_text = ast.get_source_segment(source, functions["v96_collect_live_plays"])
assert '"dark_edge": ("Dark Edge Radio", get_dark_edge_tracks,' in sync_text
assert 'item.get("source") != "dark_edge" or dark_edge_track_allowed(' in sync_text
assert 'item.get("source") == "dark_edge" and not dark_edge_track_allowed(artist, title)' in sync_text
assert 'sid == "dark_edge" and not dark_edge_track_allowed(artist, title)' in collector_text
assert '__dark_edge_strict_baseline_20261105' in sync_text
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
print("✅ Dark Edge: 8 bronnen, artiestallowlist, taalblokkade, queue-/Spotify-gates, nulmeting.")
print("ℹ️ Metadata kan gezongen taal niet altijd aantonen; twijfelgevallen worden beperkt, niet bewezen.")
