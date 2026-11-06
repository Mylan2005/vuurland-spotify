"""Offline regressie voor de strikt gefilterde achtste bron Dark Edge.

Geen netwerk-/Spotify-aanvragen, geen toestandwijzigingen.
"""
import ast
import re
from pathlib import Path

from dark_edge_filter import dark_edge_reject_reason, DARK_EDGE_BLOCKED_ARTISTS

root = Path(__file__).resolve().parent
source = (root / "vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {node.name: node for node in tree.body
             if isinstance(node, ast.FunctionDef)}

# Muse, Nothing But Thieves, The Neighbourhood, Tame Impala en Placebo.
# Zowel gekende als nog onbekende indie-artiesten krijgen toegang.
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
    ("Spinvis", "Ik wil alleen maar zwemmen"),
    ("Het Zesde Metaal", "Ploegsteert"),
    ("Nieuw Indieproject", "New Atmospheric Song"),
    ("Coldplay", "The Scientist"),
    ("Adele", "Someone Like You"),
    ("Billie Eilish", "Birds of a Feather"),
    ("Kylie Minogue", "In My Arms"),
    ("Sia", "Like a River Runs"),
    ("Taylor Swift", "Cardigan"),
    ("Ariana Grande", "We Can't Be Friends"),
    ("The Weeknd", "Blinding Lights"),
    ("Robyn", "Dancing On My Own"),
    ("Coldplay", "My Universe"),
    ("Coldplay", "Higher Power"),
    ("Muse feat. Drake", "Supermassive Black Hole"),
    ("The Weeknd & Kendrick Lamar", "Pray For Me"),
    # Spaanse indie/folk is welkom; Duitse zang niet.
    ("Blanco White", "Mano a Mano"),
    ("Blanco White", "Una Noche Más"),
    ("Blanco White", "El Búho"),
    ("Dreamy Spanish Indie", "No te vayas"),
    ("Tati Falco", "Selva y mar"),
    ("Dreamy Spanish Indie", "Te quiero"),
):
    assert dark_edge_reject_reason(artist, title) is None, (artist, title)

# Gerichte EDM-/dance-, persoonlijke Dua Lipa-, punk-/metal- en taalblokkades.
for artist, title in (
    ("Dua Lipa", "Levitating"),
    ("Avicii", "Levels"),
    ("David Guetta", "Titanium"),
    ("Calvin Harris feat. Ellie Goulding", "Outside"),
    ("Martin Garrix", "Animals"),
    ("Tiësto", "The Business"),
    ("Swedish House Mafia", "Don't You Worry Child"),
    ("Alan Walker", "Faded"),
    ("The Offspring", "Self Esteem"),
    ("Metallica", "Enter Sandman"),
    ("Faith No More", "Motherfucker"),
    ("Alexandru Andries", "Cea mai frumoasa zi"),
    ("Robin and the Backstabbers", "Sat Dupa Sat"),
    ("Travka", "Distante"),
    ("Muse feat. Avicii", "Supermassive Black Hole"),
    ("Kleerup & Robyn", "With Every Heartbeat"),
    ("Coldplay", "A Sky Full of Stars"),
    ("Eyedrops", "Culori Uitate"),
    ("Cred Ca Sunt Extraterestru", "Floare de maidan"),
):
    assert dark_edge_reject_reason(artist, title), (artist, title)

# Ook een toegelaten artiest kan een anderstalige titel hebben.
for artist, title in (
    ("Muse", "Cea mai frumoasa zi"),
    ("Muse", "Nu mai vreau"),
    ("Muse", "Ich liebe dich"),
    ("Placebo", "Je t'aime"),
    ("Editors", "Ti amo"),
    ("Interpol", "Ti voglio"),
    ("Muse", "Привет"),
):
    assert dark_edge_reject_reason(artist, title), (artist, title)

assert "muse" not in DARK_EDGE_BLOCKED_ARTISTS
assert "nothing but thieves" not in DARK_EDGE_BLOCKED_ARTISTS
assert "kylie minogue" not in DARK_EDGE_BLOCKED_ARTISTS
assert "sia" not in DARK_EDGE_BLOCKED_ARTISTS
assert "taylor swift" not in DARK_EDGE_BLOCKED_ARTISTS
assert "avicii" in DARK_EDGE_BLOCKED_ARTISTS
assert "calvin harris" in DARK_EDGE_BLOCKED_ARTISTS
assert "dua lipa" in DARK_EDGE_BLOCKED_ARTISTS
assert "adele" not in DARK_EDGE_BLOCKED_ARTISTS
assert "billie eilish" not in DARK_EDGE_BLOCKED_ARTISTS
assert "the offspring" in DARK_EDGE_BLOCKED_ARTISTS
assert dark_edge_reject_reason("Muse", "Ik ben hier") is None
assert dark_edge_reject_reason("Unknown Indie Artist", "Mijn hart") is None

