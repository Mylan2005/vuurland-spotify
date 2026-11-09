"""v203: offline unit/regression gates, no Spotify, no persistent mutations."""
import ast
from pathlib import Path
from v203_matcher_upgrade_requeue import (
    applicable_rules, release_for_matcher_upgrades, MATCHER_RETRY_RULES,
)

def key(a, t):
    return a.casefold().strip() + "|||" + t.casefold().strip()

SOURCES = ("vuurland", "indie_select", "dark_edge")
def run(cache, queue, seen=(), allowed=lambda a,t: True, now=2000000000):
    return release_for_matcher_upgrades(
        cache, queue, set(seen), active_sources=SOURCES, make_key=key,
        in_playlist=lambda a,t,known: key(a,t) in known,
        eligible=allowed, now=now,
    )

def parked(a="Tired Pony", t="All Things At Once", source="indie_select"):
    k = key(a, t)
    return k, {
        "__v51_radio_unmatched": {
            k: {"artist": a, "title": t, "source": source, "failed_at": 100}
        },
        "__v51_radio_failed_searches": {k: 5},
        "__not_found_v35__" + k: 123,
        "unrelated": "keep",
    }

assert "v200_tired_pony_verified_catalog_title" in applicable_rules("Tired Pony", "All Things At Once")
assert "v199_exact_trailing_artist" in applicable_rules("Birkii", "Holy War - Birkii")
assert "v194_reversed_the_artist_credit" in applicable_rules("Decemberists, The", "Rise To Me")
for a, t in (
    ("Hyper Nova", "Lost In Space"),
    ("Tired Pony", "All Things All At Once Remix"),
    ("Birkii", "Holy War - Other Artist"),
    ("Tired Pony Tribute", "All Things At Once"),
    ("Artist", "Song"),
):
    assert applicable_rules(a, t) == (), (a,t)

k, cache = parked()
queue = [{"artist": "Other", "title": "First", "source": "vuurland",
          "_v116_fifo_seq": 41}]
before = queue[0].copy()
assert run(cache, queue) == (1, 0)
assert queue[0] == before and len(queue) == 2
assert queue[1]["artist"] == "Tired Pony" and queue[1]["source"] == "indie_select"
assert queue[1]["_v34_search_variant"] == 0
assert k not in cache["__v51_radio_unmatched"]
assert "__not_found_v35__" + k not in cache
assert cache["unrelated"] == "keep"
assert cache["__v203_matcher_upgrade_retried_rules"][k] == [
    "v200_tired_pony_verified_catalog_title"]
assert run(cache, queue, now=2000000000 + 7 * 3600) == (0, 0)
assert len(queue) == 2

# Further syncs cannot release the SAME rule again even if search fails.
cache["__v51_radio_unmatched"][k] = {
    "artist": "Tired Pony", "title": "All Things At Once",
    "source": "indie_select", "failed_at": 2000000010,
}
queue.clear()
assert run(cache, queue, now=2000000000 + 24 * 3600) == (0, 0)
assert len(queue) == 0

# A fresh, separately tested matcher rule may retry one more time later.
cache["__v203_matcher_upgrade_retried_rules"][k] = []
assert run(cache, queue, now=2000000000 + 24 * 3600) == (1, 0)

# Zero race with already waiting tracks: no duplicate or reordered sequence.
k, cache = parked("Birkii", "Holy War - Birkii")
waiting = [{"artist":"Birkii", "title":"Holy War - Birkii", "source":"indie_select",
            "_v34_retry_at": 999999999, "_v34_search_variant": 2,
            "_v116_fifo_seq": 12}]
before = waiting[0].copy()
assert run(cache, waiting) == (0, 0)
assert waiting == [before]

# Missing or unproven source, wrong key, playlist, seen and filters fail closed.
for mode in ("unknown_source", "wrong_key", "seen", "playlist", "filter"):
    k, cache = parked()
    if mode == "unknown_source":
        cache["__v51_radio_unmatched"][k]["source"] = "invented"
    if mode == "wrong_key":
        cache["__v51_radio_unmatched"][k]["artist"] = "Not Tired Pony"
    if mode == "playlist":
        cache["__playlist_keys"] = [k]
    q=[]
    assert run(cache, q, seen=[k] if mode == "seen" else [],
               allowed=lambda a,t: mode != "filter") == (0, 0), mode
    assert not q and k in cache["__v51_radio_unmatched"], mode

# One per 6h even when multiple proven misses exist.
k, cache = parked()
k2 = key("Birkii", "Holy War - Birkii")
cache["__v51_radio_unmatched"][k2] = {
    "artist": "Birkii", "title": "Holy War - Birkii",
    "source": "vuurland", "failed_at": 100,
}
q=[]
assert run(cache, q) == (1, 0)
assert run(cache, q, now=2000000000+30) == (0, 0)
assert run(cache, q, now=2000000000+7*3600) == (1, 0)
assert len(q) == 2 and q[0]["artist"] == "Tired Pony"

# Large existing FIFO and 100+ Duyster items must not block a verified retry.
from duyster_archive_fifo import DUYSTER_MAX_PENDING, DUYSTER_MAX_TOTAL_QUEUE
k, cache = parked("Tired Pony", "All Things At Once", source="duyster")
cache["__v50_duyster_unmatched"] = cache.pop("__v51_radio_unmatched")
q = [{"artist": "Duyster older", "title": str(i), "source": "duyster"} for i in range(101)]
q += [{"artist": "Other", "title": str(i), "source": "vuurland"} for i in range(3500)]
original = list(q)
assert run(cache, q) == (1, 0)
assert q[:-1] == original and q[-1]["source"] == "duyster"
assert len(q) == 3602

# The shared limits still prevent unbounded queue growth.
k, cache = parked()
q = [{"artist": "Other", "title": str(i), "source": "vuurland"} for i in range(DUYSTER_MAX_TOTAL_QUEUE)]
assert run(cache, q) == (0,0) and len(q) == DUYSTER_MAX_TOTAL_QUEUE

# Corrupt state must never trigger broad requeue.
k, cache = parked()
cache["__v203_matcher_upgrade_retried_rules"] = "not-a-dict"
q=[]
assert run(cache, q) == (0,0) and not q

src = (Path(__file__).parent/"vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(src)
assert "max_additions_per_round = 1" in src
assert "SPOTIFY_SEARCH_HTTP_LIMIT = 1" in src
assert "v203_release_matcher_upgrade(" in src
assert "v116_stamp_fifo(live_queue, cache)" in src
assert len(MATCHER_RETRY_RULES) == len(set(MATCHER_RETRY_RULES))
print("✅ v203: specific matcher triggers, exact source/identity, FIFO, caps, no repeated old rules.")
