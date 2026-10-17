"""Offline regressies v77: Spotify wordt volledig gemockt; geen echte API-aanvragen."""
import os, tempfile, importlib.util
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
    os.environ['SPOTIFY_CLIENT_ID']='offline-test'
    os.environ['VUURLAND_DATA_DIR']=d
    spec=importlib.util.spec_from_file_location('vuurland_v77',Path(__file__).with_name('vuurland_sync.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    cases=[
      ('BON IVER','Speyside','Bon Iver','S P E Y S I D E'),
      ('Don Williams',"'Till The Rivers Run Dry",'Don Williams',"'Till The Rivers All Run Dry"),
      ('Prince','affirmations Way Back Home','Prince','WAY BACK HOME'),
      ('The Gabby Pahinui Hawaiian Band','Wahine uʻi','Gabby Pahinui',"Wahine U'i"),
      ('NOVASTAR & PIET GODDAER','Never back down','Novastar','Never Back Down'),
    ]
    def candidate(artist,title,playable=True):
        return {'uri':'spotify:track:OFFLINETEST','id':'OFFLINETEST','name':title,'artists':[{'name':artist,'id':'offline'}], 'album':{'name':'Test Album','album_type':'album'},'is_playable':playable,'duration_ms':200000,'external_ids':{'isrc':'OFFLINETEST'}}
    for source_artist,source_title,spotify_artist,spotify_title in cases:
        calls=[]
        def fake(method,endpoint,**kwargs):
            assert endpoint=='/search'
            calls.append(kwargs['params']['q'])
            return {'tracks':{'items':[candidate(spotify_artist,spotify_title)]}}
        m.spotify_request=fake
        try: result=m.find_spotify_track(source_artist,source_title)
        except Exception as e: raise AssertionError((source_artist,source_title,str(e))) from e
        assert result=='spotify:track:OFFLINETEST', (source_artist,source_title,result,calls)
        assert len(calls)==1
        print('✅',source_artist,'—',source_title)
    for a,t in [('Prince','Different Song'),('Don Williams','Wrong Song'),('NOVASTAR & PIET GODDAER','Wrong Song')]:
        m.spotify_request=lambda *args,**kwargs:{'tracks':{'items':[candidate('Another Artist','Something Else')]}}
        assert m.find_spotify_track(a,t) is None
    m.spotify_request=lambda *args,**kwargs:{'tracks':{'items':[candidate('Novastar','Never Back Down',False)]}}
    assert m.find_spotify_track('NOVASTAR & PIET GODDAER','Never back down') is None
    assert m.v71_same_song_title('affirmations Way Back Home','Way Back Home','Prince')
    assert not m.v71_same_song_title('affirmations Way Back Home','Way Back Home','Other Artist')
    print('✅ Negatieve matches, regioblokkade, duplicate-correcties')
