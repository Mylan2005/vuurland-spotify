"""Regression: a repeated radio play must not hide fresher arrivals."""
import ast
from pathlib import Path

source = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "v96_collect_live_plays")
ns = {
    "RADIO_SOURCE_ORDER": ("vuurland", "mellow_mix", "radio_britannia", "big_sonic_heaven"),
    "_v47_key": lambda a, t: a.lower() + "|||" + t.lower(),
    "normalize_match": str.lower,
    "v110_correct_radio_artist": lambda a, sid: a,
    "is_confirmed_german_vocal": lambda a, t: False,
    "is_interview_fragment": lambda t: False,
    "radio_matches_playlist": lambda a, t, keys: (a.lower() + "|||" + t.lower()) in keys,
    "time": __import__("time"),
}
exec(compile(ast.Module(body=[node], type_ignores=[]), "<v96>", "exec"), ns)
collect = ns["v96_collect_live_plays"]
for sid in ns["RADIO_SOURCE_ORDER"]:
    cache = {"__playlist_keys": []}
    queue = []
    src = [{"id": sid, "name": sid, "tracks": [
        ("Artist", "A"), ("Artist", "B"), ("Artist", "C"), ("Artist", "D")]}]
    assert collect(src, cache, set(), queue) == 0
    # A repeats: the old first-match algorithm incorrectly stopped at index 0.
    src[0]["tracks"] = [
        ("Artist", "A"), ("Artist", "Fresh 2"), ("Artist", "Fresh 1"),
        ("Artist", "B"), ("Artist", "C"), ("Artist", "D")]
    assert collect(src, cache, set(), queue) == 2
    assert [x["title"] for x in queue] == ["Fresh 1", "Fresh 2"]
    assert collect(src, cache, set(), queue) == 0
print("✅ v182: radioherhalingen maskeren geen verse uitzendingen")
