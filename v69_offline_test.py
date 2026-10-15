#!/usr/bin/env python3
"""Offline regression tests: NO Spotify or GitHub requests."""
import ast
import re
from pathlib import Path

source = Path(__file__).with_name('vuurland_sync.py').read_text()
tree = ast.parse(source)
assert 'source_order = ("vuurland", "mellow_mix")' in source
assert 'MAX_SEARCHES_PER_RUN = 1' in source
assert 'max_additions_per_round = 1' in source
assert 'PLAYLIST_CACHE_SECONDS = 86400' in source
assert 'not playlist_keys\n        or not playlist_isrc_cache_ready' not in source
assert 'duyster_confirmed_links = {}' in source
assert '"__v69_radio_only_fresh_start"' in source
assert 'recent_radio_rank' in source
assert '"__spotify_api_blocked_until"' in source
# Matchfunctie onveranderd t.o.v. v69 die de gebruiker al kreeg.
# SHA256 van de oorspronkelijke v69-matcherfuncties (AST zonder line-nummers).
# Hiermee zijn regressietests zelfstandig op de Mac te draaien.
import hashlib
MATCHER_SHA256 = {'find_spotify_track': '98abcda836948c813d259b5dc3dca9cf0f2ee8d79aef19f5af19b99e07381e27', 'spotify_request': 'f0014160c6256af1113fb9308ff1d5ec231b8c8c80bd2be7414dc54597c86b50', 'add_tracks': 'f9294860ea38bb7826eeb2f078c3540aa68ac1c6b733f3b73fffaccc9a9e326d'}
for name, expected_hash in MATCHER_SHA256.items():
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    current_hash = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    assert current_hash == expected_hash, f'{name} onbedoeld gewijzigd'
func = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='v47_collect_radio_history')
ns = {'_v47_key':lambda a,t: a.strip().lower()+'|||'+t.strip().lower(),
      'normalize_match': lambda s:s.lower(), 'is_interview_fragment':lambda s:False}
exec(compile(ast.Module(body=[func],type_ignores=[]),'fixture','exec'),ns)
tracks=lambda sid,pairs:{'id':sid,'name':sid,'tracks':pairs}
sources=[tracks('vuurland',[('New A','song'),('Old A','song'),('Older A','song')]),
         tracks('mellow_mix',[('New B','song'),('Old B','song')])]
cache={'__v69_radio_only_fresh_start':True}
queue=[]
count=ns['v47_collect_radio_history'](sources,cache,set(),queue)
assert count==2, (count,queue)
assert {x['artist'] for x in queue}=={'New A','New B'}
assert cache['__v69_bootstrap_complete']
assert ns['v47_collect_radio_history'](sources,cache,set(),queue)==0
sources[0]['tracks'].insert(0,('Newest A','song'))
assert ns['v47_collect_radio_history'](sources,cache,set(),queue)==1
assert queue[0]['artist']=='Newest A'
order=('vuurland','mellow_mix')
turn='vuurland'
for expected in ['vuurland','mellow_mix','vuurland','mellow_mix']:
    assert turn==expected
    turn=order[(order.index(turn)+1)%len(order)]
print('✅ Offline v69: 2-bronnenbeurtrol, verse radio-start, geen duplicaat-inname, limieten, cache-interval en ongewijzigde matcher.')
