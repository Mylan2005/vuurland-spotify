"""Offline safeguards for v176 incremental Spotify cache refresh.

Run: python test_v176_incremental_cache_offline.py
"""
from pathlib import Path

s = Path("vuurland_sync.py").read_text(encoding="utf-8")
start = s.index("    elif actual_playlist_total > active_playlist_count:")
end = s.index("    if (\n        not playlist_isrc_cache_ready", start)
block = s[start:end]

assert "growth = actual_playlist_total - active_playlist_count" in block
assert "0 < growth <= 50" in block
assert "playlist_isrc_cache_ready" in block
assert 'not isinstance(cache.get("__v166_playlist_scan"), dict)' in block
assert 'params={"limit": 50, "offset": 0}' in block
assert 'playlist_keys.update(make_playlist_keys(track))' in block
assert 'cache["__playlist_uris"] = sorted(playlist_uris)' in block
assert 'cache["__playlist_isrcs"] = sorted(playlist_isrcs)' in block
assert 'cache["__spotify_uri_isrc"] = spotify_uri_isrc' in block
assert 'reset_live_sync_after_rate_limit(live_queue_file, cache)' in block
assert 'cache["__vuurland_active_playlist_count"] = actual_playlist_total' in block
assert "PLAYLIST_CACHE_SECONDS = 7 * 86400" in s
assert "max_additions_per_round = 1" in s

print("v176 incremental Spotify-cache guards: OK")
