"""v171: live-nulmeting en oude seen-status blokkeren nieuwe uitzendingen niet."""
import ast
from pathlib import Path
from vuurland_music_policy import global_music_reject_reason

source = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "v96_collect_live_plays")
assert 'elif key in seen and sid not in RADIO_SOURCE_ORDER:' in ast.get_source_segment(source, node)

def key(a, t):
    return a.lower() + "|||" + t.lower()

ns = {
    "RADIO_SOURCE_ORDER": ("vuurland", "mellow_mix", "radio_britannia", "big_sonic_heaven"),
    "_v47_key": key,
    "v101_radio_key": lambda a, t: (" ".join(a.casefold().split()), " ".join(t.casefold().split())),
    "V101_EXCLUDED_RADIO_TRACKS": {("Test Blocked", "Blocked Song"), ("test blocked", "blocked song")},
    "normalize_match": str.lower,
    "global_music_reject_reason": global_music_reject_reason,
    "v110_correct_radio_artist": lambda a, sid: a,
    "is_confirmed_german_vocal": lambda a, t: False,
    "is_interview_fragment": lambda t: False,
    "radio_matches_playlist": lambda a, t, keys: key(a, t) in keys,
    "time": __import__("time"),
}
exec(compile(ast.Module(body=[node], type_ignores=[]), "<v96>", "exec"), ns)
collect = ns["v96_collect_live_plays"]

for sid in ns["RADIO_SOURCE_ORDER"]:
    cache = {"__playlist_keys": [], "__v169_fresh_radio_cache": "2026-10-28-all-four"}
    queue = []
    seen = {key("Artist", "Old")}
    source = [{"id": sid, "name": sid, "tracks": [("Artist", "Old"), ("Artist", "New")]}]
    # First page is the baseline, not a historical FIFO import.
    assert collect(source, cache, seen, queue) == 0
    assert queue == []
    source[0]["tracks"] = [("Artist", "Live"), ("Artist", "Old"), ("Artist", "New")]
    assert collect(source, cache, seen, queue) == 1
    assert [item["title"] for item in queue] == ["Live"]
    assert collect(source, cache, seen, queue) == 0
    assert len(queue) == 1

# A removed song may be present in the old cache, but must enter live FIFO.
old_key = key("Elton John", "Goodbye Yellow Brick Road")
for completed in (False, True):
    cache = {"__playlist_keys": [old_key]}
    if completed:
        cache["__v159_rebuild_scanned"] = "vuurland-live-only-rescan-v172-2026-10-29"
    q = []
    src = [{"id": "mellow_mix", "name": "Mellow", "tracks": [("Other", "Baseline")]}]
    assert collect(src, cache, set(), q) == 0
    src[0]["tracks"] = [("Elton John", "Goodbye Yellow Brick Road"), ("Other", "Baseline")]
    assert collect(src, cache, set(), q) == (0 if completed else 1)
    assert len(q) == (0 if completed else 1)

# v174: korte feedwissel zonder overlap mag enkele verse nummers behouden.
cache = {"__playlist_keys": []}
queue = []
sid = "mellow_mix"
source = [{"id": sid, "name": sid, "tracks": [("Anchor", "Before")]}]
assert collect(source, cache, set(), queue) == 0
source[0]["tracks"] = [("Fresh", "Newest"), ("Fresh", "Middle"), ("Fresh", "Oldest"), ("Fresh", "Too Old")]
assert collect(source, cache, set(), queue) == 3
assert [x["title"] for x in queue] == ["Oldest", "Middle", "Newest"]
# Een te oude snapshot mag geen historische backfill veroorzaken.
cache = {"__playlist_keys": [], "__v96_radio_snapshots": {sid: ["gone"]},
         "__v174_radio_snapshot_times": {sid: 1}}
queue = []
assert collect(source, cache, set(), queue) == 0
assert not queue

# Nieuwe wereldwijde muziekvoorkeur wordt ook door de los geladen
# collector toegepast: ongewenste pop niet in FIFO, indie wel.
cache = {"__playlist_keys": []}
q = []
src = [{"id": "vuurland", "name": "Vuurland",
        "tracks": [("Slowdive", "Alison")]}]
assert collect(src, cache, set(), q) == 0
src[0]["tracks"] = [("Ed Sheeran", "Shape of You"),
                    ("Slowdive", "Alison")]
assert collect(src, cache, set(), q) == 0
assert not q
src[0]["tracks"] = [("Cocteau Twins", "Heaven or Las Vegas"),
                    ("Ed Sheeran", "Shape of You"),
                    ("Slowdive", "Alison")]
assert collect(src, cache, set(), q) == 1
assert q[0]["artist"] == "Cocteau Twins"

# Controleer ook de nieuwe, exact gematchte gebruikersuitsluitingen.
cache = {"__playlist_keys": []}
q = []
src = [{"id": "vuurland", "name": "Vuurland",
        "tracks": [("Artist", "Baseline")]}]
assert collect(src, cache, set(), q) == 0
src[0]["tracks"] = [("Test Blocked", "Blocked Song"),
                    ("Artist", "Baseline")]
assert collect(src, cache, set(), q) == 0
assert q == []

# Oude snapshots van uitgeschakelde bronnen krijgen geen toegang tot de FIFO.
print("✅ v171: vier radiofeeds: nulmeting, enkel nieuwe plays, zonder dubbels")
