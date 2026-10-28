"""v159: after manual rebuild, first Spotify round must rescan the real playlist."""
import ast
from pathlib import Path

src = Path("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
assert 'V159_REBUILD_TOKEN = "vuurland-four-sources-fresh-rescan-v169-2026-10-28"' in src
assert 'cache["__vuurland_active_playlist_count"] = None' in src
assert 'or cache.get("__v159_rebuild_scanned") != V159_REBUILD_TOKEN' in src
scan = src.index('if (\n        not playlist_isrc_cache_ready')
marker = src.index('cache["__v159_rebuild_scanned"] = V159_REBUILD_TOKEN')
assert scan < marker
assert src.index('playlist_data = spotify_request(', scan) < marker
assert src.index('"__playlist_uris"', scan) < marker
assert src.index('"__playlist_isrcs"', scan) < marker
assert src.index('save_cache(cache)', marker) > marker
assert 'actual_playlist_total = _get_playlist_total(playlist_id)' in src
assert 'playlist_count_changed = actual_playlist_total > active_playlist_count' in src
assert 'if actual_playlist_total < active_playlist_count:' in src
assert 'cache["__vuurland_active_playlist_count"] = actual_playlist_total' in src
# v166: staged pagination, safe early return without Spotify writes.
assert 'cache["__v166_playlist_scan"] = stage' in src
assert 'cache.pop("__v166_playlist_scan", None)' in src
assert 'stage["offset"]' in src
assert 'playlist_offset + len(playlist_batch)' in src
assert 'save_cache(cache)\n                print(f"📋 v166:' in src
assert src.index('cache["__v166_playlist_scan"] = stage') < src.index('add_tracks(\n            playlist_id,')
assert 'or playlist_count_changed' in src
assert 'cache.get("__v165_existing_playlist_imported") != EXISTING_PLAYLIST_IMPORT_TOKEN' in src
assert 'cache["__v165_existing_playlist_imported"] = EXISTING_PLAYLIST_IMPORT_TOKEN' in src
assert src.index('cache["__v165_existing_playlist_imported"] = EXISTING_PLAYLIST_IMPORT_TOKEN') > scan

assert src.index('actual_playlist_total = _get_playlist_total(playlist_id)') < scan
assert 'if str(item.get("source") or "").strip() != "vuurland":' not in src
print("✅ v159: playlisttoevoegingen en rebuild scannen; verwijderingen bewaren dedupe-cache")

assert 'v167_restore_four_radio_histories(cache, live_queue, playlist_keys)' in src
assert 'four-radio-histories-after-fresh-playlist-scan-2026-10-28' in src
assert 'for sid in RADIO_SOURCE_ORDER:' in src

# v170: read all liked songs, one page per Spotify slot, before FIFO additions.
assert 'data = spotify_request("GET", "/me/tracks"' in src
assert '"limit": 50, "offset": stage["offset"]' in src
assert 'cache["__v170_liked_scan_complete"] = library_token' in src
assert src.index('if cache.get("__v170_liked_scan_complete")') < src.index('max_additions_per_round = 1')
