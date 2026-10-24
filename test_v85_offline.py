"""Vuurland v85 safety regression: no Spotify/network calls."""
import ast
from pathlib import Path

source = Path(__file__).with_name('vuurland_sync.py').read_text(encoding='utf-8')
tree = ast.parse(source)
functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
assert 'sync' in functions and 'find_spotify_track' in functions
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in source
assert 'CHECK_EVERY_SECONDS = 60' in source
assert 'max_additions_per_round = 1' in source

# No automated call removing existing playlist entries (function declaration is fine).
removal_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'remove_tracks']
assert not removal_calls, 'Onveilige automatische playlist-verwijdering gevonden!'

matcher = ast.get_source_segment(source, functions['find_spotify_track'])
assert 'same_core_title' in matcher and 'primary_artist_score < 0.98' in matcher
assert 'if candidate_family in order:' in matcher
assert 'if candidate_family == "named version"' in matcher
assert 'wanted_named_variant and spotify_named_variant != wanted_named_variant' in matcher
assert 'if spotify_version != wanted_version:' in matcher
assert 'SPOTIFY_SEARCH_HTTP_USED' in source

# Version fallback order as defined in the matcher: validate ordering and availability.
order_node = None
for n in ast.walk(functions['find_spotify_track']):
    if isinstance(n, ast.Assign):
        if any(isinstance(t, ast.Name) and t.id == 'preferred_order' for t in n.targets):
            order_node = n.value
            break
assert order_node is not None
order = ast.literal_eval(order_node)['ordinary']
assert len(order) == len(set(order))
assert order.index('ordinary') < order.index('remaster') < order.index('acoustic') < order.index('live')
assert 'session' in order and 'mix' in order

def choose(candidates):
    """Test alleen de voorkeursvolgorde, niet de volledige Spotify-matchvalidatie."""
    return min(candidates, key=order.index)

assert choose(['live', 'ordinary']) == 'ordinary'
assert choose(['live', 'acoustic']) == 'acoustic'
assert choose(['live']) == 'live'
assert choose(['remaster', 'ordinary']) == 'ordinary'
assert choose(['acoustic', 'remaster']) == 'remaster'
print('✅ v85: studio/remaster/akoestisch/live voorkeursvolgorde gecontroleerd')
print('✅ v85: versiebeperkingen, één Search, één toevoeging/60s aanwezig')
print('✅ v85: geen rechtstreekse automatische remove_tracks-aanroepen')
print('ℹ️ Dit is een offline structuur- en prioriteitstest; geen live Spotify-eindtest.')
