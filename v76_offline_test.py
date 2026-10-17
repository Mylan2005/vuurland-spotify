"""v76 — doelgerichte Jackson Browne-correctie; geen echte Spotify-requests."""
import os
os.environ['SPOTIFY_CLIENT_ID'] = 'offline'
import vuurland_sync as m

def candidate(name, artist='Jackson Browne', playable=True):
    return {'name': name, 'artists': [{'name': artist}],
            'uri': 'spotify:track:OFFLINE'+str(abs(hash(name)) % 1000000),
            'is_playable': playable, 'external_ids': {'isrc': 'TEST123'},
            'album': {'name': 'For Everyman'}}

calls=[]
def search(method, endpoint, **kwargs):
    calls.append(str(kwargs.get('params', {})))
    return {'tracks': {'items': [candidate('Sing My Songs to Me - Remastered'), candidate('For Everyman')]}}
m.spotify_request=search
result=m.find_spotify_track('Jackson Browne','Sing My Songs For Everyman')
assert result == candidate('Sing My Songs to Me - Remastered')['uri'], result
assert any('Sing My Songs to Me' in c for c in calls), calls
assert m.v71_same_song_title('Sing My Songs For Everyman', 'Sing My Songs to Me - Remastered', 'Jackson Browne')
assert not m.v71_same_song_title('Sing My Songs For Everyman', 'For Everyman', 'Jackson Browne')
assert not m.v71_same_song_title('Sing My Songs For Everyman', 'Sing My Songs to Me', 'Another Artist')
assert not m.v71_same_song_title('Sing My Songs For Everyman', 'Another Song', 'Jackson Browne')
print('✅ v76: titelcorrectie, versie, artiestgrens en duplicaatcontrole getest (offline).')
