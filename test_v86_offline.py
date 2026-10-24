"""Pure offline v86 regression guards: no Spotify, state or network writes."""
import ast
import tempfile
from pathlib import Path
from vuurland_v86_rapport import failed_list, make_report

root = Path(__file__).resolve().parent
source = (root / 'vuurland_sync.py').read_text(encoding='utf-8')
tree = ast.parse(source)
funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
assert 'find_spotify_track' in funcs and 'sync' in funcs
matcher = ast.get_source_segment(source, funcs['find_spotify_track'])
assert 'if wanted_named_variant and spotify_named_variant != wanted_named_variant:' in matcher
assert 'if version_tier and (not same_core_title or primary_artist_score < 0.98):' in matcher
assert 'if not primary_artist_exact or spotify_base_compact != wanted_base_compact:' in matcher
assert 'if wanted_family != "ordinary":' in matcher
order = next(ast.literal_eval(n.value)['ordinary'] for n in ast.walk(funcs['find_spotify_track'])
             if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'preferred_order' for t in n.targets))
assert order.index('ordinary') < order.index('remaster') < order.index('acoustic') < order.index('live')
for available, wanted in [(['live', 'ordinary'], 'ordinary'), (['live'], 'live'),
                          (['acoustic', 'live'], 'acoustic'), (['remaster', 'live'], 'remaster')]:
    assert min(available, key=order.index) == wanted
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in source
assert 'max_additions_per_round = 1' in source
assert 'CHECK_EVERY_SECONDS = 60' in source
assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'remove_tracks'
               for n in ast.walk(tree))
assert failed_list({'__v51_radio_failed_searches': {'pinback|||loro':3, 'x':0}}) == [(3, 'pinback|||loro')]
with tempfile.TemporaryDirectory() as tmp:
    report = make_report(Path(tmp))
    assert 'ontbreekt' in report and 'Geen Spotify-aanvragen' in report
print('✅ v86: strenge titel-/artiest-/versiegrenzen en terugvalvolgorde aanwezig')
print('✅ v86: één Search, één toevoeging/60s; geen automatische remove_tracks')
print('✅ v86: gezondheidsrapport leest ontbrekende state veilig')
print('ℹ️ Offline guards, geen end-to-end Spotify-test')
