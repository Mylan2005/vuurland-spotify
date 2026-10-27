"""v156: zoekopdrachten behouden gewone titels; geen extra Spotify API."""
import inspect
import vuurland_sync as sync

route = sync.v80_search_route("Pieta Brown", "Lullaby", 1)
assert route["title"] == "Lullaby"
assert route["reason"] != "spaced_letters"

for artist, title in [
    ("The xx", "Intro"),
    ("Tennis", "Dreaming"),
    ("Wye Oak", "Civilian"),
    ("Slowdive", "Alison"),
    ("Peter Gabriel", "Red Rain"),
]:
    result = sync.v80_search_route(artist, title, 1)
    assert result["title"] == title, (artist, title, result)

src = inspect.getsource(sync.find_spotify_track)
assert '" ".join(str(search_title).strip().upper())' not in src
assert 'str(primary_search_artist).casefold().strip() == "bon iver"' in src
assert 'str(search_title).casefold().strip() == "speyside"' in src
assert sync.SPOTIFY_SEARCH_HTTP_LIMIT == 1
print("✅ v156: gewone titelwoorden behouden; Speyside-uitzondering en één Search behouden")
