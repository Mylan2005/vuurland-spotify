"""v224 offline: echte Spotify-kansen eerlijk verdelen zonder extra HTTP of FIFO-wijzigingen."""
import ast
from pathlib import Path

from v221_source_round_robin import fair_source_candidates

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
sync_node = next(node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == "sync")
sync = ast.get_source_segment(src, sync_node)

# De persistent cursor voor Spotify-kansen wordt niet voor ieder queue-item
# doorgeschoven: 35 administratieve afhandelingen mogen geen bronbeurten opeten.
key = '__v224_last_spotify_opportunity_source'
assert 'round_last_selected_source = cache.get(' in sync
assert 'cache.get("__v221_last_selected_source")' in sync
assert 'fair_source_candidates(\n            live_queue, source_order, round_last_selected_source,' in sync
assert 'round_last_selected_source = selected_source' in sync
assert 'cache["__v221_last_selected_source"] = selected_source' in sync
assert sync.count(f'cache["{key}"] = selected_source') == 2
assert 'print(f"🎯 v224 Spotify-zoekbeurt: {selected_source}")' in sync
assert 'print(f"🎯 v224 Spotify-toevoegbeurt: {selected_source}")' in sync

# Precisie van de guards: Search boekt pas na de quota-check een kans,
# cache-only toevoeging pas na harde URI/ISRC-checks.
search_section = sync.index('uri = find_spotify_track(')
search_cursor = sync.index(f'cache["{key}"] = selected_source')
quota = sync.index('if searches_used >= MAX_SEARCHES_PER_RUN:', sync.index('# CACHE SEARCH RESULT'))
assert quota < search_cursor < search_section
add_cursor = sync.rindex(f'cache["{key}"] = selected_source')
assert sync.index('if uri in playlist_uris:') < add_cursor < sync.index('add_tracks(\n            playlist_id')

# Verschillende wachtrijgroottes geven dezelfde Search-kans bij 11
# actieve bronnen. Fouten of missers houden de bron niet eindeloos vast.
sources = (
    "vuurland", "mellow_mix", "big_sonic_heaven", "radio_x_chilled",
    "dreampop_radio", "indie_select", "dkfm_edge", "dark_edge",
    "dkfm_shoegaze", "dkfm_classic", "duyster",
)
queue = []
for i, source in enumerate(sources):
    for seq in range(1 + i * 50):
        queue.append({"artist": f"A{i}-{seq}", "title": "Song",
                      "source": source, "_v116_fifo_seq": i * 10000 + seq})
snapshot = [dict(item) for item in queue]
cursor = None
served = []
for _ in range(len(sources) * 3):
    choice = fair_source_candidates(queue, sources, cursor)[0][1]
    cursor = choice["source"]  # genuine Search (success or failure)
    served.append(cursor)
assert served == list(sources) * 3
assert queue == snapshot

# Opruimrondes kunnen lokaal doorschuiven maar verplaatsen niet de
# persistente Spotify-beurt. Daarom begint de volgende echte kans opnieuw
# na de laatst gebruikte Search/ADD-bron.
spotify_cursor = "radio_x_chilled"
local_cursor = spotify_cursor
for _ in range(35):
    local_cursor = fair_source_candidates(queue, sources, local_cursor)[0][1]["source"]
assert fair_source_candidates(queue, sources, spotify_cursor)[0][1]["source"] == "dreampop_radio"
assert "MAX_SEARCHES_PER_RUN = 1" in sync
assert "max_additions_per_round = 1" in sync
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
print("✅ v224: eerlijke echte Spotify-kansen, offline, geen queue/HTTP-mutaties.")
