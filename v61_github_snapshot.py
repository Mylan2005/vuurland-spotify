#!/usr/bin/env python3
"""Read-only Spotify snapshot for Actions. Never writes playlist, likes, or sync state."""
import json, os, pathlib, time, datetime, hashlib, sys
import requests
ROOT=pathlib.Path.cwd()
OUT=ROOT/'v61_snapshot'
BASE='https://api.spotify.com/v1'

def api_get(session, path, token, params=None):
    response=session.get(BASE+path, headers={'Authorization':'Bearer '+token},params=params,timeout=35)
    if response.status_code == 429:
        print('STOP: Spotify 429; Retry-After:',response.headers.get('Retry-After','onbekend'),'. Geen automatische retry.')
        raise RuntimeError('Spotify 429. Scan onvolledig; geen snapshot publiceren')
    response.raise_for_status()
    return response.json()

def collect(session,path,token,limit):
    results=[]; offset=0; total=None
    while True:
        p=api_get(session,path,token,{'limit':limit,'offset':offset})
        rows=p.get('items'); t=p.get('total')
        if not isinstance(rows,list) or not isinstance(t,int):raise RuntimeError('Ongeldige Spotify pagina')
        if total is None:total=t
        if t!=total:raise RuntimeError('Playlist veranderde tijdens scan; herstart later')
        for row in rows:
            tr=row.get('item') or row.get('track') or {}
            if not isinstance(tr,dict) or not str(tr.get('uri','')).startswith('spotify:track:'):
                raise RuntimeError('Onbekende Spotify item-structuur; geen snapshot')
            results.append({'uri':tr['uri'],'name':tr.get('name',''),
                            'artists':[a.get('name','') for a in tr.get('artists',[])],
                            'added_at':row.get('added_at'),
                            'isrc':(tr.get('external_ids') or {}).get('isrc')})
        offset+=len(rows)
        if not p.get('next'):
            if offset!=total:raise RuntimeError('Incompleet: '+str(offset)+' != '+str(total))
            break
        if not rows or offset>100000:raise RuntimeError('Pagination vastgelopen')
        time.sleep(0.3)
    return results

def main():
    cid=os.environ['SPOTIFY_CLIENT_ID']; refresh=os.environ['SPOTIFY_REFRESH_TOKEN']
    response=requests.post('https://accounts.spotify.com/api/token',data={'grant_type':'refresh_token','refresh_token':refresh,'client_id':cid},timeout=30)
    response.raise_for_status();token=response.json()['access_token']
    cachepath=ROOT/'.vuurland_spotify_cache.json'
    cache=json.loads(cachepath.read_text()) if cachepath.exists() else {}
    vols={'1':'555lFTvdRswe9ukybmOM8T'}
    for k,v in (cache.get('__vuurland_volume_playlists') or {}).items():
        if str(k).isdigit() and v:vols[str(k)]=str(v)
    if len(set(vols.values()))!=len(vols):raise RuntimeError('Conflicterende volume ID')
    session=requests.Session()
    playlists={}
    for key,pid in sorted(vols.items(),key=lambda kv:int(kv[0])):
        rows=collect(session,f'/playlists/{pid}/items',token,100)
        playlists[key]={'playlist_id':pid,'tracks':rows}
        print('🔥 Volume',key,':',len(rows))
    likes=collect(session,'/me/tracks',token,50)
    print('❤️ Liked Songs:',len(likes))
    OUT.mkdir(exist_ok=True)
    for name,data in [('playlists_na.json',playlists),('liked_na.json',likes)]:
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'playlist_counts':{k:len(v['tracks']) for k,v in playlists.items()},
              'liked_count':len(likes),
              'sha256':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ('playlists_na.json','liked_na.json')}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('✅ Volledige LIVE-snapshot opgeslagen. Geen Spotify-wijzigingen, geen cache-reset.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('❌ Scan gestopt:',str(exc));sys.exit(1)