# Test echte intakeroute met gesimuleerde RadioBox-resultaten.
ns = {
    "dark_edge_reject_reason": dark_edge_reject_reason,
    "re": re,
    "v140_is_unwanted_language_title": lambda title, artist: title in {"global-language-block", "Ich liebe dich", "Nu mai vreau"},
    "v131_block_nonlatin_east_asian": lambda artist, title: title == "Привет",
    "v191_is_german_vocal_risk": lambda artist, title: title == "Ich liebe dich",
    "DARK_EDGE_SOURCE_URL": "https://example.invalid/",
    "get_radiobox_tracks": lambda *args: [
        ("Muse", "Supermassive Black Hole"),
        ("Kylie Minogue", "In My Arms"),
        ("Sia", "Like a River Runs"),
        ("Avicii", "Levels"),
        ("Dua Lipa", "Levitating"),
        ("Alexandru Andries", "Cea mai frumoasa zi"),
        ("Nothing But Thieves", "Real Love Song"),
        ("Muse", "Nu mai vreau"),
        ("Spinvis", "Ik wil alleen maar zwemmen"),
        ("New Indie Band", "Endless Reverie"),
        ("Muse", "global-language-block"),
        ("Blanco White", "Mano a Mano"),
        ("Dreamy Spanish Indie", "No te vayas"),
        ("Sigur Rós", "Ich liebe dich"),
        ("Sigur Rós", "Inní mér syngur vitleysingur"),
        ("Ólafur Arnalds", "Nu mai vreau"),
        ("Cocteau Twins", "Привет"),
        ("Sigur Rós feat. Avicii", "Nu mai vreau"),
    ],
}
for name in ("v190_is_language_exempt_artist", "dark_edge_track_allowed", "get_dark_edge_tracks"):
    exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                 "<" + name + ">", "exec"), ns)
assert ns["get_dark_edge_tracks"]() == [
    ("Muse", "Supermassive Black Hole"),
    ("Kylie Minogue", "In My Arms"),
    ("Sia", "Like a River Runs"),
    ("Nothing But Thieves", "Real Love Song"),
    ("Spinvis", "Ik wil alleen maar zwemmen"),
    ("New Indie Band", "Endless Reverie"),
    ("Blanco White", "Mano a Mano"),
    ("Dreamy Spanish Indie", "No te vayas"),
    ("Sigur Rós", "Inní mér syngur vitleysingur"),
    ("Ólafur Arnalds", "Nu mai vreau"),
    ("Cocteau Twins", "Привет"),
]

order = next(node.value for node in tree.body
             if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "RADIO_SOURCE_ORDER"
                     for t in node.targets))
assert ns["v190_is_language_exempt_artist"]("Sigur Ros")
assert ns["v190_is_language_exempt_artist"]("Olafur Arnalds")
assert ns["v190_is_language_exempt_artist"]("Cocteau Twins feat Harold Budd")
assert not ns["v190_is_language_exempt_artist"]("Sigur Ros Tribute")
assert not ns["v190_is_language_exempt_artist"]("Avicii feat Sigur Ros")
assert not ns["dark_edge_track_allowed"]("Sigur Rós feat. Avicii", "Nu mai vreau")
assert not ns["dark_edge_track_allowed"]("Sigur Rós", "Ich liebe dich")
assert not ns["dark_edge_track_allowed"]("Blanco White", "Ich liebe dich")
assert ns["dark_edge_track_allowed"]("Sigur Rós", "Inní mér syngur vitleysingur")
assert ns["dark_edge_track_allowed"]("Blanco White", "Mano a Mano")
assert ns["dark_edge_track_allowed"]("Dreamy Spanish Indie", "No te vayas")
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
print("✅ Dark Edge: 8 bronnen; pop toegestaan, dance/EDM en Dua Lipa geblokkeerd; NL/EN/ES en queue-/Spotify-gates behouden.")
print("ℹ️ Genre en taal kunnen niet altijd uit RadioBox-metadata worden vastgesteld; dit is een risicofilter.")
