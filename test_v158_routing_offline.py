"""Regression: four live sources, no Big Sonic, German-vocal exclusion retained."""
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
assert '"tracks": get_mellow_mix_tracks()' in body
assert '"tracks": get_radio_x_chilled_tracks()' in body
assert '"tracks": get_dreampop_radio_tracks()' in body
assert 'RADIO_SOURCE_ORDER = ("vuurland", "mellow_mix", "radio_x_chilled", "dreampop_radio")' in source
assert 'x.get("source") == "big_sonic_heaven"' in body
assert 'is_confirmed_german_vocal(artist, title)' in body
assert 'v140_is_unwanted_language_title(title, artist)' in body
assert 'add_tracks(BIG_SONIC_REVIEW_PLAYLIST_ID' not in body
print("✅ Dreampop actief, Big Sonic verwijderd, Duitse zangblokkering behouden.")
