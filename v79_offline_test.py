"""v79: One real search per round; free-form spaced letters; strict validation."""
import os, tempfile, importlib.util
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
 os.environ['SPOTIFY_CLIENT_ID']='offline-test'
 os.environ['VUURLAND_DATA_DIR']=d
 spec=importlib.util.spec_from_file_location('v79',Path(__file__).with_name('vuurland_sync.py'))
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 def candidate(artist, title, playable=True):
  return {'uri':'spotify:track:OFFLINE','id':'OFFLINE','name':title,
   'artists':[{'name':artist,'id':'test'}], 'album':{'name':'Test','album_type':'album'},
   'is_playable':playable,'duration_ms':200000,'external_ids':{'isrc':'TEST'}}
 def run(artist,title,variant,results):
  queries=[]
  def fake(method,endpoint,**kwargs):
   assert endpoint=='/search'
   queries.append(kwargs['params']['q'])
   return {'tracks':{'items':results}}
  m.spotify_request=fake
  found=m.find_spotify_track(artist,title,search_variant=variant)
  assert len(queries)==1,queries
  return found,queries[0]
 for variant in (0,1):
  result,q=run('BON IVER','Speyside',variant,[candidate('Bon Iver','S P E Y S I D E')])
  assert result=='spotify:track:OFFLINE',(variant,result,q)
  if variant == 0:
   assert 'S P E Y S I D E' in q and 'track:' not in q,(variant,q)
  else:
   # Latere zoekpoging behoudt gewone titelwoorden.
   assert 'Speyside' in q and 'S P E Y S I D E' not in q,(variant,q)
  print('✅ Bon Iver variant',variant, q)
 result,q=run('Another Artist','Sunshine',1,[candidate('Another Artist','S U N S H I N E')])
 assert result=='spotify:track:OFFLINE' and 'Sunshine' in q,(result,q)
 assert 'S U N S H I N E' not in q,(result,q)
 print('✅ Algemene schrijfwijze',q)
 result,q=run('BON IVER','Speyside',1,[candidate('Wrong Artist','S P E Y S I D E')])
 assert result is None
 result,q=run('BON IVER','Speyside',1,[candidate('Bon Iver','Different Song')])
 assert result is None
 result,q=run('BON IVER','Speyside',1,[candidate('Bon Iver','S P E Y S I D E',False)])
 assert result is None
 print('✅ Onjuiste artiest/titel en niet-afspeelbaar geweigerd')
