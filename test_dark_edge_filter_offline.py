"""Dark Edge discovery regressions: open artist intake, targeted exclusions."""
import ast
import re
from pathlib import Path
from dark_edge_filter import (
    DARK_EDGE_BLOCKED_ARTISTS, DARK_EDGE_USER_BLOCKED_TRACKS,
    dark_edge_reject_reason,
)

source = (Path(__file__).resolve().parent / "vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

allowed = [
    ("Nieuw Indieproject", "New Atmospheric Song"),
    ("New Indie Band", "Endless Reverie"),
    ("Unknown Shoegaze Artist", "Beautiful Sky"),
    ("Dreamy Spanish Indie", "No te vayas"),
    ("Tati Falco", "Selva y mar"),
    ("Sam Smiths", "Different Artist"),
    ("The Sam Smiths", "Different Artist"),
    ("Coldplay", "A Sky Full of Stars"),
    ("Muse", "Ich liebe dich"),
    ("Band", "Je t'aime"),
    ("Gorillaz", "Clint Eastwood"),
    ("Adele", "Someone Like You"),
    ("Billie Eilish", "Birds of a Feather"),
    ("Sia", "Like a River Runs"),
    ("Sigur Rós", "Inní mér syngur vitleysingur"),
    ("Blanco White", "Mano a Mano"),
    ("Editors", "Magazine"),
    ("Muse", "Supermassive Black Hole"),
    ("Taylor Swift feat. Bon Iver", "exile"),
    ("Coldplay", "The Scientist"),
]
for artist, title in allowed:
    assert dark_edge_reject_reason(artist, title) is None, (artist, title)

blocked = [
    ("Avicii", "Levels"),
    ("AVICII", "Wake Me Up"),
    ("Muse feat. Avicii", "Supermassive Black Hole"),
    ("Muse (feat. Avicii)", "Supermassive Black Hole"),
    ("Muse & Avicii", "Supermassive Black Hole"),
    ("Avicii feat. Aloe Blacc", "Wake Me Up"),
    ("Grimus", "Privește-mă"),
    ("Grimus", "Priveşte-mă"),
    ("Grimus", "Priveste-ma"),
    ("Grimus", "Priveste - Ma"),
    ("Grimus", "Priveste Ma (Live)"),
    ("Travka", "Distante"),
    ("Unknown Band", "Nu mai vreau"),
    ("Unknown Band", "Cea mai frumoasa zi"),
    ("Unknown Band", "Culori uitate"),
    ("Unknown Band", "Inima mea"),
    ("Unknown Band", "Ploile nu vin"),
    ("", "Song"),
    ("Artist", ""),
]
for artist, title in blocked:
    assert dark_edge_reject_reason(artist, title), (artist, title)

assert DARK_EDGE_BLOCKED_ARTISTS == frozenset({
    "avicii", "disclosure", "the chemical brothers", "tones and i",
    "sam smith", "dua lipa", "oakenfold", "paul oakenfold", "kylie minogue",
})
assert len(DARK_EDGE_USER_BLOCKED_TRACKS) == 36
for artist, title in DARK_EDGE_USER_BLOCKED_TRACKS:
    assert dark_edge_reject_reason(artist, title), (artist, title)
for artist in [
    "Disclosure", "The Chemical Brothers", "Tones and I", "Sam Smith",
    "Dua Lipa", "Oakenfold", "Paul Oakenfold", "Kylie Minogue", "Avicii",
]:
    assert dark_edge_reject_reason(artist, "Some Other Track"), artist
for artist in ["Indie Band feat. Dua Lipa", "Indie Band (feat. Sam Smith)",
               "Band & The Chemical Brothers", "Dua Lipa feat. Indie Band"]:
    assert dark_edge_reject_reason(artist, "New Song"), artist
for artist, title in [
    ("Eyedrops", "Pastreaza-mi CalmUl"),
    ("FIRMA", "Doua suflete"),
    ("Goji\u200bra & Planet H feat. Robin", "Regele Verii"),
    ("Omul Cu Sobolani VS. Michi", "Dezorientat (Live)"),
    ("Grimus", "Priveste Ma - Live"),
    ("Byron", "Granita-n ranita"),
]:
    assert dark_edge_reject_reason(artist, title), (artist, title)
assert dark_edge_reject_reason("The Chemical Brothers Tribute", "Hey Boy Hey Girl") is None
assert dark_edge_reject_reason("Unknown Band", "Morsa") is None
assert dark_edge_reject_reason("Kumm", "English Song") is None
assert "sam smiths" not in DARK_EDGE_BLOCKED_ARTISTS
assert dark_edge_reject_reason("Avi Ciin", "More Rain") is None
assert dark_edge_reject_reason("Indie Band", "Sam Smith") is None

# RadioBox ingestion, existing queue cleaning and immediate Spotify gate
# must remain intact; unrelated sources, Duyster and Spotify budgets unchanged.
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
        ("Nieuw Indieproject", "New Atmospheric Song"),
        ("Avicii", "Levels"),
        ("Band feat. Avicii", "Great Indie Song"),
        ("Grimus", "Privește-mă"),
        ("Sam Smith", "Stay With Me"),
        ("Dua Lipa", "Levitating"),
        ("Gorillaz", "Clint Eastwood"),
        ("Sia", "Like a River Runs"),
        ("Muse", "Ich liebe dich"),
        ("Muse", "Nu mai vreau"),
        ("Sigur Rós", "Inní mér syngur vitleysingur"),
        ("Cocteau Twins", "Привет"),
    ],
}
for name in ("v190_is_language_exempt_artist",
             "dark_edge_track_allowed", "get_dark_edge_tracks"):
    exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                 "<" + name + ">", "exec"), ns)
