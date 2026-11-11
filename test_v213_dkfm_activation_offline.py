"""DKFM Shoegaze + Classic: source activation without backfill or Spotify changes."""
import ast
from pathlib import Path

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "RADIO_SOURCE_ORDER"
                          for t in node.targets))
sources = ast.literal_eval(assignment.value)
assert len(sources) == 10
assert sources[-2:] == ("dkfm_shoegaze", "dkfm_classic")
assert "duyster" not in sources
assert "radio_x_main" not in sources

funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
sync = ast.get_source_segment(src, funcs["sync"])
collect = ast.get_source_segment(src, funcs["v96_collect_live_plays"])
assert '"dkfm_shoegaze": ("DKFM Shoegaze Radio", get_dkfm_shoegaze_tracks,' in sync
assert '"dkfm_classic": ("DKFM Classic", get_dkfm_classic_tracks,' in sync
assert 'for sid in RADIO_SOURCE_ORDER' in sync
assert '__v213_dkfm_shoegaze_classic_baseline_20261109' in sync
assert 'for dkfm_sid in ("dkfm_shoegaze", "dkfm_classic"):' in sync
assert 'cache.setdefault("__v96_radio_snapshots", {}).pop(dkfm_sid, None)' in sync
assert 'cache.setdefault("__v174_radio_snapshot_times", {}).pop(dkfm_sid, None)' in sync
assert 'if sid in RADIO_SOURCE_ORDER:' in collect
assert 'arrivals = []' in collect
assert 'if sid != "dark_edge" and global_music_reject_reason(artist, title):' in collect
assert 'elif sid != "dark_edge" and is_confirmed_german_vocal(artist, title):' in collect
assert 'FIFO_SOURCE_ORDER = RADIO_SOURCE_ORDER + ("duyster",)' in src
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "max_additions_per_round = 1" in sync
assert 'if item.get("source") == "dark_edge" and not dark_edge_track_allowed(artist, title):' in sync
print("✅ Tien bronnen, nieuwe DKFM-feeds veilig nulmeten, Duyster en Spotify-limieten behouden.")
