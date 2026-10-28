"""Regression for safely replaying observed Vuurland history after rebuild."""
import ast
from pathlib import Path
src = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
f = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
         and x.name == "v160_restore_vuurland_history")
calls = []
writes = []
def key(a,t): return a.lower()+"|||"+t.lower()
def stamp(q,c):
    for i,x in enumerate(q): x.setdefault("_v116_fifo_seq", i+1)
def save(path,q,**kwargs): writes.append((path,len(q)))
ns = {
    "_v47_key": key, "v116_stamp_fifo": stamp,
    "atomic_save_json": save, "save_cache": lambda cache: None,
    "radio_matches_playlist": lambda a,t,k: key(a,t) in k,
    "is_confirmed_german_vocal": lambda a,t: False,
    "v101_radio_key": lambda a,t: (a.lower(), t.lower()),
    "V101_EXCLUDED_RADIO_TRACKS": {("blocked","song")},
}
exec(compile(ast.Module(body=[f],type_ignores=[]),"<v160>","exec"),ns)
restore=ns["v160_restore_vuurland_history"]
cache={"__v47_radio_discovered":{"vuurland":[
    "artist|||missing", "artist|||already", "blocked|||song"],
    "dark_edge":["dance|||track"]},
    "__v95_archived_pre_live_queue":[{"source":"vuurland","artist":"Old","title":"Gold"}]}
queue=[{"source":"dark_edge","artist":"Dance","title":"Track"}]
assert restore(cache,queue,{"artist|||already"})==2
assert len(queue)==3
assert [q["source"] for q in queue]==["dark_edge","vuurland","vuurland"]
assert all(q["title"]!="already" for q in queue)
assert all(q["artist"]!="dance" for q in queue[1:])
assert restore(cache,queue,{"artist|||already"})==0
assert len(queue)==3 and writes
assert 'if cache.get("__v159_rebuild_scanned") == V159_REBUILD_TOKEN' in src
assert 'if str(item.get("source") or "").strip() != "vuurland":' in src
print("✅ v160: historische Vuurland-items veilig terug in FIFO, geen duplicaten")
