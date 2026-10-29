"""Offline safety checks for v177 append-aware incremental cache.

Run: python test_v176_incremental_cache_offline.py
"""
from pathlib import Path

s = Path("vuurland_sync.py").read_text(encoding="utf-8")
start = s.index("    elif actual_playlist_total > active_playlist_count:")
end = s.index("    if (\n        not playlist_isrc_cache_ready", start)
block = s[start:end]

assert 'cache["__v177_playlist_delta"]' in block
assert '"offset": active_playlist_count' in block
assert '"target": actual_playlist_total' in block
assert 'params={"limit": min(50, delta_target - delta_offset),' in block
assert '"offset": delta_offset' in block
assert 'delta["offset"] = delta_offset + len(entries)' in block
assert 'playlist_keys.update(make_playlist_keys(track))' in block
assert 'cache["__playlist_uris"] = sorted(playlist_uris)' in block
assert 'cache["__playlist_isrcs"] = sorted(playlist_isrcs)' in block
assert 'cache["__spotify_uri_isrc"] = spotify_uri_isrc' in block
assert 'reset_live_sync_after_rate_limit(live_queue_file, cache)' in block
assert 'cache["__vuurland_active_playlist_count"] = actual_playlist_total' in block
assert 'not isinstance(cache.get("__v166_playlist_scan"), dict)' in block
assert 'cache.pop("__v177_playlist_delta", None)  # volledige scan vervangt delta' in s
assert "PLAYLIST_CACHE_SECONDS = 7 * 86400" in s
assert "max_additions_per_round = 1" in s
assert 'params={"limit": 50, "offset": 0}' not in block

print("v177 incremental Spotify-cache guards: OK")
