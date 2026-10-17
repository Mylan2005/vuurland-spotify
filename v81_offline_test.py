"""v81 offline checks: controlled catalog ID and persisted radio retry."""
import os, tempfile, importlib.util
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    os.environ['VUURLAND_DATA_DIR']=tmp
    os.environ['SPOTIFY_CLIENT_ID']='offline'
    spec=importlib.util.spec_from_file_location('vuurland_v81',Path(__file__).with_name('vuurland_sync.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    real_id='4I1hdRXL4tCnbtJfuqv58A'
    assert m.v81_catalog_locator('Gipsy Kings','Recuerdo Apasionado')==real_id
    assert m.v81_catalog_locator('Gipsy Kings','Recuerdo Other') is None
    def record(artist='Gipsy Kings',title='Recuerdo apasionado',playable=True):
        return {'id':real_id,'uri':'spotify:track:'+real_id,'name':title,
                'artists':[{'name':artist,'id':'theartist'}],
                'album':{'name':'Compas','album_type':'album'},
                'duration_ms':243000,'is_playable':playable,'external_ids':{'isrc':'FAKEISRC'}}
    calls=[]
    def respond(method,endpoint,**kw):
        calls.append((method,endpoint,kw))
        return record()
    m.spotify_request=respond
    assert m.find_spotify_track('Gipsy Kings','Recuerdo Apasionado',2)=='spotify:track:'+real_id
    assert len(calls)==1 and calls[0][1]=='/tracks/'+real_id
    assert calls[0][2]['params']['market']=='from_token'
    for kw in ({'artist':'Wrong Artist'}, {'title':'Different Song'}, {'playable':False}):
        calls.clear()
        m.spotify_request=lambda *args,**kwargs: record(**kw)
        assert m.find_spotify_track('Gipsy Kings','Recuerdo Apasionado',2) is None, kw
        assert len(calls)==0  # mock wrapper doesn't count real network
    q=[{'artist':'Other Artist','title':'Other Song','source':'vuurland'}]
    cache={'__v51_radio_unmatched':{m._v47_key('Gipsy Kings','Recuerdo Apasionado'):
                                    {'artist':'Gipsy Kings','title':'Recuerdo Apasionado','source':'mellow_mix'}},
           '__not_found_v35__'+m._v47_key('Gipsy Kings','Recuerdo Apasionado'):100}
    sources=[{'id':'vuurland','tracks':[]},{'id':'mellow_mix','tracks':[]}]
    assert m.v81_requeue_confirmed_catalog(cache,q,sources)==1
    assert q[0]['artist']=='gipsy kings' and q[0]['source']=='mellow_mix'
    assert q[1]['title']=='Other Song'
    assert m.v81_requeue_confirmed_catalog(cache,q,sources)==0
    assert len(q)==2
    assert not any(k.startswith('__not_found_v35__') for k in cache)
    assert m.v81_requeue_confirmed_catalog({},[],sources)==0
    print('✅ v81: catalogusvalidatie, foutieve matches geweigerd, bronveilig herstel, geen duplicaten')
