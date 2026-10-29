"""v179: background audit must preserve live FIFO Spotify additions."""
from pathlib import Path

src = Path("vuurland_sync.py").read_text(encoding="utf-8")
assert 'playlist_keys.update(stage.get("live_keys", []))' in src
assert 'playlist_uris.update(stage.get("live_uris", []))' in src
assert 'playlist_isrcs.update(stage.get("live_isrcs", []))' in src
assert 'spotify_uri_isrc.update(stage.get("live_uri_isrc", {}))' in src
assert 'live_stage = cache.get("__v166_playlist_scan")' in src
assert 'live_stage["live_uris"] = sorted(' in src
assert 'live_stage.setdefault("live_uri_isrc", {})[uri] = candidate_isrc' in src
assert 'active_playlist_count = max(' in src
assert 'max_additions_per_round = 1' in src
print("v179 concurrent FIFO/playlist scan guards OK")
