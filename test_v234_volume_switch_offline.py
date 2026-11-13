"""v234: 10.000-grens zonder echte Spotify-writes of wijzigingen aan wachtrij.

Voer het echte get_active_volume_playlist-functieobject uit met uitsluitend
lokale Spotify-stubs. Valideer de overgang, restart en re-use van Vol 2.
"""
import ast
from pathlib import Path

src = Path(__file__).with_name("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(src)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
          and n.name == "get_active_volume_playlist")
code = compile(ast.Module(body=[fn], type_ignores=[]), "<volume-boundary>", "exec")

base_id = "test-volume-1"
vol2_id = "test-volume-2"
existing = {base_id: 9999}
created = []
saved = []

def get_playlist_total(pid):
    return existing[pid]

def find_named_playlist(name):
    return vol2_id if name == "🔥 Vol 2" and vol2_id in existing else None

def create_volume_playlist(n):
    assert n == 2, "Never create an unexpected volume"
    created.append(n)
    existing[vol2_id] = 0
    return vol2_id

scope = {
    "VOLUME_LIMIT": 10000,
    "VOLUME_NAME_PREFIX": "🔥 Vol ",
    "PLAYLIST_ID": base_id,
    "_get_playlist_total": get_playlist_total,
    "_find_named_playlist": find_named_playlist,
    "_create_volume_playlist": create_volume_playlist,
    "save_cache": lambda cache: saved.append(dict(cache)),
}
exec(code, scope)
choose = scope["get_active_volume_playlist"]
cache = {
    "__vuurland_volume_playlists": {"1": base_id},
    "__vuurland_active_volume": 1,
    "__vuurland_active_playlist_id": base_id,
    "__vuurland_active_playlist_count": 9999,
}
assert choose(cache) == (base_id, 1, 9999)
assert not created

# At exactly 10k, the next call creates volume 2, no extra writes in vol 1.
existing[base_id] = 10000
cache["__vuurland_active_playlist_count"] = 10000
assert choose(cache) == (vol2_id, 2, 0)
assert created == [2]
assert cache["__vuurland_volume_playlists"] == {"1": base_id, "2": vol2_id}
assert saved[-1]["__vuurland_active_volume"] == 2

# A new runner must reuse volume 2, never create an extra duplicate.
assert choose(dict(cache)) == (vol2_id, 2, 0)
assert created == [2]

# If Spotify already had Vol 2, find and reuse it.
old_cache = {"__vuurland_volume_playlists": {"1": base_id},
             "__vuurland_active_volume": 1,
             "__vuurland_active_playlist_id": base_id,
             "__vuurland_active_playlist_count": 10000}
existing[vol2_id] = 22
assert choose(old_cache) == (vol2_id, 2, 22)
assert created == [2]

# When the source count is stale but the final 10 places are reached, live
# add-flow must re-read the real Spotify total before add_tracks().
assert "VOLUME_EXACT_COUNT_GUARD = 10" in src
assert "if active_playlist_count >= VOLUME_LIMIT - VOLUME_EXACT_COUNT_GUARD:" in src
guard = src.index("if active_playlist_count >= VOLUME_LIMIT - VOLUME_EXACT_COUNT_GUARD:")
add = src.index("        add_tracks(\n", guard)
assert src.index("active_playlist_count = _get_playlist_total(playlist_id)", guard) < add
assert src.index("= get_active_volume_playlist(cache)", guard) < add
print("✅ v234: 9.999→10.000→Vol 2; restart, bestaande Vol 2 en exacte guard veilig.")
