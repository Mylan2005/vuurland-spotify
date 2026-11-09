"""Dark Edge alternative-only regressions: no automatic pop leak, no queue resets.

This intentionally tests *source* acceptance, not audio genre recognition.
Unknown artists fail closed on Dark Edge; no claim they are pop.
"""
import ast
import re
from pathlib import Path

from dark_edge_filter import (
    DARK_EDGE_APPROVED_ALTERNATIVE_ARTISTS,
    DARK_EDGE_APPROVED_SONGS,
    DARK_EDGE_BLOCKED_ARTISTS,
    dark_edge_is_confirmed_alternative,
    dark_edge_reject_reason,
)

root = Path(__file__).resolve().parent
source = (root / "vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {
    node.name: node for node in tree.body
    if isinstance(node, ast.FunctionDef)
}

allowed = [
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
    ("Grizzly Bear", "Two Weeks"),
    ("Portishead", "Roads"),
    ("Massive Attack", "Teardrop"),
    ("Beach House", "Space Song"),
    ("Sigur Rós", "Hoppípolla"),
    ("Ólafur Arnalds", "Near Light"),
    ("Cocteau Twins feat. Harold Budd", "Sea, Swallow Me"),
    ("Blanco White", "Mano a Mano"),
    ("Blanco White", "Una Noche Más"),
    ("Blanco White", "El Búho"),
    ("Gorillaz", "El Mañana"),
    ("Gorillaz", "Tomorrow Comes Today"),
    ("Gorillaz", "On Melancholy Hill"),
    ("Gorillaz", "Empire Ants"),
    ("Gorillaz", "Silent Running"),
    ("Gorillaz feat. Adeleye Omotayo", "Silent Running"),
    ("Gorillaz", "Happy Dictator"),
    ("Taylor Swift", "Cardigan"),
    ("Taylor Swift", "exile"),
    ("TAYLOR SWIFT", "Willow"),
    ("Taylor Swift feat. Bon Iver", "exile"),
    ("Taylor Swift (feat. Bon Iver)", "exile"),
]
for artist, title in allowed:
    assert dark_edge_reject_reason(artist, title) is None, (artist, title)

blocked_pop = [
    ("Grimus", "Privește-mă"),
    ("Grimus", "Priveşte-mă"),
    ("Grimus", "Priveste-ma"),
    ("Grimus", "Priveste - Ma"),
    ("Grimus", "Priveste Ma (Live)"),
    ("Sam Smith", "Stay With Me"),
    ("SAM SMITH", "Too Good at Goodbyes"),
    ("Sam Smith feat. Kim Petras", "Unholy"),
    ("Kim Petras feat. Sam Smith", "Unholy"),
    ("Kim Petras (feat. Sam Smith)", "Unholy"),
    ("Sam Smith & Kim Petras", "Unholy"),
    ("Ed Sheeran", "Shape of You"),
    ("Maroon 5", "Sugar"),
    ("Kylie Minogue", "In My Arms"),
    ("Ariana Grande", "We Can't Be Friends"),
    ("Justin Bieber", "Sorry"),
    ("Shawn Mendes", "Treat You Better"),
    ("Sabrina Carpenter", "Espresso"),
    ("Lewis Capaldi", "Someone You Loved"),
    ("Benson Boone", "Beautiful Things"),
    ("Adele", "Someone Like You"),
    ("Billie Eilish", "Birds of a Feather"),
    ("Sia", "Like a River Runs"),
    ("Taylor Swift feat. Sam Smith", "Cardigan"),
    ("Taylor Swift feat. Ed Sheeran", "Everything Has Changed"),
    ("The Weeknd", "Blinding Lights"),
    ("Robyn", "Dancing On My Own"),
    ("Coldplay", "My Universe"),
    ("Coldplay", "Higher Power"),
    ("Coldplay", "The Scientist"),
    ("Dua Lipa", "Levitating"),
    ("Avicii", "Levels"),
    ("David Guetta", "Titanium"),
    ("Calvin Harris feat. Ellie Goulding", "Outside"),
    ("The Offspring", "Self Esteem"),
    ("Metallica", "Enter Sandman"),
    ("Muse feat. Drake", "Supermassive Black Hole"),
    ("Muse feat. Sam Smith", "Supermassive Black Hole"),
    ("MUSE & Sam Smith", "Supermassive Black Hole"),
    ("Muse (feat. Sam Smith)", "Supermassive Black Hole"),
    ("Gorillaz", "Clint Eastwood"),
    ("Gorillaz", "Feel Good Inc."),
    ("Gorillaz", "The Mountain"),
    ("Gorillaz feat. Sam Smith", "Silent Running"),
]
for artist, title in blocked_pop:
    assert dark_edge_reject_reason(artist, title), (artist, title)

