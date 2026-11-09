"""Offline regressies voor bronoverstijgende muziekvoorkeuren."""
import ast
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

source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {x.name: x for x in tree.body if isinstance(x, ast.FunctionDef)}
collector = ast.get_source_segment(source, functions["v96_collect_live_plays"])
sync = ast.get_source_segment(source, functions["sync"])
assert 'if global_music_reject_reason(artist, title):' in collector
assert 'not global_music_reject_reason(item.get("artist", ""), item.get("title", ""))' in sync
assert 'or global_music_reject_reason(artist, title)' in sync
assert 'rejection = global_music_reject_reason(artist, title)' in sync
assert "DUYSTER_ENQUEUE_INTERVAL_SECONDS = 120" in Path(__file__).with_name(
    "duyster_archive_fifo.py").read_text(encoding="utf-8")
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in source
assert "max_additions_per_round = 1" in source
print("✅ Bronoverstijgende muziekuitsluitingen, Duyster-tempo en Spotify-limieten veilig.")
