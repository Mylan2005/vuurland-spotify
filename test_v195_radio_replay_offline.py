"""Offline regression tests for v195: no Spotify/network/state files touched."""
import ast
from pathlib import Path
from v195_radio_replay import (
    release_parked_replay, REPLAY_INTERVAL_SECONDS, GLOBAL_INTERVAL_SECONDS,
    _LAST_GLOBAL, _LAST_BY_KEY,
)

NOW = 2_000_000_000
K = "artist|||title"


def state(age=31 * 86400):
    return {
        "__v51_radio_unmatched": {K: {
            "artist": "Artist", "title": "Title", "source": "vuurland",
            "failed_at": NOW - age, "full_search_cycles": 2,
        }},
        "__v51_radio_failed_searches": {K: 5},
        "__v51_radio_failed_cycles": {K: 2},
        "__not_found_v35__" + K: NOW - age,
        "__not_found_v34__" + K: NOW - age,
        "__v47_failed_tracks": {K: {"source": "vuurland"}},
        "__unrelated": "keep",
    }


cache = state()
assert release_parked_replay(cache, K, "Artist", "Title", "vuurland", now=NOW)
assert K not in cache["__v51_radio_unmatched"]
assert K not in cache["__v51_radio_failed_searches"]
assert K not in cache["__v51_radio_failed_cycles"]
assert "__not_found_v35__" + K not in cache
assert cache["__unrelated"] == "keep"
assert cache[_LAST_BY_KEY][K] == NOW
assert cache[_LAST_GLOBAL] == NOW
assert not release_parked_replay(cache, K, "Artist", "Title", "vuurland", now=NOW)

# Immediate replay, stale/incorrect credit and previously unseen title blocked.
for age in (0, 7 * 86400, REPLAY_INTERVAL_SECONDS - 1):
    c = state(age)
    assert not release_parked_replay(c, K, "Artist", "Title", "vuurland", now=NOW)
    assert K in c["__v51_radio_unmatched"]
c = state()
assert not release_parked_replay(c, K, "Different", "Title", "vuurland", now=NOW)
assert K in c["__v51_radio_unmatched"]
assert not release_parked_replay({}, K, "Artist", "Title", "vuurland", now=NOW)

# Even if the song was parked again after a failed replay, not sooner than 30d.
c = state()
c[_LAST_BY_KEY] = {K: NOW - 86400}
assert not release_parked_replay(c, K, "Artist", "Title", "vuurland", now=NOW)
assert K in c["__v51_radio_unmatched"]

# A different track may not consume global retry allowance for 24 hours.
c = state()
c[_LAST_GLOBAL] = NOW - GLOBAL_INTERVAL_SECONDS + 1
assert not release_parked_replay(c, K, "Artist", "Title", "vuurland", now=NOW)
assert K in c["__v51_radio_unmatched"]
c[_LAST_GLOBAL] = NOW - GLOBAL_INTERVAL_SECONDS
assert release_parked_replay(c, K, "Artist", "Title", "vuurland", now=NOW)

# Ensure the v96 integration only runs on fresh arrivals AFTER exclusion/dedupe.
source = (Path(__file__).resolve().parent / "vuurland_sync.py").read_text(encoding="utf-8")
ast.parse(source)
start = source.index("def v96_collect_live_plays(")
end = source.index("\ndef v167_restore_four_radio_histories(", start)
ingest = source[start:end]
assert ingest.index("for key, artist, title in reversed(arrivals):") < ingest.index("v195_release_parked_replay(")
assert ingest.index("elif key in known_queue:") < ingest.index("v195_release_parked_replay(")
assert ingest.index("elif key in playlist_keys") < ingest.index("v195_release_parked_replay(")
assert ingest.index("elif key in cache.get(\"__v51_radio_unmatched\"") < ingest.index("v195_release_parked_replay(")
assert ingest.count("v195_release_parked_replay(") == 1
assert GLOBAL_INTERVAL_SECONDS == 86400
print("✅ v195: parked replay throttled, exact identity, FIFO integration and state preserved.")