# Same verified Romanian recording also fails the global pre-Spotify
# language check, even if it is sourced from a different station or queue.
global_language = ast.parse(source)
language_fn = next(
    n for n in global_language.body
    if isinstance(n, ast.FunctionDef) and n.name == "v150_is_unwanted_language"
)
language_ns = {}
exec(compile(ast.Module(body=[language_fn], type_ignores=[]),
             "<v150_is_unwanted_language>", "exec"), language_ns)
for romanian_title in (
    "Privește-mă", "Priveşte-mă", "Priveste-ma",
    "Priveste Ma", "Priveste - Ma", "Priveste-ma (Live)",
):
    assert language_ns["v150_is_unwanted_language"]("Grimus", romanian_title), romanian_title
assert not language_ns["v150_is_unwanted_language"]("Grimus", "Vitriol")
assert not language_ns["v150_is_unwanted_language"]("Muse", "Supermassive Black Hole")

# Unknown is not declared pop: it's held OUT of Dark Edge's automatic FIFO.
for artist, title in [
    ("Nieuw Indieproject", "New Atmospheric Song"),
    ("New Indie Band", "Endless Reverie"),
    ("Dreamy Spanish Indie", "No te vayas"),
    ("Tati Falco", "Selva y mar"),
    ("Unknown Shoegaze Artist", "Beautiful Sky"),
    ("Sam Smiths", "Different Artist"),
    ("The Sam Smiths", "Different Artist"),
    ("Indie Band", "Sam Smith"),
]:
    assert dark_edge_reject_reason(artist, title) == (
        "Dark Edge: artiest/nummer niet bevestigd als passende alternatieve muziek"
    ), (artist, title)
# Exact-name matching, never substring bans: a newly verified 'Sam Smiths'
# could be added without affecting the separately blocked 'Sam Smith'.
assert "sam smiths" not in DARK_EDGE_BLOCKED_ARTISTS
assert "sam smith" in DARK_EDGE_BLOCKED_ARTISTS
assert "taylor swift" in DARK_EDGE_APPROVED_ALTERNATIVE_ARTISTS
assert "taylor swift" not in DARK_EDGE_BLOCKED_ARTISTS
assert "gorillaz" not in DARK_EDGE_APPROVED_ALTERNATIVE_ARTISTS
assert ("gorillaz", "silent running") in DARK_EDGE_APPROVED_SONGS
assert "sam smith" not in DARK_EDGE_APPROVED_ALTERNATIVE_ARTISTS
assert not dark_edge_is_confirmed_alternative("Sam Smith", "Whatever")

# Language exclusions remain, even for explicitly allowed artists.
for artist, title in [
    ("Muse", "Cea mai frumoasa zi"),
    ("Muse", "Nu mai vreau"),
    ("Muse", "Ich liebe dich"),
    ("Placebo", "Je t'aime"),
    ("Editors", "Ti amo"),
    ("Interpol", "Ti voglio"),
    ("Muse", "Привет"),
]:
    assert dark_edge_reject_reason(artist, title), (artist, title)

