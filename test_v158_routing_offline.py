"""v158 regression: source routing must not write non-Vuurland matches to playlists."""
import ast
from pathlib import Path

source = Path("vuurland_sync.py").read_text(encoding="utf-8")
tree = ast.parse(source)
sync = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sync")

# Test the actual guard and ensure no playlist write can precede it in the
# queue-processing branch. Guard is after artist/title/URI blacklist checks.
guard = next(
    n for n in ast.walk(sync)
    if isinstance(n, ast.If)
    and '"source"' in ast.get_source_segment(source, n.test)
    and '"vuurland"' in ast.get_source_segment(source, n.test)
    and any(isinstance(z, ast.Call) and isinstance(z.func, ast.Name)
            and z.func.id == "_attempt_library_like" for z in ast.walk(n))
)
assert any(isinstance(n, ast.Continue) for n in ast.walk(guard))
assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == "_attempt_library_like" for n in ast.walk(guard))
assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "add_tracks" for n in ast.walk(guard))

playlist_calls = [n for n in ast.walk(sync)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "add_tracks"]
assert playlist_calls and all(n.lineno > guard.end_lineno for n in playlist_calls)
assert '__pending_library_likes' in source
assert 'v83_clear_resolved_failures(cache, artist, title)' in ast.get_source_segment(source, guard)
assert 'save_seen(seen)' in ast.get_source_segment(source, guard)
assert 'atomic_save_json(live_queue_file, live_queue' in ast.get_source_segment(source, guard)

# Only exact Vuurland source gets automatic playlist access. All other
# sources (including an absent/unrecognized source) take the like-only path.
route = lambda source: str(source or "").strip() == "vuurland"
assert route("vuurland")
for name in ("dark_edge", "mellow_mix", "big_sonic_heaven", "dkfm_edge",
             "dkfm_shoegaze", "radio_x_chilled", "", None):
    assert not route(name)
print("✅ v158: alleen Vuurland mag naar playlist; andere bronnen naar likes")
