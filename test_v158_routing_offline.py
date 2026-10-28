"""Regression: all 12 sources may add to both Spotify playlist and library."""
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
print("✅ Alle radiobronnen mogen weer aan playlist én Liked Songs toevoegen; dedupe behouden")
