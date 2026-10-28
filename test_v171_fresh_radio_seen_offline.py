"""v171: live-nulmeting en oude seen-status blokkeren nieuwe uitzendingen niet."""
import ast
from pathlib import Path

source = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "v96_collect_live_plays")
assert 'elif key in seen and sid not in RADIO_SOURCE_ORDER:' in ast.get_source_segment(source, node)

def key(a, t):
    return a.lower() + "|||" + t.lower()

ns = {
    "RADIO_SOURCE_ORDER": ("vuurland", "mellow_mix", "big_sonic_heaven", "radio_britannia"),
    "_v47_key": key,
    "normalize_match": str.lower,
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

# Oude snapshots van uitgeschakelde bronnen krijgen geen toegang tot de FIFO.
print("✅ v171: vier radiofeeds: nulmeting, enkel nieuwe plays, zonder dubbels")
