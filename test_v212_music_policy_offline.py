"""Offline regressies voor bronoverstijgende muziekvoorkeuren."""
import ast
import json
from pathlib import Path
from vuurland_music_policy import global_music_reject_reason

for artist in (
    "Ed Sheeran", "Sam Smith", "Dua Lipa", "Avicii",
    "BLACKPINK", "BTS", "YOASOBI", "Jay Chou",
    "Muse feat. Sam Smith", "Kim Petras (feat. Sam Smith)",
):
    assert global_music_reject_reason(artist, "Testlied"), artist

for artist, title in (
    ("Sigur Rós", "Hoppípolla"),
    ("Cocteau Twins", "Heaven or Las Vegas"),
    ("Ólafur Arnalds", "Near Light"),
    ("Slowdive", "Sugar for the Pill"),
    ("The Japanese House", "Sunshine Baby"),
    ("Unknown Shoegaze Band", "Atmosphere"),
    ("Sam Smiths", "Different Band"),
    ("Massive Attack & Portishead", "Unfinished"),
):
    assert global_music_reject_reason(artist, title) is None, artist

# Nieuwe gebruikerskeuzes gelden ook voor DKFM, Duyster, Vuurland en alle andere.
for artist, title in [
    ("Alternosfera", "Muta"), ("Firma", "Două suflete"),
    ("The Mono Jacks", "Drumul"), ("Kumm", "Morsa"),
    ("Byron", "Granița-n răniță"), ("Eyedrops", "Bicicleta"),
    ("Tones and I", "Any Other Track"), ("Disclosure", "Different Song"),
    ("Sam Smith", "Stay With Me"), ("Oakenfold", "Any Title"),
    ("Paul Oakenfold", "Another Track"), ("Kylie Minogue", "Another Track"),
    ("Band feat. Disclosure", "New Track"),
    ("Avicii", "Levels"),
]:
    assert global_music_reject_reason(artist, title), (artist, title)
for artist, title in [
    ("The Chemical Brothers", "Hey Boy Hey Girl"),
    ("The Chemical Brothers", "Galvanize"),
    ("Band feat. The Chemical Brothers", "Collaboration"),
    ("Unknown Shoegaze Artist", "Fresh Music"),
    ("Kumm", "English Song"),
]:
    assert global_music_reject_reason(artist, title) is None, (artist, title)

# Een specifiek afgewezen nummer mag nooit opnieuw via een van de
# radiobronnen of Duyster naar Spotify gaan; andere Eefje-tracks blijven.
user_exclusions = json.loads(
    Path(__file__).with_name("vuurland_user_exclusions.json").read_text(encoding="utf-8")
)
assert ["eefje de visser", "onomkeerbaar"] in user_exclusions["pairs"]

source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {x.name: x for x in tree.body if isinstance(x, ast.FunctionDef)}
collector = ast.get_source_segment(source, functions["v96_collect_live_plays"])
sync = ast.get_source_segment(source, functions["sync"])
assert 'v101_radio_key(artist, title) in V101_EXCLUDED_RADIO_TRACKS' in collector
assert 'sid != "dark_edge" and global_music_reject_reason(artist, title)' in collector
assert 'item.get("source") == "dark_edge" or not global_music_reject_reason(' in sync
assert 'global_music_reject_reason(artist, title)' in sync
assert 'None if item.get("source") == "dark_edge" else' in sync
assert "DUYSTER_ENQUEUE_INTERVAL_SECONDS = 120" in Path(__file__).with_name(
    "duyster_archive_fifo.py").read_text(encoding="utf-8")
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
print("✅ Andere bronnen: oude muziekuitsluitingen; Dark Edge alleen bronfilter; Duyster-tempo en Spotify-limieten intact.")
