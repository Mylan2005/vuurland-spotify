"""v159: after manual rebuild, first Spotify round must rescan the real playlist."""
import ast
from pathlib import Path

src = Path("vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
assert 'V159_REBUILD_TOKEN = "vuurland-manual-rebuild-2026-10-28"' in src
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
assert 'playlist_count_changed = actual_playlist_total != active_playlist_count' in src
assert 'or playlist_count_changed' in src
assert src.index('actual_playlist_total = _get_playlist_total(playlist_id)') < scan
assert 'if str(item.get("source") or "").strip() != "vuurland":' not in src
print("✅ v159: echte playlist opnieuw lezen vóór dedupe, andere bronnen like-only")
