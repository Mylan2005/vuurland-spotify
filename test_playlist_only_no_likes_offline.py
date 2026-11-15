"""Regression gate: automatic sync must NEVER change Liked Songs.

Runs offline, no Spotify access. Playlist additions stay enabled.
"""
import ast
from pathlib import Path

source = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
def text_of(name):
    return ast.get_source_segment(source, functions[name])

assert "AUTO_LIKE_NEW_TRACKS = False" in source
for name in (
    "save_track_to_library", "_v153_send_pending_like",
    "_attempt_library_like", "_retry_one_pending_library_like",
):
    body = functions[name].body
    assert len(body) == 2, (name, ast.dump(body[0]))
    assert isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant), name
    assert isinstance(body[1], ast.Return), name
    assert body[1].value is None or isinstance(body[1].value, ast.Constant), name
    assert "spotify_request(" not in text_of(name), name

request = text_of("spotify_request")
assert '_library_path in {"/me/library", "/me/tracks"}' in request
assert 'str(method or "").upper() in {"PUT", "POST", "DELETE"}' in request
assert "raise RuntimeError(\"Playlist-only: Liked Songs wijzigingen zijn uitgeschakeld.\")" in request
assert 'f"/playlists/"' in text_of("add_tracks")
assert '"POST"' in text_of("add_tracks")
assert "_attempt_library_like(cache, uri)" in source  # old interface is inert
assert "_retry_one_pending_library_like(cache)" in source
print("✅ Playlist-only: new and pending likes disabled; existing likes untouched.")
