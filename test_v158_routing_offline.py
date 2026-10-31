"""Regression: Vuurland + Mellow Mix routing, disabled queues cleaned, German-vocal exclusion retained."""
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
assert '"vuurland": ("Studio Brussel Vuurland", get_vuurland_tracks,' in body
assert '"mellow_mix": ("Radio Paradise Mellow Mix", get_mellow_mix_tracks,' in body
assert '"tracks": source_catalog[sid][1]()' in body
assert 'for sid in RADIO_SOURCE_ORDER' in body
assert '"tracks": get_radio_x_chilled_tracks()' not in body
assert '"tracks": get_dreampop_radio_tracks()' not in body
assert '"big_sonic_heaven": ("Big Sonic Heaven Radio", get_big_sonic_heaven_tracks,' in body
assert '"radio_britannia": ("Radio Britannia", get_radio_britannia_tracks,' in body
assert 'RADIO_SOURCE_ORDER = ("vuurland", "mellow_mix")' in source
assert '"tracks": dkfm_vuurland_filter(get_dkfm_edge_tracks(), "DKFM Edge")' not in body
assert '"tracks": dkfm_vuurland_filter(get_dkfm_shoegaze_tracks(), "DKFM Shoegaze")' not in body
assert 'before_source_filter = len(live_queue)' in body
assert 'x.get("source") == "big_sonic_heaven"' not in body
assert 'is_confirmed_german_vocal(artist, title)' in body
assert 'v140_is_unwanted_language_title(title, artist)' in body
assert 'add_tracks(BIG_SONIC_REVIEW_PLAYLIST_ID, [uri])' not in body
assert 'big_sonic_destination(artist) == "review"' not in body
assert '__big_sonic_review_scan_complete' not in body
print("✅ Vuurland en Mellow Mix actief, overige bronnen uit FIFO, Duitse zangblokkering behouden.")

assert 'return "main"' in ast.get_source_segment(source, next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "big_sonic_destination"))

radio = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_radio_britannia_tracks")
radio_body = ast.get_source_segment(source, radio)
assert "RADIO_BRITANNIA_SOURCE_URL" in radio_body
assert 'normalize_match(artist) != "daniel roggiano"' in radio_body
