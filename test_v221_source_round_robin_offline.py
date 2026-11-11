"""Offline-regressies: eerlijke bronrotatie zonder verlies van FIFO/Spotify-veiligheid."""
import ast
from pathlib import Path

from v221_source_round_robin import fair_source_candidates

sources = ("vuurland", "mellow_mix", "dark_edge", "dkfm_shoegaze", "duyster")
queue = [
    {"source": "vuurland", "artist": "A1", "_v116_fifo_seq": 1},
    {"source": "vuurland", "artist": "A2", "_v116_fifo_seq": 2},
    {"source": "vuurland", "artist": "A3", "_v116_fifo_seq": 3},
    {"source": "dkfm_shoegaze", "artist": "S1", "_v116_fifo_seq": 200},
    {"source": "dark_edge", "artist": "D1", "_v116_fifo_seq": 100},
    {"source": "dkfm_shoegaze", "artist": "S2", "_v116_fifo_seq": 201},
    {"source": "duyster", "artist": "U1", "_v116_fifo_seq": 301},
]
original = [dict(x) for x in queue]
def names(last):
    return [(item["source"], item["artist"])
            for _, item in fair_source_candidates(queue, sources, last)]

assert names(None) == [
    ("vuurland", "A1"), ("dark_edge", "D1"), ("dkfm_shoegaze", "S1"),
    ("duyster", "U1"), ("vuurland", "A2"), ("dkfm_shoegaze", "S2"),
    ("vuurland", "A3"),
]
# Volgende ronde begint na de laatst geselecteerde bron, ook na runnerherstart.
assert names("vuurland")[0] == ("dark_edge", "D1")
assert names("dark_edge")[0] == ("dkfm_shoegaze", "S1")
assert names("dkfm_shoegaze")[0] == ("duyster", "U1")
assert names("duyster")[0] == ("vuurland", "A1")
assert names("unknown")[0] == ("vuurland", "A1")
assert names("mellow_mix")[0] == ("dark_edge", "D1")
assert queue == original  # Helper mag de echte FIFO nooit muteren.
assert fair_source_candidates(queue, (), None) == []
assert fair_source_candidates([{}, None, {"source": "unknown"}], sources, None) == []

# Iedere bron blijft intern strikt op _v116_fifo_seq, ook bij fysieke
# verschuivingen door de bestaande Spotify-verwerking.
shuffled = [
    {"source": "dkfm_shoegaze", "_v116_fifo_seq": 900},
    {"source": "dkfm_shoegaze", "_v116_fifo_seq": 800},
    {"source": "vuurland", "_v116_fifo_seq": 100},
]
result = fair_source_candidates(shuffled, sources, "dark_edge")
assert [item["_v116_fifo_seq"] for _, item in result] == [800, 100, 900]

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
functions = {x.name: x for x in tree.body if isinstance(x, ast.FunctionDef)}
sync = ast.get_source_segment(src, functions["sync"])
assert 'fair_source_candidates(' in sync
assert 'cache.get("__v221_last_selected_source")' in sync
assert 'cache["__v221_last_selected_source"] = selected_source' in sync
assert 'save_cache(cache)' in sync
assert 'max_additions_per_round = 1' in sync
assert 'MAX_SEARCHES_PER_RUN = 1' in sync
assert 'if now < _v41_cooldown_until(candidate):' in sync
assert 'if searches_used >= MAX_SEARCHES_PER_RUN:' in sync
assert 'processed_item_ids.add(id(live_queue[0]))' in sync
assert 'if selected_index != 0:' in sync
assert 'selected_item = live_queue.pop(selected_index)' in sync
assert 'live_queue.insert(0, selected_item)' in sync
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in src
assert 'DUYSTER_ENQUEUE_INTERVAL_SECONDS = 120' in Path(__file__).with_name(
    "duyster_archive_fifo.py").read_text(encoding="utf-8")
print("✅ Bronrotatie eerlijk, persistent, FIFO per bron intact; Spotify-budget behouden.")
