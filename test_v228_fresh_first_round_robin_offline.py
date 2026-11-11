"""v228 regressies: ongezochte liedjes eerst, retries pas daarna per bron."""
from v221_source_round_robin import fair_source_candidates
from v227_strict_source_turns import next_source_turn

sources = ("dreampop_radio", "indie_select", "dkfm_classic")
queue = [
    {"source": "dreampop_radio", "artist": "All Get Out", "title": "Time And Place",
     "_v116_fifo_seq": 6337, "_v34_search_variant": 2},
    {"source": "dreampop_radio", "artist": "Big Deal", "title": "Catch Up",
     "_v116_fifo_seq": 6395},
    {"source": "dreampop_radio", "artist": "High Highs", "title": "Horses",
     "_v116_fifo_seq": 6409},
    {"source": "indie_select", "artist": "A Projection", "title": "Young Days",
     "_v116_fifo_seq": 6246, "_v34_search_variant": 1},
    {"source": "indie_select", "artist": "Medicine Show", "title": "12 Remix",
     "_v116_fifo_seq": 6250},
    {"source": "dkfm_classic", "artist": "Veldt", "title": "End All To Be All",
     "_v116_fifo_seq": 9087, "_v34_search_variant": 1},
    {"source": "dkfm_classic", "artist": "Smudge", "title": "Weep Woman Weep",
     "_v116_fifo_seq": 9093},
    {"source": "dkfm_classic", "artist": "The Suncharms", "title": "One I See",
     "_v116_fifo_seq": 9098},
]
original = [dict(item) for item in queue]
def names(src):
    return [item["artist"] for _, item in
            fair_source_candidates(queue, sources, None) if item["source"] == src]
assert names("dreampop_radio") == ["Big Deal", "High Highs", "All Get Out"]
assert names("indie_select") == ["Medicine Show", "A Projection"]
assert names("dkfm_classic") == ["Smudge", "The Suncharms", "Veldt"]
assert queue == original

# Bronselectie blijft onafhankelijk van wachtrijgrootte en van retry-status.
cursor = None
turns = []
for _ in range(9):
    src, count = next_source_turn(queue, sources, cursor, lambda item: True)
    turns.append(src)
    assert count >= 2
    cursor = src
assert turns == list(sources) * 3
# Een retry op cooldown mag de volgende verse song van dezelfde bron niet blokkeren.
ready = lambda item: item.get("_v34_search_variant", 0) == 0
for source in sources:
    selected = [item for _, item in fair_source_candidates(queue, sources, None)
                if item["source"] == source and ready(item)]
    assert selected and selected[0].get("_v34_search_variant", 0) == 0
# Zelfs als eerder mislukte songs weer zoekklaar worden, blijven nieuwe songs eerst.
assert names("dreampop_radio")[0] == "Big Deal"

from pathlib import Path
src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
assert "fair_source_candidates(" in src
assert "next_source_turn(" in src
assert "MAX_SEARCHES_PER_RUN = 1" in src
assert "max_additions_per_round = 1" in src
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
print("✅ v228: 11-bronnenbeurtrol behoudt verse FIFO vóór retry, geen extra Spotify Search.")