# Source, queue and immediately-before-Spotify gates must all call the same
# strict function; filtered items must not reach Spotify even from old state.
ns = {
    "dark_edge_reject_reason": dark_edge_reject_reason,
    "re": re,
    "v140_is_unwanted_language_title": lambda title, artist: title in {
        "global-language-block", "Ich liebe dich", "Nu mai vreau"
    },
    "v131_block_nonlatin_east_asian": lambda artist, title: title == "Привет",
    "v191_is_german_vocal_risk": lambda artist, title: title == "Ich liebe dich",
    "DARK_EDGE_SOURCE_URL": "https://example.invalid/",
    "get_radiobox_tracks": lambda *args: [
        ("Muse", "Supermassive Black Hole"),
        ("Sam Smith", "Stay With Me"),
        ("Adele", "Someone Like You"),
        ("Unknown Shoegaze Artist", "Beautiful Sky"),
        ("Gorillaz", "El Mañana"),
        ("Taylor Swift", "Cardigan"),
        ("Taylor Swift feat. Sam Smith", "Cardigan"),
        ("Gorillaz", "Clint Eastwood"),
        ("Kylie Minogue", "In My Arms"),
        ("Sia", "Like a River Runs"),
        ("Avicii", "Levels"),
        ("Dua Lipa", "Levitating"),
        ("Nothing But Thieves", "Real Love Song"),
        ("Muse", "Nu mai vreau"),
        ("Spinvis", "Ik wil alleen maar zwemmen"),
        ("Blanco White", "Mano a Mano"),
        ("Sigur Rós", "Ich liebe dich"),
        ("Sigur Rós", "Inní mér syngur vitleysingur"),
        ("Ólafur Arnalds", "Nu mai vreau"),
        ("Cocteau Twins", "Привет"),
        ("Sigur Rós feat. Avicii", "Nu mai vreau"),
    ],
}
for name in ("v190_is_language_exempt_artist",
             "dark_edge_track_allowed", "get_dark_edge_tracks"):
    exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                 "<" + name + ">", "exec"), ns)
assert ns["get_dark_edge_tracks"]() == [
    ("Muse", "Supermassive Black Hole"),
    ("Gorillaz", "El Mañana"),
    ("Taylor Swift", "Cardigan"),
    ("Nothing But Thieves", "Real Love Song"),
    ("Spinvis", "Ik wil alleen maar zwemmen"),
    ("Blanco White", "Mano a Mano"),
    ("Sigur Rós", "Inní mér syngur vitleysingur"),
    ("Ólafur Arnalds", "Nu mai vreau"),
    ("Cocteau Twins", "Привет"),
]
assert not ns["dark_edge_track_allowed"]("Sam Smith", "Stay With Me")
assert not ns["dark_edge_track_allowed"]("Adele", "Someone Like You")
assert not ns["dark_edge_track_allowed"]("Nieuw Indieproject", "New Atmospheric Song")
assert not ns["dark_edge_track_allowed"]("Gorillaz", "Clint Eastwood")
assert ns["dark_edge_track_allowed"]("Gorillaz", "Empire Ants")
assert ns["dark_edge_track_allowed"]("Blanco White", "Mano a Mano")
assert not ns["dark_edge_track_allowed"]("Sigur Rós", "Ich liebe dich")

order = next(node.value for node in tree.body
             if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "RADIO_SOURCE_ORDER"
                     for t in node.targets))
assert len(ast.literal_eval(order)) == 10
assert ast.literal_eval(order)[-2:] == ("dkfm_shoegaze", "dkfm_classic")
sync_text = ast.get_source_segment(source, functions["sync"])
collector_text = ast.get_source_segment(source, functions["v96_collect_live_plays"])
assert '"dark_edge": ("Dark Edge Radio", get_dark_edge_tracks,' in sync_text
assert 'item.get("source") != "dark_edge" or dark_edge_track_allowed(' in sync_text
assert 'item.get("source") == "dark_edge" and not dark_edge_track_allowed(artist, title)' in sync_text
assert 'sid == "dark_edge" and not dark_edge_track_allowed(artist, title)' in collector_text
assert "__dark_edge_strict_baseline_20261105" in sync_text
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source

# The Duyster source continues using its own distinct checks; unconfirmed
# Dark Edge approvals aren't applied to Duyster or the other seven radios.
assert "def _duyster_song_allowed(artist, title):" in source
assert '"Dark Edge: artiest/nummer niet bevestigd als passende alternatieve muziek"' not in source
print("✅ Dark Edge ONLY: mainstream pop & unknown artists withheld; approved atmospheric alternative music and song-level Gorillaz remain.")
