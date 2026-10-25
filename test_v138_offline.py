"""Zero-network checks; strictly no Spotify operations."""
import pathlib, tempfile, json
from bronrapport_v138 import assess, SOURCES

def run():
    assert len(SOURCES)==12 and 'dkfm_classic' in SOURCES
    with tempfile.TemporaryDirectory() as root:
        p=pathlib.Path(root)
        (p/'log').write_text('📻 Vuurland sync\n📻 DKFM Classic wordt gecontroleerd...\n DKFM Classic: 100 nummers gevonden.\n🔢 v120 gezamenlijke FIFO: volgnummer 2000 geselecteerd (bron: dkfm_classic)\n✅ Toegevoegd: Test - Song\n',encoding='utf-8')
        (p/'queue').write_text(json.dumps([{'source':'dkfm_classic','_v116_fifo_seq':2001}]))
        import os
        old=os.getcwd()
        try:
            os.chdir(root)
            rounds,seen,ok,added,counts=assess('log','queue')
            assert (rounds,seen['DKFM Classic'],ok['DKFM Classic'],added['dkfm_classic'],counts['dkfm_classic'])==(1,1,1,1,1)
        finally: os.chdir(old)
    s=pathlib.Path('vuurland_sync.py').read_text(encoding='utf-8')
    assert '"dkfm_classic"' in s and 'SPOTIFY_SEARCH_HTTP_LIMIT = 1' in s
    assert 'VOLUME_LIMIT = 10000' in s
    assert 'def get_active_volume_playlist(cache):' in s
    assert 'def v129_restore_volume_dedupe(cache, active_volume_number):' in s
    # Execute only two explicitly selected AST functions with offline fakes.
    import ast
    tree=ast.parse(s)
    funcs=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('get_active_volume_playlist','v129_restore_volume_dedupe')]
    assert len(funcs)==2
    unit=compile(ast.Module(body=funcs,type_ignores=[]),'offline-volumes','exec')
    created=[];saved=[]
    env={'VOLUME_LIMIT':10000,'VOLUME_NAME_PREFIX':'🔥 Vol ','PLAYLIST_ID':'volume_one',
         '_get_playlist_total':lambda pid:10000 if pid=='volume_one' else 0,
         '_find_named_playlist':lambda name:None,
         '_create_volume_playlist':lambda number:created.append(number) or 'volume_two',
         'save_cache':lambda cache:saved.append(dict(cache)),
         'spotify_request':lambda *a,**k: (_ for _ in ()).throw(AssertionError('Unexpected Spotify call'))}
    exec(unit,env)
    cache={'__vuurland_active_volume':1,'__vuurland_active_playlist_count':10000,'__vuurland_active_playlist_id':'volume_one'}
    result=env['get_active_volume_playlist'](cache)
    assert result==('volume_two',2,0) and created==[2]
    assert cache['__vuurland_volume_playlists']=={'1':'volume_one','2':'volume_two'}
    try:
        env['v129_restore_volume_dedupe']({'__vuurland_volume_playlists':{}},2)
    except RuntimeError as error:
        assert 'volume-ID ontbreekt' in str(error)
    else: raise AssertionError('Missing volume must fail closed')
    workflow=pathlib.Path('.github/workflows/vuurland.yml').read_text()
    assert 'exec > >(python3 -u live_music_stream.py --log vuurland_technische_live.log) 2>&1' in workflow
    assert 'python3 -u vuurland_sync.py 2>&1 | tee -a vuurland_matcher_sync.log | tee vuurland_ronde.log' in workflow
    assert 'SYNC_EXIT=${PIPESTATUS[0]}' in workflow
    assert 'git rebase origin/main' in workflow and 'git push origin HEAD:main' in workflow
    assert 'vuurland-v138-backup' in workflow
    assert "'dkfm_classic': 'DKFM Classic'" in pathlib.Path('live_music_stream.py').read_text()
    print('✅ v138 offline veiligheidstests geslaagd.')
if __name__=='__main__': run()
