"""Regression: Mellow Mix joins Vuurland; Big Sonic stays in review."""
import ast
from pathlib import Path

source = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
sync = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sync")
body = ast.get_source_segment(source, sync)
assert 'if str(item.get("source") or "").strip() != "vuurland":' not in body
assert 'add_tracks(\n            playlist_id,\n            [uri]\n        )' in body
assert '_attempt_library_like(cache, uri)' in body
assert body.index('add_tracks(\n            playlist_id,') < body.rindex('_attempt_library_like(cache, uri)')
assert 'if uri in playlist_uris:' in body
assert 'candidate_isrc in playlist_isrcs' in body
assert 'RADIO_SOURCE_ORDER = ("vuurland", "mellow_mix", "big_sonic_heaven")' in source
assert '"tracks": get_mellow_mix_tracks()' in body
assert '"tracks": get_big_sonic_heaven_tracks()' in body
assert 'cache.setdefault("__v167_big_sonic_review_pending", {})' in body
assert 'candidate.get("source") != "big_sonic_heaven"' in body
assert 'live_queue = [x for x in live_queue if not (' in body
assert body.index('cache.setdefault("__v167_big_sonic_review_pending", {})') < body.index('if not live_queue:')
print("✅ Vuurland + Mellow Mix actief; Big Sonic veilig apart gehouden.")
