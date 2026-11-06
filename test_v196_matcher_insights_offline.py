"""Offline v196 regression: safe replay and historical insights, no Spotify."""
import ast
from pathlib import Path
from v195_radio_replay import release_parked_replay
from v196_matcher_insights import summarize, markdown

NOW = 2_000_000_000
K = "artist|||song"


def base():
    return {
        "__v51_radio_unmatched": {K: {
            "artist": "Artist", "title": "Song", "source": "indie_select",
            "failed_at": NOW - 40 * 86400,
        }},
        "__v51_radio_failed_searches": {K: 5},
        "__v47_failed_tracks": {},
        "__playlist_keys": [],
    }


c = base()
report = summarize(c, now=NOW)
assert report["totaal_unieke_meldingen"] == 1
assert report["per_status"]["geparkeerd"] == 1
assert report["per_bron"]["indie_select"] == 1
assert report["nummers"][0]["herkansingsstatus"] == "wacht_op_nieuwe_radio_uitzending_en_controles"
assert "Oudere GitHub-runrapporten" in markdown(report)
assert K in c["__v51_radio_unmatched"]  # analysis makes no mutations

c = base()
c["__v51_radio_unmatched"][K]["failed_at"] = NOW - 2 * 86400
assert summarize(c, now=NOW)["nummers"][0]["herkansingsstatus"] == "wachttijd_30_dagen"
assert not release_parked_replay(c, K, "Artist", "Song", "indie_select", now=NOW)

# The v195 module must refuse corrupt/missing/future timestamps, without crash.
for invalid in (None, "", "oops", -3, 0, NOW + 3600, {}, []):
    c = base()
    c["__v51_radio_unmatched"][K]["failed_at"] = invalid
    assert not release_parked_replay(c, K, "Artist", "Song", "indie_select", now=NOW)
    assert K in c["__v51_radio_unmatched"]

for invalid in ("oops", -1, NOW + 1, []):
    c = base()
    c["__v195_radio_replay_last_by_key"] = {K: invalid}
    assert not release_parked_replay(c, K, "Artist", "Song", "indie_select", now=NOW)

for invalid in ("oops", -1, NOW + 1, []):
    c = base()
    c["__v195_radio_replay_last_release"] = invalid
    assert not release_parked_replay(c, K, "Artist", "Song", "indie_select", now=NOW)

c = base()
assert release_parked_replay(c, K, "Artist", "Song", "indie_select", now=NOW)
assert K not in c["__v51_radio_unmatched"]

for source in ("v195_radio_replay.py", "v196_matcher_insights.py"):
    ast.parse((Path(__file__).parent / source).read_text(encoding="utf-8"))
print("✅ v196: historical audit and malformed replay state are safe.")
