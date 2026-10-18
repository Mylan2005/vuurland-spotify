"""Offline regressie voor alle 15 resterende v87-gevallen; geen Spotify-writes."""
import ast, importlib.util, os, tempfile, json
from pathlib import Path
root=Path(__file__).resolve().parent
cases=[
 ('B-Tribe','Overture (Concierto de Aranjuez)'),
 ('Clear Season',"Don't Take Too Long"),
 ('Cowboy Junkies','Black Eyed Man'),
 ('Eric Burdon & War','Summer'),
 ('Ludwig van Beethoven','Für Elise'),
 ('Pinback','Loro'),
 ('Rickie Lee Jones','Little Mysteries'),
 ('Sarah Harmer','Lodestar'),
 ('Colin Hay','Hold On To My Hand'),
 ('Largo','Hand in Mine'),
 ('Nick Drake','Hazey Jane'),
 ('Nick Lowe','When I Write The Book'),
 ('Pieta Brown','Lullaby'),
 ('Raymond Kāne','Popoki Slack Key'),
 ('The Christian Club feat. Lucy Ryan','Atlas'),
]
assert len(cases)==15
with tempfile.TemporaryDirectory() as temp:
 os.environ['SPOTIFY_CLIENT_ID']='fake-offline-only'
 os.environ['VUURLAND_DATA_DIR']=temp
 spec=importlib.util.spec_from_file_location('v87batch',root/'vuurland_sync.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 expected={('Ludwig van Beethoven','Für Elise'):'1REPTIRIQ4zI15g6rD2bpX',
           ('Nick Lowe','When I Write The Book'):'5UN8ZYczY8p56eRWhZAKVm'}
 for entry in cases:
  assert mod.v81_catalog_locator(*entry)==expected.get(entry),entry
  print('✅',entry[0],'—',entry[1],':', 'cataloguslookup met volledige validatie' if entry in expected else 'geen onveilige geforceerde koppeling')
 def candidate(artist,title,identifier,playable=True):
  return {'id':identifier,'uri':'spotify:track:'+identifier,'name':title,
          'artists':[{'name':artist}],'is_playable':playable,
          'album':{'name':'offline-test'},'external_ids':{'isrc':None}}
 for (artist,title),identifier in expected.items():
  def run_as(found):
   calls=[]
   def fake(method,endpoint,**kwargs):
    assert method=='GET' and endpoint=='/tracks/'+identifier and kwargs.get('params')=={'market':'from_token'}
    calls.append(endpoint)
    return found
   mod.spotify_request=fake
   result=mod.find_spotify_track(artist,title)
   assert len(calls)==1
   return result
  # normal title may contain a verified catalogue suffix; exact artist/title here
  assert run_as(candidate(artist,title,identifier))=='spotify:track:'+identifier,(artist,title)
  assert run_as(candidate(artist,title,identifier,False)) is None,(artist,title,'regio')
  assert run_as(candidate('Another Artist',title,identifier)) is None,(artist,title,'artiest')
  assert run_as(candidate(artist,'Different Song',identifier)) is None,(artist,title,'titel')
 # Exacte gebruikersbevestiging: War — Summer, uitsluitend voor deze track.
 # War-track mag matchen na gecontroleerde creditcorrectie.
 def war_fake(method,endpoint,**kwargs):
  assert method=='GET' and endpoint=='/search'
  return {'tracks':{'items':[candidate('War','Summer','2YKZcl6qklZ8RS0FfEgjCe')]}}
 mod.spotify_request=war_fake
 assert mod.find_spotify_track('Eric Burdon & War','Summer')=='spotify:track:2YKZcl6qklZ8RS0FfEgjCe'
 # Bij een ander lied van deze radiocredit NOOIT War als artiest accepteren.
 def wrong_credit_fake(method,endpoint,**kwargs):
  assert method=='GET' and endpoint=='/search'
  return {'tracks':{'items':[candidate('War','Different Track','2YKZcl6qklZ8RS0FfEgjCe')]}}
 mod.spotify_request=wrong_credit_fake
 assert mod.find_spotify_track('Eric Burdon & War','Different Track') is None
print('✅ Alle 15 aanwezig: 2 locators, Summer-credit, regiobeperking en foutieve matches getest; 0 writes.')
