"""v250: The Cure ambient mix -> ordinary album version, no other changes."""
from pathlib import Path
from v250_cure_album_version import owner_approved_album_version

assert owner_approved_album_version("The Cure", "This Is A Lie (Ambient Mix)") == "This Is a Lie"
assert owner_approved_album_version("the cure", "this is a lie (ambient mix)") == "This Is a Lie"
for artist, title in (
    ("The Cure", "This Is A Lie"),
    ("The Cure", "This Is A Lie (Live)"),
    ("Other Artist", "This Is A Lie (Ambient Mix)"),
):
    assert owner_approved_album_version(artist, title) == title

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
start = src.index("def find_spotify_track(")
end = src.index("def add_tracks(", start)
matching = src[start:end]
assert "v101_original_key = v101_radio_key(artist, title)" in matching
assert "title = owner_approved_album_version(artist, title)" in matching
assert matching.index("v101_original_key = v101_radio_key(artist, title)") < matching.index("title = owner_approved_album_version(artist, title)")
assert "safe_remix_original_fallback(" in matching
print("✅ v250: The Cure gewone versie, originele FIFO-identiteit en alle remixguards behouden.")
