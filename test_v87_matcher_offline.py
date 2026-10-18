"""All 18 BE audit cases: no actual Spotify requests or writes."""
import importlib.util, json, os, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CASES=json.loads((ROOT/'v87_be_resultaten.json').read_text())
assert len(CASES)==18 and {r['number'] for r in CASES}==set(range(1,19))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['SPOTIFY_CLIENT_ID']='offline-only-fake'
    os.environ['VUURLAND_DATA_DIR']=tmp
    spec=importlib.util.spec_from_file_location('vuurland_v87_safe',ROOT/'vuurland_sync.py')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lookup={r['number']:r for r in CASES}
    # Cataloguslocators are candidate sources, NEVER a free bypass into playlist.
    expected={5:'1REPTIRIQ4zI15g6rD2bpX',11:'3lpkLZfD2RJltSaAGgmoxb',13:'3EYj5rxRbNM3nijF9dOtry',14:'5UN8ZYczY8p56eRWhZAKVm',18:'0ktm6PQBeehUHJORIH76UX'}
    for n,r in lookup.items():
        identifier=mod.v81_catalog_locator(r['requested_artist'],r['requested_title'])
        if n in expected:
            assert identifier==expected[n],(n,identifier)
        else:
            assert identifier is None,(n,identifier)
    calls=[]
    def fake_request(method,path,**kwargs):
        calls.append((method,path))
        assert method=='GET'
        if path.startswith('/tracks/'):
            track_id=path.split('/')[-1]
            for r in CASES:
                for c in r['candidates']:
                    if c['id']==track_id:
                        return {'id':c['id'],'name':c['name'],'uri':c['uri'],
                                'is_playable':c['is_playable'],'external_ids':{'isrc':c.get('isrc')},
                                'artists':[{'name':a} for a in c['artists']],
                                'album':{'name':'offline-audit'}}
            raise AssertionError('Unknown catalog ID')
        raise AssertionError('Unexpected real Search during confirmed locator tests')
    mod.spotify_request=fake_request
    for n in (11,13,18):
        r=lookup[n]
        uri=mod.find_spotify_track(r['requested_artist'],r['requested_title'])
        assert uri=='spotify:track:'+expected[n],(n,uri)
    assert len(calls)==3
    # Negative guard: absent/unconfirmed cases cannot be added via v87 overrides.
    assert mod.v81_catalog_locator('Pinback','Loro') is None
    assert mod.v81_catalog_locator('Nick Drake','Hazey Jane') is None
    assert mod.v81_catalog_locator('The Christian Club feat. Lucy Ryan','Atlas') is None
print('✅ v87: 18 gevallen gedekt; 3 bevestigde tracks via volledige matcher; overige 15 niet geforceerd')
