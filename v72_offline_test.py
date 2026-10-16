"""v72 offline-regressietests; voert geen Spotify- of playlistacties uit."""
import os
os.environ.setdefault('SPOTIFY_CLIENT_ID', 'offline_test')
os.environ.setdefault('SPOTIFY_CLIENT_SECRET', 'offline_test')
os.environ.setdefault('SPOTIFY_REFRESH_TOKEN', 'offline_test')
import vuurland_sync as m

def track(name, artists, playable=True):
    return {'name': name, 'artists': [{'name': a} for a in artists],
            'uri': 'spotify:track:' + ''.join(a[0] for a in artists) + name[:2],
            'is_playable': playable, 'album': {'name': 'Offline test'}, 'external_ids': {'isrc': 'TEST12345678'}}

requests = []
def mock(method, endpoint, **kw):
    requests.append((endpoint, kw.get('params', {})))
    return {'tracks': {'items': mock.results}}
m.spotify_request = mock

# Volledige officiële duo als één Spotify-artist: niet splitsen.
mock.results = [track('Big Jet Plane', ['Angus & Julia Stone'])]
assert m.find_spotify_track('Angus & Julia Stone', 'Big Jet Plane') == mock.results[0]['uri']
# Bij dezelfde titel mag een solo-artiest NOOIT de officiële duo-credit vervangen.
mock.results = [track('Big Jet Plane', ['Angus Stone'])]
assert m.find_spotify_track('Angus & Julia Stone', 'Big Jet Plane') is None
# Een radiocredit met 'and' kan wel twee afzonderlijke Spotify-artiesten zijn.
mock.results = [track('Beachcombing', ['Mark Knopfler', 'Emmylou Harris'])]
assert m.find_spotify_track('Mark Knopfler and Emmylou Harris', 'Beachcombing') == mock.results[0]['uri']
# Regionaal grijze track wordt niet toegevoegd.
mock.results = [track('Loro', ['Pinback'], playable=False)]
assert m.find_spotify_track('Pinback', 'Loro') is None
# Een afspeelbaar equivalent mag wel.
mock.results = [track('Loro', ['Pinback'], playable=True)]
assert m.find_spotify_track('Pinback', 'Loro') == mock.results[0]['uri']
assert requests and all(params.get('market') == 'from_token' for endpoint, params in requests if endpoint == '/search')
print('✅ v72: bands vs. samenwerking, regioblokkade, afspeelbare track en market-parametertests geslaagd (offline).')