assert ns["get_dark_edge_tracks"]() == [
    ("Nieuw Indieproject", "New Atmospheric Song"),
    ("Gorillaz", "Clint Eastwood"),
    ("Sia", "Like a River Runs"),
    ("Muse", "Ich liebe dich"),
    ("Sigur Rós", "Inní mér syngur vitleysingur"),
    ("Cocteau Twins", "Привет"),
]
assert ns["dark_edge_track_allowed"]("New Alternative Band", "New Song")
assert not ns["dark_edge_track_allowed"]("Avicii", "Levels")
assert not ns["dark_edge_track_allowed"]("Sigur Rós feat. Avicii", "Great Song")
assert ns["dark_edge_track_allowed"]("Muse", "Ich liebe dich")
assert ns["dark_edge_track_allowed"]("Adele", "Someone Like You")
assert not ns["dark_edge_track_allowed"]("Dua Lipa", "Levitating")

sync_text = ast.get_source_segment(source, functions["sync"])
collector_text = ast.get_source_segment(source, functions["v96_collect_live_plays"])
assert '"dark_edge": ("Dark Edge Radio", get_dark_edge_tracks,' in sync_text
assert 'item.get("source") != "dark_edge" or dark_edge_track_allowed(' in sync_text
assert 'item.get("source") == "dark_edge" and not dark_edge_track_allowed(artist, title)' in sync_text
assert 'sid == "dark_edge" and not dark_edge_track_allowed(artist, title)' in collector_text
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
# Global policy is only bypassed for Dark Edge; remains for every other source.
assert 'sid != "dark_edge" and global_music_reject_reason(artist, title)' in collector_text
assert 'item.get("source") == "dark_edge" or not global_music_reject_reason(' in sync_text
assert 'None if item.get("source") == "dark_edge" else' in sync_text
assert 'item.get("source") != "dark_edge" and v140_is_unwanted_language_title' in sync_text
assert 'item.get("source") != "dark_edge" and is_confirmed_german_vocal' in sync_text
assert "def _duyster_song_allowed(artist, title):" in source
print("✅ Dark Edge: 36 gekozen tracks en 8 artiesten; andere artiesten welkom.")
print("✅ Andere bronnen, globale filters, FIFO en Spotify-budget onveranderd.")
