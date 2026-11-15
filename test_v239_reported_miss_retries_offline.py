"""v239: all user-reported ordinary misses get exactly the guarded FIFO route."""
from v239_reported_miss_retries import _REPORTED, reported_for_safe_retry
from v203_matcher_upgrade_requeue import applicable_rules, release_for_matcher_upgrades

assert len(_REPORTED) == 26
for artist, title in _REPORTED:
    assert reported_for_safe_retry(artist, title), (artist, title)
    assert "v239_reported_source_retry" in applicable_rules(artist, title), (artist, title)

assert not reported_for_safe_retry("CocoRosie", "Werewolf")
assert not reported_for_safe_retry(
    ". . - . . - ... . - ..",
    ".. / ..-. --- .-. --. --- - / - --- / - .- -.- . / -- -.-- / -- . -.. ...",
)

def key(a,t):
    return a.casefold().strip() + "|||" + t.casefold().strip()

artist, title = "Kyle Dixon & Michael Stein", "Stranger Things Theme (Extended)"
k = key(artist,title)
valid = {"artist":artist,"title":title,"source":"egofm_chillout"}
def retry(cache, queue):
    return release_for_matcher_upgrades(
        cache, queue, set(), active_sources=("egofm_chillout",),
        make_key=key, in_playlist=lambda a,t,known: False,
        eligible=lambda a,t: True, now=2000000000)

# A mere mention in a text log does not manufacture source evidence.
assert retry({}, []) == (0,0)
cache = {"__v51_radio_unmatched": {k:dict(valid)}}
queue = [{"artist":"Earlier","title":"Song","source":"egofm_chillout","_v116_fifo_seq":42}]
assert retry(cache,queue) == (1,0)
assert queue[0]["_v116_fifo_seq"] == 42
assert queue[1]["artist"] == artist and queue[1]["title"] == title
assert queue[1]["source"] == "egofm_chillout"
assert queue[1]["_v34_search_variant"] == 0
assert k not in cache["__v51_radio_unmatched"]
assert retry(cache,queue) == (0,0)

bad = {"__v51_radio_unmatched": {k:{**valid,"source":"unknown"}}}
assert retry(bad,[]) == (0,0)
print("✅ v239: 26 reported observations, source proof, FIFO and no invented matches")
