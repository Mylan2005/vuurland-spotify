import ast
import copy
from pathlib import Path

source = Path(__file__).with_name('vuurland_sync.py').read_text()
tree = ast.parse(source)
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
assert 'v83_clear_resolved_failures' in functions
assert 'sync' in functions
module = ast.Module(body=[functions['v83_clear_resolved_failures']], type_ignores=[])
namespace = {'_v47_key': lambda a,t: f"{a.strip().lower()}|||{t.strip().lower()}"}
exec(compile(module, '<isolated-v83>', 'exec'), namespace)
clear = namespace['v83_clear_resolved_failures']
key='pinback|||loro'
cache={
    '__v47_failed_tracks': {key:{'artist':'Pinback'},'other|||song':{'artist':'Other'}},
    '__v51_radio_unmatched': {key:1},
    '__v51_radio_failed_searches': {key:3},
    '__v51_radio_failed_cycles': {key:1},
    '__not_found_v35__'+key:1234,
    '__match_v35__'+key:'spotify:track:valid',
    '__playlist_keys':[key],
    'unrelated':'preserved',
}
assert clear(cache, 'Pinback', 'Loro') == 5
assert clear(cache, 'Pinback', 'Loro') == 0
assert cache['__v47_failed_tracks']=={'other|||song':{'artist':'Other'}}
assert cache['__match_v35__'+key]=='spotify:track:valid'
assert cache['__playlist_keys']==[key] and cache['unrelated']=='preserved'
assert clear({}, 'ISE', 'Ik reis door de nacht (live)') == 0
# Veiligheidsgrenzen in de volledige bron
assert 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in source
assert 'CHECK_EVERY_SECONDS = 60' in source
assert 'max_additions_per_round = 1' in source
assert source.count('v83_clear_resolved_failures(cache, artist, title)') == 6
print('✅ v83: oude foutstatus selectief opgeschoond; overige state intact')
print('✅ v83: bestaande limieten en liveversies ongemoeid')
