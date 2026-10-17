"""v82 regressie en veiligheid — geen echte HTTP-calls."""
import os, tempfile, importlib.util
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
    os.environ['SPOTIFY_CLIENT_ID']='offline'
    os.environ['VUURLAND_DATA_DIR']=tmp
    spec=importlib.util.spec_from_file_location('vuurland82',Path(__file__).with_name('vuurland_sync.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    uri='spotify:track:1234567890123456789012'
    cache={}
    assert not m.v82_remember_catalog(cache,'Bon Iver','Speyside','bad',('Bon Iver','S P E Y S I D E'))
    assert m.v82_remember_catalog(cache,'Bon Iver','Speyside',uri,('Bon Iver','S P E Y S I D E'))
    assert m.v82_confirmed_locator(cache,'Bon Iver','Speyside')=='1234567890123456789012'
    assert m.v82_confirmed_locator(cache,'Wrong Artist','Speyside') is None
    assert m.v82_confirmed_locator(cache,'Bon Iver','Different Song') is None
    assert m.v82_match_diagnosis([],'A','B')=='geen_resultaten'
    def track(a,t,p=True):
        return {'uri':uri,'name':t,'id':uri.rsplit(':',1)[-1],
                'artists':[{'name':a,'id':'artist'}],
                'album':{'name':'Album','album_type':'album'},
                'is_playable':p,'duration_ms':220000,
                'external_ids':{'isrc':'TEST'}}
    assert m.v82_match_diagnosis([track('Wrong','Speyside')],'Bon Iver','Speyside')=='artiestcredits_of_rangschikking'
    assert m.v82_match_diagnosis([track('Bon Iver','Wrong')],'Bon Iver','Speyside')=='titel_of_versie_verschilt'
    assert m.v82_match_diagnosis([track('Bon Iver','Speyside',False)],'Bon Iver','Speyside')=='niet_afspeelbaar'
    cache=m.load_cache();m.v82_remember_catalog(cache,'Bon Iver','Speyside',uri,('Bon Iver','S P E Y S I D E'));m.save_cache(cache)
    calls=[]
    def fake(method,endpoint,**kw):
        calls.append(endpoint)
        assert endpoint == '/tracks/1234567890123456789012'
        return track('Bon Iver','S P E Y S I D E')
    m.spotify_request=fake
    assert m.find_spotify_track('Bon Iver','Speyside')==uri
    assert calls==['/tracks/1234567890123456789012']
    m.spotify_request=lambda *a,**kw: track('Wrong Artist','S P E Y S I D E')
    assert m.find_spotify_track('Bon Iver','Speyside') is None
    m.spotify_request=lambda *a,**kw: track('Bon Iver','Another Song')
    assert m.find_spotify_track('Bon Iver','Speyside') is None
    m.spotify_request=lambda *a,**kw: track('Bon Iver','S P E Y S I D E',False)
    assert m.find_spotify_track('Bon Iver','Speyside') is None
    print('✅ v82: catalogusgeheugen, exacte bronidentiteit, afwijsdiagnose, 1 GET, negatieve matches')
