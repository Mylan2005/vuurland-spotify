"""Regression guards: periodic full refresh must not stall a ready FIFO."""
from pathlib import Path

src = Path("vuurland_sync.py").read_text(encoding="utf-8")
assert "background_refresh = (" in src
assert "and cache.get(\"__v159_rebuild_scanned\") == V159_REBUILD_TOKEN" in src
assert "and cache.get(\"__v165_existing_playlist_imported\") == EXISTING_PLAYLIST_IMPORT_TOKEN" in src
assert "if not background_refresh:\n                    return" in src
assert "scan_pending = True\n                break" in src
assert "if not scan_pending:" in src
assert 'playlist_keys = set(cache.get("__playlist_keys", []))' in src
assert 'playlist_uris = set(cache.get("__playlist_uris", []))' in src
assert 'playlist_isrcs = set(cache.get("__playlist_isrcs", []))' in src
assert 'spotify_uri_isrc = dict(cache.get("__spotify_uri_isrc", {}))' in src
assert 'cache["__playlist_cache_time"]' in src
assert "PLAYLIST_CACHE_SECONDS = 7 * 86400" in src
assert "max_additions_per_round = 1" in src
print("v178 periodic FIFO continuation guards OK")
