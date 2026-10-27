"""Offline regression tests for v80; no real Spotify, playlist or network calls."""
import os, tempfile, importlib.util
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
    os.environ['SPOTIFY_CLIENT_ID']='offline'
    os.environ['VUURLAND_DATA_DIR']=d
    spec=importlib.util.spec_from_file_location('vuurland80',Path(__file__).with_name('vuurland_sync.py'))
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.v80_unicode_search_text('Wahine uʻi') == "Wahine u'i"
    assert m.v80_unicode_search_text('Cœur æther Straße ﬁre') == 'Coeur aether Strasse fire'
    assert m.v80_search_route('Some Artist','Sunshine',1)['title']=='Sunshine'
    assert m.v80_search_route('Some Artist','Sunshine',0)['title']=='Sunshine'
    cache={}
    assert not m.v80_record_confirmed(cache,'A','B','A','B','bad-uri')
    assert m.v80_record_confirmed(cache,'Bon Iver','Speyside','Bon Iver','S P E Y S I D E','spotify:track:TEST')
    assert m.v80_search_route('Bon Iver','Speyside',0,cache['__v80_confirmed_spellings'][m._v47_key('Bon Iver','Speyside')])['title']=='S P E Y S I D E'
    assert m.v80_failure_reason([], 'A','B')=='no_results'
    assert m.v80_failure_reason([{'artists':[{'name':'Wrong Artist'}], 'is_playable':True}], 'Bon Iver','Speyside')=='artist_credit_or_search_ranking'
    assert m.v80_failure_reason([{'artists':[{'name':'Bon Iver'}], 'is_playable':False}], 'Bon Iver','Speyside')=='includes_unplayable_candidates'
    def candidate(artist,title,playable=True):
        return {'uri':'spotify:track:OFFLINE','name':title,'id':'OFFLINE','artists':[{'name':artist,'id':'a'}],
                'album':{'name':'Test','album_type':'album'},'is_playable':playable,
                'duration_ms':200000,'external_ids':{'isrc':'OFFLINE'}}
    calls=[]
    def fake(method,endpoint,**kwargs):
        assert endpoint == '/search'
        calls.append(kwargs['params']['q'])
        return {'tracks':{'items':[candidate('Bon Iver','S P E Y S I D E')]}}
    m.spotify_request=fake
    assert m.find_spotify_track('Bon Iver','Speyside',0)=='spotify:track:OFFLINE'
    assert len(calls)==1
    # Cached spelling survives without granting a match to a wrong artist.
    m.save_cache(cache); calls.clear()
    assert m.find_spotify_track('Bon Iver','Speyside',0)=='spotify:track:OFFLINE'
    assert len(calls)==1 and 'S P E Y S I D E' in calls[0]
    m.spotify_request=lambda *args,**kwargs: {'tracks':{'items':[candidate('Wrong Artist','S P E Y S I D E')]}}
    assert m.find_spotify_track('Bon Iver','Speyside',0) is None
    m.spotify_request=lambda *args,**kwargs: {'tracks':{'items':[candidate('Bon Iver','Different Song')]}}
    assert m.find_spotify_track('Bon Iver','Speyside',0) is None
    m.spotify_request=lambda *args,**kwargs: {'tracks':{'items':[candidate('Bon Iver','S P E Y S I D E',False)]}}
    assert m.find_spotify_track('Bon Iver','Speyside',0) is None
    print('✅ v80: zoekroute, geleerde schrijfwijzen, unicode, diagnose, één Search en veiligheidscontroles')
