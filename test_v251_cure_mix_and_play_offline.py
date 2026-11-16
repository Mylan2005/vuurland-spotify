"""v251: The Cure Play correction and ordinary studio versions of mixes."""
from pathlib import Path
from v250_cure_album_version import owner_approved_album_version as corrected

for title in ("Play", "play", " PLAY "):
    assert corrected("The Cure", title) == "Play for Today"
for title, expected in (
    ("This Is A Lie (Ambient Mix)", "This Is a Lie"),
    ("A Night Like This (Hello Goodbye Mix 2018)", "A Night Like This"),
    ("Close to Me (closer mix)", "Close to Me"),
    ("Just Like Heaven - Extended Mix", "Just Like Heaven"),
    ("Pictures of You [Radio Mix]", "Pictures of You"),
):
    assert corrected("The Cure", title) == expected
for artist, title in (
    ("The Cure", "Play for Today"),
    ("The Cure", "Playground"),
    ("The Cure", "The Mix"),
    ("The Cure", "This Is A Lie (Live)"),
    ("The Cure", "This Is A Lie (Demo)"),
    ("The Cure", "A Night Like This (Hello Goodbye Remix 2018)"),
    ("The Cure", "A Night Like This (Live Mix)"),
    ("The Cure", "Mixer"),
    ("Some Other Band", "Play"),
    ("Some Other Band", "Close to Me (closer mix)"),
):
    assert corrected(artist, title) == title, (artist, title)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
matcher = src[src.index("def find_spotify_track("):src.index("def add_tracks(")]
assert matcher.index("v101_original_key = v101_radio_key(artist, title)") < matcher.index("title = owner_approved_album_version(artist, title)")
assert "safe_remix_original_fallback(" in matcher
sync = src[src.index("def sync("):]
assert "owner_approved_album_version(artist, title) != title" in sync
assert 'cache.pop(match_cache_key, None)' in sync
assert '"__v251_cure_version_migrated"' in sync
assert 'if uri in playlist_uris:' in sync
print("✅ v251: alleen The Cure - Play en expliciete mixversies naar reguliere opname.")
