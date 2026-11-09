"""v214: Spotify-verwijdering zonder handmatige GitHub-input nooit opnieuw toevoegen."""
import ast
from pathlib import Path
from v214_processed_history import preserve_processed_playlist_history as keep

old = {
    "__playlist_keys": ["slowdive|||alison", "cocteau twins|||heaven or las vegas"],
    "__playlist_uris": ["spotify:track:old", "spotify:track:still"],
    "__playlist_isrcs": ["OLDISRC", "STILLISRC"],
    "__spotify_uri_isrc": {
        "spotify:track:old": "OLDISRC",
        "spotify:track:still": "STILLISRC",
    },
}
before = repr(old)
keys, uris, isrcs, codes = keep(
    old,
    {"cocteau twins|||heaven or las vegas", "mogwai|||take me somewhere nice"},
    {"spotify:track:still", "spotify:track:new"},
    {"STILLISRC", "NEWISRC"},
    {"spotify:track:still": "STILLISRC", "spotify:track:new": "NEWISRC"},
)
# Deleted Slowdive track is still processed, without manual commands or
# a Spotify search. New songs are still accepted.
assert "slowdive|||alison" in keys
assert "spotify:track:old" in uris
assert "OLDISRC" in isrcs
assert codes["spotify:track:old"] == "OLDISRC"
assert "mogwai|||take me somewhere nice" in keys
assert "spotify:track:new" in uris
assert repr(old) == before  # no mutation of persisted state before validation

# Idempotent even after several complete weekly scans, and with staged
# recent self-additions; all historical no-readd markers remain.
again = dict(zip(
    ("__playlist_keys", "__playlist_uris", "__playlist_isrcs", "__spotify_uri_isrc"),
    (sorted(keys), sorted(uris), sorted(isrcs), codes),
))
assert keep(again, set(), set(), set(), {})[0] == keys

# Broken cache must stop safely; never silently discard the user's history.
for broken in (
    {"__playlist_uris": "not a list"},
    {"__playlist_keys": None},
    {"__spotify_uri_isrc": []},
):
    try:
        keep(broken, set(), set(), set(), {})
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid cache would erase historical rejections")

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
start = src.index("if not scan_pending:")
finish = src.index('cache.pop("__v166_playlist_scan", None)', start)
span = src[start:finish]
assert "preserve_processed_playlist_history(" in span
assert span.index('stage.get("live_keys", [])') < span.index("preserve_processed_playlist_history(")
assert "max_additions_per_round = 1" in src
assert 'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)' in src
# No new Liked Songs inventory or destructive Spotify write was introduced.
assert 'spotify_request("GET", "/me/tracks"' not in src
print("✅ v214: handmatig verwijderde playlistnummers blijven verwerkt; geen herimport na scan.")
