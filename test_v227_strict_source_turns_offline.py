"""v227: de 11 bronnen krijgen een echte, vaste beurt per Spotify-slot."""
import ast
from pathlib import Path
from v227_strict_source_turns import next_source_turn
from v221_source_round_robin import fair_source_candidates

sources = (
    "vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled",
    "dreampop_radio", "indie_select", "dkfm_edge", "dark_edge",
    "dkfm_shoegaze", "dkfm_classic", "duyster",
)
queue = []
for i, source in enumerate(sources):
    for j in range((i + 1) * 10):
        queue.append({"source":source, "artist":f"Artist {i}-{j}",
                      "title":"Song", "_v116_fifo_seq":1000*i+j})
before = [dict(item) for item in queue]
turns=[]
cursor=None
for _ in range(33):
    selected, count = next_source_turn(queue, sources, cursor, lambda row: True)
    assert count > 0
    turns.append(selected)
    cursor = selected
assert turns == list(sources) * 3, turns
assert queue == before  # geen mutaties en geen herordening
# Het verwijderen van de gehele Classic-bron laat het systeem doorroteren.
without_classic=[item for item in queue if item["source"]!="dkfm_classic"]
next_source,_ = next_source_turn(without_classic, sources, "dkfm_shoegaze", lambda row: True)
assert next_source == "duyster"
# Tijdelijke cooldown laat de bron weg, maar de volgende ronde komt hij terug.
next_source,_ = next_source_turn(queue, sources, "radio_x_chilled",
                                 lambda row: row["source"]!="dreampop_radio")
assert next_source == "indie_select"
next_source,_ = next_source_turn(queue, sources, "radio_x_chilled", lambda row: True)
assert next_source == "dreampop_radio"
assert next_source_turn([], sources, None, lambda row: True) == (None, 0)
assert next_source_turn(queue, sources, None, lambda row: False) == (None, 0)

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree=ast.parse(src)
sync=ast.get_source_segment(src, next(n for n in tree.body
    if isinstance(n,ast.FunctionDef) and n.name=="sync"))
assert 'turn_source, ready_count = next_source_turn(' in sync
assert 'cache["__v227_last_source_turn"] = turn_source' in sync
assert 'if str(candidate.get("source") or "vuurland").strip() != turn_source:' in sync
assert '🎟️ v227 bronbeurt:' in sync
assert 'max_additions_per_round = 1' in sync
assert 'MAX_SEARCHES_PER_RUN = 1' in sync
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in src
assert 'fair_source_candidates(' in sync
assert 'processed_item_ids.add(id(live_queue[0]))' in sync
assert 'atomic_save_json(live_queue_file, live_queue' in sync
print("✅ v227: 11 stations in vaste beurt, één bron per slot, FIFO behouden.")
